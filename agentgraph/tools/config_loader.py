"""Tool configuration loader."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from .registry import ToolMeta

LOGGER = logging.getLogger(__name__)


class ToolConfig:
    """Tool configuration manager."""

    def __init__(self, config_path: Path):
        """Load tool configuration from YAML file.

        Args:
            config_path: Path to tools.yaml configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load and parse YAML configuration."""
        if not self.config_path.exists():
            LOGGER.warning(f"Tools config not found: {self.config_path}, using defaults")
            return self._default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                LOGGER.info(f"Loaded tools configuration from {self.config_path}")
                return config or {}
        except Exception as e:
            LOGGER.error(f"Failed to load tools config: {e}, using defaults")
            return self._default_config()

    def _default_config(self) -> dict:
        """Return default configuration if file not found."""
        return {
            "core": {
                "now": {"category": "meta", "tags": ["meta"]},
                "calc": {"category": "compute", "tags": ["compute"]},
                "format_json": {"category": "meta", "tags": ["meta"]},
                "todo_write": {"category": "meta", "tags": ["meta"]},
                "todo_read": {"category": "meta", "tags": ["meta"]},
                "call_subagent": {"category": "agent", "tags": ["agent"]},
            },
            "optional": {},
            "directories": {
                "builtin": "agentgraph/tools/builtin",
                "custom": "agentgraph/tools/custom"
            }
        }

    def get_core_tools(self) -> List[str]:
        """Get list of core tool names (always enabled).

        Returns:
            List of core tool names
        """
        core = self.config.get("core", {})
        # Support both dict format (new) and list format (legacy)
        if isinstance(core, dict):
            return list(core.keys())
        return core if isinstance(core, list) else []

    def get_enabled_optional_tools(self) -> List[str]:
        """Get list of enabled optional tool names.

        Returns:
            List of enabled optional tool names
        """
        optional = self.config.get("optional", {})
        enabled = []

        for tool_name, settings in optional.items():
            if isinstance(settings, dict) and settings.get("enabled", False):
                enabled.append(tool_name)

        return enabled

    def get_all_enabled_tools(self) -> Set[str]:
        """Get set of all enabled tool names (core + optional).

        Returns:
            Set of enabled tool names
        """
        core = set(self.get_core_tools())
        optional = set(self.get_enabled_optional_tools())
        return core | optional

    def is_always_available(self, tool_name: str) -> bool:
        """Check if a tool should always be available in tool list.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool should always be available, False otherwise
        """
        # Core tools are always available
        if tool_name in self.get_core_tools():
            return True

        # Check optional tool settings
        optional = self.config.get("optional", {})
        if tool_name in optional:
            settings = optional[tool_name]
            if isinstance(settings, dict):
                return settings.get("always_available", False)

        return False

    def get_builtin_directory(self) -> Path:
        """Get path to builtin tools directory.

        Returns:
            Path to builtin tools directory
        """
        dirs = self.config.get("directories", {})
        builtin = dirs.get("builtin", "agentgraph/tools/builtin")
        return Path(builtin)

    def get_custom_directory(self) -> Path:
        """Get path to custom tools directory.

        Returns:
            Path to custom tools directory
        """
        dirs = self.config.get("directories", {})
        custom = dirs.get("custom", "agentgraph/tools/custom")
        return Path(custom)

    def get_scan_directories(self) -> List[Path]:
        """Get list of directories to scan for tools.

        Returns:
            List of paths to scan (builtin first, then custom for override)
        """
        return [
            self.get_builtin_directory(),
            self.get_custom_directory()
        ]

    def get_tool_metadata(self, tool_name: str) -> Optional[ToolMeta]:
        """Get metadata for a tool from configuration.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolMeta if found, None otherwise
        """
        # Check core tools
        core = self.config.get("core", {})
        if isinstance(core, dict) and tool_name in core:
            tool_config = core[tool_name]
            if isinstance(tool_config, dict):
                return ToolMeta(
                    name=tool_name,
                    risk=tool_config.get("category", "unknown"),
                    tags=tool_config.get("tags", []),
                    always_available=True,  # Core tools are always available
                )

        # Check optional tools
        optional = self.config.get("optional", {})
        if tool_name in optional:
            tool_config = optional[tool_name]
            if isinstance(tool_config, dict):
                return ToolMeta(
                    name=tool_name,
                    risk=tool_config.get("category", "unknown"),
                    tags=tool_config.get("tags", []),
                    always_available=tool_config.get("always_available", False),
                )

        return None

    def get_all_tool_metadata(self) -> List[ToolMeta]:
        """Get metadata for all enabled tools.

        Returns:
            List of ToolMeta for all enabled tools
        """
        metadata = []

        # Add core tools metadata
        core = self.config.get("core", {})
        if isinstance(core, dict):
            for tool_name, tool_config in core.items():
                if isinstance(tool_config, dict):
                    metadata.append(ToolMeta(
                        name=tool_name,
                        risk=tool_config.get("category", "unknown"),
                        tags=tool_config.get("tags", []),
                        always_available=True,
                    ))

        # Add enabled optional tools metadata
        optional = self.config.get("optional", {})
        for tool_name, tool_config in optional.items():
            if isinstance(tool_config, dict) and tool_config.get("enabled", False):
                metadata.append(ToolMeta(
                    name=tool_name,
                    risk=tool_config.get("category", "unknown"),
                    tags=tool_config.get("tags", []),
                    always_available=tool_config.get("always_available", False),
                ))

        return metadata


def load_tool_config(config_path: Path | None = None) -> ToolConfig:
    """Load tool configuration from file.

    Args:
        config_path: Path to config file (defaults to agentgraph/config/tools.yaml)

    Returns:
        ToolConfig instance
    """
    if config_path is None:
        config_path = Path("agentgraph/config/tools.yaml")

    return ToolConfig(config_path)
