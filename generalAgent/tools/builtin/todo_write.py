"""Todo write tool for creating and updating task lists."""

from __future__ import annotations

from typing import List
from langchain_core.tools import tool


@tool
def todo_write(
    todos: List[dict]
) -> dict:
    """Create or update task list for tracking progress.

    Use this tool to manage complex tasks with multiple steps. It helps track
    progress and gives users visibility into what you're working on.

    When to use:
    - Complex multi-step tasks (3+ steps)
    - User explicitly requests todo list
    - Tasks requiring careful planning
    - After receiving new instructions

    When NOT to use:
    - Single, straightforward tasks
    - Trivial tasks (< 3 steps)
    - Purely conversational requests

    Task management rules:
    1. Mark tasks as 'in_progress' BEFORE starting work
    2. Update to 'completed' IMMEDIATELY after finishing
    3. Only ONE task should be 'in_progress' at a time
    4. Don't batch completions - update after each task
    5. Add new tasks if you discover additional work

    Args:
        todos: List of tasks, each containing:
            - content (str): Task description
            - status (str): "pending" | "in_progress" | "completed"
            - priority (str): "high" | "medium" | "low"
            - id (str): Unique task identifier

    Returns:
        Success status and context (main or subagent)

    Example:
        todo_write([
            {
                "id": "task-1",
                "content": "Analyze codebase structure",
                "status": "in_progress",
                "priority": "high"
            },
            {
                "id": "task-2",
                "content": "Implement new feature",
                "status": "pending",
                "priority": "medium"
            }
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
