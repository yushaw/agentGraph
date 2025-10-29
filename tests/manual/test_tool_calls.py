"""
测试 tool calls 在移除 add_messages reducer 后是否正常工作
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage
from generalAgent.runtime.app import build_application


async def test_tool_calls():
    """测试 tool calls 正常工作"""
    print("=" * 80)
    print("测试 Tool Calls")
    print("=" * 80)

    # 构建应用
    print("\n[1/3] 构建应用...")
    app, initial_state_factory, _, _, _ = await build_application()

    # 创建 state
    print("[2/3] 创建 state...")
    state = initial_state_factory()
    state["messages"] = [HumanMessage(content="帮我创建一个待办任务：测试自动压缩")]

    # 执行
    print("[3/3] 执行 agent...")
    try:
        config = {"configurable": {"thread_id": "test_tool_calls"}}
        final_state = None
        step_count = 0
        max_steps = 5

        async for event in app.astream(state, config, stream_mode="values"):
            final_state = event
            step_count += 1
            messages = event.get("messages", [])
            print(f"  - Step {step_count}: {len(messages)} messages")

            if step_count >= max_steps:
                break

        # 验证
        if final_state:
            messages = final_state.get("messages", [])
            print(f"\n最终结果:")
            print(f"  - 总消息数: {len(messages)}")
            print(f"  - 最后一条消息类型: {type(messages[-1]).__name__}")
            print(f"  - 最后一条消息内容预览: {messages[-1].content[:100] if messages[-1].content else 'N/A'}")

            # 检查是否有 ToolMessage
            from langchain_core.messages import ToolMessage
            tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
            print(f"  - ToolMessage 数量: {len(tool_messages)}")

            if tool_messages:
                print("\n✅ Tool calls 正常工作!")
                return True
            else:
                print("\n❌ 没有 ToolMessage，可能有问题")
                return False
        else:
            print("\n❌ 未能获取最终 state")
            return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_tool_calls())
    sys.exit(0 if success else 1)
