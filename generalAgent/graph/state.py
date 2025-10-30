"""Shared state definition for the LangGraph flow."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AppState(TypedDict, total=False):
    """Conversation state tracked across graph execution - Agent Loop architecture.

    This state supports a flexible agent loop architecture (Claude Code style):
    - Single agent loop that decides its own execution flow
    - TodoWrite tool for progress tracking (observer, not commander)
    - Subagents run in independent State instances for context isolation

    Architecture change: Removed Plan-and-Execute pattern in favor of flexible LLM-driven flow.
    """

    # ========== Messages and media ==========
    messages: Annotated[List[BaseMessage], add_messages]
    images: List[Any]

    # ========== Skills and tools ==========
    active_skill: Optional[str]
    allowed_tools: List[str]

    # ========== @Mention tracking ==========
    mentioned_agents: List[str]  # All @mentioned agent/skill/tool names (historical record)
    new_mentioned_agents: List[str]  # Current turn's @mentions (for reminder generation, cleared after use)
    persistent_tools: List[str]  # Tools that should remain active for the session

    # ========== Task tracking ==========
    todos: List[dict]  # Task list managed by TodoWrite tool (for progress tracking)

    # ========== Context isolation ==========
    context_id: str                # "main" or "subagent-{uuid}"
    parent_context: Optional[str]  # Parent context ID (only for subagents)

    # ========== Execution control ==========
    loops: int          # Global loop counter
    max_loops: int      # Hard limit on total loops

    # ========== Model preference ==========
    model_pref: Optional[str]  # User's preferred model type (e.g., "vision", "code")

    # ========== Session context ==========
    thread_id: Optional[str]     # Session identifier for persistence
    user_id: Optional[str]       # User identifier (for future personalization)
    workspace_path: Optional[str]  # Isolated workspace directory for this session
    uploaded_files: List[Any]  # All uploaded files (historical record, never cleared)
    new_uploaded_files: List[Any]  # Files uploaded in current turn (for reminder generation, cleared after use)

    # ========== Agent system (NEW) ==========
    agent_call_stack: List[str]  # 当前调用栈（嵌套层级），用于循环检测 (e.g., ["agent", "simple"])
    agent_call_history: List[str]  # 历史调用记录（已返回的），用于审计 (e.g., ["simple", "simple", "general"])
    current_agent: Optional[str]  # Current active agent (for handoff routing, e.g., "agent", "simple")

    # ========== Context management (Token tracking and compression) ==========
    cumulative_prompt_tokens: int  # Current context size in tokens (not cumulative!)
    cumulative_completion_tokens: int  # Cumulative completion tokens since last compression
    last_prompt_tokens: int  # Last LLM call's prompt tokens (for logging)
    compact_count: int  # Number of times context has been compressed
    last_compact_strategy: Optional[Literal["compact", "summarize"]]  # Last compression strategy used
    last_compression_ratio: Optional[float]  # Last compression ratio (for dynamic strategy selection)
    auto_compressed_this_request: bool  # Flag to prevent multiple auto-compressions in one request
    needs_compression: bool  # Flag set by planner when token usage is critical, read by routing
