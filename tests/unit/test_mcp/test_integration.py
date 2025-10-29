"""End-to-end integration tests for MCP."""

import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_full_integration_flow(test_mcp_config, mcp_manager):
    """Test complete MCP integration flow."""
    from generalAgent.tools.mcp import load_mcp_tools

    # 1. Load MCP tools
    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)
    assert len(mcp_tools) == 3

    # 2. Verify server not started yet (lazy mode)
    assert not mcp_manager.is_server_started("test_stdio")

    # 3. Call tool (triggers lazy server startup)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")
    result = await echo_tool._arun(message="Integration test")

    # 4. Verify server started
    assert mcp_manager.is_server_started("test_stdio")
    assert "Echo: Integration test" in result

    # 5. Call another tool (reuse connection)
    add_tool = next(t for t in mcp_tools if t.name == "mcp_add")
    result = await add_tool._arun(a=100, b=200)
    assert "100 + 200 = 300" in result

    # 6. Cleanup
    await mcp_manager.shutdown()
    assert len(mcp_manager.list_started_servers()) == 0


@pytest.mark.asyncio
async def test_tool_registry_integration(test_mcp_config, mcp_manager):
    """Test MCP tools in ToolRegistry."""
    from generalAgent.tools import ToolRegistry
    from generalAgent.tools.mcp import load_mcp_tools

    # Load MCP tools
    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)

    # Create ToolRegistry and register MCP tools
    registry = ToolRegistry()
    for tool in mcp_tools:
        registry.register_tool(tool)
        registry.register_discovered(tool)

    # Verify registration
    all_tools = registry.list_tools()
    assert len(all_tools) == 3

    # Get tool by name
    echo_tool = registry.get_tool("mcp_echo")
    assert echo_tool is not None
    assert echo_tool.name == "mcp_echo"

    # Check if discovered
    assert registry.is_discovered("mcp_echo")
    assert registry.is_discovered("mcp_add")
    assert registry.is_discovered("mcp_time")

    # Call tool through registry
    result = await echo_tool._arun(message="Registry test")
    assert "Echo: Registry test" in result


@pytest.mark.asyncio
async def test_available_to_subagent_tools(test_mcp_config, mcp_manager):
    """Test available_to_subagent tool filtering."""
    from generalAgent.tools.mcp import load_mcp_tools

    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)

    # Check which tools are available_to_subagent
    available_to_subagent = [t for t in mcp_tools if t.available_to_subagent]
    not_available_to_subagent = [t for t in mcp_tools if not t.available_to_subagent]

    # From config: only mcp_time is available_to_subagent
    assert len(available_to_subagent) == 1
    assert len(not_available_to_subagent) == 2

    assert available_to_subagent[0].name == "mcp_time"


@pytest.mark.asyncio
async def test_concurrent_tool_calls(test_mcp_config, mcp_manager):
    """Test concurrent calls to MCP tools."""
    import asyncio
    from generalAgent.tools.mcp import load_mcp_tools

    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Make multiple concurrent calls
    tasks = [
        echo_tool._arun(message=f"Message {i}")
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # Verify all succeeded
    assert len(results) == 5
    for i, result in enumerate(results):
        assert f"Echo: Message {i}" in result


@pytest.mark.asyncio
async def test_error_recovery(test_mcp_config, mcp_manager):
    """Test error handling and recovery."""
    from generalAgent.tools.mcp import load_mcp_tools

    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Call with missing required argument
    result1 = await echo_tool._arun()  # Missing 'message'
    assert "failed" in result1.lower() or "error" in result1.lower()

    # Server should still be running and able to handle valid call
    result2 = await echo_tool._arun(message="Recovery test")
    assert "Echo: Recovery test" in result2


@pytest.mark.asyncio
async def test_server_restart_after_shutdown(test_mcp_config, mcp_manager):
    """Test that server can restart after shutdown."""
    from generalAgent.tools.mcp import load_mcp_tools

    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # First call (starts server)
    result1 = await echo_tool._arun(message="First call")
    assert "Echo: First call" in result1
    assert mcp_manager.is_server_started("test_stdio")

    # Shutdown
    await mcp_manager.shutdown()
    assert not mcp_manager.is_server_started("test_stdio")

    # Second call (should restart server)
    result2 = await echo_tool._arun(message="Second call")
    assert "Echo: Second call" in result2
    assert mcp_manager.is_server_started("test_stdio")


@pytest.mark.asyncio
async def test_multiple_sessions(test_mcp_config):
    """Test multiple independent MCP sessions."""
    from generalAgent.tools.mcp import MCPServerManager, load_mcp_tools

    # Create two independent managers
    manager1 = MCPServerManager(test_mcp_config)
    manager2 = MCPServerManager(test_mcp_config)

    tools1 = load_mcp_tools(test_mcp_config, manager1)
    tools2 = load_mcp_tools(test_mcp_config, manager2)

    # Use tools from both sessions
    echo1 = next(t for t in tools1 if t.name == "mcp_echo")
    echo2 = next(t for t in tools2 if t.name == "mcp_echo")

    result1 = await echo1._arun(message="Session 1")
    result2 = await echo2._arun(message="Session 2")

    assert "Echo: Session 1" in result1
    assert "Echo: Session 2" in result2

    # Both managers have started servers
    assert manager1.is_server_started("test_stdio")
    assert manager2.is_server_started("test_stdio")

    # Cleanup both
    await manager1.shutdown()
    await manager2.shutdown()


@pytest.mark.asyncio
async def test_build_application_with_mcp(test_mcp_config, test_server_path):
    """Test build_application with MCP tools."""
    from generalAgent.runtime import build_application
    from generalAgent.tools.mcp import MCPServerManager, load_mcp_tools

    # Prepare MCP tools
    manager = MCPServerManager(test_mcp_config)
    mcp_tools = load_mcp_tools(test_mcp_config, manager)

    # Build application with MCP tools
    app, initial_state, skill_registry, tool_registry = await build_application(
        mcp_tools=mcp_tools
    )

    # Verify MCP tools registered
    all_tools = tool_registry.list_tools()
    tool_names = [t.name for t in all_tools]

    assert "mcp_echo" in tool_names
    assert "mcp_add" in tool_names
    assert "mcp_time" in tool_names

    # Verify tools work
    mcp_echo = tool_registry.get_tool("mcp_echo")
    result = await mcp_echo._arun(message="App integration test")
    assert "Echo: App integration test" in result

    # Cleanup
    await manager.shutdown()
