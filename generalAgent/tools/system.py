"""Tools that depend on runtime registries."""

from __future__ import annotations

from typing import List

from generalAgent.skills import SkillRegistry


def build_skill_tools(skill_registry: SkillRegistry) -> List:
    """Create discovery tools bound to the skill registry.

    Note: Skills are now accessed by reading SKILL.md files directly via Read tool.
    This function remains for backward compatibility but returns empty list.
    """
    return []
