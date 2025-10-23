"""Planner node implementation - Charlie MVP Edition."""

from __future__ import annotations

import logging
from typing import Iterable, List

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import BaseTool

from agentgraph.agents import ModelResolver, invoke_planner
from agentgraph.graph.message_utils import clean_message_history, truncate_messages_safely
from agentgraph.graph.prompts import PLANNER_SYSTEM_PROMPT, build_dynamic_reminder
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

        # Add tools from explicitly activated skills (via select_skill)
        allowed = state.get("allowed_tools")
        if allowed:
            allowed_count = len(tool_registry.allowed_tools(allowed))
            visible_tools.extend(tool_registry.allowed_tools(allowed))
            LOGGER.info(f"  - Added {allowed_count} tools from activated skills: {allowed}")

        # Add tools from @mentioned agents/skills/tools
        mentioned = state.get("mentioned_agents", [])
        if mentioned:
            LOGGER.info(f"  - Processing @mentions: {mentioned}")
            for mention in mentioned:
                # Try to find matching skill
                try:
                    skill = skill_registry.get(mention)
                    if skill and skill.allowed_tools:
                        # Add all tools from this skill
                        skill_tools = tool_registry.allowed_tools(skill.allowed_tools)
                        visible_tools.extend(skill_tools)
                        LOGGER.info(f"    - @{mention} → skill with {len(skill_tools)} tools: {skill.allowed_tools}")
                except (KeyError, AttributeError):
                    LOGGER.debug(f"    - @{mention} not found as skill")

                # Try to find matching tool directly
                try:
                    tool = tool_registry.get_tool(mention)
                    visible_tools.append(tool)
                    LOGGER.info(f"    - @{mention} → direct tool: {tool.name}")
                except KeyError:
                    LOGGER.debug(f"    - @{mention} not found as tool")

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
        mentioned_agents = state.get("mentioned_agents", [])

        LOGGER.info("Building system prompt...")
        dynamic_reminder = build_dynamic_reminder(
            active_skill=active_skill,
            mentioned_agents=mentioned_agents,
            has_images=has_images,
            has_code=has_code,
        )

        # Clean and safely truncate message history (keep last 20 for planner - token optimization)
        cleaned_history = clean_message_history(history)
        recent_history = truncate_messages_safely(cleaned_history, keep_recent=20)
        LOGGER.info(f"  - Message history: {len(history)} → {len(cleaned_history)} (cleaned) → {len(recent_history)} (kept)")

        # Construct prompt with dynamic reminder
        base_prompt = PLANNER_SYSTEM_PROMPT
        if dynamic_reminder:
            base_prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{dynamic_reminder}"
            LOGGER.info(f"  - Dynamic reminder added: {len(dynamic_reminder)} chars")

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
        updates = {"messages": [output]}
        log_node_exit(LOGGER, "planner", updates)
        return updates

    return planner_node
