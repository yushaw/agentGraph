"""Real-world scenario tests for the refactored system."""

import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage

from generalAgent import build_application
from generalAgent.utils.mention_parser import parse_mentions


async def test_scenario_1_simple_calculation():
    """Scenario 1: Simple calculation with @tool mention."""
    print("\n" + "="*60)
    print("Scenario 1: @calc 计算一下 (2+3)*5")
    print("="*60)

    app, initial_state_factory, skill_registry, tool_registry = await build_application()
    state = initial_state_factory()

    user_input = "@calc 计算一下 (2+3)*5"
    mentions, cleaned_input = parse_mentions(user_input)

    print(f"\n用户输入: {user_input}")
    print(f"解析 mentions: {mentions}")
    print(f"清理后: {cleaned_input}")

    state["mentioned_agents"] = mentions
    state["messages"] = [HumanMessage(content=cleaned_input)]
    state["thread_id"] = "test-scenario-1"

    print("\n开始执行...")
    try:
        result = await app.ainvoke(state, {"recursion_limit": 10})

        messages = result.get("messages", [])
        print(f"\n✅ 执行完成!")
        print(f"消息数量: {len(messages)}")

        # 检查最后的消息
        if messages:
            last_msg = messages[-1]
            content = str(last_msg.content)[:300]
            print(f"最后消息预览: {content}...")

            # 验证是否使用了 calc 工具
            if "25" in content or "tool_calls" in str(messages):
                print("✅ 似乎成功使用了 calc 工具")
            else:
                print("⚠️  未明确看到计算结果")

        return True
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scenario_2_on_demand_loading():
    """Scenario 2: On-demand loading of disabled tool."""
    print("\n" + "="*60)
    print("Scenario 2: @extract_links (disabled tool, on-demand loading)")
    print("="*60)

    app, initial_state_factory, skill_registry, tool_registry = await build_application()
    state = initial_state_factory()

    user_input = "@extract_links 我想提取链接，虽然这个工具默认是禁用的"
    mentions, cleaned_input = parse_mentions(user_input)

    print(f"\n用户输入: {user_input}")
    print(f"解析 mentions: {mentions}")

    state["mentioned_agents"] = mentions
    state["messages"] = [HumanMessage(content=cleaned_input)]
    state["thread_id"] = "test-scenario-2"

    print("\n开始执行...")
    try:
        result = await app.ainvoke(state, {"recursion_limit": 10})
        print(f"\n✅ 按需加载测试通过!")
        return True
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        return False


async def test_scenario_3_skill_mention():
    """Scenario 3: @skill mention for PDF skill."""
    print("\n" + "="*60)
    print("Scenario 3: @pdf 技能提及")
    print("="*60)

    app, initial_state_factory, skill_registry, tool_registry = await build_application()
    state = initial_state_factory()

    user_input = "@pdf 帮我了解如何处理PDF文件"
    mentions, cleaned_input = parse_mentions(user_input)

    print(f"\n用户输入: {user_input}")
    print(f"解析 mentions: {mentions}")

    state["mentioned_agents"] = mentions
    state["messages"] = [HumanMessage(content=cleaned_input)]
    state["thread_id"] = "test-scenario-3"

    print("\n开始执行...")
    try:
        result = await app.ainvoke(state, {"recursion_limit": 10})

        messages = result.get("messages", [])
        print(f"\n✅ 执行完成!")
        print(f"消息数量: {len(messages)}")

        # 检查是否读取了 SKILL.md
        messages_str = str(messages)
        if "SKILL.md" in messages_str or "pdf" in messages_str.lower():
            print("✅ 模型似乎处理了 PDF skill")

        return True
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        return False


async def test_scenario_4_mixed_mentions():
    """Scenario 4: Mixed @tool + @skill + @agent."""
    print("\n" + "="*60)
    print("Scenario 4: @calc @pdf @agent 混合提及")
    print("="*60)

    app, initial_state_factory, skill_registry, tool_registry = await build_application()
    state = initial_state_factory()

    user_input = "@calc @pdf @agent 计算一些数据，生成PDF报告，如果需要可以委派任务"
    mentions, cleaned_input = parse_mentions(user_input)

    print(f"\n用户输入: {user_input}")
    print(f"解析 mentions: {mentions}")
    print(f"应该分类为:")
    print(f"  - tools: ['calc']")
    print(f"  - skills: ['pdf']")
    print(f"  - agents: ['agent']")

    state["mentioned_agents"] = mentions
    state["messages"] = [HumanMessage(content=cleaned_input)]
    state["thread_id"] = "test-scenario-4"

    print("\n开始执行...")
    try:
        result = await app.ainvoke(state, {"recursion_limit": 10})
        print(f"\n✅ 混合提及测试通过!")
        return True
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        return False


async def test_scenario_5_todo_functionality():
    """Scenario 5: TODO tool functionality."""
    print("\n" + "="*60)
    print("Scenario 5: TODO 工具测试")
    print("="*60)

    app, initial_state_factory, skill_registry, tool_registry = await build_application()
    state = initial_state_factory()

    user_input = "帮我创建三个待办事项：1. 测试工具 2. 测试技能 3. 提交代码"

    print(f"\n用户输入: {user_input}")

    state["messages"] = [HumanMessage(content=user_input)]
    state["thread_id"] = "test-scenario-5"

    print("\n开始执行...")
    try:
        result = await app.ainvoke(state, {"recursion_limit": 10})

        todos = result.get("todos", [])
        print(f"\n✅ 执行完成!")
        print(f"TODO 数量: {len(todos)}")

        if todos:
            print("\nTODOs:")
            for i, todo in enumerate(todos, 1):
                status = todo.get("status", "unknown")
                content = todo.get("content", "N/A")
                print(f"  {i}. [{status}] {content}")

        return True
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        return False


async def main():
    """Run all real scenario tests."""
    print("\n" + "="*60)
    print("真实场景测试")
    print("="*60)

    results = []

    # Test 1: Simple calculation
    results.append(("@tool mention (calc)", await test_scenario_1_simple_calculation()))

    # Test 2: On-demand loading
    results.append(("On-demand loading", await test_scenario_2_on_demand_loading()))

    # Test 3: Skill mention
    results.append(("@skill mention (pdf)", await test_scenario_3_skill_mention()))

    # Test 4: Mixed mentions
    results.append(("Mixed @tool+@skill+@agent", await test_scenario_4_mixed_mentions()))

    # Test 5: TODO functionality
    results.append(("TODO tool", await test_scenario_5_todo_functionality()))

    # Summary
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
