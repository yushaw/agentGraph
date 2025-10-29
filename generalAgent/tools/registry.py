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
    available_to_subagent: bool = False  # Whether subagent can use this tool


class ToolRegistry:
    """Tracks tool instances and governance metadata."""

    def __init__(self, tools: Optional[Iterable[BaseTool]] = None, meta: Optional[Iterable[ToolMeta]] = None) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._meta: Dict[str, ToolMeta] = {}
        self._discovered: Dict[str, BaseTool] = {}  # All discovered tools (for on-demand loading)
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
        return [self._tools[item.name] for item in self._meta.values() if item.available_to_subagent]

    def allowed_tools(self, allowlist: Optional[Iterable[str]]) -> List[BaseTool]:
        if not allowlist:
            return []
        return [self._tools[name] for name in allowlist if name in self._tools]

    def register_discovered(self, tool: BaseTool) -> None:
        """Register a discovered tool (may not be enabled yet).

        This is used to keep track of all scanned tools for on-demand loading.
        """
        self._discovered[tool.name] = tool

    def is_discovered(self, tool_name: str) -> bool:
        """Check if a tool was discovered during scan.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is in discovered pool (registered or discoverable)
        """
        return tool_name in self._tools or tool_name in self._discovered

    def load_on_demand(self, tool_name: str) -> BaseTool:
        """Load a tool on-demand from discovered tools.

        This is used when a user @mentions a tool that wasn't enabled at startup.

        Args:
            tool_name: Name of the tool to load

        Returns:
            Tool instance

        Raises:
            KeyError: If tool was not discovered during scan
        """
        if tool_name in self._tools:
            # Already registered, return it
            return self._tools[tool_name]

        if tool_name not in self._discovered:
            raise KeyError(f"Tool not found in discovered tools: {tool_name}")

        # Load from discovered pool
        tool = self._discovered[tool_name]
        self.register_tool(tool)
        return tool
