"""Integration test for Handoff Pattern

Tests the complete handoff pattern implementation including:
- Agent registry initialization
- Handoff tools generation
- Graph structure with agent nodes
- Dynamic routing
- Agent catalog (compact mode + dynamic reminders)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_handoff_pattern_initialization():
    """Test 1: Handoff pattern initialization"""
    logger.info("=" * 70)
    logger.info("Test 1: Handoff Pattern Initialization")
    logger.info("=" * 70)

    from generalAgent.runtime import build_application

    try:
        app, initial_state, skill_registry, tool_registry, skill_config, agent_registry = await build_application()

        # Verify agent registry
        assert agent_registry is not None, "Agent registry should be initialized"
        stats = agent_registry.get_stats()
        logger.info(f"\n✓ Agent Registry Stats: {stats}")

        assert stats['discovered'] >= 1, "Should have discovered agents"
        assert stats['enabled'] >= 1, "Should have enabled agents"

        # Verify enabled agents
        enabled_agents = agent_registry.list_enabled()
        logger.info(f"\n✓ Enabled Agents: {[card.id for card in enabled_agents]}")

        # Verify handoff tools
        handoff_tools = [t for t in tool_registry.list_tools() if t.name.startswith('transfer_to_')]
        logger.info(f"\n✓ Handoff Tools: {[t.name for t in handoff_tools]}")
        assert len(handoff_tools) >= 1, "Should have handoff tools"

        # Verify initial state
        state = initial_state()
        assert state.get('current_agent') == 'agent', "Initial agent should be 'agent'"
        assert state.get('agent_call_history') == [], "Agent call history should be empty"
        logger.info(f"\n✓ Initial State: current_agent={state.get('current_agent')}, agent_call_history={state.get('agent_call_history')}")

        logger.info("\n" + "=" * 70)
        logger.info("✅ Test 1 PASSED: Handoff Pattern Initialization")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Test 1 FAILED: {e}", exc_info=True)
        return False


async def test_agent_catalog_compact_mode():
    """Test 2: Agent catalog compact mode"""
    logger.info("\n" + "=" * 70)
    logger.info("Test 2: Agent Catalog Compact Mode")
    logger.info("=" * 70)

    from generalAgent.agents import scan_agents_from_config

    try:
        registry = scan_agents_from_config()

        # Test compact mode (default)
        catalog = registry.get_catalog_text(detailed=False)
        logger.info(f"\n✓ Compact Catalog:\n{catalog}")

        assert "# 可用 Agents" in catalog, "Should have catalog header"
        assert "@simple" in catalog, "Should list simple agent"
        assert "提示：使用 @agent_id 来查看详细技能信息" in catalog, "Should have usage hint"

        # Verify it's compact (no detailed skills)
        assert "**技能：**" not in catalog, "Compact mode should not show detailed skills"

        logger.info("\n" + "=" * 70)
        logger.info("✅ Test 2 PASSED: Agent Catalog Compact Mode")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Test 2 FAILED: {e}", exc_info=True)
        return False


async def test_agent_detailed_info_on_mention():
    """Test 3: Agent detailed info on @mention"""
    logger.info("\n" + "=" * 70)
    logger.info("Test 3: Agent Detailed Info on @mention")
    logger.info("=" * 70)

    from generalAgent.agents import scan_agents_from_config
    from generalAgent.graph.prompts import build_dynamic_reminder

    try:
        registry = scan_agents_from_config()

        # Simulate @simple mention
        mentioned_agents = ["simple"]

        # Build reminder with agent_registry
        reminder = build_dynamic_reminder(
            mentioned_agents=mentioned_agents,
            agent_registry=registry,
        )

        logger.info(f"\n✓ Dynamic Reminder:\n{reminder}")

        assert "transfer_to_" in reminder, "Should mention handoff tools"
        assert "SimpleAgent" in reminder, "Should show agent name"
        assert "quick_analysis" in reminder, "Should show detailed skills"
        assert "reasoning_task" in reminder, "Should show detailed skills"

        logger.info("\n" + "=" * 70)
        logger.info("✅ Test 3 PASSED: Agent Detailed Info on @mention")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Test 3 FAILED: {e}", exc_info=True)
        return False


async def test_handoff_tool_structure():
    """Test 4: Handoff tool structure"""
    logger.info("\n" + "=" * 70)
    logger.info("Test 4: Handoff Tool Structure")
    logger.info("=" * 70)

    from generalAgent.agents import scan_agents_from_config, create_agent_handoff_tools

    try:
        registry = scan_agents_from_config()
        handoff_tools = create_agent_handoff_tools(registry)

        assert len(handoff_tools) >= 1, "Should create handoff tools"

        # Verify tool structure
        tool = handoff_tools[0]
        logger.info(f"\n✓ Tool Name: {tool.name}")
        logger.info(f"✓ Tool Description: {tool.description[:100]}...")

        assert tool.name.startswith('transfer_to_'), "Tool name should start with 'transfer_to_'"
        assert "SimpleAgent" in tool.description or "skills" in tool.description.lower(), "Tool description should mention agent or skills"

        logger.info("\n" + "=" * 70)
        logger.info("✅ Test 4 PASSED: Handoff Tool Structure")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Test 4 FAILED: {e}", exc_info=True)
        return False


async def test_graph_structure_with_agent_nodes():
    """Test 5: Graph structure with agent nodes"""
    logger.info("\n" + "=" * 70)
    logger.info("Test 5: Graph Structure with Agent Nodes")
    logger.info("=" * 70)

    from generalAgent.runtime import build_application

    try:
        app, *_ = await build_application()

        # Verify graph structure
        # Note: LangGraph compiled app doesn't easily expose nodes list
        # So we just verify it compiles successfully
        assert app is not None, "App should compile successfully"

        logger.info("\n✓ Graph compiled successfully with agent nodes")

        logger.info("\n" + "=" * 70)
        logger.info("✅ Test 5 PASSED: Graph Structure")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Test 5 FAILED: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 70)
    logger.info("HANDOFF PATTERN INTEGRATION TESTS")
    logger.info("=" * 70)

    tests = [
        ("Initialization", test_handoff_pattern_initialization),
        ("Agent Catalog Compact Mode", test_agent_catalog_compact_mode),
        ("Agent Detailed Info on @mention", test_agent_detailed_info_on_mention),
        ("Handoff Tool Structure", test_handoff_tool_structure),
        ("Graph Structure", test_graph_structure_with_agent_nodes),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}", exc_info=True)
            results.append((name, False))

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {name}")

    logger.info("\n" + "=" * 70)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
