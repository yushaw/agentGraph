"""Project root path detection - works regardless of working directory."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Get absolute path to project root directory.

    This works by finding the directory containing 'generalAgent' package,
    regardless of the current working directory.

    Returns:
        Path: Absolute path to project root

    Example:
        >>> root = get_project_root()
        >>> config_file = root / "generalAgent" / "config" / "tools.yaml"
        >>> logs_dir = root / "logs"
    """
    # Start from this file's location
    current_file = Path(__file__).resolve()

    # Go up: project_root.py -> config/ -> generalAgent/ -> project_root/
    project_root = current_file.parent.parent.parent

    # Validate: check that generalAgent directory exists
    if not (project_root / "generalAgent").exists():
        raise RuntimeError(
            f"Could not locate project root. Expected 'generalAgent' directory at {project_root}"
        )

    return project_root


def resolve_project_path(relative_path: str | Path) -> Path:
    """Resolve a path relative to project root.

    Args:
        relative_path: Path relative to project root (e.g., "logs", "data/workspace")

    Returns:
        Path: Absolute path

    Example:
        >>> logs_dir = resolve_project_path("logs")
        >>> tools_config = resolve_project_path("generalAgent/config/tools.yaml")
    """
    return get_project_root() / relative_path


__all__ = ["get_project_root", "resolve_project_path"]
