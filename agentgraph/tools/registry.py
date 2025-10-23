"""Tool metadata management and registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from langchain_core.tools import BaseTool


@dataclass(frozen=True, slots=True)
class ToolMeta:
    """Describes governance attributes for a tool."""

    name: str
    risk: str
    tags: List[str]
    always_available: bool = False


class ToolRegistry:
    """Tracks tool instances and governance metadata."""

    def __init__(self, tools: Optional[Iterable[BaseTool]] = None, meta: Optional[Iterable[ToolMeta]] = None) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._meta: Dict[str, ToolMeta] = {}
        if tools:
            for tool in tools:
                self.register_tool(tool)
        if meta:
            for item in meta:
                self.register_meta(item)

    def register_tool(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def register_meta(self, metadata: ToolMeta) -> None:
        self._meta[metadata.name] = metadata

    def get_tool(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def get_meta(self, name: str) -> ToolMeta:
        if name not in self._meta:
            raise KeyError(f"Missing metadata for tool: {name}")
        return self._meta[name]

    def get_meta_optional(self, name: str) -> ToolMeta | None:
        return self._meta.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def list_global_tools(self) -> List[BaseTool]:
        return [self._tools[item.name] for item in self._meta.values() if item.always_available]

    def allowed_tools(self, allowlist: Optional[Iterable[str]]) -> List[BaseTool]:
        if not allowlist:
            return []
        return [self._tools[name] for name in allowlist if name in self._tools]
