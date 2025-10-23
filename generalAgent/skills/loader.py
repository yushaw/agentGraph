"""Skill metadata loading utilities.

Supports both SKILL.yaml (legacy) and SKILL.md (Claude Code format).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import yaml

from .schema import SkillMeta

LOGGER = logging.getLogger(__name__)


def load_skill_from_file(path: Path) -> SkillMeta:
    """Load a SKILL.yaml document into `SkillMeta` (legacy format)."""

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    meta = SkillMeta.model_validate(data)
    meta.path = path.parent
    return meta


def load_skills_directory(root: Path) -> Dict[str, SkillMeta]:
    """Load all skills from a directory tree.

    Supports both SKILL.yaml (legacy) and SKILL.md (preferred).
    SKILL.md takes precedence if both exist.
    """
    from .md_loader import load_skill_from_md

    registry: Dict[str, SkillMeta] = {}
    if not root.exists():
        return registry

    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue

        # Prefer SKILL.md over SKILL.yaml
        skill_md = candidate / "SKILL.md"
        skill_yaml = candidate / "SKILL.yaml"

        if skill_md.exists():
            try:
                meta = load_skill_from_md(skill_md)
                registry[meta.id] = meta
                LOGGER.debug(f"Loaded skill '{meta.id}' from SKILL.md")
            except Exception as e:
                LOGGER.warning(f"Failed to load {skill_md}: {e}")
        elif skill_yaml.exists():
            try:
                meta = load_skill_from_file(skill_yaml)
                registry[meta.id] = meta
                LOGGER.debug(f"Loaded skill '{meta.id}' from SKILL.yaml (legacy)")
            except Exception as e:
                LOGGER.warning(f"Failed to load {skill_yaml}: {e}")

    return registry
