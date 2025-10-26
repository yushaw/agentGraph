"""Test MCP connection layer."""

import pytest
import sys


@pytest.mark.asyncio
async def test_stdio_connection_lifecycle(test_server_path):
    """Test stdio connection start and close."""
    from generalAgent.tools.mcp.connection import StdioMCPConnection

    connection = StdioMCPConnection(
        server_id="test_stdio",
        command=sys.executable,
        args=[str(test_server_path)],
        env={}
    )

    # Start server
    await connection.start()
    assert connection._initialized is True
    assert connection._client is not None

    # List tools
    tools = await connection.list_tools()
    assert len(tools) == 3
    tool_names = [tool.name for tool in tools]
    assert "echo" in tool_names
    assert "add" in tool_names
    assert "get_time" in tool_names

    # Close connection
    await connection.close()
    assert connection._initialized is False


@pytest.mark.asyncio
async def test_call_echo_tool(test_server_path):
    """Test calling echo tool."""
    from generalAgent.tools.mcp.connection import StdioMCPConnection

    connection = StdioMCPConnection(
        server_id="test_stdio",
        command=sys.executable,
        args=[str(test_server_path)],
        env={}
    )

    await connection.start()

    # Call echo tool
    result = await connection.call_tool("echo", {"message": "Hello MCP!"})
    assert "Echo: Hello MCP!" in result

    await connection.close()


@pytest.mark.asyncio
async def test_call_add_tool(test_server_path):
    """Test calling add tool."""
    from generalAgent.tools.mcp.connection import StdioMCPConnection

    connection = StdioMCPConnection(
        server_id="test_stdio",
        command=sys.executable,
        args=[str(test_server_path)],
        env={}
    )

    await connection.start()

    # Call add tool
    result = await connection.call_tool("add", {"a": 5, "b": 3})
    assert "5 + 3 = 8" in result

    await connection.close()


@pytest.mark.asyncio
async def test_call_get_time_tool(test_server_path):
    """Test calling get_time tool."""
    from generalAgent.tools.mcp.connection import StdioMCPConnection

    connection = StdioMCPConnection(
        server_id="test_stdio",
        command=sys.executable,
        args=[str(test_server_path)],
        env={}
    )

    await connection.start()

    # Call get_time tool
    result = await connection.call_tool("get_time", {})
    assert "Current time:" in result
    assert "-" in result  # Date format

    await connection.close()


@pytest.mark.asyncio
async def test_get_tool_info(test_server_path):
    """Test getting tool information."""
    from generalAgent.tools.mcp.connection import StdioMCPConnection

    connection = StdioMCPConnection(
        server_id="test_stdio",
        command=sys.executable,
        args=[str(test_server_path)],
        env={}
    )

    await connection.start()

    # Get tool info
    tool_info = await connection.get_tool_info("echo")
    assert tool_info.name == "echo"
    assert "message" in str(tool_info.inputSchema)

    await connection.close()


@pytest.mark.asyncio
async def test_invalid_tool_call(test_server_path):
    """Test calling non-existent tool."""
    from generalAgent.tools.mcp.connection import StdioMCPConnection

    connection = StdioMCPConnection(
        server_id="test_stdio",
        command=sys.executable,
        args=[str(test_server_path)],
        env={}
    )

    await connection.start()

    # Call invalid tool
    with pytest.raises(Exception):
        await connection.call_tool("nonexistent_tool", {})

    await connection.close()
