"""Skill metadata schema definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    """Declarative metadata describing a skill bundle.

    Skills are knowledge packages containing:
    - Documentation (SKILL.md, reference.md, etc.)
    - Utility scripts (scripts/ directory)
    - Supporting assets

    Skills do NOT contain LangChain tools. The model accesses skills
    via Read tool (for docs) and Bash tool (for scripts).
    """

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    version: str = Field(default="0.1.0")
    path: Optional[Path] = None
    # Removed: inputs_schema, allowed_tools (legacy concepts)


class SkillListItem(BaseModel):
    """Lightweight representation returned in discovery."""

    id: str
    name: str
    description: str
    version: str
