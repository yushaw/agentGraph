"""Test delegate_task tool with new state fields."""
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage
import asyncio


@pytest.mark.asyncio
async def test_delegate_state_has_required_fields():
    """Test that delegate state includes all required fields including new ones."""
    from generalAgent.tools.builtin.delegate_task import delegate_task, _app_graph_ctx

    # Mock app graph
    mock_app = MagicMock()
    mock_app.astream = MagicMock()

    # Create async iterator that yields one result
    async def mock_astream(*args, **kwargs):
        # Extract the state that was passed to astream
        if args:
            passed_state = args[0]
            # Return the state with a final message
            final_state = passed_state.copy()
            final_state["messages"].append(HumanMessage(content="Result"))
            yield final_state

    mock_app.astream.side_effect = mock_astream

    # Set context
    token = _app_graph_ctx.set(mock_app)

    try:
        # Call using ainvoke for async tool
        result_json = await delegate_task.ainvoke({"task": "Test task", "max_loops": 3})

        # Parse result
        import json
        result = json.loads(result_json)

        # Should succeed (not error about missing fields)
        assert result["ok"] is True, f"Expected success but got: {result}"

        # Verify the state passed to astream had all required fields
        call_args = mock_app.astream.call_args
        passed_state = call_args[0][0]

        # Check original fields
        assert "messages" in passed_state
        assert "images" in passed_state
        assert "active_skill" in passed_state
        assert "allowed_tools" in passed_state
        assert "mentioned_agents" in passed_state
        assert "persistent_tools" in passed_state
        assert "todos" in passed_state
        assert "context_id" in passed_state
        assert "parent_context" in passed_state
        assert "loops" in passed_state
        assert "max_loops" in passed_state

        # Check NEW fields (added to fix reminder deduplication)
        assert "new_mentioned_agents" in passed_state, "Missing new_mentioned_agents field"
        assert "uploaded_files" in passed_state, "Missing uploaded_files field"
        assert "new_uploaded_files" in passed_state, "Missing new_uploaded_files field"

        # Verify new fields are initialized correctly
        assert passed_state["new_mentioned_agents"] == []
        assert passed_state["uploaded_files"] == []
        assert passed_state["new_uploaded_files"] == []

    finally:
        _app_graph_ctx.reset(token)


@pytest.mark.asyncio
async def test_delegate_state_field_types():
    """Test that all state fields have correct types."""
    from generalAgent.tools.builtin.delegate_task import delegate_task, _app_graph_ctx

    # Mock app graph
    mock_app = MagicMock()

    async def mock_astream(*args, **kwargs):
        passed_state = args[0]
        final_state = passed_state.copy()
        final_state["messages"].append(HumanMessage(content="Done"))
        yield final_state

    mock_app.astream.side_effect = mock_astream

    token = _app_graph_ctx.set(mock_app)

    try:
        await delegate_task.ainvoke({"task": "Task", "max_loops": 5})

        # Get the state that was passed
        passed_state = mock_app.astream.call_args[0][0]

        # Check types
        assert isinstance(passed_state["messages"], list)
        assert isinstance(passed_state["images"], list)
        assert isinstance(passed_state["allowed_tools"], list)
        assert isinstance(passed_state["mentioned_agents"], list)
        assert isinstance(passed_state["new_mentioned_agents"], list)
        assert isinstance(passed_state["persistent_tools"], list)
        assert isinstance(passed_state["todos"], list)
        assert isinstance(passed_state["uploaded_files"], list)
        assert isinstance(passed_state["new_uploaded_files"], list)
        assert isinstance(passed_state["loops"], int)
        assert isinstance(passed_state["max_loops"], int)
        assert isinstance(passed_state["context_id"], str)

    finally:
        _app_graph_ctx.reset(token)


@pytest.mark.asyncio
async def test_delegate_without_app_graph():
    """Test error handling when app graph is not initialized."""
    from generalAgent.tools.builtin.delegate_task import delegate_task, _app_graph_ctx

    # Ensure no app graph in context
    token = _app_graph_ctx.set(None)

    try:
        result_json = await delegate_task.ainvoke({"task": "Test task"})

        import json
        result = json.loads(result_json)

        # Should return error
        assert result["ok"] is False
        assert "not initialized" in result["error"].lower()

    finally:
        _app_graph_ctx.reset(token)


@pytest.mark.asyncio
async def test_delegate_context_isolation():
    """Test that delegate has isolated context."""
    from generalAgent.tools.builtin.delegate_task import delegate_task, _app_graph_ctx

    mock_app = MagicMock()

    async def mock_astream(*args, **kwargs):
        passed_state = args[0]
        final_state = passed_state.copy()
        final_state["messages"].append(HumanMessage(content="Result"))
        yield final_state

    mock_app.astream.side_effect = mock_astream

    token = _app_graph_ctx.set(mock_app)

    try:
        await delegate_task.ainvoke({"task": "Isolated task", "max_loops": 10})

        passed_state = mock_app.astream.call_args[0][0]

        # Verify context isolation
        assert passed_state["context_id"].startswith("delegate-")
        assert passed_state["parent_context"] == "main"
        assert passed_state["loops"] == 0  # Fresh start
        assert passed_state["max_loops"] == 10

        # Verify isolation: should have empty collections
        assert passed_state["mentioned_agents"] == []
        assert passed_state["new_mentioned_agents"] == []
        assert passed_state["todos"] == []
        assert passed_state["uploaded_files"] == []
        assert passed_state["new_uploaded_files"] == []

    finally:
        _app_graph_ctx.reset(token)


@pytest.mark.asyncio
async def test_delegate_with_real_state_schema():
    """Test that delegate state matches AppState schema."""
    from generalAgent.graph.state import AppState
    from generalAgent.tools.builtin.delegate_task import _app_graph_ctx
    from typing import get_type_hints

    # Get AppState fields
    # Note: TypedDict doesn't have __annotations__ in all Python versions
    # So we check if the state we create would be valid

    mock_app = MagicMock()

    async def mock_astream(*args, **kwargs):
        passed_state = args[0]

        # Verify state has expected structure
        required_fields = [
            "messages", "images", "active_skill", "allowed_tools",
            "mentioned_agents", "new_mentioned_agents",
            "persistent_tools", "model_pref", "todos",
            "context_id", "parent_context", "loops", "max_loops",
            "thread_id", "user_id",
            "uploaded_files", "new_uploaded_files"
        ]

        for field in required_fields:
            assert field in passed_state, f"Missing required field: {field}"

        final_state = passed_state.copy()
        final_state["messages"].append(HumanMessage(content="Success"))
        yield final_state

    mock_app.astream.side_effect = mock_astream

    token = _app_graph_ctx.set(mock_app)

    try:
        from generalAgent.tools.builtin.delegate_task import delegate_task
        result_json = await delegate_task.ainvoke({"task": "Schema test"})

        import json
        result = json.loads(result_json)
        assert result["ok"] is True

    finally:
        _app_graph_ctx.reset(token)
