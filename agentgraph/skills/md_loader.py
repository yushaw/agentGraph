"""SKILL.md Markdown + frontmatter loader.

Supports Claude Code's SKILL.md format with YAML frontmatter.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

import yaml

from .schema import SkillMeta


def parse_skill_md(content: str) -> tuple[dict, str]:
    """Parse SKILL.md content into frontmatter and body.

    Args:
        content: The full content of a SKILL.md file

    Returns:
        Tuple of (frontmatter_dict, markdown_body)

    Raises:
        ValueError: If frontmatter is missing or invalid
    """
    # Match YAML frontmatter (--- ... ---)
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter (--- ... ---)")

    frontmatter_str = match.group(1)
    body = match.group(2).strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise ValueError("Frontmatter must be a YAML dictionary")

    return frontmatter, body


def load_skill_from_md(path: Path) -> SkillMeta:
    """Load a SKILL.md file into SkillMeta.

    Args:
        path: Path to SKILL.md file

    Returns:
        SkillMeta instance with frontmatter metadata

    Note:
        The markdown body is NOT loaded into memory (progressive loading).
        Use read_skill_content() to load the body when needed.
    """
    with path.open("r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, _ = parse_skill_md(content)

    # Validate required fields
    if "name" not in frontmatter:
        raise ValueError(f"SKILL.md missing required field 'name': {path}")
    if "description" not in frontmatter:
        raise ValueError(f"SKILL.md missing required field 'description': {path}")

    # Map frontmatter to SkillMeta schema
    # Skills only need: id, name, description, version, path
    # No allowed_tools or inputs_schema (those were legacy concepts)

    meta_data = {
        "id": frontmatter.get("id", path.parent.name),  # Default to directory name
        "name": frontmatter["name"],
        "description": frontmatter["description"],
        "version": frontmatter.get("version", "0.1.0"),
        "path": path.parent,
    }

    return SkillMeta.model_validate(meta_data)


def read_skill_content(skill_path: Path) -> str:
    """Read the markdown body of a SKILL.md file (progressive loading).

    Args:
        skill_path: Path to the skill directory (containing SKILL.md)

    Returns:
        The markdown content (without frontmatter)
    """
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md not found: {skill_md}")

    with skill_md.open("r", encoding="utf-8") as f:
        content = f.read()

    _, body = parse_skill_md(content)
    return body


def load_skills_directory_md(root: Path) -> Dict[str, SkillMeta]:
    """Load all SKILL.md files from a directory tree.

    Args:
        root: Root directory to scan for skills

    Returns:
        Dictionary mapping skill_id -> SkillMeta

    Note:
        Only frontmatter is loaded; markdown bodies are loaded on-demand.
    """
    registry: Dict[str, SkillMeta] = {}

    if not root.exists():
        return registry

    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue

        skill_md = candidate / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            meta = load_skill_from_md(skill_md)
            registry[meta.id] = meta
        except Exception as e:
            # Log but don't fail on individual skill errors
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to load skill from {skill_md}: {e}"
            )

    return registry
