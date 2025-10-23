"""Detailed test to see the full message flow."""

from agentgraph.runtime import build_application
from langchain_core.messages import HumanMessage
import json

print("=== 详细测试: 查看完整消息流 ===\n")

app, initial_state_factory = build_application()

# 测试: 显式要求创建计划
print("测试: '请创建一个计划: 先查北京天气，然后生成天气报告'\n")
state = initial_state_factory()
state["messages"] = [HumanMessage(content="请创建一个计划: 先查北京天气，然后生成一份天气报告PPT")]

try:
    result = app.invoke(state)

    print(f"执行结果:")
    print(f"  - 总消息数: {len(result['messages'])}")
    print(f"  - execution_phase: {result.get('execution_phase', 'N/A')}")
    print(f"  - task_complexity: {result.get('task_complexity', 'N/A')}")
    print(f"  - plan exists: {result.get('plan') is not None}")

    if result.get('plan'):
        plan = result['plan']
        print(f"\n创建的计划:")
        print(f"  总步骤数: {len(plan.get('steps', []))}")
        for i, step in enumerate(plan.get('steps', []), 1):
            print(f"\n  步骤 {i}:")
            print(f"    - id: {step.get('id')}")
            print(f"    - description: {step.get('description')}")
            print(f"    - agent: {step.get('agent', 'N/A')}")
            print(f"    - deliverables: {step.get('deliverables', [])}")

    print(f"\n所有消息:")
    for i, msg in enumerate(result['messages'], 1):
        msg_type = getattr(msg, 'type', 'unknown')

        # 获取内容
        content = getattr(msg, 'content', '')

        # 检查是否有tool_calls
        tool_calls = getattr(msg, 'tool_calls', None)

        print(f"\n  消息 {i} [{msg_type}]:")

        if tool_calls:
            print(f"    Tool Calls: {len(tool_calls)}")
            for tc in tool_calls[:3]:  # 只显示前3个
                name = tc.get('name') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown')
                args = tc.get('args') if isinstance(tc, dict) else getattr(tc, 'args', {})
                print(f"      - {name}({list(args.keys()) if isinstance(args, dict) else 'N/A'})")

        # 显示内容
        if isinstance(content, str):
            if len(content) > 200:
                print(f"    Content: {content[:200]}...")
            else:
                print(f"    Content: {content}")
        else:
            print(f"    Content type: {type(content)}")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
