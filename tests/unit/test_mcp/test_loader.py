"""Test MCP configuration loader."""

import pytest
import yaml
from pathlib import Path


def test_load_mcp_config(tmp_path):
    """Test loading MCP configuration from YAML."""
    from generalAgent.tools.mcp import load_mcp_config

    # Create test config
    config_path = tmp_path / "test_mcp_config.yaml"
    test_config = {
        "servers": {
            "test_server": {
                "command": "python",
                "args": ["test.py"],
                "enabled": True,
                "tools": {
                    "test_tool": {
                        "enabled": True,
                        "alias": "my_tool"
                    }
                }
            }
        },
        "settings": {
            "lazy_start": True
        }
    }

    with open(config_path, "w") as f:
        yaml.dump(test_config, f)

    # Load config
    loaded = load_mcp_config(config_path)
    assert loaded == test_config
    assert "servers" in loaded
    assert "test_server" in loaded["servers"]


def test_load_mcp_config_nonexistent():
    """Test loading non-existent config."""
    from generalAgent.tools.mcp import load_mcp_config

    with pytest.raises(FileNotFoundError):
        load_mcp_config(Path("/nonexistent/config.yaml"))


def test_load_mcp_tools(test_mcp_config):
    """Test loading MCP tools from config."""
    from generalAgent.tools.mcp import load_mcp_tools, MCPServerManager

    manager = MCPServerManager(test_mcp_config)
    tools = load_mcp_tools(test_mcp_config, manager)

    # Check tools loaded
    assert len(tools) == 3

    tool_names = [t.name for t in tools]
    assert "mcp_echo" in tool_names
    assert "mcp_add" in tool_names
    assert "mcp_time" in tool_names


def test_load_mcp_tools_with_disabled_server():
    """Test that disabled servers are skipped."""
    from generalAgent.tools.mcp import load_mcp_tools, MCPServerManager

    config = {
        "servers": {
            "disabled_server": {
                "command": "python",
                "args": ["test.py"],
                "enabled": False,
                "tools": {
                    "tool1": {"enabled": True, "alias": "t1"}
                }
            }
        },
        "settings": {"lazy_start": True}
    }

    manager = MCPServerManager(config)
    tools = load_mcp_tools(config, manager)

    # No tools loaded from disabled server
    assert len(tools) == 0


def test_load_mcp_tools_with_disabled_tools(test_mcp_config):
    """Test that disabled tools are skipped."""
    from generalAgent.tools.mcp import load_mcp_tools, MCPServerManager

    # Disable one tool
    test_mcp_config["servers"]["test_stdio"]["tools"]["echo"]["enabled"] = False

    manager = MCPServerManager(test_mcp_config)
    tools = load_mcp_tools(test_mcp_config, manager)

    # Only 2 tools loaded (echo disabled)
    assert len(tools) == 2

    tool_names = [t.name for t in tools]
    assert "mcp_echo" not in tool_names
    assert "mcp_add" in tool_names
    assert "mcp_time" in tool_names


def test_tool_naming_alias_strategy():
    """Test alias naming strategy."""
    from generalAgent.tools.mcp import load_mcp_tools, MCPServerManager

    config = {
        "servers": {
            "test": {
                "command": "python",
                "args": ["test.py"],
                "enabled": True,
                "tools": {
                    "my_tool": {
                        "enabled": True,
                        "alias": "custom_name",
                        "description": "Test"
                    }
                }
            }
        },
        "settings": {
            "namespace_strategy": "alias",
            "lazy_start": True
        }
    }

    manager = MCPServerManager(config)
    tools = load_mcp_tools(config, manager)

    # Tool should use alias
    assert len(tools) == 1
    assert tools[0].name == "custom_name"


def test_tool_naming_prefix_strategy():
    """Test prefix naming strategy."""
    from generalAgent.tools.mcp import load_mcp_tools, MCPServerManager

    config = {
        "servers": {
            "test_server": {
                "command": "python",
                "args": ["test.py"],
                "enabled": True,
                "tools": {
                    "my_tool": {
                        "enabled": True,
                        "description": "Test"
                    }
                }
            }
        },
        "settings": {
            "namespace_strategy": "prefix",
            "lazy_start": True
        }
    }

    manager = MCPServerManager(config)
    tools = load_mcp_tools(config, manager)

    # Tool should use prefix
    assert len(tools) == 1
    assert tools[0].name == "mcp__test_server__my_tool"
