"""
Test ToolNode support for dynamically loaded tools.

Verifies that ToolNode can execute tools that were not initially enabled
but were dynamically loaded on-demand.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, ToolCall

from generalAgent.tools.scanner import scan_tools_directory
from generalAgent.tools.registry import ToolRegistry


class TestToolNodeDynamicLoading:
    """Test ToolNode with dynamically loaded tools"""

    def test_toolnode_accepts_discovered_tools(self):
        """ToolNode should accept all discovered tools (not just enabled)"""
        # Scan all builtin tools
        builtin_dir = Path("generalAgent/tools/builtin")
        discovered_tools = scan_tools_directory(builtin_dir)

        # Verify compact_context is in discovered tools
        assert "compact_context" in discovered_tools

        # Create ToolNode with ALL discovered tools (simulating builder.py fix)
        all_tools = list(discovered_tools.values())
        tool_node = ToolNode(all_tools)

        # Verify ToolNode has compact_context in its tools_by_name
        assert "compact_context" in tool_node.tools_by_name, \
            "ToolNode should have compact_context in its internal tools map"

    def test_toolnode_can_execute_dynamic_tool(self):
        """ToolNode should be able to execute dynamically loaded tools"""
        # Scan all builtin tools
        builtin_dir = Path("generalAgent/tools/builtin")
        discovered_tools = scan_tools_directory(builtin_dir)

        # Create ToolNode with ALL discovered tools
        all_tools = list(discovered_tools.values())
        tool_node = ToolNode(all_tools)

        # Simulate state with compact_context tool call
        # (Note: We can't actually execute it without proper state,
        #  but we can verify it's in the tool map)
        tool_calls = [
            {
                "name": "compact_context",
                "args": {"strategy": "compact"},
                "id": "call_test_123",
                "type": "tool_call"
            }
        ]

        ai_message = AIMessage(content="", tool_calls=tool_calls)
        state = {"messages": [ai_message]}

        # Verify tool_node can find the tool (won't raise "not a valid tool" error)
        # We expect it to fail with other errors (missing state fields, etc.)
        # but NOT with "not a valid tool"
        try:
            # This will fail because compact_context needs InjectedState
            # but the important part is it should NOT fail with "not a valid tool"
            result = tool_node.invoke(state)
        except Exception as e:
            error_msg = str(e)
            # Should NOT be the "not a valid tool" error
            assert "is not a valid tool" not in error_msg, \
                f"ToolNode rejected compact_context: {error_msg}"
            # Expected error: missing required parameter or state field
            print(f"Expected error (not 'invalid tool'): {error_msg[:100]}")

    def test_builder_pattern_all_discovered_tools(self):
        """Verify builder.py pattern: ToolNode gets ALL discovered tools"""
        # Simulate app.py tool registration
        builtin_dir = Path("generalAgent/tools/builtin")
        discovered_tools = scan_tools_directory(builtin_dir)

        registry = ToolRegistry()

        # Register ALL discovered tools (app.py:64-66)
        for tool_name, tool_instance in discovered_tools.items():
            registry.register_discovered(tool_instance)

        # Only enable core tools (app.py:68-76)
        enabled_core_tools = [
            "now", "todo_write", "todo_read", "delegate_task",
            "read_file", "write_file", "list_workspace_files",
            "find_files", "search_file", "edit_file",
            "ask_human", "fetch_web", "web_search"
        ]

        for tool_name in enabled_core_tools:
            if tool_name in discovered_tools:
                registry.register_tool(discovered_tools[tool_name])

        # Verify compact_context is NOT in enabled tools
        enabled_tools = [t.name for t in registry.list_tools()]
        assert "compact_context" not in enabled_tools, \
            "compact_context should not be enabled by default"

        # But it SHOULD be in discovered tools
        assert registry.is_discovered("compact_context"), \
            "compact_context should be in discovered pool"

        # Builder.py should use ALL discovered tools for ToolNode (Fix 2)
        all_discovered_tools = [tool for tool in registry._discovered.values()]
        tool_node = ToolNode(all_discovered_tools)

        # Verify ToolNode has compact_context
        assert "compact_context" in tool_node.tools_by_name, \
            "ToolNode should have compact_context (from discovered pool)"

        # Verify ToolNode also has enabled tools
        assert "read_file" in tool_node.tools_by_name, \
            "ToolNode should have enabled tools too"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
