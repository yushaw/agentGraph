"""Tool scanner for automatic discovery and loading."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.tools import BaseTool

LOGGER = logging.getLogger(__name__)


def scan_tools_directory(directory: Path) -> Dict[str, BaseTool]:
    """Scan a directory for tool modules and load them.

    Each tool file should:
    - Be a .py file (not __init__.py or __pycache__)
    - Define a tool using @tool decorator
    - Export the tool in __all__ or as a module-level variable

    Args:
        directory: Directory to scan for tool files

    Returns:
        Dict mapping tool names to tool instances

    Example:
        tools = scan_tools_directory(Path("generalAgent/tools/builtin"))
        # Returns: {"now": <now_tool>, "calc": <calc_tool>, ...}
    """
    tools = {}

    if not directory.exists():
        LOGGER.warning(f"Tools directory does not exist: {directory}")
        return tools

    if not directory.is_dir():
        LOGGER.warning(f"Tools path is not a directory: {directory}")
        return tools

    LOGGER.info(f"Scanning tools directory: {directory}")

    # Get all .py files (exclude __init__.py and __pycache__)
    tool_files = [
        f for f in directory.glob("*.py")
        if f.stem != "__init__" and not f.stem.startswith("_")
    ]

    for tool_file in tool_files:
        try:
            # Build full module path (e.g., agentgraph.tools.builtin.call_subagent)
            # This ensures we use the same module instance if it's already imported
            module_name = tool_file.stem

            # Try to construct module path from directory structure
            # Assume directory is like .../agentgraph/tools/builtin
            # We need to find where "agentgraph" starts
            parts = directory.resolve().parts
            agentgraph_idx = None
            for i, part in enumerate(parts):
                if part == "agentgraph":
                    agentgraph_idx = i
                    break

            if agentgraph_idx is not None:
                # Build module path: agentgraph.tools.builtin.module_name
                module_parts = parts[agentgraph_idx:] + (module_name,)
                full_module_path = ".".join(module_parts)
            else:
                # Fallback: just use module_name
                full_module_path = module_name

            # Try to import using full path first (reuses existing import)
            try:
                module = importlib.import_module(full_module_path)
                LOGGER.debug(f"  Reused existing import: {full_module_path}")
            except (ImportError, ModuleNotFoundError):
                # Fall back to dynamic loading if not already imported
                spec = importlib.util.spec_from_file_location(full_module_path, tool_file)
                if spec is None or spec.loader is None:
                    LOGGER.warning(f"Could not load spec for {tool_file}")
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[full_module_path] = module
                spec.loader.exec_module(module)
                LOGGER.debug(f"  Dynamically loaded: {full_module_path}")

            # Find tool(s) in module
            tool_instances = _extract_tools_from_module(module, module_name)

            if tool_instances:
                for tool_instance in tool_instances:
                    tools[tool_instance.name] = tool_instance
                    LOGGER.info(f"  ✓ Loaded tool: {tool_instance.name} from {tool_file.name}")
            else:
                LOGGER.warning(f"  ✗ No tool found in {tool_file.name}")

        except Exception as e:
            LOGGER.error(f"  ✗ Failed to load {tool_file.name}: {e}")

    LOGGER.info(f"Loaded {len(tools)} tools from {directory}")
    return tools


def _extract_tools_from_module(module, module_name: str) -> List[BaseTool]:
    """Extract tool instance(s) from a module.

    Tries multiple strategies:
    1. Look for __all__ export (can return multiple tools)
    2. Look for variable matching module name
    3. Look for any BaseTool instance

    Args:
        module: The imported module
        module_name: Name of the module (for fallback matching)

    Returns:
        List of tool instances found (may be empty, single, or multiple)
    """
    tools = []

    # Strategy 1: Check __all__ (can have multiple tools)
    if hasattr(module, "__all__"):
        for name in module.__all__:
            obj = getattr(module, name, None)
            if obj and isinstance(obj, BaseTool):
                tools.append(obj)

        # If we found tools via __all__, return them (may be multiple)
        if tools:
            return tools

    # Strategy 2: Check for variable matching module name
    obj = getattr(module, module_name, None)
    if obj and isinstance(obj, BaseTool):
        return [obj]

    # Strategy 3: Find any BaseTool instance
    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        obj = getattr(module, attr_name)
        if isinstance(obj, BaseTool):
            # Only return the first one found to avoid duplicates
            return [obj]

    return []


def scan_multiple_directories(directories: List[Path]) -> Dict[str, BaseTool]:
    """Scan multiple directories and merge results.

    Later directories override earlier ones if tools have same name.

    Args:
        directories: List of directories to scan

    Returns:
        Merged dict of all discovered tools

    Example:
        tools = scan_multiple_directories([
            Path("generalAgent/tools/builtin"),
            Path("generalAgent/tools/custom"),
        ])
    """
    all_tools = {}

    for directory in directories:
        tools = scan_tools_directory(directory)
        # Later directories override
        all_tools.update(tools)

    return all_tools
