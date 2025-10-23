"""Simple CLI for multi-turn conversations with the agent."""

from __future__ import annotations

import asyncio
from typing import Any, Iterable, List, Optional, Set

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from agentgraph.runtime import build_application
from agentgraph.utils import get_logger, log_user_message, log_agent_response, log_error, parse_mentions
from agentgraph.persistence.session_store import SessionStore


def _stringify_content(content: Any) -> str:
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                pieces.append(str(item["text"]))
            else:
                pieces.append(str(item))
        return "\n".join(pieces)
    return str(content)


def _role_and_text(message: Any) -> tuple[str, str]:
    if isinstance(message, SystemMessage):
        return "system", _stringify_content(message.content)
    if isinstance(message, HumanMessage):
        return "user", _stringify_content(message.content)
    if isinstance(message, AIMessage):
        return "assistant", _stringify_content(message.content)
    if isinstance(message, ToolMessage):
        return "tool", _stringify_content(message.content)
    if isinstance(message, BaseMessage):
        return message.type, _stringify_content(message.content)
    if isinstance(message, tuple) and len(message) >= 2:
        return str(message[0]), _stringify_content(message[1])
    if hasattr(message, "type"):
        role = getattr(message, "type")
        content = getattr(message, "content", "")
        return str(role), _stringify_content(content)
    if isinstance(message, dict):
        role = message.get("role") or message.get("type") or "unknown"
        return str(role), _stringify_content(message.get("content", ""))
    return "unknown", _stringify_content(message)


def _print_new_messages(messages: Iterable[Any], start_index: int, seen_tools: Set[str]) -> None:
    message_list = list(messages)
    for message in message_list[start_index:]:
        role, text = _role_and_text(message)
        if not text:
            continue
        if role in {"assistant", "ai"}:
            print(f"Agent> {text}")
        elif role == "tool":
            tool_id = getattr(message, "id", None)
            if tool_id and tool_id in seen_tools:
                continue
            if tool_id:
                seen_tools.add(tool_id)
            print(f"[tool] {text}")
        elif role == "system":
            print(f"[system] {text}")


async def async_main():
    # Initialize logger and session store
    logger = get_logger()
    session_store = SessionStore()

    try:
        app, initial_state_factory = build_application()
        state = initial_state_factory()

        # Generate thread_id for this session
        import uuid
        thread_id = str(uuid.uuid4())
        state["thread_id"] = thread_id

        print("AgentGraph CLI 已就绪。")
        print(f"会话 ID: {thread_id[:8]}...")
        print(f"日志文件: {logger.handlers[0].baseFilename if logger.handlers else 'N/A'}")
        print("\n命令列表:")
        print("  /quit, /exit    - 退出程序")
        print("  /reset          - 重置当前会话")
        print("  /sessions       - 列出所有已保存的会话")
        print("  /load <id>      - 加载指定会话（使用会话ID前几位）")
        print("  /current        - 显示当前会话信息")
        print()

        logger.info(f"New session started with thread_id: {thread_id}")

        printed_tool_ids: Set[str] = set()

        while True:
            try:
                # Use run_in_executor to avoid blocking the async loop
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(None, lambda: input("You> ").strip())
            except (KeyboardInterrupt, EOFError):
                print("\n再见！")
                logger.info("Session ended by user")
                break

            if not user_input:
                continue

            if user_input.lower() in {"/quit", "/exit"}:
                print("会话结束。")
                logger.info("Session ended by /quit command")
                break

            if user_input.lower() == "/reset":
                state = initial_state_factory()
                # Generate new thread_id for reset session
                thread_id = str(uuid.uuid4())
                state["thread_id"] = thread_id
                printed_tool_ids.clear()
                print(f"状态已重置。新会话 ID: {thread_id[:8]}...")
                logger.info(f"State reset with new thread_id: {thread_id}")
                continue

            if user_input.lower() == "/sessions":
                sessions = session_store.list_sessions()
                if not sessions:
                    print("没有找到已保存的会话。")
                else:
                    print(f"\n找到 {len(sessions)} 个已保存的会话:\n")
                    for i, (tid, created_at, updated_at, msg_count) in enumerate(sessions, 1):
                        print(f"{i}. ID: {tid[:16]}... | 消息数: {msg_count} | 更新时间: {updated_at[:16]}")
                    print()
                continue

            if user_input.lower().startswith("/load "):
                session_prefix = user_input[6:].strip()
                if not session_prefix:
                    print("请提供会话ID前缀，例如: /load abc123")
                    continue

                # Find matching session
                sessions = session_store.list_sessions()
                matching = [s for s in sessions if s[0].startswith(session_prefix)]

                if not matching:
                    print(f"未找到以 '{session_prefix}' 开头的会话。")
                    continue

                if len(matching) > 1:
                    print(f"找到 {len(matching)} 个匹配的会话，请提供更长的ID前缀:")
                    for tid, _, _, msg_count in matching[:5]:
                        print(f"  - {tid[:16]}... ({msg_count} 条消息)")
                    continue

                # Load the session
                target_thread_id = matching[0][0]
                loaded_state = session_store.load(target_thread_id)

                if loaded_state:
                    state = loaded_state
                    thread_id = target_thread_id
                    printed_tool_ids.clear()
                    msg_count = len(state.get("messages", []))
                    print(f"✅ 已加载会话 {thread_id[:16]}... (共 {msg_count} 条消息)")
                    logger.info(f"Loaded session {thread_id} with {msg_count} messages")

                    # Print last few messages to show context
                    if msg_count > 0:
                        print("\n最近的对话:")
                        recent_msgs = state.get("messages", [])[-3:]
                        for msg in recent_msgs:
                            role, text = _role_and_text(msg)
                            if role in {"user", "human"}:
                                print(f"You> {text[:100]}...")
                            elif role in {"assistant", "ai"}:
                                print(f"Agent> {text[:100]}...")
                        print()
                else:
                    print(f"❌ 无法加载会话 {target_thread_id[:16]}...")
                continue

            if user_input.lower() == "/current":
                msg_count = len(state.get("messages", []))
                phase = state.get("execution_phase", "unknown")
                complexity = state.get("task_complexity", "unknown")
                print(f"\n当前会话信息:")
                print(f"  ID: {thread_id}")
                print(f"  消息数: {msg_count}")
                print(f"  执行阶段: {phase}")
                print(f"  任务复杂度: {complexity}")
                if state.get("active_skill"):
                    print(f"  激活技能: {state['active_skill']}")
                if state.get("mentioned_agents"):
                    print(f"  提到的代理: {', '.join(state['mentioned_agents'])}")
                print()
                continue

            # Parse @mentions from user input
            mentions, cleaned_input = parse_mentions(user_input)

            if mentions:
                logger.info(f"Detected @mentions: {mentions}")
                print(f"[检测到 @{', @'.join(mentions)}]")

                # Update state with mentions
                existing_mentions = state.get("mentioned_agents", [])
                # Keep unique mentions
                all_mentions = list(set(existing_mentions + mentions))
                state["mentioned_agents"] = all_mentions

            # Log user input (original)
            log_user_message(logger, user_input)

            messages: List[BaseMessage] = list(state.get("messages", []))
            # Use cleaned input (without @mentions) for the message
            messages.append(HumanMessage(content=cleaned_input if mentions else user_input))
            state["messages"] = messages
            start_index = len(messages)

            try:
                # Use thread_id for session persistence (if checkpointer is enabled)
                config = {
                    "recursion_limit": 50,
                    "configurable": {
                        "thread_id": thread_id
                    }
                }

                # Stream responses for real-time output using "values" mode
                # This gives us the full state after each node execution
                last_printed_msg_count = start_index

                async for state_snapshot in app.astream(state, config=config, stream_mode="values"):
                    # state_snapshot is the full AppState after each node
                    current_messages = state_snapshot.get("messages", [])

                    # Print any new messages since last update
                    for idx in range(last_printed_msg_count, len(current_messages)):
                        msg = current_messages[idx]
                        role, text = _role_and_text(msg)

                        if not text:
                            continue

                        if role in {"assistant", "ai"}:
                            print(f"Agent> {text}")
                        elif role == "tool":
                            tool_id = getattr(msg, "id", None)
                            if tool_id and tool_id in printed_tool_ids:
                                continue
                            if tool_id:
                                printed_tool_ids.add(tool_id)
                            print(f"[tool] {text}")

                    last_printed_msg_count = len(current_messages)

                # Update state with the final snapshot
                state = state_snapshot

                # Log agent response
                for msg in state.get("messages", [])[start_index:]:
                    if isinstance(msg, (AIMessage, tuple)) and hasattr(msg, 'content'):
                        if isinstance(msg, AIMessage):
                            log_agent_response(logger, msg.content)
                        break

                # Save session after each turn
                try:
                    session_store.save(thread_id, state)
                    logger.info(f"Session {thread_id[:8]}... saved ({len(state.get('messages', []))} messages)")
                except Exception as e:
                    logger.warning(f"Failed to save session: {e}")

            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                log_error(logger, e, context="main loop - app.astream()")
                print("请查看日志文件获取详细信息\n")

    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        if 'logger' in locals():
            log_error(logger, e, context="async_main() initialization")
        else:
            import traceback
            traceback.print_exc()


def main():
    """Entry point that runs the async main function."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
