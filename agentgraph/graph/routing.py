"""Conditional routing helpers for simplified MVP architecture."""

from __future__ import annotations

import logging
from typing import Literal

from .state import AppState
from agentgraph.utils.logging_utils import log_routing_decision

LOGGER = logging.getLogger("agentgraph.routing")


def post_route(state: AppState) -> Literal["analyze", "step_executor"]:
    """Route after post node to handle skill selection and plan creation.

    Returns:
        "analyze": No plan created, go to analyze for complexity assessment
        "step_executor": Plan was created via create_plan tool, start execution
    """
    # Check if create_plan was called successfully
    if state.get("plan"):
        decision = "step_executor"
        reason = "Plan created via create_plan tool, starting execution"
    else:
        decision = "analyze"
        reason = "No plan created, analyzing task complexity"

    log_routing_decision(LOGGER, "post", decision, reason)
    return decision


def analyze_route(state: AppState) -> Literal["continue", "simple", "end"]:
    """Route after analyze node based on task complexity.

    Returns:
        "continue": LLM has more tool calls, continue conversation (loop back to plan)
        "simple": Task completed, go to finalize
        "end": Complex task but no plan (error case)
    """
    complexity = state.get("task_complexity", "unknown")

    # LLM wants to continue calling tools
    if complexity == "continue":
        decision = "continue"
        reason = f"Task complexity is 'continue', LLM has more tool calls to make"
    # Task completed
    elif complexity in ("simple", "unknown"):
        decision = "simple"
        reason = f"Task complexity is '{complexity}', task completed"
    # Complex task but no plan (shouldn't happen)
    else:
        decision = "end"
        reason = f"Complex task but no plan (complexity={complexity})"

    log_routing_decision(LOGGER, "analyze", decision, reason)
    return decision


def tools_route(state: AppState) -> Literal["post", "step_executor"]:
    """Route after tools node based on execution phase.

    Returns:
        "post": Initial phase, go to post for skill/plan extraction
        "step_executor": Loop phase, continue plan execution
    """
    phase = state.get("execution_phase", "initial")

    if phase == "loop":
        decision = "step_executor"
        reason = f"Execution phase is 'loop', continuing plan execution"
    else:
        decision = "post"
        reason = f"Execution phase is '{phase}', processing tool results"

    log_routing_decision(LOGGER, "tools", decision, reason)
    return decision


def step_route(state: AppState) -> Literal["tools", "finalize"]:
    """Route after step_executor based on plan progress.

    Returns:
        "tools": Execute tools for current step
        "finalize": All steps completed or budget exhausted
    """
    plan = state.get("plan") or {}
    steps = plan.get("steps", [])
    idx = state.get("step_idx", 0)
    loops = state.get("loops", 0)
    max_loops = state.get("max_loops", 20)

    # All steps completed
    if idx >= len(steps):
        decision = "finalize"
        reason = f"All steps completed ({idx}/{len(steps)})"
    # Global loop limit reached
    elif loops >= max_loops:
        decision = "finalize"
        reason = f"Global loop limit reached ({loops}/{max_loops})"
    # Continue to execute current step
    else:
        decision = "tools"
        reason = f"Continue step execution (step {idx + 1}/{len(steps)}, loop {loops}/{max_loops})"

    log_routing_decision(LOGGER, "step_executor", decision, reason)
    return decision
