"""Factory for assembling the LangGraph state machine - Simplified MVP architecture."""

from __future__ import annotations

from typing import Dict, List

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from agentgraph.agents import ModelResolver
from agentgraph.graph.nodes import (
    build_analyze_node,
    build_finalize_node,
    build_planner_node,
    build_post_node,
    build_step_executor_node,
)
from agentgraph.graph.routing import (
    post_route,
    analyze_route,
    tools_route,
    step_route,
)
from agentgraph.graph.state import AppState
from agentgraph.models import ModelRegistry
from agentgraph.tools import ToolRegistry


def build_state_graph(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: List,
    subagent_catalog: Dict[str, List[str]],
    skill_registry,
    checkpointer=None,
):
    """Compose the simplified agent graph for MVP.

    Simplified Architecture (No Guard/Verify):

    Phase 1 (Simple Tasks):
        START → plan → tools → post → analyze
                 ↑____________↓         ↓
                  (continue)      (simple)
                                      ↓
                                  finalize → END

    Phase 2 (Complex Tasks with Plan):
        START → plan → tools → post → step_executor
                                           ↑_____↓
                                           (loop)
                                              ↓
                                          finalize → END

    Key simplifications for MVP:
    - Removed guard node (no approval flow)
    - Removed verify node (trust LLM's judgment)
    - Removed deliverable_checkers (not needed for MVP)
    - Step executor decides autonomously when to continue/finish
    - Focus on core functionality: tool calling, task decomposition, multi-turn context
    """

    # ========== Build nodes ==========
    planner_node = build_planner_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        skill_registry=skill_registry,
    )

    post_node = build_post_node()

    analyze_node = build_analyze_node()

    step_executor_node = build_step_executor_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        subagent_catalog=subagent_catalog,
        skill_registry=skill_registry,
    )

    finalize_node = build_finalize_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
    )

    # ========== Build graph ==========
    graph = StateGraph(AppState)

    # Add all nodes
    graph.add_node("plan", planner_node)
    graph.add_node("tools", ToolNode(tool_registry.list_tools()))
    graph.add_node("post", post_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("step_executor", step_executor_node)
    graph.add_node("finalize", finalize_node)

    # ========== Phase 1: Initial Analysis ==========
    # Entry point
    graph.add_edge(START, "plan")

    # Direct tool execution (no guard)
    graph.add_edge("plan", "tools")

    # Tool execution routing based on phase
    graph.add_conditional_edges(
        "tools",
        tools_route,
        {
            "post": "post",            # Phase 1: post-processing
            "step_executor": "step_executor",  # Phase 2: continue plan execution
        }
    )

    # Routing based on whether plan was created
    graph.add_conditional_edges(
        "post",
        post_route,
        {
            "analyze": "analyze",        # No plan yet, analyze task complexity
            "step_executor": "step_executor",  # Plan created, start executing
        }
    )

    # Analyze decides next action
    graph.add_conditional_edges(
        "analyze",
        analyze_route,
        {
            "continue": "plan",    # LLM has more tools to call, loop back
            "simple": "finalize",  # Task completed
            "end": "finalize",     # Error case
        }
    )

    # ========== Phase 2: Plan Execution Loop ==========
    # Step executor decides autonomously whether to continue or finish
    graph.add_conditional_edges(
        "step_executor",
        step_route,
        {
            "tools": "tools",      # Execute tools for current step
            "finalize": "finalize",  # All steps done
        }
    )

    # ========== Exit ==========
    graph.add_edge("finalize", END)

    # ========== Compile ==========
    return graph.compile(checkpointer=checkpointer)
