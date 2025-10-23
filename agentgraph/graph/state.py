"""Shared state definition for the LangGraph flow."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AppState(TypedDict, total=False):
    """Conversation state tracked across graph execution - Simplified MVP version.

    This state supports a simplified two-phase architecture:
    - Phase 1 (initial): plan → tools → post → analyze
    - Phase 2 (loop): step_executor → tools → (continue or finalize)

    Removed: guard, verify, awaiting_approval, evidence (not needed for MVP)
    """

    # ========== Messages and media ==========
    messages: Annotated[List[BaseMessage], add_messages]
    images: List[Any]

    # ========== Skills and tools ==========
    active_skill: Optional[str]
    allowed_tools: List[str]

    # ========== @Mention tracking ==========
    mentioned_agents: List[str]  # List of @mentioned agent/skill/tool names
    persistent_tools: List[str]  # Tools that should remain active for the session

    # ========== Execution plan ==========
    plan: Optional[Dict[str, Any]]  # Structured plan created by LLM via create_plan tool
    step_idx: int                   # Current step index in plan
    step_calls: int                 # Tool calls within current step
    max_step_calls: int             # Budget per step

    # ========== Execution control ==========
    execution_phase: Literal["initial", "loop"]  # Which phase we're in
    task_complexity: Literal["simple", "complex", "continue", "unknown"]  # Determined by analyze node
    complexity_reason: Optional[str]  # Why the task was classified as complex/simple/continue

    loops: int          # Global loop counter
    max_loops: int      # Hard limit on total loops

    # ========== Model preference ==========
    model_pref: Optional[str]  # User's preferred model type (e.g., "vision", "code")

    # ========== Session context ==========
    thread_id: Optional[str]  # Session identifier for persistence
    user_id: Optional[str]    # User identifier (for future personalization)
