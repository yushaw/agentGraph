"""Test script for the refactored AgentGraph architecture."""

from agentgraph.runtime import build_application
from langchain_core.messages import HumanMessage

print("=== 测试 AgentGraph 重构版本 ===\n")

# 构建应用
print("1. 构建应用...")
app, initial_state_factory = build_application()
state = initial_state_factory()
print("   ✓ 应用已构建")
print(f"   - 可用工具数: {len(state.get('allowed_tools', []))}")
print(f"   - 初始消息数: {len(state.get('messages', []))}\n")

# 测试1: 简单计算任务
print("2. 测试简单任务: 'What is 2+2?'")
state = initial_state_factory()
state["messages"] = [HumanMessage(content="What is 2+2?")]

try:
    result = app.invoke(state)
    print(f"   ✓ 执行完成")
    print(f"   - Messages count: {len(result['messages'])}")
    print(f"   - execution_phase: {result.get('execution_phase', 'not set')}")
    print(f"   - task_complexity: {result.get('task_complexity', 'not set')}")
    print(f"   - plan created: {result.get('plan') is not None}")
    print(f"   - step_idx: {result.get('step_idx', 0)}")

    # 打印最后几条消息
    print("\n   最后的消息:")
    for i, msg in enumerate(result['messages'][-5:], 1):
        msg_type = getattr(msg, 'type', 'unknown')
        content = str(getattr(msg, 'content', ''))
        if len(content) > 100:
            content = content[:100] + "..."
        print(f"   {i}. [{msg_type}] {content}")

except Exception as e:
    print(f"   ✗ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)

# 测试2: 复杂任务（需要create_plan）
print("\n3. 测试复杂任务: '先列出可用技能，然后选择一个'")
state = initial_state_factory()
state["messages"] = [HumanMessage(content="先列出可用的技能，然后帮我选择pptx技能")]

try:
    result = app.invoke(state)
    print(f"   ✓ 执行完成")
    print(f"   - Messages count: {len(result['messages'])}")
    print(f"   - execution_phase: {result.get('execution_phase', 'not set')}")
    print(f"   - task_complexity: {result.get('task_complexity', 'not set')}")
    print(f"   - plan created: {result.get('plan') is not None}")

    if result.get('plan'):
        plan = result['plan']
        print(f"   - plan steps: {len(plan.get('steps', []))}")
        for i, step in enumerate(plan.get('steps', []), 1):
            print(f"     Step {i}: {step.get('id')} - {step.get('description', 'N/A')[:50]}")

    print(f"   - active_skill: {result.get('active_skill', 'None')}")
    print(f"   - evidence collected: {len(result.get('evidence', []))}")

except Exception as e:
    print(f"   ✗ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")
