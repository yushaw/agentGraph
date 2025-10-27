"""Unit tests for TODO tools (todo_write and todo_read).

Tests cover:
1. State synchronization using Command objects
2. Validation rules (only one in_progress, required fields, etc.)
3. TODO reminder display logic
"""

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from generalAgent.tools.builtin.todo_write import todo_write
from generalAgent.tools.builtin.todo_read import todo_read


def invoke_todo_write(todos):
    """Helper to invoke todo_write with proper ToolCall structure."""
    tool_call = {
        "name": "todo_write",
        "args": {"todos": todos},
        "id": "test_call_123",
        "type": "tool_call"
    }
    return todo_write.invoke(tool_call)


class TestTodoWrite:
    """Test todo_write tool."""

    def test_basic_todo_write_returns_command(self):
        """Test that todo_write returns a Command object."""
        todos = [
            {"content": "任务1", "status": "pending"},
            {"content": "任务2", "status": "in_progress"}
        ]

        result = invoke_todo_write(todos)

        assert isinstance(result, Command), "todo_write must return Command object"
        assert "todos" in result.update, "Command must include todos in update"
        assert "messages" in result.update, "Command must include messages in update"

    def test_state_todos_updated_correctly(self):
        """Test that Command.update contains correct todos."""
        todos = [
            {"content": "分析代码", "status": "in_progress"},
            {"content": "实现功能", "status": "pending"},
            {"content": "编写测试", "status": "pending"}
        ]

        result = invoke_todo_write(todos)

        updated_todos = result.update["todos"]
        assert len(updated_todos) == 3

        # Check IDs are auto-generated
        for todo in updated_todos:
            assert "id" in todo, "Each todo should have auto-generated id"
            assert len(todo["id"]) == 8, "ID should be 8 characters (UUID prefix)"

        # Check default priority
        for todo in updated_todos:
            assert todo.get("priority") == "medium", "Default priority should be 'medium'"

    def test_validation_missing_fields(self):
        """Test validation for missing required fields."""
        # Missing status
        todos = [{"content": "任务1"}]
        result = invoke_todo_write(todos)

        assert "messages" in result.update
        assert len(result.update["messages"]) == 1
        assert isinstance(result.update["messages"][0], ToolMessage)
        assert "错误" in result.update["messages"][0].content

        # Missing content
        todos = [{"status": "pending"}]
        result = invoke_todo_write(todos)

        assert "错误" in result.update["messages"][0].content

    def test_validation_invalid_status(self):
        """Test validation for invalid status values."""
        todos = [{"content": "任务1", "status": "invalid_status"}]
        result = invoke_todo_write(todos)

        assert "messages" in result.update
        assert "错误" in result.update["messages"][0].content
        assert "invalid_status" in result.update["messages"][0].content

    def test_validation_multiple_in_progress(self):
        """Test validation: only one task can be in_progress."""
        todos = [
            {"content": "任务1", "status": "in_progress"},
            {"content": "任务2", "status": "in_progress"},  # ❌ 第二个 in_progress
            {"content": "任务3", "status": "pending"}
        ]

        result = invoke_todo_write(todos)

        assert "messages" in result.update
        assert "错误" in result.update["messages"][0].content
        assert "只能有一个" in result.update["messages"][0].content

    def test_validation_allows_single_in_progress(self):
        """Test that exactly one in_progress is allowed."""
        todos = [
            {"content": "任务1", "status": "in_progress"},
            {"content": "任务2", "status": "pending"},
            {"content": "任务3", "status": "completed"}
        ]

        result = invoke_todo_write(todos)

        # Should succeed
        assert "todos" in result.update
        assert len(result.update["todos"]) == 3

    def test_validation_allows_zero_in_progress(self):
        """Test that zero in_progress is also allowed."""
        todos = [
            {"content": "任务1", "status": "pending"},
            {"content": "任务2", "status": "pending"}
        ]

        result = invoke_todo_write(todos)

        # Should succeed
        assert "todos" in result.update
        assert len(result.update["todos"]) == 2

    def test_custom_priority(self):
        """Test that custom priority is preserved."""
        todos = [
            {"content": "高优先级任务", "status": "pending", "priority": "high"},
            {"content": "低优先级任务", "status": "pending", "priority": "low"}
        ]

        result = invoke_todo_write(todos)

        updated_todos = result.update["todos"]
        assert updated_todos[0]["priority"] == "high"
        assert updated_todos[1]["priority"] == "low"

    def test_success_message(self):
        """Test success message format."""
        todos = [
            {"content": "任务1", "status": "in_progress"},
            {"content": "任务2", "status": "pending"},
            {"content": "任务3", "status": "completed"}
        ]

        result = invoke_todo_write(todos)

        msg = result.update["messages"][0]
        assert isinstance(msg, ToolMessage)
        assert "✅" in msg.content
        assert "2 个待完成" in msg.content  # in_progress + pending
        assert "1 个已完成" in msg.content


class TestTodoRead:
    """Test todo_read tool."""

    def test_todo_read_with_empty_state(self):
        """Test reading from empty state."""
        state = {"todos": []}

        result = todo_read.invoke({"state": state})

        assert result["ok"] is True
        assert result["todos"] == []
        assert result["summary"]["total"] == 0
        assert result["summary"]["pending"] == 0
        assert result["summary"]["in_progress"] == 0
        assert result["summary"]["completed"] == 0

    def test_todo_read_with_tasks(self):
        """Test reading state with tasks."""
        state = {
            "todos": [
                {"content": "任务1", "status": "in_progress", "id": "abc123"},
                {"content": "任务2", "status": "pending", "id": "def456"},
                {"content": "任务3", "status": "pending", "id": "ghi789"},
                {"content": "任务4", "status": "completed", "id": "jkl012"}
            ]
        }

        result = todo_read.invoke({"state": state})

        assert result["ok"] is True
        assert len(result["todos"]) == 4
        assert result["summary"]["total"] == 4
        assert result["summary"]["in_progress"] == 1
        assert result["summary"]["pending"] == 2
        assert result["summary"]["completed"] == 1

    def test_todo_read_context_id(self):
        """Test that context_id is included in result."""
        state = {
            "todos": [],
            "context_id": "subagent-xyz"
        }

        result = todo_read.invoke({"state": state})

        assert result["context"] == "subagent-xyz"


class TestTodoReminder:
    """Test TODO reminder display logic (from planner.py).

    Note: These are unit tests for the reminder building logic.
    The actual integration happens in planner_node.
    """

    def build_todo_reminder(self, todos: list) -> str:
        """Replicate the reminder building logic from planner.py:190-234."""
        if not todos:
            return ""

        in_progress = [t for t in todos if t.get("status") == "in_progress"]
        pending = [t for t in todos if t.get("status") == "pending"]
        completed = [t for t in todos if t.get("status") == "completed"]

        incomplete = in_progress + pending

        if incomplete:
            todo_lines = []

            # Show in_progress task(s)
            if in_progress:
                for task in in_progress:
                    priority = task.get('priority', 'medium')
                    priority_tag = f"[{priority}]" if priority != "medium" else ""
                    todo_lines.append(f"  [进行中] {task.get('content')} {priority_tag}".strip())

            # Show all pending tasks
            if pending:
                for task in pending:
                    priority = task.get('priority', 'medium')
                    priority_tag = f"[{priority}]" if priority != "medium" else ""
                    todo_lines.append(f"  [待完成] {task.get('content')} {priority_tag}".strip())

            # Show completed count
            completed_summary = f"  (已完成 {len(completed)} 个)" if completed else ""

            return f"""<system_reminder>
⚠️ 任务追踪 ({len(incomplete)} 个未完成):
{chr(10).join(todo_lines)}
{completed_summary}

完成所有任务后再停止！
</system_reminder>"""
        elif completed:
            return f"<system_reminder>✅ 所有 {len(completed)} 个任务已完成！可以输出最终结果。</system_reminder>"

        return ""

    def test_reminder_shows_all_tasks(self):
        """Test that reminder displays ALL incomplete tasks."""
        todos = [
            {"content": "任务A", "status": "in_progress"},
            {"content": "任务B", "status": "pending"},
            {"content": "任务C", "status": "pending"},
            {"content": "任务D", "status": "pending"},
            {"content": "任务E", "status": "completed"}
        ]

        reminder = self.build_todo_reminder(todos)

        # Should show all 4 incomplete tasks
        assert "[进行中] 任务A" in reminder
        assert "[待完成] 任务B" in reminder
        assert "[待完成] 任务C" in reminder
        assert "[待完成] 任务D" in reminder

        # Should show completed count
        assert "(已完成 1 个)" in reminder

        # Should show total count
        assert "(4 个未完成)" in reminder

    def test_reminder_priority_tags(self):
        """Test that priority tags are shown correctly."""
        todos = [
            {"content": "高优", "status": "pending", "priority": "high"},
            {"content": "中优", "status": "pending", "priority": "medium"},
            {"content": "低优", "status": "pending", "priority": "low"}
        ]

        reminder = self.build_todo_reminder(todos)

        # High and low priority should show tags
        assert "[待完成] 高优 [high]" in reminder
        assert "[待完成] 低优 [low]" in reminder

        # Medium priority should NOT show tag
        assert "[待完成] 中优 [medium]" not in reminder
        assert "[待完成] 中优" in reminder  # But without tag

    def test_reminder_all_completed(self):
        """Test reminder when all tasks are completed."""
        todos = [
            {"content": "任务1", "status": "completed"},
            {"content": "任务2", "status": "completed"}
        ]

        reminder = self.build_todo_reminder(todos)

        assert "✅ 所有 2 个任务已完成" in reminder
        assert "可以输出最终结果" in reminder

    def test_reminder_empty_todos(self):
        """Test reminder with no todos."""
        reminder = self.build_todo_reminder([])

        assert reminder == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
