"""Todo write tool for creating and updating task lists."""

from __future__ import annotations

from typing import Annotated, List
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command


@tool
def todo_write(
    todos: List[dict],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
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
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="❌ 错误: 每个任务必须包含 'content' 和 'status' 字段",
                            tool_call_id=tool_call_id
                        )
                    ]
                }
            )

        if todo["status"] not in ["pending", "in_progress", "completed"]:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"❌ 错误: 无效的状态 '{todo['status']}'，必须是 pending/in_progress/completed 之一",
                            tool_call_id=tool_call_id
                        )
                    ]
                }
            )

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
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"❌ 错误: 只能有一个任务处于 'in_progress' 状态，当前有 {len(in_progress)} 个",
                        tool_call_id=tool_call_id
                    )
                ]
            }
        )

    # Success: update both todos and messages
    incomplete_count = len([t for t in todos if t["status"] != "completed"])
    completed_count = len([t for t in todos if t["status"] == "completed"])

    return Command(
        update={
            "todos": todos,  # ← 更新 state["todos"]
            "messages": [
                ToolMessage(
                    content=f"✅ TODO 列表已更新: {incomplete_count} 个待完成, {completed_count} 个已完成",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )


__all__ = ["todo_write"]
