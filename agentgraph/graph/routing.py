"""Conditional routing helpers for two-phase architecture."""

from __future__ import annotations

from typing import Literal

from .state import AppState


def guard_route(state: AppState) -> Literal["ask", "tools"]:
    """Route after guard check (used in both initial and loop phases).

    Returns:
        "ask": High-risk operation detected, need user approval
        "tools": Safe to execute tools
    """
    return "ask" if state.get("awaiting_approval") else "tools"


def post_route(state: AppState) -> Literal["analyze", "plan"]:
    """Route after post node to handle skill selection and plan creation.

    Returns:
        "analyze": No plan created, go to analyze for complexity assessment
        "plan": Plan was created via create_plan tool, start execution
    """
    # Check if create_plan was called successfully
    if state.get("plan"):
        return "plan"

    # No plan yet, analyze task complexity
    return "analyze"


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
        return "continue"

    # Task completed
    if complexity in ("simple", "unknown"):
        return "simple"

    # Complex task but no plan (shouldn't happen)
    return "end"


def tools_route(state: AppState) -> Literal["post", "verify"]:
    """Route after tools node based on execution phase.

    Returns:
        "post": Initial phase, go to post for skill/plan extraction
        "verify": Loop phase, go to verify for step validation
    """
    phase = state.get("execution_phase", "initial")
    return "verify" if phase == "loop" else "post"


def verify_route(state: AppState) -> Literal["continue", "end"]:
    """Route after verify node based on plan progress.

    Returns:
        "continue": More steps to execute or current step needs retry
        "end": All steps completed or budget exhausted
    """
    plan = state.get("plan") or {}
    steps = plan.get("steps", [])
    idx = state.get("step_idx", 0)

    # All steps completed
    if idx >= len(steps):
        return "end"

    # Global loop limit reached
    max_loops = state.get("max_loops", 20)
    if state.get("loops", 0) >= max_loops:
        return "end"

    # Continue to next step or retry current step
    return "continue"
