"""Skill detection helpers for model-invoked pattern."""

from __future__ import annotations

import logging
from typing import List, Optional, Set

from langchain_core.messages import AIMessage

LOGGER = logging.getLogger(__name__)


def detect_skill_from_tool_calls(tool_calls: List, skill_registry) -> Optional[str]:
    """Detect which skill should be activated based on tool calls.

    Model-invoked pattern: When the model calls tools belonging to a skill,
    automatically activate that skill to provide its tools.

    Args:
        tool_calls: List of tool call dictionaries from AIMessage
        skill_registry: SkillRegistry instance

    Returns:
        skill_id if a skill should be activated, None otherwise
    """
    if not tool_calls:
        return None

    # Get all tool names from this invocation
    called_tool_names = {tc.get("name") if isinstance(tc, dict) else tc.name
                         for tc in tool_calls}

    LOGGER.debug(f"Detecting skill from tool calls: {called_tool_names}")

    # Check each skill to see if its tools match
    for skill_meta in skill_registry.list_meta():
        skill = skill_registry.get(skill_meta.id)
        if not skill or not skill.allowed_tools:
            continue

        skill_tools = set(skill.allowed_tools)

        # If any called tool belongs to this skill, activate it
        if called_tool_names & skill_tools:
            LOGGER.info(f"  → Detected skill '{skill.id}' from tool calls: {called_tool_names & skill_tools}")
            return skill.id

    LOGGER.debug("  → No skill detected from tool calls")
    return None


def should_load_skill_tools(
    last_message: AIMessage,
    current_active_skill: Optional[str],
    skill_registry,
) -> tuple[bool, Optional[str], List[str]]:
    """Determine if skill tools should be loaded based on model's response.

    Args:
        last_message: Last message from the model
        current_active_skill: Currently active skill (if any)
        skill_registry: SkillRegistry instance

    Returns:
        (should_load, skill_id, allowed_tools):
            - should_load: True if tools need to be added
            - skill_id: The skill to activate
            - allowed_tools: List of tool names to make available
    """
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return False, None, []

    # Detect skill from tool calls
    detected_skill = detect_skill_from_tool_calls(last_message.tool_calls, skill_registry)

    if not detected_skill:
        return False, None, []

    # If skill already active, no need to reload
    if detected_skill == current_active_skill:
        LOGGER.debug(f"Skill '{detected_skill}' already active, no reload needed")
        return False, detected_skill, []

    # Load the skill's allowed tools
    skill = skill_registry.get(detected_skill)
    if not skill or not skill.allowed_tools:
        return False, None, []

    LOGGER.info(f"Activating skill '{detected_skill}' with tools: {skill.allowed_tools}")
    return True, detected_skill, skill.allowed_tools
