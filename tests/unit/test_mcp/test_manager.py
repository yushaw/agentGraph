"""Test MCP server manager."""

import pytest


@pytest.mark.asyncio
async def test_manager_initialization(test_mcp_config):
    """Test manager initialization."""
    from generalAgent.tools.mcp import MCPServerManager

    manager = MCPServerManager(test_mcp_config)

    # Check configured servers
    configured = manager.list_configured_servers()
    assert len(configured) == 1
    assert "test_stdio" in configured

    # No servers started yet
    started = manager.list_started_servers()
    assert len(started) == 0


@pytest.mark.asyncio
async def test_lazy_server_startup(mcp_manager):
    """Test lazy server startup."""
    # Initially no servers started
    assert len(mcp_manager.list_started_servers()) == 0

    # Get server (triggers lazy startup)
    connection = await mcp_manager.get_server("test_stdio")
    assert connection is not None
    assert connection._initialized is True

    # Server now started
    assert len(mcp_manager.list_started_servers()) == 1
    assert "test_stdio" in mcp_manager.list_started_servers()

    # Getting again returns same connection
    connection2 = await mcp_manager.get_server("test_stdio")
    assert connection2 is connection


@pytest.mark.asyncio
async def test_manager_shutdown(mcp_manager):
    """Test manager shutdown."""
    # Start server
    await mcp_manager.get_server("test_stdio")
    assert len(mcp_manager.list_started_servers()) == 1

    # Shutdown
    await mcp_manager.shutdown()
    assert len(mcp_manager.list_started_servers()) == 0


@pytest.mark.asyncio
async def test_get_nonexistent_server(mcp_manager):
    """Test getting non-configured server."""
    with pytest.raises(ValueError, match="not configured"):
        await mcp_manager.get_server("nonexistent_server")


@pytest.mark.asyncio
async def test_is_server_started(mcp_manager):
    """Test checking if server is started."""
    assert not mcp_manager.is_server_started("test_stdio")

    await mcp_manager.get_server("test_stdio")

    assert mcp_manager.is_server_started("test_stdio")
