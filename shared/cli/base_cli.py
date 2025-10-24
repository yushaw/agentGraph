"""Base CLI framework for agent interfaces."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Callable, Optional

from shared.session.manager import SessionManager

LOGGER = logging.getLogger(__name__)


class BaseCLI(ABC):
    """Base CLI class handling common command-line interaction patterns.

    Provides:
    - Command routing (/quit, /help, /sessions, /load, /reset, /current)
    - Main input/output loop
    - Session management integration

    Subclasses implement:
    - Agent-specific welcome message
    - User message processing logic
    - Custom commands (optional)
    """

    # Base commands available to all agents
    BASE_COMMANDS: Dict[str, str] = {
        "/quit": "退出程序",
        "/exit": "退出程序",
        "/help": "显示帮助信息",
        "/sessions": "列出所有已保存的会话",
        "/load <id>": "加载指定会话（使用会话ID前几位）",
        "/reset": "重置当前会话",
        "/current": "显示当前会话信息",
    }

    def __init__(self, session_manager: SessionManager):
        """Initialize CLI.

        Args:
            session_manager: Session lifecycle manager
        """
        self.session_manager = session_manager
        self._command_handlers = self._build_command_handlers()
        self._running = False

        LOGGER.info(f"{self.__class__.__name__} initialized")

    def _build_command_handlers(self) -> Dict[str, Callable]:
        """Build command handler mapping.

        Subclasses can override to add custom commands.
        """
        return {
            "/quit": self._handle_quit,
            "/exit": self._handle_quit,
            "/help": self._handle_help,
            "/sessions": self._handle_sessions,
            "/load": self._handle_load,
            "/reset": self._handle_reset,
            "/current": self._handle_current,
        }

    @property
    def commands(self) -> Dict[str, str]:
        """Get available commands (for help display).

        Subclasses can override to add custom commands.
        """
        return self.BASE_COMMANDS

    # ========== Main Loop ==========

    async def run(self):
        """Main CLI loop.

        Handles:
        1. Welcome message
        2. Input loop
        3. Command routing
        4. User message processing
        5. Graceful shutdown
        """
        self._running = True
        self.print_welcome()

        while self._running:
            try:
                user_input = await self.get_input()

                if not user_input:
                    continue

                if self.is_command(user_input):
                    should_continue = await self.handle_command(user_input)
                    if not should_continue:
                        break
                else:
                    await self.handle_user_message(user_input)

            except (KeyboardInterrupt, EOFError):
                print("\n再见！")
                LOGGER.info("Session interrupted by user")
                break
            except Exception as e:
                LOGGER.error(f"Unexpected error in main loop: {e}", exc_info=True)
                print(f"❌ 发生错误: {e}")

        # Cleanup on exit
        await self.on_shutdown()

    async def on_shutdown(self):
        """Cleanup before shutdown.

        Subclasses can override to add custom cleanup logic.
        """
        LOGGER.info("CLI shutting down")

    # ========== Command Handling ==========

    def is_command(self, text: str) -> bool:
        """Check if input is a command."""
        return text.startswith("/")

    async def handle_command(self, cmd: str) -> bool:
        """Handle command input.

        Args:
            cmd: Command string (e.g., "/load abc123")

        Returns:
            True to continue main loop, False to exit
        """
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0].lower()
        cmd_arg = parts[1] if len(parts) > 1 else None

        handler = self._command_handlers.get(cmd_name)
        if handler:
            return await handler(cmd_arg)
        else:
            print(f"❌ 未知命令: {cmd_name}")
            print("   输入 /help 查看可用命令")
            return True

    # ========== Built-in Command Handlers ==========

    async def _handle_quit(self, arg: Optional[str]) -> bool:
        """Handle /quit command."""
        print("会话结束。")
        LOGGER.info("Exit requested by /quit command")
        return False  # Stop main loop

    async def _handle_help(self, arg: Optional[str]) -> bool:
        """Handle /help command."""
        print("\n可用命令:")
        for cmd, desc in self.commands.items():
            print(f"  {cmd:<20} {desc}")
        print()
        return True

    async def _handle_sessions(self, arg: Optional[str]) -> bool:
        """Handle /sessions command."""
        sessions = self.session_manager.list_sessions()
        if not sessions:
            print("没有找到已保存的会话。\n")
        else:
            print(f"\n找到 {len(sessions)} 个已保存的会话:\n")
            for i, (tid, created_at, updated_at, msg_count) in enumerate(sessions, 1):
                print(f"{i}. ID: {tid[:16]}... | 消息数: {msg_count} | 更新: {updated_at[:16]}")
            print()
        return True

    async def _handle_load(self, session_id_prefix: Optional[str]) -> bool:
        """Handle /load command."""
        if not session_id_prefix:
            print("❌ 请提供会话ID前缀，例如: /load abc123")
            return True

        # Try to load session
        sessions = self.session_manager.list_sessions()
        matching = [s for s in sessions if s[0].startswith(session_id_prefix)]

        if not matching:
            print(f"❌ 未找到以 '{session_id_prefix}' 开头的会话。")
            return True

        if len(matching) > 1:
            print(f"⚠️  找到 {len(matching)} 个匹配的会话，请提供更长的ID前缀:")
            for tid, _, _, msg_count in matching[:5]:
                print(f"   - {tid[:16]}... ({msg_count} 条消息)")
            print()
            return True

        # Load the unique match
        success = self.session_manager.load_session(session_id_prefix)
        if success:
            info = self.session_manager.get_current_session_info()
            print(f"✅ 已加载会话 {info['session_id_short']}... (共 {info['message_count']} 条消息)")

            # Print recent messages for context
            await self.print_recent_messages(info)
        else:
            print(f"❌ 无法加载会话")

        return True

    async def _handle_reset(self, arg: Optional[str]) -> bool:
        """Handle /reset command."""
        session_id, _ = self.session_manager.reset_session()
        print(f"✅ 状态已重置。新会话 ID: {session_id[:8]}...\n")
        return True

    async def _handle_current(self, arg: Optional[str]) -> bool:
        """Handle /current command."""
        info = self.session_manager.get_current_session_info()

        if not info.get("active"):
            print("❌ 无活动会话\n")
            return True

        print(f"\n当前会话信息:")
        print(f"  ID: {info['session_id_short']}...")
        print(f"  消息数: {info['message_count']}")
        print(f"  Workspace: {info['workspace_path']}")

        if info.get("active_skill"):
            print(f"  激活技能: {info['active_skill']}")
        if info.get("mentioned_agents"):
            print(f"  提到的代理: {', '.join(info['mentioned_agents'])}")

        todos = info.get("todos", [])
        if todos:
            pending = [t for t in todos if t.get("status") == "pending"]
            in_progress = [t for t in todos if t.get("status") == "in_progress"]
            completed = [t for t in todos if t.get("status") == "completed"]
            print(f"  任务: {len(completed)} 已完成 | {len(in_progress)} 进行中 | {len(pending)} 待办")

        print()
        return True

    # ========== Abstract Methods (Subclass Implementation) ==========

    @abstractmethod
    def print_welcome(self):
        """Print welcome message (agent-specific).

        Example:
            print("GeneralAgent CLI 已就绪。")
            print(f"会话 ID: {self.session_manager.current_session_id[:8]}...")
            print("\\n输入 /help 查看命令列表\\n")
        """
        pass

    @abstractmethod
    async def get_input(self) -> str:
        """Get user input (may be CLI, HTTP, WebSocket, etc.).

        Example for CLI:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: input("You> ").strip())

        Returns:
            User input string
        """
        pass

    @abstractmethod
    async def handle_user_message(self, message: str):
        """Handle user message (agent-specific logic).

        This is where the agent processes the user's input and generates responses.
        Each agent implementation will have different logic here.

        Args:
            message: User input text
        """
        pass

    # ========== Optional Helper Methods ==========

    async def print_recent_messages(self, info: Dict):
        """Print recent messages from loaded session.

        Subclasses can override for custom formatting.
        """
        state = self.session_manager.current_state
        if not state:
            return

        messages = state.get("messages", [])
        if len(messages) > 0:
            print("\n最近的对话:")
            recent = messages[-3:]
            for msg in recent:
                # Basic formatting - subclass can customize
                role = getattr(msg, "type", "unknown")
                content = str(getattr(msg, "content", ""))[:100]
                if role in {"human", "user"}:
                    print(f"  You> {content}...")
                elif role in {"ai", "assistant"}:
                    print(f"  Agent> {content}...")
            print()


__all__ = ["BaseCLI"]
