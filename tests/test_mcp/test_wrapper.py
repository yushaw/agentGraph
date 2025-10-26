"""Test MCP tool wrapper."""

import pytest


@pytest.mark.asyncio
async def test_wrapper_creation(mcp_tools):
    """Test MCP tool wrapper creation."""
    from generalAgent.tools.mcp import MCPToolWrapper

    assert len(mcp_tools) == 3

    # Check tool names
    tool_names = [tool.name for tool in mcp_tools]
    assert "mcp_echo" in tool_names
    assert "mcp_add" in tool_names
    assert "mcp_time" in tool_names

    # Check types
    for tool in mcp_tools:
        assert isinstance(tool, MCPToolWrapper)


@pytest.mark.asyncio
async def test_wrapper_async_call(mcp_tools):
    """Test async tool call via wrapper."""
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Call via _arun
    result = await echo_tool._arun(message="Test async call")
    assert "Echo: Test async call" in result


@pytest.mark.asyncio
async def test_wrapper_sync_call(mcp_tools):
    """Test sync tool call via wrapper."""
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Call via _run (sync wrapper)
    result = echo_tool._run(message="Test sync call")
    assert "Echo: Test sync call" in result


@pytest.mark.asyncio
async def test_wrapper_add_tool(mcp_tools):
    """Test add tool via wrapper."""
    add_tool = next(t for t in mcp_tools if t.name == "mcp_add")

    result = await add_tool._arun(a=10, b=20)
    assert "10 + 20 = 30" in result


@pytest.mark.asyncio
async def test_wrapper_lazy_server_startup(mcp_tools, mcp_manager):
    """Test that tool call triggers lazy server startup."""
    # Server not started yet
    assert not mcp_manager.is_server_started("test_stdio")

    # Call tool (should trigger server startup)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")
    result = await echo_tool._arun(message="Trigger startup")

    # Server now started
    assert mcp_manager.is_server_started("test_stdio")
    assert "Echo: Trigger startup" in result


@pytest.mark.asyncio
async def test_wrapper_metadata(mcp_tools):
    """Test wrapper metadata."""
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    assert echo_tool.server_id == "test_stdio"
    assert echo_tool.original_tool_name == "echo"
    assert echo_tool.name == "mcp_echo"
    assert "Echo back a message" in echo_tool.description
    assert echo_tool.always_available is False

    # Check always_available tool
    time_tool = next(t for t in mcp_tools if t.name == "mcp_time")
    assert time_tool.always_available is True


@pytest.mark.asyncio
async def test_wrapper_error_handling(mcp_tools):
    """Test wrapper error handling."""
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Call with invalid arguments (missing required 'message')
    result = await echo_tool._arun()
    assert "failed" in result.lower() or "error" in result.lower()
