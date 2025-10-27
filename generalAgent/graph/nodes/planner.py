"""Planner node implementation - Charlie MVP Edition."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from generalAgent.agents import ModelResolver, invoke_planner
from generalAgent.graph.message_utils import clean_message_history, truncate_messages_safely
from generalAgent.graph.prompts import (
    PLANNER_SYSTEM_PROMPT,
    SUBAGENT_SYSTEM_PROMPT,
    build_dynamic_reminder,
    build_skills_catalog,
    get_current_datetime_tag,
)
from generalAgent.graph.state import AppState
from generalAgent.models import ModelRegistry
from generalAgent.tools import ToolRegistry
from generalAgent.utils.logging_utils import (
    log_node_entry,
    log_node_exit,
    log_visible_tools,
    log_prompt,
    log_model_selection,
)
from generalAgent.utils.error_handler import with_error_boundary, handle_model_error, ModelInvocationError
from generalAgent.utils.mention_classifier import classify_mentions, group_by_type

LOGGER = logging.getLogger("agentgraph.planner")


def _detect_multimodal_input(messages: List[BaseMessage]) -> tuple[bool, bool]:
    """Detect if recent messages contain images or code.

    Returns:
        (has_images, has_code): Tuple of boolean flags
    """
    has_images = False
    has_code = False

    # Check last 3 messages
    for msg in messages[-3:]:
        content = getattr(msg, "content", "")

        # Check for images (list content with image types)
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") in ("image", "image_url"):
                        has_images = True

        # Check for code blocks (markdown code fence)
        # DISABLED: Too broad - matches any content with ``` including error messages
        # if isinstance(content, str):
        #     if "```" in content:
        #         has_code = True

    return has_images, has_code


def build_planner_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: Iterable[BaseTool],
    skill_registry,
    skill_config,
    settings,
):
    """Create a planner node bound to runtime registries."""

    persistent_global_tools = list(persistent_global_tools)
    max_message_history = settings.governance.max_message_history

    # ========== Build static system prompt (with fixed datetime) ==========
    # Generate datetime tag once at initialization (minute precision, never updates)
    now = datetime.now(timezone.utc)
    static_datetime_tag = f"<current_datetime>{now.strftime('%Y-%m-%d %H:%M UTC')}</current_datetime>"

    # Build base system prompts (main agent and subagent)
    # Datetime tag is placed at the bottom of system prompt for better KV cache reuse
    # Only include enabled skills in catalog (controlled by skills.yaml)
    static_main_prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{build_skills_catalog(skill_registry, skill_config)}\n\n{static_datetime_tag}"
    static_subagent_prompt = f"{SUBAGENT_SYSTEM_PROMPT}\n\n{static_datetime_tag}"

    LOGGER.info(f"Built static system prompts with datetime: {static_datetime_tag}")

    @with_error_boundary("planner")
    async def planner_node(state: AppState) -> AppState:
        log_node_entry(LOGGER, "planner", state)

        # ========== Assemble visible tools ==========
        visible_tools: List[BaseTool] = list(persistent_global_tools)

        # Process @mentions (tools, skills, agents)
        mentioned = state.get("mentioned_agents", [])
        grouped_mentions = {"tools": [], "skills": [], "agents": [], "unknown": []}

        if mentioned:
            # Classify mentions by type
            classifications = classify_mentions(mentioned, tool_registry, skill_registry)
            grouped_mentions = group_by_type(classifications)

            if grouped_mentions['unknown']:
                LOGGER.warning(f"Unknown @mentions: {grouped_mentions['unknown']}")

            # Handle @tool mentions (load and add to visible_tools)
            for tool_name in grouped_mentions['tools']:
                try:
                    tool = tool_registry.get_tool(tool_name)
                    visible_tools.append(tool)
                except KeyError:
                    try:
                        tool = tool_registry.load_on_demand(tool_name)
                        visible_tools.append(tool)
                    except KeyError:
                        LOGGER.error(f"@{tool_name} load failed")

            # Handle @agent mentions (ensure call_subagent is available)
            if grouped_mentions['agents']:
                try:
                    subagent_tool = tool_registry.get_tool("call_subagent")
                    if subagent_tool not in visible_tools:
                        visible_tools.append(subagent_tool)
                except KeyError:
                    LOGGER.warning("call_subagent not found")

        # Deduplicate
        deduped: List[BaseTool] = []
        seen = set()
        for tool in visible_tools:
            if tool.name in seen:
                continue
            seen.add(tool.name)
            deduped.append(tool)
        visible_tools = deduped

        # ========== Subagent tool filtering ==========
        # Subagents should NOT have access to call_subagent (prevent nesting)
        context_id = state.get("context_id", "main")
        is_subagent = context_id != "main" and context_id.startswith("subagent-")

        if is_subagent:
            # Remove call_subagent from visible tools
            visible_tools = [t for t in visible_tools if t.name != "call_subagent"]

        # ========== Detect capabilities needed ==========
        need_code = False
        need_vision = False
        for tool in visible_tools:
            metadata = tool_registry.get_meta_optional(tool.name)
            if metadata:
                if "code" in metadata.tags:
                    need_code = True
                if "vision" in metadata.tags:
                    need_vision = True

        # ========== Detect multimodal input ==========
        history: List[BaseMessage] = list(state.get("messages") or [])
        has_images, has_code = _detect_multimodal_input(history)

        # Override model preference if images detected
        preference = state.get("model_pref")
        if has_images and not preference:
            preference = "vision"

        # ========== Build dynamic system prompt ==========
        active_skill = state.get("active_skill")

        LOGGER.info("Building system prompt...")
        dynamic_reminder = build_dynamic_reminder(
            active_skill=active_skill,
            mentioned_tools=grouped_mentions.get('tools', []),
            mentioned_skills=grouped_mentions.get('skills', []),
            mentioned_agents=grouped_mentions.get('agents', []),
            has_images=has_images,
            has_code=has_code,
        )

        # Clean and safely truncate message history (configurable via MAX_MESSAGE_HISTORY)
        cleaned_history = clean_message_history(history)
        recent_history = truncate_messages_safely(cleaned_history, keep_recent=max_message_history)

        # Add todo reminder if there are todos
        todos = state.get("todos", [])
        todo_reminder = ""
        if todos:
            in_progress = [t for t in todos if t.get("status") == "in_progress"]
            pending = [t for t in todos if t.get("status") == "pending"]
            completed = [t for t in todos if t.get("status") == "completed"]

            # Check if there are incomplete tasks
            incomplete = in_progress + pending

            if incomplete:
                # Build concise reminder: current + next only
                todo_lines = []
                if in_progress:
                    todo_lines.append(f"当前: {in_progress[0].get('content')}")
                if pending:
                    # Show only next task
                    todo_lines.append(f"下一个: {pending[0].get('content')}")
                    if len(pending) > 1:
                        todo_lines.append(f"(还有 {len(pending) - 1} 个待办)")

                # Strong reminder to prevent early stopping
                todo_reminder = f"""<system_reminder>
                ⚠️ 任务追踪: {' | '.join(todo_lines)}
                使用 todo_read 查看所有任务。完成所有任务后再停止！
                </system_reminder>"""
                LOGGER.info(f"  - Todo reminder: {len(incomplete)} incomplete, {len(completed)} completed")
            elif completed:
                # All tasks completed
                todo_reminder = f"<system_reminder>✅ 所有 {len(completed)} 个任务已完成！可以输出最终结果。</system_reminder>"
                LOGGER.info(f"  - Todo reminder: All {len(completed)} tasks completed")

        # Choose prompt based on context (main agent or subagent)
        context_id = state.get("context_id", "main")
        is_subagent = context_id != "main" and context_id.startswith("subagent-")

        # Use static system prompt (datetime is already at the bottom)
        if is_subagent:
            base_prompt = static_subagent_prompt
            LOGGER.info(f"  - Using SUBAGENT prompt for context: {context_id}")
            # Subagents don't get reminders (keep them focused)
            combined_reminders = ""
        else:
            base_prompt = static_main_prompt
            enabled_skills_count = len(skill_config.get_enabled_skills()) if skill_config else len(skill_registry.list_meta())
            LOGGER.info(f"  - Using MAIN AGENT prompt with {enabled_skills_count} enabled skills")

            # Build file upload reminder if there are uploaded files
            from generalAgent.utils.file_processor import build_file_upload_reminder
            uploaded_files = state.get("uploaded_files", [])
            file_upload_reminder = ""
            if uploaded_files:
                file_upload_reminder = build_file_upload_reminder(uploaded_files, skill_config)

            # Collect all dynamic reminders
            reminders = [r for r in [dynamic_reminder, todo_reminder, file_upload_reminder] if r]
            combined_reminders = "\n\n".join(reminders) if reminders else ""

            if combined_reminders:
                LOGGER.info(f"  - Built {len(reminders)} reminder(s) to append to last message")

        # Log prompt with truncation for readability
        log_prompt(LOGGER, "planner", base_prompt, max_length=500)
        log_visible_tools(LOGGER, "planner", visible_tools)

        # ========== Append reminders to last message (KV cache optimization) ==========
        # Copy recent_history to avoid modifying state
        message_history = list(recent_history)

        if combined_reminders:
            if message_history and isinstance(message_history[-1], HumanMessage):
                # Case A: Last message is HumanMessage - append reminders to it
                last_msg = message_history[-1]
                message_history[-1] = HumanMessage(
                    content=f"{last_msg.content}\n\n{combined_reminders}"
                )
                LOGGER.info("  - Appended reminders to last HumanMessage")
            else:
                # Case B: Last message is not HumanMessage - add lightweight context message
                message_history.append(HumanMessage(content=combined_reminders))
                LOGGER.info("  - Appended lightweight context message with reminders")

        prompt_messages = [SystemMessage(content=base_prompt), *message_history]

        # ========== Invoke planner ==========
        # Invoke planner with model selection

        try:
            output = await invoke_planner(
                model_registry=model_registry,
                model_resolver=model_resolver,
                tools=visible_tools,
                messages=prompt_messages,
                need_code=need_code or has_code,
                need_vision=has_images,
                preference=preference,
            )
        except Exception as e:
            LOGGER.error(f"Planner model invocation failed: {e}")
            error_msg = handle_model_error(e)
            raise ModelInvocationError(str(e), user_message=error_msg)

        LOGGER.info("Planner invocation completed")

        # Increment loop counter for Agent Loop tracking
        current_loops = state.get("loops", 0)
        updates = {
            "messages": [output],
            "loops": current_loops + 1,
        }

        log_node_exit(LOGGER, "planner", updates)
        return updates

    return planner_node
