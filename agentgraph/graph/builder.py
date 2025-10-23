"""Factory for assembling the LangGraph state machine - Refactored two-phase architecture."""

from __future__ import annotations

from typing import Callable, Dict, List

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from agentgraph.agents import ModelResolver
from agentgraph.graph.nodes import (
    build_analyze_node,
    # build_decompose_node,
    build_finalize_node,
    build_guard_node,
    build_planner_node,
    build_post_node,
    build_step_executor_node,
    build_verify_node,
)
from agentgraph.graph.routing import (
    guard_route,
    post_route,
    analyze_route,
    tools_route,
    verify_route,
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
    deliverable_checkers: Dict[str, Callable[[dict], bool]],
    default_policy: Dict[str, bool],
    skill_registry,
    checkpointer=None,
):
    """Compose the full agent graph with two-phase architecture.

    Phase 1 (Initial Analysis):
        START → plan → guard → tools → post → analyze
                 ↑       ↓                       ↓
                 └───ask─┘              ┌────simple────┐
                                        ↓              ↓
                                       plan         finalize → END
                                        ↓
                                   (plan loop)

    Phase 2 (Plan Execution Loop):
        plan → step_executor → guard → tools → verify
        ↑            ↑           ↓                ↓
        └────────────┘       ask (approval)    continue/end
                                                  ↓
                                              finalize → END

    Key improvements over original:
    - create_plan is now a tool (LLM decides when to decompose)
    - analyze node intelligently detects task complexity
    - verify node is in the main loop path (not orphaned)
    - step_executor handles user approval properly
    - Clear phase separation with execution_phase state field
    """

    # ========== Build nodes ==========
    planner_node = build_planner_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
    )

    guard_node = build_guard_node(
        tool_registry=tool_registry,
        default_policy=default_policy,
    )

    post_node = build_post_node()

    analyze_node = build_analyze_node()

    # The actual planning is done by LLM calling create_plan tool

    step_executor_node = build_step_executor_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        subagent_catalog=subagent_catalog,
    )

    verify_node = build_verify_node(
        deliverable_checkers=deliverable_checkers,
    )

    finalize_node = build_finalize_node(
        model_registry=model_registry,
        model_resolver=model_resolver,
    )

    # ========== Build graph ==========
    graph = StateGraph(AppState)

    # Add all nodes
    graph.add_node("plan", planner_node)
    graph.add_node("guard", guard_node)
    graph.add_node("tools", ToolNode(tool_registry.list_tools()))
    graph.add_node("post", post_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("step_executor", step_executor_node)
    graph.add_node("verify", verify_node)
    graph.add_node("finalize", finalize_node)

    # ========== Phase 1: Initial Analysis ==========
    # Entry point
    graph.add_edge(START, "plan")

    # Planning and security
    graph.add_edge("plan", "guard")
    graph.add_conditional_edges(
        "guard",
        guard_route,
        {
            "ask": "plan",      # High-risk operation, loop back for user approval
            "tools": "tools",   # Safe to execute
        }
    )

    # Tool execution routing based on phase
    graph.add_conditional_edges(
        "tools",
        tools_route,
        {
            "post": "post",      # Phase 1: post-processing
            "verify": "verify",  # Phase 2: verification
        }
    )

    # Routing based on whether plan was created
    graph.add_conditional_edges(
        "post",
        post_route,
        {
            "analyze": "analyze",  # No plan yet, analyze task complexity
            "plan": "step_executor",  # Plan created, start executing
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
    # Note: decompose node is kept for backward compatibility
    # but in the new architecture, plans are created via create_plan tool
    # graph.add_edge("decompose", "step_executor")

    # Step execution flow
    graph.add_edge("step_executor", "guard")  # Security check before each step
    # Guard routing is same as phase 1 (reused)

    # Verify decides whether to continue, retry, or finish
    graph.add_conditional_edges(
        "verify",
        verify_route,
        {
            "continue": "step_executor",  # More steps or retry current step
            "end": "finalize",            # All steps done or budget exhausted
        }
    )

    # ========== Exit ==========
    graph.add_edge("finalize", END)

    # ========== Compile ==========
    return graph.compile(checkpointer=checkpointer)
