"""Test script to verify streaming and async functionality."""

import asyncio
from langchain_core.messages import HumanMessage

from agentgraph.runtime import build_application


async def test_simple_query():
    """Test a simple query with streaming."""
    print("=" * 60)
    print("Testing streaming with simple query")
    print("=" * 60)

    app, initial_state_factory = build_application()
    state = initial_state_factory()

    # Generate thread_id
    import uuid
    thread_id = str(uuid.uuid4())
    state["thread_id"] = thread_id
    print(f"Session ID: {thread_id[:8]}...\n")

    # Add a simple user message
    state["messages"] = [HumanMessage(content="1+1等于多少？")]

    config = {
        "recursion_limit": 50,
        "configurable": {
            "thread_id": thread_id
        }
    }

    print("User> 1+1等于多少？\n")
    print("Agent> ", end="", flush=True)

    # Stream responses
    msg_count = 0
    async for state_snapshot in app.astream(state, config=config, stream_mode="values"):
        current_messages = state_snapshot.get("messages", [])

        # Print new messages
        for idx in range(msg_count, len(current_messages)):
            msg = current_messages[idx]
            if hasattr(msg, 'type') and msg.type == 'ai' and msg.content:
                print(msg.content, end="", flush=True)
            elif hasattr(msg, 'name'):  # Tool message
                print(f"\n[Tool: {msg.name}]", flush=True)

        msg_count = len(current_messages)

    print("\n")
    print("=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_simple_query())
