"""End-to-end scenario tests."""

import pytest
import asyncio
from pathlib import Path


@pytest.mark.asyncio
@pytest.mark.slow
async def test_complete_agent_workflow(test_mcp_config, test_server_path):
    """
    Test complete agent workflow with MCP tools.

    This simulates a real agent session:
    1. Initialize MCP infrastructure
    2. Build application with MCP tools
    3. Simulate agent tool calls
    4. Verify results
    5. Cleanup
    """
    from generalAgent.runtime import build_application
    from generalAgent.tools.mcp import MCPServerManager, load_mcp_tools

    print("\n=== Starting E2E Agent Workflow Test ===")

    # Step 1: Initialize MCP
    print("\n[1/6] Initializing MCP infrastructure...")
    manager = MCPServerManager(test_mcp_config)
    mcp_tools = load_mcp_tools(test_mcp_config, manager)
    print(f"      ✓ Loaded {len(mcp_tools)} MCP tools")
    print(f"      ✓ Tools: {[t.name for t in mcp_tools]}")

    # Step 2: Build application
    print("\n[2/6] Building application with MCP tools...")
    app, initial_state, skill_registry, tool_registry = await build_application(
        mcp_tools=mcp_tools
    )
    print(f"      ✓ Application built")
    print(f"      ✓ Total tools in registry: {len(tool_registry.list_tools())}")

    # Step 3: Verify lazy startup (server not started yet)
    print("\n[3/6] Verifying lazy startup...")
    assert not manager.is_server_started("test_stdio")
    print("      ✓ Server not started yet (lazy mode)")

    # Step 4: Simulate agent tool calls
    print("\n[4/6] Simulating agent tool calls...")

    # Call 1: Echo (triggers server startup)
    print("      → Calling mcp_echo (should trigger server startup)...")
    echo_tool = tool_registry.get_tool("mcp_echo")
    result1 = await echo_tool._arun(message="Hello from agent!")
    print(f"      ✓ Result: {result1}")
    assert "Echo: Hello from agent!" in result1
    assert manager.is_server_started("test_stdio")
    print("      ✓ Server started on first call")

    # Call 2: Add (reuse connection)
    print("      → Calling mcp_add...")
    add_tool = tool_registry.get_tool("mcp_add")
    result2 = await add_tool._arun(a=42, b=58)
    print(f"      ✓ Result: {result2}")
    assert "42 + 58 = 100" in result2

    # Call 3: Get time
    print("      → Calling mcp_time...")
    time_tool = tool_registry.get_tool("mcp_time")
    result3 = await time_tool._arun()
    print(f"      ✓ Result: {result3}")
    assert "Current time:" in result3

    # Step 5: Test concurrent calls
    print("\n[5/6] Testing concurrent tool calls...")
    tasks = [
        echo_tool._arun(message=f"Concurrent {i}")
        for i in range(3)
    ]
    concurrent_results = await asyncio.gather(*tasks)
    print(f"      ✓ Completed {len(concurrent_results)} concurrent calls")
    for i, result in enumerate(concurrent_results):
        assert f"Concurrent {i}" in result

    # Step 6: Cleanup
    print("\n[6/6] Cleaning up...")
    await manager.shutdown()
    assert not manager.is_server_started("test_stdio")
    print("      ✓ All servers shut down")

    print("\n=== E2E Test Completed Successfully ===\n")


@pytest.mark.asyncio
async def test_agent_session_lifecycle(test_mcp_config):
    """Test full agent session lifecycle with MCP."""
    from generalAgent.runtime import build_application
    from generalAgent.tools.mcp import MCPServerManager, load_mcp_tools
    from shared.session.store import SessionStore
    from shared.workspace.manager import WorkspaceManager

    print("\n=== Starting Session Lifecycle Test ===")

    # Initialize MCP
    manager = MCPServerManager(test_mcp_config)
    mcp_tools = load_mcp_tools(test_mcp_config, manager)

    # Build application
    app, initial_state_factory, skill_registry, tool_registry = await build_application(
        mcp_tools=mcp_tools
    )

    # Create session infrastructure (simplified)
    session_id = "test-session-001"
    state = initial_state_factory()
    state["thread_id"] = session_id

    print(f"      ✓ Session created: {session_id}")

    # Simulate agent turns
    print("\n      Simulating agent turns...")

    # Turn 1: Use MCP tool
    echo_tool = tool_registry.get_tool("mcp_echo")
    result = await echo_tool._arun(message="Turn 1")
    print(f"      Turn 1: {result}")

    # Turn 2: Use different MCP tool
    add_tool = tool_registry.get_tool("mcp_add")
    result = await add_tool._arun(a=10, b=20)
    print(f"      Turn 2: {result}")

    # End session
    await manager.shutdown()
    print("      ✓ Session ended, resources cleaned up")

    print("\n=== Session Lifecycle Test Completed ===\n")


@pytest.mark.asyncio
async def test_mcp_tool_discovery(test_mcp_config):
    """Test MCP tool discovery and registration."""
    from generalAgent.tools.mcp import MCPServerManager, load_mcp_tools

    print("\n=== Starting Tool Discovery Test ===")

    # Initialize
    manager = MCPServerManager(test_mcp_config)
    mcp_tools = load_mcp_tools(test_mcp_config, manager)

    print(f"\n      Discovered {len(mcp_tools)} tools:")
    for tool in mcp_tools:
        print(f"      - {tool.name}: {tool.description}")
        print(f"        Server: {tool.server_id}")
        print(f"        Original name: {tool.original_tool_name}")
        print(f"        Always available: {tool.always_available}")

    # Verify tool properties
    assert len(mcp_tools) == 3

    # Check each tool
    echo = next(t for t in mcp_tools if t.name == "mcp_echo")
    assert echo.server_id == "test_stdio"
    assert echo.original_tool_name == "echo"
    assert not echo.always_available

    add = next(t for t in mcp_tools if t.name == "mcp_add")
    assert add.server_id == "test_stdio"
    assert add.original_tool_name == "add"
    assert not add.always_available

    time = next(t for t in mcp_tools if t.name == "mcp_time")
    assert time.server_id == "test_stdio"
    assert time.original_tool_name == "get_time"
    assert time.always_available  # Configured as always_available

    print("\n      ✓ All tools verified")
    print("\n=== Tool Discovery Test Completed ===\n")


@pytest.mark.asyncio
async def test_mcp_error_scenarios(test_mcp_config, mcp_manager):
    """Test various error scenarios."""
    from generalAgent.tools.mcp import load_mcp_tools

    print("\n=== Starting Error Scenarios Test ===")

    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Scenario 1: Missing required argument
    print("\n      Scenario 1: Missing required argument")
    result = await echo_tool._arun()
    print(f"      Result: {result}")
    assert "error" in result.lower() or "failed" in result.lower()

    # Scenario 2: Server can recover after error
    print("\n      Scenario 2: Recovery after error")
    result = await echo_tool._arun(message="Recovery test")
    print(f"      Result: {result}")
    assert "Echo: Recovery test" in result

    # Scenario 3: Invalid server access
    print("\n      Scenario 3: Invalid server access")
    try:
        await mcp_manager.get_server("nonexistent_server")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"      Expected error: {e}")
        assert "not configured" in str(e)

    print("\n      ✓ All error scenarios handled correctly")
    print("\n=== Error Scenarios Test Completed ===\n")


@pytest.mark.asyncio
async def test_performance_metrics(test_mcp_config, mcp_manager):
    """Test performance characteristics."""
    import time
    from generalAgent.tools.mcp import load_mcp_tools

    print("\n=== Starting Performance Test ===")

    mcp_tools = load_mcp_tools(test_mcp_config, mcp_manager)
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Measure lazy startup time
    print("\n      Measuring lazy startup...")
    start = time.time()
    result = await echo_tool._arun(message="Startup test")
    startup_time = time.time() - start
    print(f"      First call (with startup): {startup_time:.3f}s")
    assert "Echo: Startup test" in result

    # Measure subsequent call time (no startup)
    print("\n      Measuring subsequent call...")
    start = time.time()
    result = await echo_tool._arun(message="Fast test")
    fast_time = time.time() - start
    print(f"      Subsequent call: {fast_time:.3f}s")
    assert "Echo: Fast test" in result

    # Subsequent calls should be faster
    print(f"\n      Speedup: {startup_time / fast_time:.1f}x")
    assert fast_time < startup_time

    print("\n      ✓ Performance metrics collected")
    print("\n=== Performance Test Completed ===\n")
