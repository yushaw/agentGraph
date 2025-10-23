"""Test simple session persistence with SessionStore."""

from agentgraph.persistence.session_store import SessionStore
from langchain_core.messages import HumanMessage, AIMessage


def test_session_store():
    """Test basic save/load functionality."""
    print("=" * 60)
    print("测试简单会话持久化")
    print("=" * 60)

    # Initialize store
    store = SessionStore("test_sessions.db")

    # Create a test session
    test_id = "test-session-123"
    state = {
        "thread_id": test_id,
        "messages": [
            HumanMessage(content="你好"),
            AIMessage(content="你好！有什么可以帮你的吗？"),
            HumanMessage(content="1+1等于多少？"),
            AIMessage(content="1+1等于2"),
        ],
        "execution_phase": "initial",
        "loops": 0,
    }

    # Test 1: Save session
    print(f"\n[Test 1] 保存会话 {test_id[:16]}...")
    store.save(test_id, state)
    print("✅ 会话已保存")

    # Test 2: Load session
    print(f"\n[Test 2] 加载会话 {test_id[:16]}...")
    loaded = store.load(test_id)

    if loaded:
        print(f"✅ 会话加载成功")
        print(f"   - 消息数: {len(loaded['messages'])}")
        print(f"   - 执行阶段: {loaded['execution_phase']}")

        # Verify messages
        print("\n   加载的消息:")
        for i, msg in enumerate(loaded["messages"], 1):
            if isinstance(msg, HumanMessage):
                print(f"     {i}. [User] {msg.content}")
            elif isinstance(msg, AIMessage):
                print(f"     {i}. [AI] {msg.content}")
    else:
        print("❌ 加载失败")
        return

    # Test 3: List sessions
    print("\n[Test 3] 列出所有会话...")
    sessions = store.list_sessions()
    print(f"✅ 找到 {len(sessions)} 个会话:")
    for tid, created, updated, msg_count in sessions[:3]:
        print(f"   - {tid[:16]}... | {msg_count} 条消息 | {updated[:16]}")

    # Test 4: Update session
    print("\n[Test 4] 更新会话（添加新消息）...")
    state["messages"].append(HumanMessage(content="谢谢！"))
    state["messages"].append(AIMessage(content="不客气！"))
    store.save(test_id, state)

    reloaded = store.load(test_id)
    if reloaded and len(reloaded["messages"]) == 6:
        print(f"✅ 会话更新成功 (现在有 {len(reloaded['messages'])} 条消息)")
    else:
        print("❌ 更新失败")

    # Test 5: Delete session
    print(f"\n[Test 5] 删除会话 {test_id[:16]}...")
    store.delete(test_id)

    deleted_check = store.load(test_id)
    if deleted_check is None:
        print("✅ 会话已删除")
    else:
        print("❌ 删除失败")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)

    # Cleanup
    import os
    if os.path.exists("test_sessions.db"):
        os.remove("test_sessions.db")
        print("\n清理：删除测试数据库")


if __name__ == "__main__":
    test_session_store()
