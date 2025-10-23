"""Skill metadata loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import yaml

from .schema import SkillMeta


def load_skill_from_file(path: Path) -> SkillMeta:
    """Load a SKILL.yaml document into `SkillMeta`."""

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    meta = SkillMeta.model_validate(data)
    meta.path = path.parent
    return meta


def load_skills_directory(root: Path) -> Dict[str, SkillMeta]:
    """Load all skills from a directory tree."""

    registry: Dict[str, SkillMeta] = {}
    if not root.exists():
        return registry

    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue
        skill_manifest = candidate / "SKILL.yaml"
        if not skill_manifest.exists():
            continue
        meta = load_skill_from_file(skill_manifest)
        registry[meta.id] = meta
    return registry
