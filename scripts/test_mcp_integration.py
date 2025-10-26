#!/usr/bin/env python3
"""
Quick MCP integration test without pytest.
Tests the actual application flow.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_mcp_basic_integration():
    """Test basic MCP integration without starting servers."""
    print("=" * 60)
    print("MCP Integration Test")
    print("=" * 60)
    print()

    # Test 1: Configuration loading
    print("[1/5] Testing configuration loading...")
    try:
        from generalAgent.tools.mcp import load_mcp_config, MCPServerManager

        # Create test config
        test_config = {
            "servers": {
                "test_server": {
                    "command": sys.executable,
                    "args": ["test.py"],
                    "enabled": True,
                    "tools": {
                        "test_tool": {
                            "enabled": True,
                            "alias": "my_tool",
                            "description": "Test tool"
                        }
                    }
                }
            },
            "settings": {
                "lazy_start": True,
                "namespace_strategy": "alias"
            }
        }

        manager = MCPServerManager(test_config)
        print(f"   ✓ Config loaded")
        print(f"   ✓ Configured servers: {manager.list_configured_servers()}")
        print()
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 2: Tool loading
    print("[2/5] Testing tool loading...")
    try:
        from generalAgent.tools.mcp import load_mcp_tools

        tools = load_mcp_tools(test_config, manager)
        print(f"   ✓ Loaded {len(tools)} tools")
        for tool in tools:
            print(f"   ✓ Tool: {tool.name}")
        print()
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 3: ToolRegistry integration
    print("[3/5] Testing ToolRegistry integration...")
    try:
        from generalAgent.tools import ToolRegistry

        registry = ToolRegistry()
        for tool in tools:
            registry.register_tool(tool)
            registry.register_discovered(tool)

        all_tools = registry.list_tools()
        print(f"   ✓ Registered {len(all_tools)} tools in registry")

        # Get tool by name
        test_tool = registry.get_tool("my_tool")
        print(f"   ✓ Retrieved tool: {test_tool.name}")

        # Check if discovered
        is_discovered = registry.is_discovered("my_tool")
        print(f"   ✓ Tool discoverable: {is_discovered}")
        print()
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 4: Application building (without starting servers)
    print("[4/5] Testing application building...")
    try:
        from generalAgent.runtime import build_application

        app, initial_state, skill_registry, tool_registry = \
            await build_application(mcp_tools=tools)

        print(f"   ✓ Application built")
        print(f"   ✓ Total tools in registry: {len(tool_registry.list_tools())}")

        # Check if MCP tool is registered
        has_mcp_tool = tool_registry.is_discovered("my_tool")
        print(f"   ✓ MCP tool registered: {has_mcp_tool}")
        print()
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5: Cleanup
    print("[5/5] Testing cleanup...")
    try:
        await manager.shutdown()
        print(f"   ✓ Manager shut down")
        print(f"   ✓ Started servers: {len(manager.list_started_servers())}")
        print()
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    return True


async def main():
    print()
    success = await test_mcp_basic_integration()

    print("=" * 60)
    if success:
        print("✅ All tests passed!")
        print()
        print("MCP integration is working correctly.")
        print("You can now:")
        print("  1. Configure MCP servers in generalAgent/config/mcp_servers.yaml")
        print("  2. Run: python main.py")
        print("  3. Use MCP tools in your agent")
    else:
        print("❌ Some tests failed")
        print("Check the error messages above for details.")
    print("=" * 60)
    print()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
