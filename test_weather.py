"""Test weather query scenario."""

from agentgraph.runtime import build_application
from langchain_core.messages import HumanMessage

print("=== 测试: '北京的天气如何' ===\n")

app, initial_state_factory = build_application()
state = initial_state_factory()
state["messages"] = [HumanMessage(content="北京的天气如何")]

try:
    result = app.invoke(state, config={"recursion_limit": 50})

    print(f"执行结果:")
    print(f"  - 总消息数: {len(result['messages'])}")
    print(f"  - execution_phase: {result.get('execution_phase', 'N/A')}")
    print(f"  - task_complexity: {result.get('task_complexity', 'N/A')}")
    print(f"  - plan exists: {result.get('plan') is not None}")
    print(f"  - active_skill: {result.get('active_skill', 'None')}")
    print(f"  - allowed_tools: {result.get('allowed_tools', [])}")

    print(f"\n所有消息:")
    for i, msg in enumerate(result['messages'], 1):
        msg_type = getattr(msg, 'type', 'unknown')
        content = str(getattr(msg, 'content', ''))

        # 检查工具调用
        tool_calls = getattr(msg, 'tool_calls', None)

        if tool_calls:
            print(f"\n  {i}. [{msg_type}] - {len(tool_calls)} tool call(s):")
            for tc in tool_calls[:3]:
                name = tc.get('name') if isinstance(tc, dict) else getattr(tc, 'name', '?')
                print(f"      → {name}")
        elif hasattr(msg, 'name'):
            # ToolMessage
            print(f"\n  {i}. [{msg_type}] Tool: {msg.name}")
            if len(content) > 100:
                print(f"      Result: {content[:100]}...")
            else:
                print(f"      Result: {content}")
        else:
            if len(content) > 150:
                print(f"\n  {i}. [{msg_type}] {content[:150]}...")
            else:
                print(f"\n  {i}. [{msg_type}] {content}")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
