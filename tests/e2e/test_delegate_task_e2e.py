"""End-to-end test for delegate_task tool with real application graph."""
import pytest
import os
from pathlib import Path


@pytest.mark.asyncio
async def test_delegate_basic_task():
    """Test basic delegate execution with simple file search task."""
    from generalAgent.runtime.app import build_application
    from generalAgent.tools.builtin.delegate_task import set_app_graph
    import json

    # Build application
    app, _, skill_registry, tool_registry, _ = await build_application()

    # Set app graph for delegate_task tool
    set_app_graph(app)

    # Create initial state
    initial_state = {
        "messages": [],
        "images": [],
        "active_skill": None,
        "allowed_tools": [],
        "mentioned_agents": [],
        "new_mentioned_agents": [],
        "persistent_tools": [],
        "model_pref": None,
        "todos": [],
        "context_id": "test-main",
        "parent_context": None,
        "loops": 0,
        "max_loops": 50,
        "thread_id": "test-thread-1",
        "user_id": None,
        "uploaded_files": [],
        "new_uploaded_files": [],
    }

    # Import and invoke delegate_task tool
    from generalAgent.tools.builtin.delegate_task import delegate_task

    # Task: Simple greeting (no tool calls needed)
    task = "请简单介绍一下你自己，说明你可以做什么。不要调用任何工具。"

    result_json = await delegate_task.ainvoke({
        "task": task,
        "max_loops": 5
    })

    # Parse result
    result = json.loads(result_json)

    # Verify result structure
    assert "ok" in result
    assert result["ok"] is True, f"Delegated agent failed: {result.get('error', 'Unknown error')}"
    assert "result" in result
    assert "context_id" in result
    assert result["context_id"].startswith("delegate-")
    assert "loops" in result

    # Verify result content has meaningful response
    response = result["result"]
    assert isinstance(response, str)
    assert len(response) > 10, "Response too short"

    print(f"\n✅ Delegated agent completed in {result['loops']} loops")
    print(f"📝 Response preview: {response[:200]}...")


@pytest.mark.asyncio
async def test_delegate_with_tool_calls():
    """Test delegate execution that requires tool calls."""
    from generalAgent.runtime.app import build_application
    from generalAgent.tools.builtin.delegate_task import set_app_graph
    import json

    # Build application
    app, _, skill_registry, tool_registry, _ = await build_application()
    set_app_graph(app)

    # Import tool
    from generalAgent.tools.builtin.delegate_task import delegate_task

    # Task: Get current time (requires now tool)
    task = "请使用 now 工具获取当前时间，并告诉我现在是几点。"

    result_json = await delegate_task.ainvoke({
        "task": task,
        "max_loops": 10
    })

    result = json.loads(result_json)

    # Verify success
    assert result["ok"] is True, f"Delegated agent failed: {result.get('error', 'Unknown error')}"

    # Verify result mentions time-related keywords
    response = result["result"]
    assert any(keyword in response.lower() for keyword in ["utc", "时间", "time", "2025"]), \
        f"Response doesn't mention time: {response}"

    # Verify at least one loop was used (tool call + response)
    assert result["loops"] >= 1, f"Expected at least 1 loop, got {result['loops']}"

    print(f"\n✅ Delegated agent with tool call completed in {result['loops']} loops")
    print(f"📝 Response: {response}")


@pytest.mark.asyncio
async def test_delegate_context_isolation():
    """Test that delegate has isolated context and doesn't pollute main state."""
    from generalAgent.runtime.app import build_application
    from generalAgent.tools.builtin.delegate_task import set_app_graph
    import json

    app, _, skill_registry, tool_registry, _ = await build_application()
    set_app_graph(app)

    from generalAgent.tools.builtin.delegate_task import delegate_task

    # Run two delegates sequentially
    task1 = "任务1：说'Hello from task 1'"
    task2 = "任务2：说'Hello from task 2'"

    result1_json = await delegate_task.ainvoke({"task": task1, "max_loops": 5})
    result1 = json.loads(result1_json)

    result2_json = await delegate_task.ainvoke({"task": task2, "max_loops": 5})
    result2 = json.loads(result2_json)

    # Both should succeed
    assert result1["ok"] is True
    assert result2["ok"] is True

    # They should have different context IDs
    assert result1["context_id"] != result2["context_id"]
    assert result1["context_id"].startswith("delegate-")
    assert result2["context_id"].startswith("delegate-")

    # Both should be independent (no shared state)
    assert "task 1" in result1["result"].lower() or "hello" in result1["result"].lower()
    assert "task 2" in result2["result"].lower() or "hello" in result2["result"].lower()

    print(f"\n✅ Context isolation verified")
    print(f"   Delegated agent 1: {result1['context_id']}")
    print(f"   Delegated agent 2: {result2['context_id']}")


@pytest.mark.asyncio
async def test_delegate_max_loops_limit():
    """Test that delegate respects max_loops limit."""
    from generalAgent.runtime.app import build_application
    from generalAgent.tools.builtin.delegate_task import set_app_graph
    import json

    app, _, skill_registry, tool_registry, _ = await build_application()
    set_app_graph(app)

    from generalAgent.tools.builtin.delegate_task import delegate_task

    # Set very low max_loops
    task = "请帮我执行一个复杂的任务，需要多次思考和工具调用。"

    result_json = await delegate_task.ainvoke({
        "task": task,
        "max_loops": 2  # Very low limit
    })

    result = json.loads(result_json)

    # Should still succeed (or gracefully handle limit)
    assert result["ok"] is True

    # Should not exceed max_loops
    assert result["loops"] <= 2, f"Exceeded max_loops: {result['loops']} > 2"

    print(f"\n✅ Max loops limit respected: {result['loops']}/2")


@pytest.mark.asyncio
async def test_delegate_error_handling():
    """Test delegate error handling when app graph is not set."""
    from generalAgent.tools.builtin.delegate_task import delegate_task, _app_graph_ctx
    import json

    # Explicitly set app graph to None
    token = _app_graph_ctx.set(None)

    try:
        result_json = await delegate_task.ainvoke({
            "task": "Test task",
            "max_loops": 5
        })

        result = json.loads(result_json)

        # Should return error
        assert result["ok"] is False
        assert "error" in result
        assert "not initialized" in result["error"].lower()

        print(f"\n✅ Error handling works: {result['error']}")

    finally:
        _app_graph_ctx.reset(token)


@pytest.mark.asyncio
async def test_delegate_state_field_preservation():
    """Test that delegate has all required state fields including new ones."""
    from generalAgent.runtime.app import build_application
    from generalAgent.tools.builtin.delegate_task import set_app_graph
    from unittest.mock import MagicMock, patch
    import json

    app, _, skill_registry, tool_registry, _ = await build_application()

    # Mock astream to capture the state passed to it
    original_astream = app.astream
    captured_state = {}

    async def mock_astream(state, config=None, stream_mode=None):
        # Capture the state
        captured_state.update(state)
        # Call original
        async for s in original_astream(state, config=config, stream_mode=stream_mode):
            yield s

    # Replace astream temporarily
    app.astream = mock_astream
    set_app_graph(app)

    from generalAgent.tools.builtin.delegate_task import delegate_task

    try:
        result_json = await delegate_task.ainvoke({
            "task": "简单说 hello",
            "max_loops": 3
        })

        result = json.loads(result_json)
        assert result["ok"] is True

        # Verify captured state has all required fields
        required_fields = [
            "messages", "images", "active_skill", "allowed_tools",
            "mentioned_agents", "new_mentioned_agents",
            "persistent_tools", "todos",
            "context_id", "parent_context", "loops", "max_loops",
            "uploaded_files", "new_uploaded_files"
        ]

        for field in required_fields:
            assert field in captured_state, f"Missing field: {field}"

        # Verify new fields are initialized correctly
        assert captured_state["new_mentioned_agents"] == []
        assert captured_state["uploaded_files"] == []
        assert captured_state["new_uploaded_files"] == []

        print(f"\n✅ All state fields present and initialized correctly")

    finally:
        # Restore original astream
        app.astream = original_astream
