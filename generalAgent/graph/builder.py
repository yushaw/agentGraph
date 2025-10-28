"""Factory for assembling the LangGraph state machine - Agent Loop architecture."""

from __future__ import annotations

from typing import Dict, List

from langgraph.graph import StateGraph, START, END

from generalAgent.agents import ModelResolver
from generalAgent.graph.nodes import (
    build_finalize_node,
    build_planner_node,
)
from generalAgent.graph.routing import (
    agent_route,
    tools_route,
)
from generalAgent.graph.state import AppState
from generalAgent.hitl import ApprovalToolNode
from generalAgent.models import ModelRegistry
from generalAgent.tools import ToolRegistry


def build_state_graph(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: List,
    skill_registry,
    skill_config,
    settings,
    checkpointer=None,
    approval_checker=None,  # HITL: 审批检测器（可选）
):
    """Compose the agent graph with Agent Loop architecture (Claude Code style).

    Simplified Architecture:

        START → agent ⇄ tools → agent ⇄ ... → finalize → END
                  ↑_____________↓

    Agent Loop design (no Plan-and-Execute):
    - Single agent node that decides its own flow
    - LLM chooses to call tools or finish
    - TodoWrite tool for progress tracking (observer, not commander)
    - No complexity analysis, no multi-phase execution
    - Agent operates continuously until task complete or loop limit

    Key changes from Plan-and-Execute:
    - Removed: post, analyze, step_executor nodes
    - Removed: plan/step_idx/step_calls state fields
    - Simplified routing: agent decides everything via tool_calls
    - Agent can use TodoWrite to track progress dynamically
    """

    # ========== Build nodes ==========
    agent_node = build_planner_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        skill_registry=skill_registry,
        skill_config=skill_config,
        settings=settings,
    )

    finalize_node = build_finalize_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        settings=settings,
    )

    # ========== Build graph ==========
    graph = StateGraph(AppState)

    # Add nodes
    graph.add_node("agent", agent_node)

    # Tools node with optional approval
    # IMPORTANT: Use ALL discovered tools (not just enabled ones) for ToolNode
    # This allows dynamic on-demand loading (e.g., compact_context) to work correctly
    # The planner controls which tools are visible to the LLM via bind_tools()
    all_discovered_tools = [tool for tool in tool_registry._discovered.values()]

    if approval_checker:
        tools_node = ApprovalToolNode(
            tools=all_discovered_tools,
            approval_checker=approval_checker,
            enable_approval=True,
        )
    else:
        # Fallback: 如果没有提供 approval_checker，使用原来的 ToolNode
        from langgraph.prebuilt import ToolNode
        tools_node = ToolNode(all_discovered_tools)

    graph.add_node("tools", tools_node)
    graph.add_node("finalize", finalize_node)

    # ========== Agent Loop ==========
    # Entry point
    graph.add_edge(START, "agent")

    # Agent decides: call tools or finish
    graph.add_conditional_edges(
        "agent",
        agent_route,
        {
            "tools": "tools",      # LLM wants to call tools
            "finalize": "finalize",  # LLM decided to finish
        }
    )

    # Tools always return to agent
    graph.add_conditional_edges(
        "tools",
        tools_route,
        {
            "agent": "agent",  # Continue loop
        }
    )

    # Exit
    graph.add_edge("finalize", END)

    # ========== Compile ==========
    return graph.compile(checkpointer=checkpointer)
