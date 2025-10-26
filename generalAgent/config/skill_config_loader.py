"""Skill configuration loader.

Loads and parses skills.yaml configuration file.
"""

from pathlib import Path
from typing import Dict, List, Optional

import yaml


class SkillConfig:
    """Skill configuration manager."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize skill config.

        Args:
            config_path: Path to skills.yaml file
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        if not self.config_path or not self.config_path.exists():
            return self._default_config()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                return config
        except Exception as e:
            print(f"Warning: Failed to load skills config: {e}")
            return self._default_config()

    def _default_config(self) -> dict:
        """Default configuration if file not found."""
        return {
            "global": {
                "enabled": True,
                "auto_load_on_file_upload": True,
            },
            "core": [],
            "optional": {},
            "directories": {
                "builtin": "generalAgent/skills",
            },
        }

    def is_enabled(self) -> bool:
        """Check if skills system is globally enabled."""
        return self.config.get("global", {}).get("enabled", True)

    def auto_load_on_file_upload(self) -> bool:
        """Check if auto-load on file upload is enabled."""
        return self.config.get("global", {}).get("auto_load_on_file_upload", True)

    def get_core_skills(self) -> List[str]:
        """Get list of core skills (always loaded)."""
        return self.config.get("core", [])

    def get_enabled_skills(self) -> List[str]:
        """Get list of enabled skills.

        Returns:
            List of skill IDs that are enabled in config
        """
        enabled = []

        # Add core skills
        enabled.extend(self.get_core_skills())

        # Add enabled optional skills
        optional = self.config.get("optional", {})
        for skill_id, skill_config in optional.items():
            if skill_config.get("enabled", False):
                enabled.append(skill_id)

        return enabled

    def get_skill_config(self, skill_id: str) -> Optional[Dict]:
        """Get configuration for a specific skill.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill configuration dict or None if not found
        """
        # Check core skills
        if skill_id in self.get_core_skills():
            return {"enabled": True, "always_available": True}

        # Check optional skills
        optional = self.config.get("optional", {})
        return optional.get(skill_id)

    def is_skill_enabled(self, skill_id: str) -> bool:
        """Check if a skill is enabled in config.

        Args:
            skill_id: Skill identifier

        Returns:
            True if skill is enabled
        """
        config = self.get_skill_config(skill_id)
        if not config:
            return False
        return config.get("enabled", False) or skill_id in self.get_core_skills()

    def get_skills_for_file_type(self, file_type: str) -> List[str]:
        """Get skills that should be auto-loaded for a file type.

        Args:
            file_type: File type (e.g., "pdf", "xlsx")

        Returns:
            List of skill IDs to load
        """
        if not self.auto_load_on_file_upload():
            return []

        skills = []
        optional = self.config.get("optional", {})

        for skill_id, skill_config in optional.items():
            auto_load_types = skill_config.get("auto_load_on_file_types", [])
            if file_type.lower() in [t.lower() for t in auto_load_types]:
                skills.append(skill_id)

        return skills

    def get_builtin_directory(self) -> str:
        """Get builtin skills directory path."""
        return self.config.get("directories", {}).get(
            "builtin", "generalAgent/skills"
        )


def load_skill_config(config_path: Optional[Path] = None) -> SkillConfig:
    """Load skill configuration.

    Args:
        config_path: Optional path to skills.yaml

    Returns:
        SkillConfig instance
    """
    return SkillConfig(config_path)
