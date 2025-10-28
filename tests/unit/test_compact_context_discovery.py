"""
Test compact_context tool discovery and on-demand loading.

This test verifies that compact_context is properly discovered during tool scanning
and can be loaded on-demand when token usage is critical.
"""

import pytest
from pathlib import Path

from generalAgent.tools.scanner import scan_tools_directory
from generalAgent.tools.registry import ToolRegistry


class TestCompactContextDiscovery:
    """Test compact_context discovery and loading"""

    def test_compact_context_is_discovered(self):
        """compact_context should be discovered during tool scan"""
        # Scan builtin tools directory
        builtin_dir = Path("generalAgent/tools/builtin")
        discovered_tools = scan_tools_directory(builtin_dir)

        # Verify compact_context is in discovered tools
        assert "compact_context" in discovered_tools, \
            f"compact_context not found in discovered tools. Found: {list(discovered_tools.keys())}"

        # Verify it's a valid tool with correct metadata
        tool = discovered_tools["compact_context"]
        assert tool.name == "compact_context"
        assert "compress" in tool.description.lower() or "压缩" in tool.description

    def test_compact_context_can_be_loaded_on_demand(self):
        """compact_context should be loadable via load_on_demand()"""
        # Create registry and scan tools
        builtin_dir = Path("generalAgent/tools/builtin")
        discovered_tools = scan_tools_directory(builtin_dir)

        registry = ToolRegistry()

        # Register all discovered tools (simulating app.py behavior)
        for tool_name, tool_instance in discovered_tools.items():
            registry.register_discovered(tool_instance)

        # Verify compact_context is in discovered pool
        assert registry.is_discovered("compact_context"), \
            "compact_context should be in discovered tools pool"

        # Load on-demand (simulating planner.py behavior when token usage is high)
        try:
            loaded_tool = registry.load_on_demand("compact_context")
            assert loaded_tool.name == "compact_context"
            assert loaded_tool == registry.get_tool("compact_context")
        except KeyError as e:
            pytest.fail(f"Failed to load compact_context on-demand: {e}")

    def test_compact_context_not_enabled_by_default(self):
        """compact_context should NOT be in core tools (only loaded when needed)"""
        # Scan builtin tools directory
        builtin_dir = Path("generalAgent/tools/builtin")
        discovered_tools = scan_tools_directory(builtin_dir)

        # Create registry but only register enabled tools
        # (compact_context has enabled: false in tools.yaml)
        registry = ToolRegistry()

        # Simulate enabled tools only (compact_context should NOT be here)
        # In real app, only tools with enabled: true are registered initially
        enabled_core_tools = [
            "now", "todo_write", "todo_read", "delegate_task",
            "read_file", "write_file", "list_workspace_files",
            "find_files", "search_file", "edit_file",
            "ask_human", "fetch_web", "web_search"
        ]

        for tool_name in enabled_core_tools:
            if tool_name in discovered_tools:
                registry.register_tool(discovered_tools[tool_name])

        # compact_context should NOT be in enabled tools
        try:
            registry.get_tool("compact_context")
            pytest.fail("compact_context should not be enabled by default")
        except KeyError:
            pass  # Expected - not enabled

        # But it should be in discovered pool for on-demand loading
        for tool_name, tool_instance in discovered_tools.items():
            registry.register_discovered(tool_instance)

        assert registry.is_discovered("compact_context"), \
            "compact_context should be discoverable for on-demand loading"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
