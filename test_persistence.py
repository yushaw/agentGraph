"""Test script to verify session persistence with SQLite."""

import asyncio
import uuid
from langchain_core.messages import HumanMessage

from agentgraph.runtime import build_application


async def test_session_persistence():
    """Test that sessions are saved and can be restored."""
    print("=" * 60)
    print("Testing Session Persistence")
    print("=" * 60)

    app, initial_state_factory = build_application()

    # === Test 1: Create a session and save messages ===
    print("\n[Test 1] Creating a new session...")
    session_id = str(uuid.uuid4())
    state = initial_state_factory()
    state["thread_id"] = session_id

    config = {
        "recursion_limit": 50,
        "configurable": {"thread_id": session_id}
    }

    # Add first message
    print(f"Session ID: {session_id[:16]}...")
    state["messages"] = [HumanMessage(content="你好，我叫张三")]

    async for state_snapshot in app.astream(state, config=config, stream_mode="values"):
        state = state_snapshot

    print(f"✅ 第一条消息已保存 ({len(state['messages'])} 条消息)")

    # Add second message
    state["messages"].append(HumanMessage(content="1+1等于多少？"))

    async for state_snapshot in app.astream(state, config=config, stream_mode="values"):
        state = state_snapshot

    print(f"✅ 第二条消息已保存 ({len(state['messages'])} 条消息)")

    # === Test 2: Load the session and continue ===
    print("\n[Test 2] 加载已保存的会话...")

    # Create a new state and load from checkpointer
    checkpointer = getattr(app, 'checkpointer', None)
    if not checkpointer:
        print("❌ Checkpointer 未启用")
        return

    # Get the saved state
    checkpoint_tuple = checkpointer.get_tuple(config)
    if checkpoint_tuple is None:
        print("❌ 未找到已保存的会话")
        return

    loaded_state = checkpoint_tuple.checkpoint.get("channel_values", {})
    print(f"✅ 成功加载会话 (共 {len(loaded_state['messages'])} 条消息)")

    # Verify messages
    print("\n加载的消息:")
    for i, msg in enumerate(loaded_state["messages"][-4:], 1):
        if hasattr(msg, 'type'):
            content = getattr(msg, 'content', '')
            if msg.type == 'human':
                print(f"  {i}. [User] {content[:50]}...")
            elif msg.type == 'ai':
                print(f"  {i}. [AI] {content[:50]}...")

    # === Test 3: Continue the conversation ===
    print("\n[Test 3] 继续对话...")

    loaded_state["messages"].append(HumanMessage(content="谢谢！"))

    async for state_snapshot in app.astream(loaded_state, config=config, stream_mode="values"):
        loaded_state = state_snapshot

    print(f"✅ 对话继续成功 (现在共 {len(loaded_state['messages'])} 条消息)")

    # === Test 4: List all sessions ===
    print("\n[Test 4] 列出所有会话...")

    session_count = 0
    for state_obj in checkpointer.list({}):
        thread_id = state_obj.config.get("configurable", {}).get("thread_id")
        if thread_id:
            msg_count = len(state_obj.checkpoint.get("channel_values", {}).get("messages", []))
            print(f"  - {thread_id[:16]}... ({msg_count} 条消息)")
            session_count += 1

    print(f"✅ 找到 {session_count} 个会话")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_session_persistence())
