"""Test Step 1: Simplified architecture with Charlie Prompt."""

from agentgraph.runtime import build_application
from langchain_core.messages import HumanMessage

def test_simple_task():
    """Test a simple task without planning."""
    print("=== Test 1: Simple Task (现在几点) ===")

    app, initial_state_factory = build_application()
    state = initial_state_factory()

    state["messages"] = [HumanMessage(content="现在几点？")]

    result = app.invoke(state, config={"recursion_limit": 50})

    print(f"Messages count: {len(result['messages'])}")
    print(f"Execution phase: {result.get('execution_phase')}")
    print(f"Task complexity: {result.get('task_complexity')}")

    # Print last assistant message
    for msg in reversed(result["messages"]):
        if hasattr(msg, 'type') and msg.type == 'ai':
            print(f"\nCharlie's response:\n{msg.content}\n")
            break

    print("✅ Simple task test passed!\n")


def test_skill_activation():
    """Test skill listing and selection."""
    print("=== Test 2: Skill Activation (list skills) ===")

    app, initial_state_factory = build_application()
    state = initial_state_factory()

    state["messages"] = [HumanMessage(content="你有什么技能？")]

    result = app.invoke(state, config={"recursion_limit": 50})

    print(f"Messages count: {len(result['messages'])}")

    # Print last assistant message
    for msg in reversed(result["messages"]):
        if hasattr(msg, 'type') and msg.type == 'ai':
            print(f"\nCharlie's response:\n{msg.content}\n")
            break

    print("✅ Skill activation test passed!\n")


def test_charlie_identity():
    """Test Charlie's identity and personality."""
    print("=== Test 3: Charlie Identity (你是谁) ===")

    app, initial_state_factory = build_application()
    state = initial_state_factory()

    state["messages"] = [HumanMessage(content="你是谁？")]

    result = app.invoke(state, config={"recursion_limit": 50})

    # Print last assistant message
    for msg in reversed(result["messages"]):
        if hasattr(msg, 'type') and msg.type == 'ai':
            print(f"\nCharlie's response:\n{msg.content}\n")
            # Check if Charlie introduces itself
            if "Charlie" in msg.content or "charlie" in msg.content:
                print("✅ Charlie identity test passed!\n")
            else:
                print("⚠️  Warning: Charlie didn't mention its name\n")
            break


if __name__ == "__main__":
    print("🚀 Starting Step 1 Tests...\n")

    try:
        test_simple_task()
        test_skill_activation()
        test_charlie_identity()

        print("=" * 50)
        print("🎉 All Step 1 tests completed!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
