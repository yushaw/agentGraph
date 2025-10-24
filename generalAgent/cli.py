"""GeneralAgent CLI implementation using shared framework."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Set

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from shared.cli.base_cli import BaseCLI
from shared.session.manager import SessionManager
from generalAgent.config.project_root import resolve_project_path
from generalAgent.utils import (
    get_logger,
    log_user_message,
    log_agent_response,
    log_error,
    parse_mentions,
    parse_file_mentions,
    process_file,
    FILE_TYPE_TO_SKILL,
)
from generalAgent.utils.mention_classifier import classify_mentions, group_by_type

LOGGER = logging.getLogger(__name__)


class GeneralAgentCLI(BaseCLI):
    """CLI interface for GeneralAgent.

    Extends BaseCLI with:
    - @mention parsing and skill loading
    - File upload processing
    - LangGraph streaming execution
    - Session autosave
    """

    BASE_COMMANDS = {
        **BaseCLI.BASE_COMMANDS,
        "/clean": "清理旧的 workspace 文件（>7天）",
    }

    def __init__(
        self,
        app,
        session_manager: SessionManager,
        skill_registry,
        tool_registry,
        logger
    ):
        """Initialize GeneralAgent CLI.

        Args:
            app: Compiled LangGraph application
            session_manager: Session lifecycle manager
            skill_registry: Skill registry for mention classification
            tool_registry: Tool registry for mention classification
            logger: Application logger
        """
        super().__init__(session_manager)
        self.app = app
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.logger = logger

        # Add custom command handler
        self._command_handlers["/clean"] = self._handle_clean

        # Track printed tool IDs to avoid duplication
        self.printed_tool_ids: Set[str] = set()

        LOGGER.info("GeneralAgentCLI initialized")

    @property
    def commands(self) -> dict:
        """Override to include custom commands."""
        return self.BASE_COMMANDS

    # ========== CLI Interface Implementation ==========

    def print_welcome(self):
        """Print welcome message."""
        info = self.session_manager.get_current_session_info()
        session_id_short = info.get("session_id_short", "unknown")

        print("AgentGraph CLI 已就绪。")
        print(f"会话 ID: {session_id_short}...")
        print(f"日志文件: {self.logger.handlers[0].baseFilename if self.logger.handlers else 'N/A'}")
        print("\n输入 /help 查看命令列表\n")

    async def get_input(self) -> str:
        """Get user input from CLI."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input("You> ").strip())

    async def handle_user_message(self, user_input: str):
        """Process user message through GeneralAgent."""
        state = self.session_manager.current_state
        if not state:
            print("❌ 无活动会话")
            return

        thread_id = self.session_manager.current_session_id

        # ========== Step 1: Parse @mentions ==========
        mentions, cleaned_input_mentions = parse_mentions(user_input)

        # ========== Step 2: Parse #filename mentions ==========
        file_mentions, cleaned_input_files = parse_file_mentions(
            cleaned_input_mentions if mentions else user_input
        )

        # Combined cleaned input
        cleaned_input = cleaned_input_files if file_mentions else (
            cleaned_input_mentions if mentions else user_input
        )

        # ========== Step 3: Handle @mentions ==========
        if mentions:
            self.logger.info(f"Detected @mentions: {mentions}")
            print(f"[检测到 @{', @'.join(mentions)}]")

            # Update state with mentions
            existing_mentions = state.get("mentioned_agents", [])
            all_mentions = list(set(existing_mentions + mentions))
            state["mentioned_agents"] = all_mentions

            # Classify mentions and load skills
            classifications = classify_mentions(mentions, self.tool_registry, self.skill_registry)
            grouped = group_by_type(classifications)

            if grouped['skills']:
                self.logger.info(f"Loading skills to workspace: {grouped['skills']}")
                self.session_manager.update_workspace_skills(grouped['skills'])
                print(f"[已加载技能: {', '.join(grouped['skills'])}]")

        # ========== Step 4: Process file uploads ==========
        processed_files = []
        auto_load_skills = []

        if file_mentions:
            tmp_dir = resolve_project_path("uploads")
            workspace_path = state.get("workspace_path")

            if workspace_path:
                workspace_dir = Path(workspace_path)
                self.logger.info(f"Processing {len(file_mentions)} file uploads: {file_mentions}")

                for filename in file_mentions:
                    result = process_file(filename, tmp_dir, workspace_dir)

                    if result.error:
                        self.logger.warning(f"File upload error: {filename} - {result.error}")
                    else:
                        processed_files.append(result)
                        self.logger.info(
                            f"File uploaded: {filename} ({result.file_type}, "
                            f"{result.size_formatted}) → {result.workspace_path}"
                        )

                        # Auto-load corresponding skill
                        skill_id = FILE_TYPE_TO_SKILL.get(result.file_type)
                        if skill_id and skill_id not in auto_load_skills:
                            auto_load_skills.append(skill_id)

                if processed_files:
                    print(f"[已上传 {len(processed_files)} 个文件]")

                # Auto-load skills based on file types
                if auto_load_skills:
                    self.logger.info(f"Auto-loading skills for uploaded files: {auto_load_skills}")
                    self.session_manager.update_workspace_skills(auto_load_skills)
                    print(f"[已自动加载技能: {', '.join(auto_load_skills)}]")

        # ========== Step 5: Build message content ==========
        log_user_message(self.logger, user_input)

        messages: List[BaseMessage] = list(state.get("messages", []))
        message_content = []

        # Text part
        message_content.append({"type": "text", "text": cleaned_input})

        # Image parts (base64 encoded)
        for file in processed_files:
            if file.file_type == "image" and file.base64_data:
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{file.mime_type};base64,{file.base64_data}"
                    }
                })

        # Text file content injection
        text_injections = []
        for file in processed_files:
            if file.file_type in ("text", "code") and file.text_content:
                text_injections.append(f"\n\n[File: {file.filename}]\n{file.text_content}")

        if text_injections:
            message_content[0]["text"] += "".join(text_injections)

        # Add HumanMessage
        if len(message_content) == 1 and message_content[0]["type"] == "text":
            messages.append(HumanMessage(content=message_content[0]["text"]))
        else:
            messages.append(HumanMessage(content=message_content))

        state["messages"] = messages
        # Convert ProcessedFile dataclass to dict for JSON serialization
        from dataclasses import asdict
        state["uploaded_files"] = [asdict(f) for f in processed_files]

        # ========== Step 6: Execute agent ==========
        start_index = len(messages)

        try:
            # Set workspace path in environment
            workspace_path = state.get("workspace_path")
            if workspace_path:
                os.environ["AGENT_WORKSPACE_PATH"] = workspace_path

            # Configure LangGraph execution
            config = {
                "recursion_limit": 50,
                "configurable": {"thread_id": thread_id}
            }

            # Stream responses
            last_printed_msg_count = start_index
            final_state = state

            async for state_snapshot in self.app.astream(state, config=config, stream_mode="values"):
                current_messages = state_snapshot.get("messages", [])

                # Print new messages
                for idx in range(last_printed_msg_count, len(current_messages)):
                    msg = current_messages[idx]
                    await self._print_message(msg)

                last_printed_msg_count = len(current_messages)
                final_state = state_snapshot

            # Update state
            state = final_state
            self.session_manager.current_state = state

            # Log agent response
            for msg in state.get("messages", [])[start_index:]:
                if isinstance(msg, AIMessage) and hasattr(msg, 'content'):
                    log_agent_response(self.logger, msg.content)
                    break

            # Auto-save session
            self.session_manager.save_current_session()
            self.logger.info(
                f"Session {thread_id[:8]}... saved ({len(state.get('messages', []))} messages)"
            )

        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            log_error(self.logger, e, context="handle_user_message - app.astream()")
            print("请查看日志文件获取详细信息\n")

    # ========== Custom Command Handlers ==========

    async def _handle_clean(self, arg: str) -> bool:
        """Handle /clean command."""
        print("正在清理旧的 workspace 文件...")
        cleaned = self.session_manager.workspace_manager.cleanup_old_workspaces(days=7)
        if cleaned > 0:
            print(f"✅ 已清理 {cleaned} 个旧 workspace（>7天）")
            self.logger.info(f"Manual cleanup: removed {cleaned} workspaces")
        else:
            print("没有需要清理的旧文件。")
        return True

    async def _handle_reset(self, arg: str) -> bool:
        """Override reset to clear printed_tool_ids."""
        result = await super()._handle_reset(arg)
        self.printed_tool_ids.clear()
        return result

    async def _handle_load(self, session_id_prefix: str) -> bool:
        """Override load to clear printed_tool_ids."""
        result = await super()._handle_load(session_id_prefix)
        if result:
            self.printed_tool_ids.clear()
        return result

    # ========== Cleanup ==========

    async def on_shutdown(self):
        """Cleanup on shutdown."""
        await super().on_shutdown()

        # Cleanup old workspaces
        try:
            self.logger.info("Cleaning up old workspaces on exit...")
            cleaned = self.session_manager.workspace_manager.cleanup_old_workspaces(days=7)
            if cleaned > 0:
                self.logger.info(f"Cleaned {cleaned} old workspaces on exit")
        except Exception as e:
            self.logger.warning(f"Cleanup failed on exit: {e}")

    # ========== Helper Methods ==========

    async def _print_message(self, msg: BaseMessage):
        """Print a single message with appropriate formatting."""
        role, text = self._role_and_text(msg)

        if not text:
            return

        if role in {"assistant", "ai"}:
            print(f"Agent> {text}")
        elif role == "tool":
            tool_id = getattr(msg, "id", None)
            if tool_id and tool_id in self.printed_tool_ids:
                return
            if tool_id:
                self.printed_tool_ids.add(tool_id)
            print(f"[tool] {text}")

    @staticmethod
    def _role_and_text(message: BaseMessage) -> tuple[str, str]:
        """Extract role and text from message."""
        from generalAgent.utils import _stringify_content

        if hasattr(message, "type"):
            role = message.type
        else:
            role = "unknown"

        content = getattr(message, "content", "")
        text = _stringify_content(content)

        return role, text


__all__ = ["GeneralAgentCLI"]
