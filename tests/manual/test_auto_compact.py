"""
手动测试自动压缩功能

测试步骤：
1. 创建一个包含大量消息的 state (模拟 token 达到 96%)
2. 调用 agent 触发自动压缩
3. 验证压缩是否自动执行
4. 验证 state 是否正确更新

运行方式：
    python tests/manual/test_auto_compact.py
"""

import asyncio
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from generalAgent.runtime.app import build_application
from generalAgent.config.settings import get_settings


async def test_auto_compression():
    """测试自动压缩功能"""
    print("=" * 80)
    print("测试自动压缩功能")
    print("=" * 80)

    # 1. 构建应用
    print("\n[1/5] 构建应用...")
    app, initial_state_factory, skill_registry, tool_registry, skill_config = await build_application()

    # 2. 创建初始 state
    print("[2/5] 创建初始 state...")
    state = initial_state_factory()

    # 添加大量消息以模拟高 token 使用
    messages = [SystemMessage(content="You are a helpful assistant.")]
    for i in range(150):
        messages.append(HumanMessage(content=f"User question {i}: " + "x" * 200))  # 每条消息约 200 tokens
        messages.append(AIMessage(content=f"AI response {i}: " + "y" * 200))

    state["messages"] = messages
    state["cumulative_prompt_tokens"] = 123000  # 96% of 128k (critical threshold)
    state["cumulative_completion_tokens"] = 5000
    state["compact_count"] = 0
    state["auto_compressed_this_request"] = False

    print(f"   - 初始消息数: {len(state['messages'])}")
    print(f"   - 累积 prompt tokens: {state['cumulative_prompt_tokens']:,}")
    print(f"   - Token 使用率: {state['cumulative_prompt_tokens'] / 128000:.1%}")

    # 3. 添加一条新的用户消息
    print("[3/5] 添加用户消息触发 planner...")
    state["messages"].append(HumanMessage(content="请总结一下我们的对话"))

    # 4. 执行一次 agent 循环（应该触发自动压缩）
    print("[4/5] 执行 agent (应该触发自动压缩)...")
    try:
        # 执行到 planner 节点完成
        config = {"configurable": {"thread_id": "test_auto_compact"}}
        result = None
        step_count = 0

        async for event in app.astream(state, config, stream_mode="values"):
            result = event
            step_count += 1
            cumul = event.get('cumulative_prompt_tokens', 0)
            print(f"   - Step {step_count}: messages={len(event.get('messages', []))}, "
                  f"auto_compressed={event.get('auto_compressed_this_request', False)}, "
                  f"cumulative_tokens={cumul}")

            # 执行至少 4 步，确保 summarization + agent 运行
            if step_count >= 4:
                break

        # 5. 验证结果
        print("[5/5] 验证结果...")
        print(f"\n自动压缩结果:")
        print(f"   - auto_compressed_this_request: {result.get('auto_compressed_this_request', False)}")
        print(f"   - compact_count: {result.get('compact_count', 0)}")
        print(f"   - 压缩前消息数: {len(state['messages'])}")
        print(f"   - 压缩后消息数: {len(result.get('messages', []))}")
        print(f"   - cumulative_prompt_tokens: {result.get('cumulative_prompt_tokens', 0)}")

        # 断言：检查 compact_count 是否增加（表示压缩已执行）
        initial_compact_count = state.get("compact_count", 0)
        final_compact_count = result.get("compact_count", 0)

        if final_compact_count > initial_compact_count:
            print("\n✅ 自动压缩已触发！")
            print(f"✅ 消息从 {len(state['messages'])} 条压缩到 {len(result['messages'])} 条")
            print(f"✅ compact_count 已更新: {initial_compact_count} → {final_compact_count}")

            # Token应该被重置或大幅减少
            final_tokens = result.get('cumulative_prompt_tokens', 0)
            if final_tokens < state['cumulative_prompt_tokens'] * 0.5:
                print(f"✅ Token 已减少: {state['cumulative_prompt_tokens']:,} → {final_tokens:,}")
            else:
                print(f"⚠️ Token 减少不明显: {state['cumulative_prompt_tokens']:,} → {final_tokens:,}")

            return True
        else:
            print("\n❌ 自动压缩未触发")
            print(f"   可能原因:")
            print(f"   1. Token 使用率未达到 critical 阈值 (95%)")
            print(f"   2. Context management 未启用")
            print(f"   3. 压缩过程中发生错误")
            print(f"   compact_count: {initial_compact_count} → {final_compact_count} (未变化)")
            return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_no_auto_compression_below_threshold():
    """测试在阈值以下不触发自动压缩"""
    print("\n" + "=" * 80)
    print("测试低于阈值时不自动压缩")
    print("=" * 80)

    # 构建应用
    print("\n[1/4] 构建应用...")
    app, initial_state_factory, _, _, _ = await build_application()

    # 创建 state with 80% token usage (below critical)
    print("[2/4] 创建 state (80% token usage)...")
    state = initial_state_factory()
    messages = [SystemMessage(content="You are a helpful assistant.")]
    for i in range(50):
        messages.append(HumanMessage(content=f"Question {i}"))
        messages.append(AIMessage(content=f"Response {i}"))

    state["messages"] = messages
    state["cumulative_prompt_tokens"] = 102000  # 80% of 128k
    state["compact_count"] = 0
    state["auto_compressed_this_request"] = False

    print(f"   - Token 使用率: {state['cumulative_prompt_tokens'] / 128000:.1%}")

    # 添加消息
    print("[3/4] 添加用户消息...")
    state["messages"].append(HumanMessage(content="Hello"))

    # 执行
    print("[4/4] 执行 agent (不应触发自动压缩)...")
    try:
        config = {"configurable": {"thread_id": "test_no_auto_compact"}}
        result = None
        step_count = 0

        async for event in app.astream(state, config, stream_mode="values"):
            result = event
            step_count += 1
            # 执行至少 2 步
            if step_count >= 2:
                break

        # 验证
        if not result.get("auto_compressed_this_request", False):
            print("\n✅ 正确：未触发自动压缩 (token 使用低于 95%)")
            return True
        else:
            print("\n❌ 错误：不应该触发自动压缩")
            return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("自动压缩功能测试套件")
    print("=" * 80)

    results = []

    # Test 1: 自动压缩触发
    result1 = await test_auto_compression()
    results.append(("自动压缩触发测试", result1))

    # Test 2: 低于阈值不触发
    result2 = await test_no_auto_compression_below_threshold()
    results.append(("低于阈值测试", result2))

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(r for _, r in results)
    print("\n" + ("=" * 80))
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("❌ 部分测试失败")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
