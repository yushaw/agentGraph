"""Test extended @mention mechanism (tool, skill, agent)."""

from pathlib import Path
from generalAgent.tools.registry import ToolRegistry
from generalAgent.tools.scanner import scan_multiple_directories
from generalAgent.tools.config_loader import load_tool_config
from generalAgent.skills import SkillRegistry
from generalAgent.utils.mention_classifier import classify_mentions, group_by_type


def test_mention_classification():
    """Test classification of different @mention types."""

    print("\n=== Testing @Mention Classification ===\n")

    # Setup registries
    tool_config = load_tool_config()
    tool_registry = ToolRegistry()

    # Scan and register tools
    scan_dirs = tool_config.get_scan_directories()
    discovered_tools = scan_multiple_directories(scan_dirs)

    for tool_name, tool_instance in discovered_tools.items():
        tool_registry.register_discovered(tool_instance)

    enabled_tools = tool_config.get_all_enabled_tools()
    for tool_name, tool_instance in discovered_tools.items():
        if tool_name in enabled_tools:
            tool_registry.register_tool(tool_instance)

    # Setup skill registry
    skills_root = Path("skills")
    skill_registry = SkillRegistry(skills_root)

    print(f"✓ Tool registry ready: {len(discovered_tools)} tools discovered")
    print(f"✓ Skill registry ready: {len(skill_registry.list_meta())} skills loaded\n")

    # Test cases
    test_cases = [
        # Case 1: @tool (enabled)
        {
            "input": ["calc"],
            "expected_type": {"tools": ["calc"], "skills": [], "agents": [], "unknown": []},
        },
        # Case 2: @tool (disabled but discoverable)
        {
            "input": ["extract_links"],
            "expected_type": {"tools": ["extract_links"], "skills": [], "agents": [], "unknown": []},
        },
        # Case 3: @skill
        {
            "input": ["pdf"],
            "expected_type": {"tools": [], "skills": ["pdf"], "agents": [], "unknown": []},
        },
        # Case 4: @agent
        {
            "input": ["agent"],
            "expected_type": {"tools": [], "skills": [], "agents": ["agent"], "unknown": []},
        },
        # Case 5: Mixed @tool + @skill + @agent
        {
            "input": ["calc", "pdf", "agent"],
            "expected_type": {"tools": ["calc"], "skills": ["pdf"], "agents": ["agent"], "unknown": []},
        },
        # Case 6: Unknown mention
        {
            "input": ["unknown_thing"],
            "expected_type": {"tools": [], "skills": [], "agents": [], "unknown": ["unknown_thing"]},
        },
    ]

    print("Testing classification:\n")
    all_passed = True

    for i, case in enumerate(test_cases, 1):
        mentions = case["input"]
        expected = case["expected_type"]

        classifications = classify_mentions(mentions, tool_registry, skill_registry)
        result = group_by_type(classifications)

        passed = result == expected
        status = "✅" if passed else "❌"

        print(f"{status} Case {i}: @{', @'.join(mentions)}")
        print(f"   Result: {result}")

        if not passed:
            print(f"   Expected: {expected}")
            all_passed = False

        print()

    if all_passed:
        print("✅ All classification tests passed!")
    else:
        print("❌ Some tests failed")

    return all_passed


def test_mention_reminders():
    """Test that different mention types generate appropriate reminders."""

    from generalAgent.graph.prompts import build_dynamic_reminder

    print("\n=== Testing @Mention Reminders ===\n")

    test_cases = [
        {
            "name": "@tool mention",
            "kwargs": {"mentioned_tools": ["calc", "now"]},
            "should_contain": ["工具", "calc", "now"],
        },
        {
            "name": "@skill mention",
            "kwargs": {"mentioned_skills": ["pdf", "pptx"]},
            "should_contain": ["技能", "pdf", "pptx", "Read", "SKILL.md"],
        },
        {
            "name": "@agent mention",
            "kwargs": {"mentioned_agents": ["agent"]},
            "should_contain": ["代理", "agent", "call_subagent"],
        },
        {
            "name": "Mixed mentions",
            "kwargs": {
                "mentioned_tools": ["calc"],
                "mentioned_skills": ["pdf"],
                "mentioned_agents": ["agent"],
            },
            "should_contain": ["工具", "calc", "技能", "pdf", "代理", "agent"],
        },
    ]

    all_passed = True

    for case in test_cases:
        reminder = build_dynamic_reminder(**case["kwargs"])

        passed = all(keyword in reminder for keyword in case["should_contain"])
        status = "✅" if passed else "❌"

        print(f"{status} {case['name']}")
        print(f"   Generated reminder preview:")
        print(f"   {reminder[:200]}..." if len(reminder) > 200 else f"   {reminder}")

        if not passed:
            missing = [kw for kw in case["should_contain"] if kw not in reminder]
            print(f"   ❌ Missing keywords: {missing}")
            all_passed = False

        print()

    if all_passed:
        print("✅ All reminder tests passed!")
    else:
        print("❌ Some tests failed")

    return all_passed


if __name__ == "__main__":
    print("="*60)
    print("Testing Extended @Mention Mechanism")
    print("="*60)

    # Test 1: Classification
    result1 = test_mention_classification()

    print("\n" + "="*60 + "\n")

    # Test 2: Reminders
    result2 = test_mention_reminders()

    print("\n" + "="*60)
    if result1 and result2:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("="*60)
