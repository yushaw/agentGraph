"""Skill metadata schema definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    """Declarative metadata describing a skill bundle."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    version: str = Field(default="0.1.0")
    inputs_schema: Optional[Dict[str, Any]] = None
    allowed_tools: Optional[List[str]] = None
    path: Optional[Path] = None


class SkillListItem(BaseModel):
    """Lightweight representation returned in discovery."""

    id: str
    name: str
    description: str
    version: str
