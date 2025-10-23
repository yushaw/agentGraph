"""Planner node implementation - Charlie MVP Edition."""

from __future__ import annotations

import logging
from typing import Iterable, List

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import BaseTool

from agentgraph.agents import ModelResolver, invoke_planner
from agentgraph.graph.message_utils import clean_message_history, truncate_messages_safely
from agentgraph.graph.prompts import PLANNER_SYSTEM_PROMPT, SUBAGENT_SYSTEM_PROMPT, build_dynamic_reminder, build_skills_catalog
from agentgraph.graph.state import AppState
from agentgraph.models import ModelRegistry
from agentgraph.tools import ToolRegistry
from agentgraph.utils.logging_utils import (
    log_node_entry,
    log_node_exit,
    log_visible_tools,
    log_prompt,
    log_model_selection,
)
from agentgraph.utils.error_handler import with_error_boundary, handle_model_error, ModelInvocationError
from agentgraph.utils.mention_classifier import classify_mentions, group_by_type

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
        if isinstance(content, str):
            if "```" in content:
                has_code = True

    return has_images, has_code


def build_planner_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: Iterable[BaseTool],
    skill_registry,
):
    """Create a planner node bound to runtime registries."""

    persistent_global_tools = list(persistent_global_tools)

    @with_error_boundary("planner")
    async def planner_node(state: AppState) -> AppState:
        log_node_entry(LOGGER, "planner", state)

        # ========== Assemble visible tools ==========
        visible_tools: List[BaseTool] = list(persistent_global_tools)
        LOGGER.info("Building visible tools...")
        LOGGER.info(f"  - Starting with {len(persistent_global_tools)} persistent global tools")

        # Process @mentions (tools, skills, agents)
        mentioned = state.get("mentioned_agents", [])
        grouped_mentions = {"tools": [], "skills": [], "agents": [], "unknown": []}

        if mentioned:
            LOGGER.info(f"  - Processing @mentions: {mentioned}")

            # Classify mentions by type
            classifications = classify_mentions(mentioned, tool_registry, skill_registry)
            grouped_mentions = group_by_type(classifications)

            LOGGER.info(f"    - Tools: {grouped_mentions['tools']}")
            LOGGER.info(f"    - Skills: {grouped_mentions['skills']}")
            LOGGER.info(f"    - Agents: {grouped_mentions['agents']}")
            if grouped_mentions['unknown']:
                LOGGER.warning(f"    - Unknown: {grouped_mentions['unknown']}")

            # Handle @tool mentions (load and add to visible_tools)
            for tool_name in grouped_mentions['tools']:
                try:
                    tool = tool_registry.get_tool(tool_name)
                    visible_tools.append(tool)
                    LOGGER.info(f"    ✓ @{tool_name} → tool (already loaded)")
                except KeyError:
                    try:
                        tool = tool_registry.load_on_demand(tool_name)
                        visible_tools.append(tool)
                        LOGGER.info(f"    ✓ @{tool_name} → tool (loaded on-demand)")
                    except KeyError:
                        LOGGER.error(f"    ✗ @{tool_name} classification error")

            # Handle @agent mentions (ensure call_subagent is available)
            if grouped_mentions['agents']:
                LOGGER.info(f"    📢 @agent mentioned, ensuring call_subagent is available")
                try:
                    subagent_tool = tool_registry.get_tool("call_subagent")
                    if subagent_tool not in visible_tools:
                        visible_tools.append(subagent_tool)
                        LOGGER.info(f"    ✓ Added call_subagent for @agent mentions")
                except KeyError:
                    LOGGER.warning(f"    ✗ call_subagent not found in registry")

            # Handle @skill mentions (will be passed to prompt via reminder)
            # Skills are handled in build_dynamic_reminder(), no action needed here
            if grouped_mentions['skills']:
                LOGGER.info(f"    📚 @skill mentions will be handled via system reminder")

        # Deduplicate
        deduped: List[BaseTool] = []
        seen = set()
        for tool in visible_tools:
            if tool.name in seen:
                continue
            seen.add(tool.name)
            deduped.append(tool)
        visible_tools = deduped
        LOGGER.info(f"  - Final tool count after deduplication: {len(visible_tools)}")

        # ========== Subagent tool filtering ==========
        # Subagents should NOT have access to call_subagent (prevent nesting)
        context_id = state.get("context_id", "main")
        is_subagent = context_id != "main" and context_id.startswith("subagent-")

        if is_subagent:
            # Remove call_subagent from visible tools
            visible_tools = [t for t in visible_tools if t.name != "call_subagent"]
            LOGGER.info(f"  - Subagent context detected, removed 'call_subagent' tool")
            LOGGER.info(f"  - Subagent tool count: {len(visible_tools)}")

        # ========== Detect capabilities needed ==========
        need_code = False
        need_vision = False
        LOGGER.info("Detecting capability requirements from tools...")
        for tool in visible_tools:
            metadata = tool_registry.get_meta_optional(tool.name)
            if metadata:
                if "code" in metadata.tags:
                    need_code = True
                if "vision" in metadata.tags:
                    need_vision = True
        LOGGER.info(f"  - need_code: {need_code}, need_vision: {need_vision}")

        # ========== Detect multimodal input ==========
        history: List[BaseMessage] = list(state.get("messages") or [])
        has_images, has_code = _detect_multimodal_input(history)
        LOGGER.info(f"Multimodal input detected: has_images={has_images}, has_code={has_code}")

        # Override model preference if images detected
        preference = state.get("model_pref")
        if has_images and not preference:
            preference = "vision"
            LOGGER.info(f"  - Model preference set to 'vision' due to image input")

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

        # Clean and safely truncate message history (keep last 20 for planner - token optimization)
        cleaned_history = clean_message_history(history)
        recent_history = truncate_messages_safely(cleaned_history, keep_recent=20)
        LOGGER.info(f"  - Message history: {len(history)} → {len(cleaned_history)} (cleaned) → {len(recent_history)} (kept)")

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
                # Build detailed reminder
                todo_lines = []
                if in_progress:
                    todo_lines.append(f"当前进行中: {in_progress[0].get('content')}")
                if pending:
                    pending_list = [t.get('content', '') for t in pending[:3]]  # Show first 3
                    todo_lines.append(f"待办任务 ({len(pending)} 个): {', '.join(pending_list)}")
                if completed:
                    todo_lines.append(f"已完成: {len(completed)} 个")

                # Strong reminder to prevent early stopping
                todo_reminder = f"""<system_reminder>
⚠️ 任务进度追踪: {', '.join(todo_lines)}

你还有 {len(incomplete)} 个未完成任务！
- 请使用 todo_read 工具检查详细状态
- 完成所有任务后再停止（不调用工具）
- 不要过早停止！
</system_reminder>"""
                LOGGER.info(f"  - Todo reminder: {len(incomplete)} incomplete, {len(completed)} completed")
            elif completed:
                # All tasks completed
                todo_reminder = f"<system_reminder>✅ 所有 {len(completed)} 个任务已完成！可以输出最终结果。</system_reminder>"
                LOGGER.info(f"  - Todo reminder: All {len(completed)} tasks completed")

        # Choose prompt based on context (main agent or subagent)
        context_id = state.get("context_id", "main")
        is_subagent = context_id != "main" and context_id.startswith("subagent-")

        if is_subagent:
            # Subagent: use task-focused prompt, no reminders
            base_prompt = SUBAGENT_SYSTEM_PROMPT
            LOGGER.info(f"  - Using SUBAGENT prompt for context: {context_id}")
        else:
            # Main agent: use conversational prompt with reminders
            base_prompt = PLANNER_SYSTEM_PROMPT

            # Add skills catalog (model-invoked pattern)
            skills_catalog = build_skills_catalog(skill_registry)
            if skills_catalog:
                base_prompt = f"{base_prompt}\n\n{skills_catalog}"
                LOGGER.info(f"  - Skills catalog added ({len(skill_registry.list_meta())} skills)")

            # Add dynamic reminders
            reminders = [r for r in [dynamic_reminder, todo_reminder] if r]
            if reminders:
                base_prompt = f"{base_prompt}\n\n{chr(10).join(reminders)}"
                LOGGER.info(f"  - Reminders added: {len(reminders)} reminder(s)")

        # Log the full system prompt
        log_prompt(LOGGER, "planner", base_prompt)

        # Log visible tools
        log_visible_tools(LOGGER, "planner", visible_tools)

        prompt_messages = [SystemMessage(content=base_prompt), *recent_history]

        # ========== Invoke planner ==========
        LOGGER.info(f"Invoking planner (need_code={need_code or has_code}, need_vision={has_images}, preference={preference})...")

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
