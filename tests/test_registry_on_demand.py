"""Test ToolRegistry on-demand loading functionality."""

from pathlib import Path
from generalAgent.tools.registry import ToolRegistry
from generalAgent.tools.scanner import scan_multiple_directories
from generalAgent.tools.config_loader import load_tool_config


def test_registry_on_demand():
    """Test that discovered tools can be loaded on-demand."""

    print("\n=== Testing ToolRegistry On-Demand Loading ===\n")

    # Create registry
    registry = ToolRegistry()

    # Load configuration
    tool_config = load_tool_config()

    # Scan for tools
    scan_dirs = tool_config.get_scan_directories()
    discovered_tools = scan_multiple_directories(scan_dirs)
    print(f"✓ Discovered {len(discovered_tools)} tools")
    print(f"  Tools: {sorted(discovered_tools.keys())}\n")

    # Register all as discovered
    for tool_name, tool_instance in discovered_tools.items():
        registry.register_discovered(tool_instance)
    print(f"✓ Registered {len(discovered_tools)} tools as discovered\n")

    # Get enabled tools
    enabled_tools = tool_config.get_all_enabled_tools()
    print(f"✓ Enabled tools from config: {sorted(enabled_tools)}\n")

    # Register only enabled tools as immediately available
    for tool_name, tool_instance in discovered_tools.items():
        if tool_name in enabled_tools:
            registry.register_tool(tool_instance)

    # Now test on-demand loading
    print("=" * 60)
    print("Testing on-demand loading scenarios:\n")

    # Scenario 1: Tool already registered (enabled)
    print("1. Tool already enabled (calc):")
    try:
        tool = registry.get_tool("calc")
        print(f"   ✓ get_tool('calc') → {tool.name}")
    except KeyError as e:
        print(f"   ✗ {e}")

    try:
        tool = registry.load_on_demand("calc")
        print(f"   ✓ load_on_demand('calc') → {tool.name} (returns existing)")
    except KeyError as e:
        print(f"   ✗ {e}")

    print()

    # Scenario 2: Tool discovered but not enabled
    # Find a tool that's discovered but not enabled
    disabled_tool = None
    for tool_name in discovered_tools:
        if tool_name not in enabled_tools:
            disabled_tool = tool_name
            break

    if disabled_tool:
        print(f"2. Tool discovered but not enabled ({disabled_tool}):")
        try:
            tool = registry.get_tool(disabled_tool)
            print(f"   ✗ Unexpected: get_tool('{disabled_tool}') should have failed")
        except KeyError:
            print(f"   ✓ get_tool('{disabled_tool}') → KeyError (expected)")

        try:
            tool = registry.load_on_demand(disabled_tool)
            print(f"   ✓ load_on_demand('{disabled_tool}') → {tool.name} (loaded!)")

            # Verify it's now registered
            tool2 = registry.get_tool(disabled_tool)
            print(f"   ✓ get_tool('{disabled_tool}') → {tool2.name} (now available)")
        except KeyError as e:
            print(f"   ✗ {e}")
    else:
        print("2. No disabled tools found to test\n")

    print()

    # Scenario 3: Tool not discovered at all
    print("3. Tool not discovered (fake_tool):")
    try:
        tool = registry.load_on_demand("fake_tool")
        print(f"   ✗ Unexpected: should have raised KeyError")
    except KeyError as e:
        print(f"   ✓ load_on_demand('fake_tool') → KeyError (expected)")
        print(f"      Error: {e}")

    print("\n" + "=" * 60)
    print("✅ All registry on-demand loading tests passed!")


if __name__ == "__main__":
    test_registry_on_demand()
