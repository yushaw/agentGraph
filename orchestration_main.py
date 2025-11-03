#!/usr/bin/env python3
"""OrchestrationAgent - Main entry point.

Usage:
    python orchestration_main.py
    # Or from orchestrationAgent directory:
    cd orchestrationAgent && python main.py

The Orchestration Agent is a "manager" agent that:
- Decomposes complex tasks into sub-tasks
- Delegates to Worker Agents (GeneralAgent)
- Monitors progress and reports results
- Does NOT execute concrete work (file ops, network, etc.)

See orchestrationAgent/README.md for detailed documentation.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path for imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from generalAgent.config.settings import get_settings
from generalAgent.utils.logging_utils import setup_logging
from orchestrationAgent.runtime.app import build_orchestration_app
from shared.cli.base_cli import BaseCLI
from shared.session.manager import SessionManager


class OrchestrationCLI(BaseCLI):
    """CLI for OrchestrationAgent (Host).

    Reuses BaseCLI infrastructure from shared/cli/base_cli.py.
    """

    async def handle_user_message(self, user_input: str):
        """Handle user message by streaming through the Host graph.

        Args:
            user_input: User input text
        """
        # Add user message to state
        from langchain_core.messages import HumanMessage

        current_state = await self.app.aget_state(self.config)
        messages = list(current_state.values.get("messages", []))
        messages.append(HumanMessage(content=user_input))

        # Update state
        input_state = {"messages": messages}

        # Stream execution
        async for state_snapshot in self.app.astream(
            input_state,
            config=self.config,
            stream_mode="values"
        ):
            # Print new messages
            current_messages = state_snapshot.get("messages", [])
            for msg in current_messages[len(messages):]:
                if hasattr(msg, "content") and msg.content:
                    msg_type = getattr(msg, "type", msg.__class__.__name__)
                    if msg_type in {"ai", "AIMessage"}:
                        print(f"\n{msg.content}")
                    elif msg_type in {"tool", "ToolMessage"}:
                        # Only print tool results for user-facing tools
                        tool_name = getattr(msg, "name", "tool")
                        if tool_name in ["done_and_report", "ask_human"]:
                            print(f"\n[{tool_name}] {msg.content[:200]}...")

            messages = current_messages

        # Handle interrupts (ask_human)
        await self._handle_interrupts()

    async def _handle_interrupts(self):
        """Handle graph interrupts (ask_human tool)."""
        while True:
            graph_state = await self.app.aget_state(self.config)

            if (graph_state.next and graph_state.tasks and
                hasattr(graph_state.tasks[0], 'interrupts') and
                graph_state.tasks[0].interrupts):

                interrupt_value = graph_state.tasks[0].interrupts[0].value
                interrupt_type = interrupt_value.get("type", "generic")

                if interrupt_type == "user_input_request":
                    # Handle ask_human request
                    question = interrupt_value.get("question", "")
                    context_info = interrupt_value.get("context", "")
                    default = interrupt_value.get("default")

                    print()
                    if context_info:
                        print(f"💡 {context_info}")
                    print(f"💬 {question}")
                    if default:
                        print(f"   (默认: {default})")

                    # Get user input
                    loop = asyncio.get_event_loop()
                    answer = await loop.run_in_executor(None, lambda: input("> ").strip())

                    if not answer and default:
                        answer = default
                        print(f"✓ 使用默认值: {default}")

                    # Resume with answer
                    from langgraph.types import Command
                    async for state_snapshot in self.app.astream(
                        Command(resume=answer),
                        config=self.config,
                        stream_mode="values"
                    ):
                        current_messages = state_snapshot.get("messages", [])
                        for msg in current_messages:
                            if hasattr(msg, "content") and msg.content:
                                msg_type = getattr(msg, "type", msg.__class__.__name__)
                                if msg_type in {"ai", "AIMessage"}:
                                    print(f"\n{msg.content}")
                else:
                    print(f"⚠️  Unknown interrupt type: {interrupt_type}")
                    break
            else:
                # No more interrupts
                break


async def main():
    """Main entry point for OrchestrationAgent CLI."""
    # Setup logging
    settings = get_settings()
    setup_logging(settings.observability)

    print("=" * 60)
    print("OrchestrationAgent - Task Decomposition & Delegation Manager")
    print("=" * 60)
    print()
    print("你好！我是 Orchestration Agent（编排代理）。")
    print("我的职责是拆解复杂任务并委派给 Worker Agent 执行。")
    print()
    print("可用命令：")
    print("  /quit, /exit  - 退出程序")
    print("  /reset        - 重置当前会话")
    print("  /sessions     - 列出所有会话")
    print("  /load <id>    - 加载指定会话")
    print("  /current      - 显示当前会话信息")
    print()

    # Build application (async)
    app, initial_state_factory, model_registry, tool_registry = await build_orchestration_app()

    print("应用构建成功！")
    print(f"工具列表: {sorted(list(tool_registry._tools.keys()))}")
    print()
    print("暂时使用简化模式（无会话持久化）")
    print("输入你的任务，或输入 /quit 退出：")
    print()

    # Simple REPL loop (without session management for now)
    import uuid
    from langchain_core.messages import HumanMessage

    thread_id = str(uuid.uuid4())

    # Configure with higher recursion limit for complex delegated tasks
    # Use max_loops * 3 to account for: planner + tools + summarization nodes
    max_loops = settings.governance.max_loops
    recursion_limit = max_loops * 3
    config = {
        "recursion_limit": recursion_limit,
        "configurable": {"thread_id": thread_id}
    }

    # Create initial state
    initial_state = initial_state_factory(thread_id=thread_id, user_id="default")

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input in ["/quit", "/exit"]:
                print("\n再见！")
                break

            # Add user message
            initial_state["messages"].append(HumanMessage(content=user_input))

            # Run graph
            async for state_snapshot in app.astream(
                initial_state,
                config=config,
                stream_mode="values"
            ):
                # Print new messages
                messages = state_snapshot.get("messages", [])
                for msg in messages[len(initial_state["messages"]):]:
                    if hasattr(msg, "content") and msg.content:
                        msg_type = getattr(msg, "type", msg.__class__.__name__)
                        if msg_type in {"ai", "AIMessage"}:
                            print(f"\nHost> {msg.content}\n")

                initial_state = state_snapshot

        except KeyboardInterrupt:
            print("\n\n使用 /quit 退出")
            continue
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n再见！")
        sys.exit(0)
