"""Tests for tool configuration loader."""

import pytest
from pathlib import Path

from agentgraph.tools.config_loader import ToolConfig, load_tool_config


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample tools.yaml config."""
    config_file = tmp_path / "tools.yaml"
    config_file.write_text("""
core:
  - now
  - calc
  - todo_write

optional:
  get_weather:
    enabled: true
    always_available: false

  http_fetch:
    enabled: false
    always_available: false

directories:
  builtin: "agentgraph/tools/builtin"
  custom: "custom_tools"
""")
    return config_file


def test_load_config(sample_config):
    """Test loading configuration from file."""
    config = ToolConfig(sample_config)

    assert config.get_core_tools() == ["now", "calc", "todo_write"]
    assert "get_weather" in config.get_enabled_optional_tools()
    assert "http_fetch" not in config.get_enabled_optional_tools()


def test_get_all_enabled_tools(sample_config):
    """Test getting all enabled tools."""
    config = ToolConfig(sample_config)

    all_enabled = config.get_all_enabled_tools()
    assert "now" in all_enabled
    assert "calc" in all_enabled
    assert "get_weather" in all_enabled
    assert "http_fetch" not in all_enabled


def test_is_always_available(sample_config):
    """Test checking if tool is always available."""
    config = ToolConfig(sample_config)

    # Core tools are always available
    assert config.is_always_available("now") is True
    assert config.is_always_available("calc") is True

    # Optional tools check their config
    assert config.is_always_available("get_weather") is False
    assert config.is_always_available("http_fetch") is False


def test_get_directories(sample_config):
    """Test getting scan directories."""
    config = ToolConfig(sample_config)

    assert config.get_builtin_directory() == Path("agentgraph/tools/builtin")
    assert config.get_custom_directory() == Path("custom_tools")

    scan_dirs = config.get_scan_directories()
    assert len(scan_dirs) == 2
    assert scan_dirs[0] == Path("agentgraph/tools/builtin")
    assert scan_dirs[1] == Path("custom_tools")


def test_default_config_when_file_missing():
    """Test default configuration when file doesn't exist."""
    config = ToolConfig(Path("/nonexistent/tools.yaml"))

    # Should use defaults
    core = config.get_core_tools()
    assert "now" in core
    assert "calc" in core
    assert "todo_write" in core


def test_load_tool_config_helper():
    """Test the load_tool_config helper function."""
    # Should use default path
    config = load_tool_config()
    assert isinstance(config, ToolConfig)

    # Should accept custom path
    custom_config = load_tool_config(Path("custom/path.yaml"))
    assert isinstance(custom_config, ToolConfig)
