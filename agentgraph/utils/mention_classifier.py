"""Classifier for @mention types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from agentgraph.tools import ToolRegistry
from agentgraph.skills import SkillRegistry


@dataclass
class MentionClassification:
    """Classification result for a @mention."""

    name: str
    type: str  # "tool" | "skill" | "agent" | "unknown"
    needs_loading: bool = False  # For tools: whether on-demand loading is needed


def classify_mentions(
    mentions: List[str],
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
) -> List[MentionClassification]:
    """Classify each @mention as tool, skill, agent, or unknown.

    Classification priority:
    1. Tool (already registered or discoverable)
    2. Skill (registered in skill registry)
    3. Agent (special keyword: "agent" or specific agent names)
    4. Unknown

    Args:
        mentions: List of @mentioned names
        tool_registry: Tool registry for checking tools
        skill_registry: Skill registry for checking skills

    Returns:
        List of classifications

    Examples:
        >>> mentions = ["calc", "pdf", "agent", "unknown"]
        >>> classify_mentions(mentions, tool_reg, skill_reg)
        [
            MentionClassification("calc", "tool", needs_loading=False),
            MentionClassification("pdf", "skill"),
            MentionClassification("agent", "agent"),
            MentionClassification("unknown", "unknown"),
        ]
    """
    classifications = []

    for mention in mentions:
        classification = classify_single_mention(mention, tool_registry, skill_registry)
        classifications.append(classification)

    return classifications


def classify_single_mention(
    mention: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
) -> MentionClassification:
    """Classify a single @mention.

    Args:
        mention: Mentioned name
        tool_registry: Tool registry
        skill_registry: Skill registry

    Returns:
        Classification result
    """
    # 1. Check if it's a registered tool
    try:
        tool_registry.get_tool(mention)
        return MentionClassification(mention, "tool", needs_loading=False)
    except KeyError:
        pass

    # 2. Check if it's a discoverable tool (can be loaded on-demand)
    try:
        # Try to load on-demand (this will succeed if tool is in _discovered)
        # We use a peek method instead of actually loading
        if tool_registry.is_discovered(mention):
            return MentionClassification(mention, "tool", needs_loading=True)
    except AttributeError:
        # Fallback if is_discovered doesn't exist yet
        try:
            # Try loading (will register if successful)
            tool_registry.load_on_demand(mention)
            return MentionClassification(mention, "tool", needs_loading=True)
        except KeyError:
            pass

    # 3. Check if it's an agent keyword (before checking skills)
    if mention.lower() in ("agent", "subagent", "call_subagent"):
        return MentionClassification(mention, "agent")

    # 4. Check if it's a skill
    skill_meta = skill_registry.get(mention)
    if skill_meta is not None:
        return MentionClassification(mention, "skill")

    # 5. Unknown
    return MentionClassification(mention, "unknown")


def group_by_type(classifications: List[MentionClassification]) -> dict:
    """Group classifications by type.

    Args:
        classifications: List of classifications

    Returns:
        Dict with keys "tools", "skills", "agents", "unknown"

    Example:
        >>> result = group_by_type(classifications)
        >>> result["tools"]  # ["calc", "weather"]
        >>> result["skills"]  # ["pdf", "pptx"]
        >>> result["agents"]  # ["agent"]
    """
    result = {
        "tools": [],
        "skills": [],
        "agents": [],
        "unknown": [],
    }

    for classification in classifications:
        if classification.type == "tool":
            result["tools"].append(classification.name)
        elif classification.type == "skill":
            result["skills"].append(classification.name)
        elif classification.type == "agent":
            result["agents"].append(classification.name)
        else:
            result["unknown"].append(classification.name)

    return result
