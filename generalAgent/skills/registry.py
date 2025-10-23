"""Skill registry supporting discovery and progressive disclosure."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .loader import load_skills_directory
from .schema import SkillListItem, SkillMeta


class SkillRegistry:
    """File-backed registry with optional in-memory seeding."""

    def __init__(self, root: Path, seeds: Optional[Iterable[SkillMeta]] = None) -> None:
        self.root = root
        self._cache: Dict[str, SkillMeta] = {}
        if seeds:
            for meta in seeds:
                self._cache[meta.id] = meta
        self.reload()

    def reload(self) -> None:
        """Refresh cache from disk."""

        if self.root.exists():
            self._cache.update(load_skills_directory(self.root))

    def list_meta(self) -> List[SkillListItem]:
        """Return lightweight skill cards for discovery."""

        return [
            SkillListItem(
                id=meta.id,
                name=meta.name,
                description=meta.description,
                version=meta.version,
            )
            for meta in self._cache.values()
        ]

    def get(self, skill_id: str) -> Optional[SkillMeta]:
        """Return full metadata for a skill."""

        return self._cache.get(skill_id)
