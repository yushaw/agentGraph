"""Todo read tool for checking task status."""

from __future__ import annotations

from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


@tool
def todo_read(state: Annotated[dict, InjectedState]) -> dict:
    """Read the current todo list to check task status and remaining work.

    Use this tool proactively and frequently to stay aware of:
    - What tasks are still pending or in progress
    - What you should work on next
    - Whether all tasks are completed

    **IMPORTANT**: You should use this tool:
    - At the beginning of conversations to see what's pending
    - Before deciding to stop/finish to ensure all tasks are done
    - After completing tasks to see what's next
    - Whenever uncertain about what to do next
    - Every few iterations to stay on track

    This tool takes NO parameters. Leave input empty.

    Returns:
        dict with:
        - ok (bool): Success status
        - todos (list): Current todo list with status/priority
        - summary (dict): Quick stats (pending, in_progress, completed counts)

    Example:
        # Check current todos
        result = todo_read()
        # Returns: {
        #   "ok": true,
        #   "todos": [...],
        #   "summary": {"pending": 2, "in_progress": 1, "completed": 3}
        # }
    """
    todos = state.get("todos", [])

    # Calculate summary stats
    summary = {
        "pending": len([t for t in todos if t.get("status") == "pending"]),
        "in_progress": len([t for t in todos if t.get("status") == "in_progress"]),
        "completed": len([t for t in todos if t.get("status") == "completed"]),
        "total": len(todos)
    }

    return {
        "ok": True,
        "todos": todos,
        "summary": summary,
        "context": state.get("context_id", "main")
    }


__all__ = ["todo_read"]
