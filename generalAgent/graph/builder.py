"""Factory for assembling the LangGraph state machine - Agent Loop architecture."""

from __future__ import annotations

import logging
from typing import Dict, List

from langgraph.graph import StateGraph, START, END

LOGGER = logging.getLogger(__name__)

from generalAgent.agents import ModelResolver
from generalAgent.graph.nodes import (
    build_finalize_node,
    build_planner_node,
    build_agent_node_from_card,
)
from generalAgent.graph.nodes.summarization import build_summarization_node
from generalAgent.graph.routing import (
    agent_route,
    tools_route,
    summarization_route,
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
    agent_registry=None,  # NEW: Agent Registry（可选）
):
    """Compose the agent graph with Agent Loop architecture (Claude Code style).

    Architecture with Auto-Compression:

        START → agent ⇄ tools → agent ⇄ ... → finalize → END
                  ↑      ↓
                  ↑ summarization (auto-compress when >95% tokens)
                  ↑______↓

    Agent Loop design (no Plan-and-Execute):
    - Single agent node that decides its own flow
    - LLM chooses to call tools or finish
    - TodoWrite tool for progress tracking (observer, not commander)
    - Automatic compression when token usage >95% (via routing)
    - Agent operates continuously until task complete or loop limit

    Key features:
    - Simplified routing: agent decides everything via tool_calls
    - Automatic context compression via dedicated summarization node
    - Compression triggers before agent response, ensuring continuity
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
        agent_registry=agent_registry,  # NEW: Pass agent_registry to planner
    )

    finalize_node = build_finalize_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        settings=settings,
    )

    summarization_node = build_summarization_node(
        settings=settings,
    )

    # ========== Build graph ==========
    graph = StateGraph(AppState)

    # Add main agent node
    graph.add_node("agent", agent_node)
    graph.add_node("summarization", summarization_node)

    # Add specialized agent nodes (handoff pattern)
    if agent_registry:
        for card in agent_registry.list_enabled():
            try:
                agent_node_func = build_agent_node_from_card(card)
                graph.add_node(card.id, agent_node_func)
                LOGGER.info(f"Added agent node: {card.id} ({card.name})")
            except (NotImplementedError, ValueError) as e:
                LOGGER.warning(f"Skipping agent node {card.id}: {e}")
                continue

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

    # ========== Agent Loop with Auto-Compression ==========
    # Entry point
    graph.add_edge(START, "agent")

    # Agent decides: compress, call tools, or finish
    graph.add_conditional_edges(
        "agent",
        agent_route,
        {
            "summarization": "summarization",  # Token usage >95%, compress first
            "tools": "tools",                  # LLM wants to call tools
            "finalize": "finalize",            # LLM decided to finish
        }
    )

    # Summarization always returns to agent (to continue with original request)
    graph.add_conditional_edges(
        "summarization",
        summarization_route,
        {
            "agent": "agent",  # Return to agent after compression
        }
    )

    # Tools return to calling agent (supports handoff pattern)
    # Build dynamic routing map for agent handoffs
    tools_routing_map = {"agent": "agent"}  # Default: return to main agent

    if agent_registry:
        for card in agent_registry.list_enabled():
            tools_routing_map[card.id] = card.id  # Add route for each agent

    graph.add_conditional_edges(
        "tools",
        tools_route,
        tools_routing_map,
    )

    # Agent nodes routing (each agent can call tools or finish)
    if agent_registry:
        for card in agent_registry.list_enabled():
            # Each agent node uses same routing logic as main agent
            # They can call tools or finish (return to main agent via Command)
            # The agent_route is reused, but agent nodes return Command directly
            pass  # Agent nodes return Command, no conditional edges needed

    # Exit
    graph.add_edge("finalize", END)

    # ========== Compile ==========
    return graph.compile(checkpointer=checkpointer)
