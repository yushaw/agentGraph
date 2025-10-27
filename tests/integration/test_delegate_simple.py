"""Simple test to verify delegate_task initialization."""

import asyncio
from generalAgent.runtime import build_application
from langchain_core.messages import HumanMessage


async def test_delegate_init():
    print("Building application...")
    app, initial_state_factory, skill_registry, tool_registry, _ = await build_application()

    print("Creating initial state...")
    state = initial_state_factory()

    # Add a simple message that should trigger delegate_task
    state["messages"] = [
        HumanMessage(content="使用 delegate_task 帮我测试一下")
    ]

    # Mention agent to trigger delegate loading
    state["mentioned_agents"] = ["agent"]

    print("Running graph...")
    config = {"configurable": {"thread_id": "test-123"}}

    try:
        async for state_snapshot in app.astream(state, config=config, stream_mode="values"):
            messages = state_snapshot.get("messages", [])
            if messages:
                last_msg = messages[-1]
                print(f"[{last_msg.__class__.__name__}] {getattr(last_msg, 'content', '')[:200]}")

        print("\n✅ Test completed successfully")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_delegate_init())
