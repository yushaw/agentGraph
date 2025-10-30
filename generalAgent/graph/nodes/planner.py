"""Planner node implementation - Charlie MVP Edition."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, RemoveMessage
from langchain_core.tools import BaseTool
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from generalAgent.agents import ModelResolver, invoke_planner
from generalAgent.context.manager import ContextManager
from generalAgent.context.token_tracker import TokenTracker
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
from generalAgent.context.manager import ContextManager

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
    agent_registry=None,  # NEW: Agent Registry（可选）
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
    skills_catalog = build_skills_catalog(skill_registry, skill_config)
    agents_catalog = agent_registry.get_catalog_text() if agent_registry else ""

    static_main_prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{skills_catalog}"
    if agents_catalog:
        static_main_prompt += f"\n\n{agents_catalog}"
    static_main_prompt += f"\n\n{static_datetime_tag}"

    static_subagent_prompt = f"{SUBAGENT_SYSTEM_PROMPT}\n\n{static_datetime_tag}"

    LOGGER.info(f"Built static system prompts with datetime: {static_datetime_tag}")
    if agents_catalog:
        LOGGER.info(f"  - Included Agent Catalog with {len(agent_registry.list_enabled())} agents")

    @with_error_boundary("planner")
    async def planner_node(state: AppState) -> AppState:
        log_node_entry(LOGGER, "planner", state)

        # Reset auto-compression flag at start of each request
        state["auto_compressed_this_request"] = False

        # ========== Context Management: Initialize ==========
        context_manager = ContextManager(settings) if settings.context.enabled else None

        # ========== Assemble visible tools ==========
        visible_tools: List[BaseTool] = list(persistent_global_tools)

        # Process @mentions (tools, skills, agents)
        # Use ALL mentions (historical) to ensure tools/skills remain available
        mentioned = state.get("mentioned_agents", [])
        grouped_mentions = {"tools": [], "skills": [], "agents": [], "unknown": []}

        if mentioned:
            # Classify mentions by type
            classifications = classify_mentions(mentioned, tool_registry, skill_registry, agent_registry)
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

            # Handle @agent mentions (load agents and ensure call_agent tool is available)
            if grouped_mentions['agents']:
                # Load mentioned agents on-demand
                if agent_registry:
                    for agent_id in grouped_mentions['agents']:
                        try:
                            agent_registry.load_on_demand(agent_id)
                            LOGGER.info(f"Loaded agent: @{agent_id}")
                        except KeyError:
                            LOGGER.warning(f"Agent @{agent_id} not found in registry")

                # Ensure call_agent tool is available
                try:
                    call_agent_tool = tool_registry.get_tool("call_agent")
                    if call_agent_tool not in visible_tools:
                        visible_tools.append(call_agent_tool)
                except KeyError:
                    LOGGER.warning("call_agent tool not found (agents system may not be enabled)")

                # Also include delegate_task for backward compatibility
                try:
                    delegate_tool = tool_registry.get_tool("delegate_task")
                    if delegate_tool not in visible_tools:
                        visible_tools.append(delegate_tool)
                except KeyError:
                    pass  # delegate_task is optional

        # Deduplicate
        deduped: List[BaseTool] = []
        seen = set()
        for tool in visible_tools:
            if tool.name in seen:
                continue
            seen.add(tool.name)
            deduped.append(tool)
        visible_tools = deduped

        # ========== Delegated agent tool filtering ==========
        # Delegated agents should NOT have access to delegate_task (prevent nesting)
        context_id = state.get("context_id", "main")
        is_delegated = context_id != "main" and context_id.startswith("subagent-")

        if is_delegated:
            # Remove delegate_task from visible tools (prevent nesting)
            visible_tools = [t for t in visible_tools if t.name != "delegate_task"]

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

        # For reminder generation: use NEW mentions only (not historical)
        new_mentions = state.get("new_mentioned_agents", [])
        new_grouped_mentions = {"tools": [], "skills": [], "agents": [], "unknown": []}
        if new_mentions:
            new_classifications = classify_mentions(new_mentions, tool_registry, skill_registry, agent_registry)
            new_grouped_mentions = group_by_type(new_classifications)

        LOGGER.info("Building system prompt...")
        dynamic_reminder = build_dynamic_reminder(
            active_skill=active_skill,
            mentioned_tools=new_grouped_mentions.get('tools', []),
            mentioned_skills=new_grouped_mentions.get('skills', []),
            mentioned_agents=new_grouped_mentions.get('agents', []),
            has_images=has_images,
            has_code=has_code,
            agent_registry=agent_registry,  # NEW: For showing detailed agent info
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
                # Build detailed reminder: show ALL tasks grouped by status
                todo_lines = []

                # Show in_progress task(s)
                if in_progress:
                    for task in in_progress:
                        priority = task.get('priority', 'medium')
                        priority_tag = f"[{priority}]" if priority != "medium" else ""
                        todo_lines.append(f"  [进行中] {task.get('content')} {priority_tag}".strip())

                # Show all pending tasks
                if pending:
                    for task in pending:
                        priority = task.get('priority', 'medium')
                        priority_tag = f"[{priority}]" if priority != "medium" else ""
                        todo_lines.append(f"  [待完成] {task.get('content')} {priority_tag}".strip())

                # Show completed count (don't list all completed to save tokens)
                completed_summary = f"  (已完成 {len(completed)} 个)" if completed else ""

                # Strong reminder to prevent early stopping
                todo_reminder = f"""<system_reminder>
⚠️ 任务追踪 ({len(incomplete)} 个未完成):
{chr(10).join(todo_lines)}
{completed_summary}

完成所有任务后再停止！
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

            # Build file upload reminder for NEW uploads only (not historical)
            from generalAgent.utils.file_processor import build_file_upload_reminder
            new_uploaded_files = state.get("new_uploaded_files", [])
            file_upload_reminder = ""
            if new_uploaded_files:
                file_upload_reminder = build_file_upload_reminder(new_uploaded_files, skill_config)

            # Collect all dynamic reminders
            reminders = [r for r in [dynamic_reminder, todo_reminder, file_upload_reminder] if r]

            # ========== Context Management: Check token usage and add warning ==========
            token_warning = ""
            LOGGER.info(f"  - Context manager enabled: {context_manager is not None}")
            if context_manager:
                cumulative_prompt_tokens = state.get("cumulative_prompt_tokens", 0)
                compact_count = state.get("compact_count", 0)
                last_compression_ratio = state.get("last_compression_ratio")

                LOGGER.info(f"  - Checking token status: cumulative={cumulative_prompt_tokens}, compact_count={compact_count}")

                # Get model ID for context window lookup
                model_id = settings.models.base  # Use base model ID

                # Check status
                tracker = TokenTracker(settings)
                status = tracker.check_status(
                    cumulative_prompt_tokens=cumulative_prompt_tokens,
                    model_id=model_id
                )

                LOGGER.info(f"  - Token status: level={status.level}, usage={status.usage_ratio:.1%}")

                # Add warning if needed and load compact_context tool
                # Note: Critical (>95%) is now handled by routing to summarization node
                if status.level in ["info", "warning"]:
                    token_warning = status.message

                    # Dynamically load compact_context tool (on-demand loading)
                    try:
                        LOGGER.info(f"  - Attempting to load compact_context (is_discovered: {tool_registry.is_discovered('compact_context')})")
                        compact_tool = tool_registry.load_on_demand("compact_context")
                        if compact_tool and compact_tool not in visible_tools:
                            visible_tools.append(compact_tool)
                            LOGGER.info(f"  - Loaded compact_context tool (token usage: {status.usage_ratio:.1%})")
                    except KeyError as e:
                        LOGGER.error(f"compact_context tool not found in discovered tools: {e}")
                        LOGGER.error(f"  - Available discovered tools: {list(tool_registry._discovered.keys())[:10]}...")

                # If critical (>95%), skip LLM call and trigger compression via routing
                elif status.level == "critical":
                    LOGGER.warning(f"  - Token usage CRITICAL: {status.usage_ratio:.1%}")
                    LOGGER.info("  - Skipping LLM call, will route to summarization")

                    # Return immediately with flag for routing
                    return {
                        "needs_compression": True,  # Flag for routing
                        "loops": state.get("loops", 0) + 1,
                    }

            # Add token warning to reminders
            if token_warning:
                reminders.append(token_warning)

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

        # ========== Store parent state for delegate_task inheritance ==========
        # If delegate_task is in visible_tools, store current state for subagent inheritance
        if any(t.name == "delegate_task" for t in visible_tools):
            from generalAgent.tools.builtin.delegate_task import set_parent_state
            thread_id = state.get("thread_id")
            if thread_id:
                # Store minimal state needed for inheritance
                inheritance_state = {
                    "mentioned_agents": state.get("mentioned_agents", []),
                    "active_skill": state.get("active_skill"),
                    "workspace_path": state.get("workspace_path"),
                    "uploaded_files": state.get("uploaded_files", []),
                    "context_id": state.get("context_id", "main"),
                    "user_id": state.get("user_id"),
                }
                set_parent_state(thread_id, inheritance_state)
                LOGGER.info(f"  - Stored parent state for potential delegation (thread_id={thread_id})")

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

        # ========== Context Management: Extract and accumulate tokens ==========
        cumulative_prompt_tokens = state.get("cumulative_prompt_tokens", 0)
        cumulative_completion_tokens = state.get("cumulative_completion_tokens", 0)

        # Check for output truncation (finish_reason="length")
        finish_reason = output.response_metadata.get("finish_reason")
        if finish_reason == "length":
            LOGGER.warning(
                "⚠️ Model output truncated due to max_tokens limit (finish_reason='length'). "
                "This may cause incomplete tool calls or responses."
            )

            # Check if tool calls were affected
            if hasattr(output, "invalid_tool_calls") and output.invalid_tool_calls:
                LOGGER.error(
                    f"❌ {len(output.invalid_tool_calls)} invalid tool call(s) detected. "
                    "Likely caused by JSON truncation. "
                    "Consider: (1) Increase MODEL_*_MAX_TOKENS in .env, "
                    "(2) Use edit_file instead of write_file for long content"
                )

        if context_manager:
            token_usage = context_manager.tracker.extract_token_usage(output)

            if token_usage:
                # Use prompt_tokens directly (not累加) - it represents current context size
                # API returns prompt_tokens = total tokens sent (system + history + current input)
                cumulative_prompt_tokens = token_usage.prompt_tokens
                cumulative_completion_tokens += token_usage.completion_tokens

                LOGGER.info(
                    f"  - Token usage: Prompt {token_usage.prompt_tokens:,} "
                    f"(current context size), "
                    f"Completion {token_usage.completion_tokens:,}"
                )

        # Increment loop counter for Agent Loop tracking
        current_loops = state.get("loops", 0)
        updates = {
            "messages": [output],
            "loops": current_loops + 1,
            # Clear one-time reminders (used in this turn, no longer needed)
            "new_uploaded_files": [],  # File upload reminder shown once
            "new_mentioned_agents": [],  # @mention reminder shown once
            # Update token tracking
            "cumulative_prompt_tokens": cumulative_prompt_tokens,
            "cumulative_completion_tokens": cumulative_completion_tokens,
            "last_prompt_tokens": token_usage.prompt_tokens if context_manager and token_usage else 0,
            # Reset auto-compression flag (set to False if no compression happened)
            "auto_compressed_this_request": False,
        }

        log_node_exit(LOGGER, "planner", updates)
        return updates

    return planner_node
