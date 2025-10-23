"""Simple CLI for multi-turn conversations with the agent."""

from __future__ import annotations

from typing import Any, Iterable, List, Set

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from agentgraph.runtime import build_application


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


def main():
    app, initial_state_factory = build_application()
    state = initial_state_factory()
    print("AgentGraph CLI 已就绪。输入内容开始对话，输入 /quit 退出，/reset 重置状态。")
    printed_tool_ids: Set[str] = set()

    while True:
        try:
            user_input = input("You> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in {"/quit", "/exit"}:
            print("会话结束。")
            break
        if user_input.lower() == "/reset":
            state = initial_state_factory()
            printed_tool_ids.clear()
            print("状态已重置。")
            continue

        messages: List[BaseMessage] = list(state.get("messages", []))
        messages.append(HumanMessage(content=user_input))
        state["messages"] = messages
        start_index = len(messages)
        state = app.invoke(state, config={"recursion_limit": 50})
        _print_new_messages(state.get("messages", []), start_index, printed_tool_ids)


if __name__ == "__main__":
    main()
