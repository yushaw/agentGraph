"""Todo write tool for creating and updating task lists."""

from __future__ import annotations

from typing import List
from langchain_core.tools import tool


@tool
def todo_write(
    todos: List[dict]
) -> dict:
    """Track multi-step tasks (3+ steps). Helps user see progress.

    Use when: Complex multi-step tasks, user requests it, user provides list
    Don't use: Single task, trivial tasks (<3 steps), conversational requests

    Task states: pending | in_progress | completed
    Required fields: content, status
    Optional fields: id (auto-generated if missing), priority (default: medium)

    Rules:
    - Mark in_progress BEFORE starting work
    - Mark completed IMMEDIATELY after finishing (don't batch)
    - Only ONE in_progress at a time
    - Don't mark completed if tests fail, errors occur, or incomplete

    Args:
        todos: List of {content, status, id (optional), priority (optional)}

    Examples:
        todo_write([
            {"content": "分析代码", "status": "in_progress"},
            {"content": "实现功能", "status": "pending"}
        ])
    """
    # Validate todos
    for todo in todos:
        if "content" not in todo or "status" not in todo:
            return {
                "ok": False,
                "error": "Each todo must have 'content' and 'status' fields"
            }

        if todo["status"] not in ["pending", "in_progress", "completed"]:
            return {
                "ok": False,
                "error": f"Invalid status: {todo['status']}"
            }

        # Ensure id exists
        if "id" not in todo:
            import uuid
            todo["id"] = str(uuid.uuid4())[:8]

        # Set default priority
        if "priority" not in todo:
            todo["priority"] = "medium"

    # Check only one in_progress
    in_progress = [t for t in todos if t["status"] == "in_progress"]
    if len(in_progress) > 1:
        return {
            "ok": False,
            "error": f"Only one task can be 'in_progress', found {len(in_progress)}"
        }

    # TODO: Context detection (main vs subagent) will be added later
    return {
        "ok": True,
        "todos": todos,
        "context": "main"  # Default to main context for now
    }


__all__ = ["todo_write"]
