"""Pytest fixtures for MCP tests."""

import asyncio
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_server_path():
    """Path to test stdio server."""
    return Path(__file__).parent.parent / "mcp_servers" / "test_stdio_server.py"


@pytest.fixture
def test_mcp_config(test_server_path):
    """Test MCP configuration."""
    import sys
    python_exe = sys.executable  # Use current Python interpreter

    return {
        "servers": {
            "test_stdio": {
                "command": python_exe,
                "args": [str(test_server_path)],
                "enabled": True,
                "env": {},
                "tools": {
                    "echo": {
                        "enabled": True,
                        "always_available": False,
                        "alias": "mcp_echo",
                        "description": "Echo back a message"
                    },
                    "add": {
                        "enabled": True,
                        "always_available": False,
                        "alias": "mcp_add",
                        "description": "Add two numbers"
                    },
                    "get_time": {
                        "enabled": True,
                        "always_available": True,  # Test always_available
                        "alias": "mcp_time",
                        "description": "Get current server time"
                    }
                }
            }
        },
        "settings": {
            "lazy_start": True,
            "namespace_strategy": "alias",
            "startup_timeout": 30,
            "default_connection_mode": "stdio"
        }
    }


@pytest.fixture
async def mcp_manager(test_mcp_config):
    """Create and cleanup MCP manager."""
    from generalAgent.tools.mcp import MCPServerManager

    manager = MCPServerManager(test_mcp_config)
    yield manager

    # Cleanup
    await manager.shutdown()


@pytest.fixture
async def mcp_tools(test_mcp_config, mcp_manager):
    """Create MCP tools."""
    from generalAgent.tools.mcp import load_mcp_tools

    tools = load_mcp_tools(test_mcp_config, mcp_manager)
    return tools
