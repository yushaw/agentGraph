"""Checkpointer for LangGraph state persistence.

Required for HITL (Human-in-the-Loop) interrupt support.
"""

from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.memory import MemorySaver


def build_checkpointer(db_path: Optional[str] = None):
    """Build a LangGraph checkpointer for state persistence.

    Required for interrupt/resume functionality in HITL.

    Note: Currently uses MemorySaver for simplicity. For production use,
    consider using AsyncSqliteSaver for persistent checkpointing.

    Args:
        db_path: Path to SQLite database file (ignored for now)

    Returns:
        MemorySaver instance for LangGraph checkpointing
    """
    # Use MemorySaver for now (in-memory, session-scoped)
    # This is sufficient for HITL interrupt handling within a session
    return MemorySaver()
