"""Quick integration test for Agent Registry system

This test verifies that the Agent Registry system is properly integrated.
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_agent_registry_integration():
    """Test that Agent Registry is properly integrated"""
    logger.info("=" * 60)
    logger.info("Testing Agent Registry Integration")
    logger.info("=" * 60)

    # Test 1: Import all components
    logger.info("\n[Test 1] Importing components...")
    try:
        from generalAgent.agents import AgentRegistry, AgentCard, AgentSkill, scan_agents_from_config
        from generalAgent.tools.builtin.call_agent import call_agent, set_agent_registry
        logger.info("  ✓ All imports successful")
    except ImportError as e:
        logger.error(f"  ✗ Import failed: {e}")
        return False

    # Test 2: Load agents from config
    logger.info("\n[Test 2] Loading agents from config...")
    try:
        agent_registry = scan_agents_from_config()
        stats = agent_registry.get_stats()
        logger.info(f"  ✓ Agent Registry loaded successfully")
        logger.info(f"    - Discovered: {stats['discovered']}")
        logger.info(f"    - Enabled: {stats['enabled']}")
        logger.info(f"    - Available to subagent: {stats['available_to_subagent']}")
    except Exception as e:
        logger.error(f"  ✗ Failed to load agent registry: {e}")
        return False

    # Test 3: Verify enabled agents
    logger.info("\n[Test 3] Verifying enabled agents...")
    enabled_agents = agent_registry.list_enabled()
    if not enabled_agents:
        logger.warning("  ⚠ No agents enabled")
    else:
        for card in enabled_agents:
            logger.info(f"  ✓ Agent: {card.id} ({card.name})")
            logger.info(f"    - Skills: {len(card.skills)}")
            logger.info(f"    - Capabilities: {[c.name for c in card.capabilities]}")
            logger.info(f"    - Tags: {card.tags}")

    # Test 4: Query agents by skill
    logger.info("\n[Test 4] Testing query by skill...")
    try:
        results = agent_registry.query_by_skill("quick_analysis")
        logger.info(f"  ✓ Query for 'quick_analysis': {len(results)} agent(s) found")
        for card in results:
            logger.info(f"    - {card.id}: {card.name}")
    except Exception as e:
        logger.error(f"  ✗ Query failed: {e}")
        return False

    # Test 5: Query agents by tag
    logger.info("\n[Test 5] Testing query by tag...")
    try:
        results = agent_registry.query_by_tags(["lightweight"])
        logger.info(f"  ✓ Query for tag 'lightweight': {len(results)} agent(s) found")
        for card in results:
            logger.info(f"    - {card.id}: {card.name}")
    except Exception as e:
        logger.error(f"  ✗ Query failed: {e}")
        return False

    # Test 6: Generate Agent Catalog
    logger.info("\n[Test 6] Generating Agent Catalog...")
    try:
        catalog = agent_registry.get_catalog_text()
        if catalog:
            logger.info("  ✓ Agent Catalog generated successfully")
            logger.info("  Preview:")
            for line in catalog.split("\n")[:10]:
                logger.info(f"    {line}")
            if len(catalog.split("\n")) > 10:
                logger.info(f"    ... ({len(catalog.split('\n')) - 10} more lines)")
        else:
            logger.warning("  ⚠ Catalog is empty")
    except Exception as e:
        logger.error(f"  ✗ Catalog generation failed: {e}")
        return False

    # Test 7: Test call_agent tool import
    logger.info("\n[Test 7] Testing call_agent tool...")
    try:
        set_agent_registry(agent_registry)
        logger.info("  ✓ Agent Registry injected into call_agent tool")
        logger.info(f"  ✓ call_agent tool: {call_agent.name}")
        logger.info(f"  ✓ Description: {call_agent.description[:100]}...")
    except Exception as e:
        logger.error(f"  ✗ call_agent test failed: {e}")
        return False

    # Test 8: Verify Agent Card structure
    logger.info("\n[Test 8] Verifying Agent Card structure...")
    try:
        simple_card = agent_registry.get("simple")
        if simple_card:
            logger.info("  ✓ SimpleAgent card found")
            logger.info(f"    - Provider: {simple_card.provider.value}")
            logger.info(f"    - Version: {simple_card.version}")
            logger.info(f"    - Factory: {simple_card.factory is not None}")
            logger.info(f"    - Skills: {[s.name for s in simple_card.skills]}")

            # Verify skill structure
            if simple_card.skills:
                first_skill = simple_card.skills[0]
                logger.info(f"    - First skill details:")
                logger.info(f"      * Name: {first_skill.name}")
                logger.info(f"      * Input mode: {first_skill.input_mode.value}")
                logger.info(f"      * Output mode: {first_skill.output_mode.value}")
                logger.info(f"      * Examples: {len(first_skill.examples)}")
        else:
            logger.warning("  ⚠ SimpleAgent not found")
    except Exception as e:
        logger.error(f"  ✗ Agent Card verification failed: {e}")
        return False

    logger.info("\n" + "=" * 60)
    logger.info("✅ All tests passed!")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_agent_registry_integration())
    exit(0 if success else 1)
