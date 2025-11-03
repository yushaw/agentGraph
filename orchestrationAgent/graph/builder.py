"""Graph Builder for OrchestrationAgent.

Host (Orchestration) Graph Architecture:

    START → planner → [summarization] → tools (HITL) → planner → finalize → END
                ↑___________|                          |_________|
                (feedback loop)                    (forced return)

Key Differences from generalAgent:
- Simplified routing (no handoff pattern, no agent nodes)
- HITL protection for delegate_task (critical for safety)
- Summarization support (Host conversations can be long)
- No skill loading (Host doesn't use skills)
"""

from __future__ import annotations

import logging
from typing import List

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from orchestrationAgent.graph.state import OrchestrationState
from orchestrationAgent.graph.nodes import build_host_planner_node
from orchestrationAgent.graph.routing import host_agent_route, host_tools_route, host_summarization_route
from generalAgent.graph.nodes.summarization import build_summarization_node
from generalAgent.hitl import ApprovalToolNode
from generalAgent.models import ModelRegistry
from generalAgent.agents import ModelResolver
from generalAgent.tools import ToolRegistry
from generalAgent.config.settings import Settings

LOGGER = logging.getLogger(__name__)


def build_host_graph(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    settings: Settings,
    checkpointer=None,
    approval_checker=None,
):
    """Build the OrchestrationAgent (Host) graph.

    Args:
        model_registry: Model registry
        model_resolver: Model resolver
        tool_registry: Tool registry (should only contain orchestration tools)
        settings: Application settings
        checkpointer: Optional checkpointer for persistence
        approval_checker: Optional HITL approval checker

    Returns:
        Compiled LangGraph application
    """

    # ========== Build Nodes ==========
    planner_node = build_host_planner_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        settings=settings,
    )

    # NOTE: No finalize node for Host!
    # When Host calls done_and_report, we end directly
    # The final_result from done_and_report is already user-friendly

    summarization_node = build_summarization_node(
        settings=settings,
    )

    # ========== Build Tools Node with HITL ==========
    all_tools = list(tool_registry._discovered.values())

    if approval_checker:
        tools_node = ApprovalToolNode(
            tools=all_tools,
            approval_checker=approval_checker,
            enable_approval=True,
        )
        LOGGER.info("[Host Graph] HITL protection enabled for tools")
    else:
        tools_node = ToolNode(all_tools)
        LOGGER.warning("[Host Graph] HITL protection disabled (not recommended)")

    # ========== Build Graph ==========
    graph = StateGraph(OrchestrationState)

    graph.add_node("planner", planner_node)
    graph.add_node("tools", tools_node)
    graph.add_node("summarization", summarization_node)
    # No finalize node - done_and_report ends directly

    # ========== Routing ==========
    # Entry point
    graph.add_edge(START, "planner")

    # Planner routing: compress, call tools, or finish
    graph.add_conditional_edges(
        "planner",
        host_agent_route,
        {
            "summarization": "summarization",  # Token usage >95%, compress first
            "tools": "tools",                  # LLM wants to call tools
            "end": END,                        # LLM called done_and_report, end directly
        }
    )

    # Summarization always returns to planner
    graph.add_conditional_edges(
        "summarization",
        host_summarization_route,
        {
            "planner": "planner",
        }
    )

    # Tools routing: check if done_and_report was executed
    graph.add_conditional_edges(
        "tools",
        host_tools_route,
        {
            "planner": "planner",  # Continue feedback loop
            "end": END,            # done_and_report executed, end task
        }
    )

    # ========== Compile ==========
    return graph.compile(checkpointer=checkpointer)


__all__ = ["build_host_graph"]
