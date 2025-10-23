"""Test multi-turn conversation with complex task demo."""

from agentgraph.runtime import build_application
from langchain_core.messages import HumanMessage

print("=== 多轮对话测试 ===\n")

app, initial_state_factory = build_application()
state = initial_state_factory()

# Turn 1
print("Turn 1: 你好")
state["messages"] = [HumanMessage(content="你好")]
state = app.invoke(state, config={"recursion_limit": 50})
print(f"  Messages: {len(state['messages'])}\n")

# Turn 2
print("Turn 2: 你能做什么")
state["messages"].append(HumanMessage(content="你能做什么"))
state = app.invoke(state, config={"recursion_limit": 50})
print(f"  Messages: {len(state['messages'])}\n")

# Turn 3 - Complex task demo
print("Turn 3: 演示一个复杂任务看看")
state["messages"].append(HumanMessage(content="演示一个复杂任务看看"))

try:
    state = app.invoke(state, config={"recursion_limit": 50})
    print(f"  Messages: {len(state['messages'])}")
    print(f"  Plan created: {state.get('plan') is not None}")
    print(f"  Execution phase: {state.get('execution_phase')}")
    print(f"  Task complexity: {state.get('task_complexity')}")
    print("\n✅ 测试成功!")
except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
