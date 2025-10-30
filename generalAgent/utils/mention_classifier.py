"""Classifier for @mention types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from generalAgent.tools import ToolRegistry
from generalAgent.skills import SkillRegistry

# Type hint for optional agent_registry (避免循环导入)
try:
    from generalAgent.agents.registry import AgentRegistry
except ImportError:
    AgentRegistry = None


@dataclass
class MentionClassification:
    """Classification result for a @mention."""

    name: str
    type: str  # "tool" | "skill" | "agent" | "unknown"
    needs_loading: bool = False  # For tools/agents: whether on-demand loading is needed


def classify_mentions(
    mentions: List[str],
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
    agent_registry=None,  # Optional AgentRegistry
) -> List[MentionClassification]:
    """Classify each @mention as tool, skill, agent, or unknown.

    Classification priority:
    1. Tool (already registered or discoverable)
    2. Skill (registered in skill registry)
    3. Agent (registered in agent registry or special keywords)
    4. Unknown

    Args:
        mentions: List of @mentioned names
        tool_registry: Tool registry for checking tools
        skill_registry: Skill registry for checking skills
        agent_registry: Agent registry for checking agents (optional)

    Returns:
        List of classifications

    Examples:
        >>> mentions = ["calc", "pdf", "simple", "unknown"]
        >>> classify_mentions(mentions, tool_reg, skill_reg, agent_reg)
        [
            MentionClassification("calc", "tool", needs_loading=False),
            MentionClassification("pdf", "skill"),
            MentionClassification("simple", "agent", needs_loading=False),
            MentionClassification("unknown", "unknown"),
        ]
    """
    classifications = []

    for mention in mentions:
        classification = classify_single_mention(
            mention, tool_registry, skill_registry, agent_registry
        )
        classifications.append(classification)

    return classifications


def classify_single_mention(
    mention: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
    agent_registry=None,  # Optional AgentRegistry
) -> MentionClassification:
    """Classify a single @mention.

    Args:
        mention: Mentioned name
        tool_registry: Tool registry
        skill_registry: Skill registry
        agent_registry: Agent registry (optional)

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

    # 3. Check if it's a skill
    skill_meta = skill_registry.get(mention)
    if skill_meta is not None:
        return MentionClassification(mention, "skill")

    # 4. Check if it's an agent (new!)
    if agent_registry is not None:
        # Check if it's a registered agent
        if agent_registry.is_enabled(mention):
            return MentionClassification(mention, "agent", needs_loading=False)

        # Check if it's a discoverable agent (can be loaded on-demand)
        if agent_registry.is_discovered(mention):
            return MentionClassification(mention, "agent", needs_loading=True)

    # 5. Check if it's a legacy agent keyword (for backward compatibility)
    if mention.lower() in ("agent", "subagent", "delegate_task"):
        return MentionClassification(mention, "agent")

    # 6. Unknown
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
