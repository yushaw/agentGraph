"""Shared state definition for the LangGraph flow."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AppState(TypedDict, total=False):
    """Conversation state tracked across graph execution.

    This state supports a two-phase architecture:
    - Phase 1 (initial): plan → guard → tools → analyze
    - Phase 2 (loop): plan_executor → guard → tools → verify → (continue or end)
    """

    # ========== Messages and media ==========
    messages: Annotated[List[BaseMessage], add_messages]
    images: List[Any]

    # ========== Skills and tools ==========
    active_skill: Optional[str]
    allowed_tools: List[str]

    # ========== Execution plan ==========
    plan: Optional[Dict[str, Any]]  # Structured plan created by LLM via create_plan tool
    step_idx: int                   # Current step index in plan
    step_calls: int                 # Tool calls within current step
    max_step_calls: int             # Budget per step
    evidence: List[Dict[str, Any]]  # Collected deliverables and results

    # ========== Execution control ==========
    execution_phase: Literal["initial", "loop"]  # Which phase we're in
    task_complexity: Literal["simple", "complex", "continue", "unknown"]  # Determined by analyze node
    complexity_reason: Optional[str]  # Why the task was classified as complex/simple/continue

    loops: int          # Global loop counter
    max_loops: int      # Hard limit on total loops

    # ========== Security policy ==========
    policy: Dict[str, Any]              # e.g., {"auto_approve_writes": False}
    awaiting_approval: bool             # Set by guard when high-risk tool detected
    pending_calls: List[Dict[str, Any]]  # Stashed tool calls awaiting approval

    # ========== Model preference ==========
    model_pref: Optional[str]  # User's preferred model type
