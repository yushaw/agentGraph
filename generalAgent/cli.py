"""GeneralAgent CLI implementation using shared framework."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Set

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import Command

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
        skill_config,
        logger
    ):
        """Initialize GeneralAgent CLI.

        Args:
            app: Compiled LangGraph application
            session_manager: Session lifecycle manager
            skill_registry: Skill registry for mention classification
            tool_registry: Tool registry for mention classification
            skill_config: Skill configuration loader
            logger: Application logger
        """
        super().__init__(session_manager)
        self.app = app
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.skill_config = skill_config
        self.logger = logger

        # Add custom command handler
        self._command_handlers["/clean"] = self._handle_clean

        # Track printed tool IDs and message IDs to avoid duplication
        self.printed_tool_ids: Set[str] = set()
        self.printed_message_ids: Set[str] = set()

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
        # Update state with mentions:
        # - new_mentioned_agents: Current turn only (for reminder generation)
        # - mentioned_agents: Cumulative history (append new mentions)
        state["new_mentioned_agents"] = mentions if mentions else []

        if mentions:
            self.logger.info(f"Detected @mentions: {mentions}")
            print(f"[检测到 @{', @'.join(mentions)}]")

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

                        # Auto-load corresponding skill (if enabled in config)
                        if self.skill_config.auto_load_on_file_upload():
                            skills_for_type = self.skill_config.get_skills_for_file_type(result.file_type)
                            for skill_id in skills_for_type:
                                if skill_id not in auto_load_skills:
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

        # Update file tracking:
        # - new_uploaded_files: Current turn only (for reminder generation)
        # - uploaded_files: Cumulative history (append new files)
        state["new_uploaded_files"] = [asdict(f) for f in processed_files]
        if processed_files:
            existing_files = state.get("uploaded_files", [])
            state["uploaded_files"] = existing_files + [asdict(f) for f in processed_files]

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

            # Update state after initial stream
            state = final_state
            self.session_manager.current_state = state

            # Handle interrupts (HITL support)
            while True:
                graph_state = await self.app.aget_state(config)

                # Check if there are any interrupts
                if graph_state.next and graph_state.tasks and hasattr(graph_state.tasks[0], 'interrupts') and graph_state.tasks[0].interrupts:
                    # Update last_printed_msg_count BEFORE handling interrupt
                    # to avoid reprinting messages after resume
                    current_msg_count = len(state.get("messages", []))
                    last_printed_msg_count = current_msg_count

                    # Get interrupt data
                    interrupt_value = graph_state.tasks[0].interrupts[0].value
                    resume_value = await self._handle_interrupt(interrupt_value)

                    if resume_value is not None:
                        # Resume execution with user's response
                        async for state_snapshot in self.app.astream(
                            Command(resume=resume_value),
                            config=config,
                            stream_mode="values"
                        ):
                            current_messages = state_snapshot.get("messages", [])

                            # Print new messages
                            for idx in range(last_printed_msg_count, len(current_messages)):
                                msg = current_messages[idx]
                                await self._print_message(msg)

                            last_printed_msg_count = len(current_messages)
                            final_state = state_snapshot

                        # Update state after resume
                        state = final_state
                        self.session_manager.current_state = state
                    else:
                        # User cancelled, break loop
                        print("⚠️  任务已取消")
                        break
                else:
                    # No more interrupts, execution complete
                    break

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
            # Handle different error types
            error_msg = str(e)
            error_type = type(e).__name__

            # Check for common LLM errors
            if "token" in error_msg.lower() and ("limit" in error_msg.lower() or "maximum" in error_msg.lower()):
                print(f"\n❌ Token 限制错误:")
                print(f"   {error_msg}")
                print(f"   建议：尝试精简输入内容或重置会话 (/reset)")
            elif "api" in error_msg.lower() and "key" in error_msg.lower():
                print(f"\n❌ API 密钥错误:")
                print(f"   {error_msg}")
                print(f"   建议：检查 .env 文件中的 API key 配置")
            elif "rate" in error_msg.lower() and "limit" in error_msg.lower():
                print(f"\n❌ API 速率限制:")
                print(f"   {error_msg}")
                print(f"   建议：稍等片刻后重试")
            elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                print(f"\n❌ 网络连接错误:")
                print(f"   {error_msg}")
                print(f"   建议：检查网络连接或稍后重试")
            else:
                # Generic error
                print(f"\n❌ 发生错误 ({error_type}):")
                print(f"   {error_msg}")

            # Always log full error details
            log_error(self.logger, e, context="handle_user_message - app.astream()")
            print(f"\n详细信息已记录到日志: {self.logger.handlers[0].baseFilename if self.logger.handlers else 'N/A'}\n")

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
        """Override reset to clear printed IDs."""
        result = await super()._handle_reset(arg)
        self.printed_tool_ids.clear()
        self.printed_message_ids.clear()
        return result

    async def _handle_load(self, session_id_prefix: str) -> bool:
        """Override load to clear printed IDs."""
        result = await super()._handle_load(session_id_prefix)
        if result:
            self.printed_tool_ids.clear()
            self.printed_message_ids.clear()
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

    # ========== HITL Interrupt Handling ==========

    async def _handle_interrupt(self, interrupt_data: dict):
        """Handle interrupt events (HITL core logic).

        Args:
            interrupt_data: Interrupt data from LangGraph

        Returns:
            Resume value or None if user cancels
        """
        interrupt_type = interrupt_data.get("type", "generic")

        if interrupt_type == "user_input_request":
            return await self._handle_user_input_request(interrupt_data)
        elif interrupt_type == "tool_approval":
            return await self._handle_tool_approval(interrupt_data)
        else:
            # Generic interrupt handling
            self.logger.warning(f"Unknown interrupt type: {interrupt_type}")
            return None

    async def _handle_user_input_request(self, data: dict) -> str:
        """Handle ask_human tool request (极简版 UI).

        Args:
            data: Request data with question, context, etc.

        Returns:
            User's answer or None if cancelled
        """
        question = data.get("question", "")
        context = data.get("context", "")
        default = data.get("default")
        required = data.get("required", True)

        # Print question (极简版)
        print()
        if context:
            print(f"💡 {context}")
        print(f"💬 {question}")
        if default:
            print(f"   (默认: {default})")

        # Get user input
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, lambda: input("> ").strip())

        # Handle empty answer
        if not answer:
            if default:
                print(f"✓ 使用默认值: {default}")
                return default
            if required:
                print("⚠️  必须回答此问题")
                return await self._handle_user_input_request(data)  # Retry

        return answer

    async def _handle_tool_approval(self, data: dict) -> str:
        """Handle tool approval request (极简版 UI).

        Args:
            data: Approval request data

        Returns:
            "approve" or "reject"
        """
        tool = data.get("tool", "unknown")
        args = data.get("args", {})
        reason = data.get("reason", "")
        risk_level = data.get("risk_level", "medium")

        # Print approval request (极简版)
        print()
        print(f"🛡️  工具审批: {tool}")
        if reason:
            print(f"   原因: {reason}")
        print(f"   参数: {self._format_tool_args(args, max_length=60)}")

        # Get approval decision
        loop = asyncio.get_event_loop()
        while True:
            choice = await loop.run_in_executor(
                None,
                lambda: input("   批准? [y/n] > ").strip().lower()
            )

            if choice in ["y", "yes", "是"]:
                print("✓ 已批准")
                return "approve"
            elif choice in ["n", "no", "否"]:
                print("✗ 已拒绝")
                return "reject"
            else:
                print("   请输入 y 或 n")

    # ========== Helper Methods ==========

    async def _print_message(self, msg: BaseMessage):
        """Print a single message with appropriate formatting."""
        # Check if message already printed (avoid duplicates during interrupt/resume)
        msg_id = getattr(msg, "id", None)
        if msg_id and msg_id in self.printed_message_ids:
            return

        role, text = self._role_and_text(msg)

        # Print tool calls if present (before text content)
        if role in {"assistant", "ai"} and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                # Format args concisely
                args_str = self._format_tool_args(tool_args)
                print(f">> [call] {tool_name}({args_str})")

        if not text:
            # Mark as printed even if no text (to avoid reprinting tool_calls)
            if msg_id:
                self.printed_message_ids.add(msg_id)
            return

        if role in {"assistant", "ai"}:
            print(f"Agent> {text}")
        elif role == "tool":
            # Keep old tool_id tracking for backward compatibility
            tool_id = getattr(msg, "id", None)
            if tool_id and tool_id in self.printed_tool_ids:
                return
            if tool_id:
                self.printed_tool_ids.add(tool_id)
            print(f"<< [result] {text}")

        # Mark message as printed
        if msg_id:
            self.printed_message_ids.add(msg_id)

    @staticmethod
    def _format_tool_args(args: dict, max_length: int = 80) -> str:
        """Format tool arguments for display.

        Args:
            args: Tool arguments dictionary
            max_length: Maximum length for formatted string

        Returns:
            Formatted argument string
        """
        if not args:
            return ""

        # Format each argument
        parts = []
        for key, value in args.items():
            if isinstance(value, str):
                # Truncate long strings
                if len(value) > 40:
                    value_str = f'"{value[:37]}..."'
                else:
                    value_str = f'"{value}"'
            elif isinstance(value, list):
                # Show list length for long lists
                if len(value) > 3:
                    value_str = f"[{len(value)} items]"
                else:
                    value_str = str(value)
            else:
                value_str = str(value)

            parts.append(f"{key}={value_str}")

        result = ", ".join(parts)

        # Truncate if too long
        if len(result) > max_length:
            result = result[:max_length-3] + "..."

        return result

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
