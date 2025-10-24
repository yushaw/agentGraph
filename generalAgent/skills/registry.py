"""Skill registry supporting discovery and progressive disclosure."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .loader import load_skills_directory
from .schema import SkillListItem, SkillMeta

LOGGER = logging.getLogger(__name__)


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

    def ensure_dependencies(self, skill_id: str) -> tuple[bool, str]:
        """Check and install skill dependencies if needed.

        Args:
            skill_id: Skill identifier

        Returns:
            (success, message): Installation status and message
        """
        skill = self.get(skill_id)
        if not skill or not skill.path:
            return False, f"Skill not found: {skill_id}"

        # Check if already installed
        if skill.dependencies_installed:
            LOGGER.debug(f"Dependencies for skill '{skill_id}' already installed")
            return True, "Dependencies already installed"

        # Check for requirements.txt
        requirements_file = skill.path / "requirements.txt"
        if not requirements_file.exists():
            LOGGER.debug(f"No requirements.txt for skill '{skill_id}'")
            skill.dependencies_installed = True  # Mark as done (no deps needed)
            return True, "No dependencies required"

        # Install dependencies
        LOGGER.info(f"Installing dependencies for skill '{skill_id}' from {requirements_file}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)],
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes timeout
            )

            if result.returncode != 0:
                error_msg = f"Failed to install dependencies:\n{result.stderr}"
                LOGGER.error(f"Skill '{skill_id}': {error_msg}")
                return False, error_msg

            # Mark as installed
            skill.dependencies_installed = True
            LOGGER.info(f"Successfully installed dependencies for skill '{skill_id}'")
            return True, "Dependencies installed successfully"

        except subprocess.TimeoutExpired:
            error_msg = "Dependency installation timeout (120s)"
            LOGGER.error(f"Skill '{skill_id}': {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Dependency installation error: {e}"
            LOGGER.error(f"Skill '{skill_id}': {error_msg}")
            return False, error_msg
