"""OrchestrationAgent State - Simplified version of AppState.

Host (Orchestration Agent) has a SIMPLIFIED state compared to GeneralAgent (Worker).

Why? Host doesn't need to:
- Process images (images)
- Use skills (active_skill)
- Load tools dynamically (mentioned_agents, allowed_tools)

Host DOES need to:
- Track conversation (messages)
- Manage high-level project plan (todos)
- Control loops (loops, max_loops)
- Pass context to Workers (workspace_path, uploaded_files, context_id)
"""

from __future__ import annotations

from typing import TypedDict, Annotated
from langgraph.graph import add_messages


class OrchestrationState(TypedDict, total=False):
    """State for OrchestrationAgent (Host).

    This is a SUBSET of generalAgent.graph.state.AppState.
    """

    # ========== Core Conversation State ==========
    messages: Annotated[list, add_messages]
    """Conversation history (HumanMessage, AIMessage, ToolMessage)."""

    # ========== Progress Management ==========
    todos: list[dict]
    """High-level project plan (managed by todo_write tool).

    Each todo: {"content": str, "status": "pending"|"in_progress"|"completed", "activeForm": str}
    """

    # ========== Loop Control ==========
    loops: int
    """Current loop count (incremented after each agent node execution)."""

    max_loops: int
    """Maximum allowed loops (default: 100 for Host, prevents infinite orchestration)."""

    # ========== Context Management ==========
    needs_compression: bool
    """Flag set by planner when token usage >95%, triggers summarization node."""

    auto_compressed_this_request: bool
    """Flag to prevent multiple compressions in one request cycle."""

    cumulative_prompt_tokens: int
    """Total prompt tokens used in this conversation (for compression triggering)."""

    # ========== Worker Context (Inherited by Workers) ==========
    workspace_path: str
    """Path to session workspace (shared with Workers)."""

    uploaded_files: list[dict]
    """Files uploaded by user (inherited by Workers).

    Each file: {"path": str, "name": str, "type": str, "size": int}
    """

    # ========== Session Management ==========
    context_id: str
    """Current context ID (for Host, this is the session thread_id).

    Workers will have their own context_id (e.g., "subagent-abc123").
    """

    parent_context: str | None
    """Parent context ID (None for Host, set for Workers)."""

    thread_id: str
    """Session thread ID (for checkpointer persistence)."""

    user_id: str | None
    """User ID (for multi-user scenarios)."""

    # ========== Fields NOT NEEDED by Host ==========
    # These are commented out to make the difference explicit

    # images: list  # Host doesn't process images
    # active_skill: str | None  # Host doesn't use skills
    # allowed_tools: list  # Host has fixed toolset
    # mentioned_agents: list  # Host doesn't dynamically load tools
    # new_mentioned_agents: list
    # persistent_tools: list
    # model_pref: str | None
    # new_uploaded_files: list


__all__ = ["OrchestrationState"]
