"""Configuration loader and tool factory for MCP integration."""

import logging
from pathlib import Path
from typing import List

import yaml
from langchain_core.tools import BaseTool

from .manager import MCPServerManager
from .wrapper import MCPToolWrapper

LOGGER = logging.getLogger(__name__)


def load_mcp_config(config_path: Path) -> dict:
    """
    Load MCP configuration from YAML file.

    Args:
        config_path: Path to mcp_servers.yaml

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"MCP config not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not config:
        return {"servers": {}, "settings": {}}

    return config


def load_mcp_tools(config: dict, manager: MCPServerManager) -> List[BaseTool]:
    """
    Create MCP tool wrappers from configuration.

    This does NOT start servers - servers are started lazily on first tool call.

    Args:
        config: MCP configuration dict
        manager: MCPServerManager instance

    Returns:
        List of MCPToolWrapper instances
    """
    tools = []
    namespace_strategy = config.get("settings", {}).get("namespace_strategy", "alias")

    for server_id, server_cfg in config.get("servers", {}).items():
        # Skip disabled servers
        if not server_cfg.get("enabled", True):
            LOGGER.debug(f"  Skipping disabled MCP server: {server_id}")
            continue

        # Load tools from server config
        tools_config = server_cfg.get("tools", {})
        if not tools_config:
            LOGGER.warning(f"  No tools configured for MCP server: {server_id}")
            continue

        for tool_name, tool_cfg in tools_config.items():
            # Skip disabled tools
            if not tool_cfg.get("enabled", True):
                LOGGER.debug(f"    Skipping disabled tool: {server_id}.{tool_name}")
                continue

            # Determine final tool name
            final_name = _resolve_tool_name(
                server_id, tool_name, tool_cfg, namespace_strategy
            )

            # Get tool description
            description = tool_cfg.get(
                "description",
                f"MCP tool '{tool_name}' from server '{server_id}'"
            )

            # Create wrapper (server not started yet)
            wrapper = MCPToolWrapper(
                server_id=server_id,
                tool_name=final_name,
                original_tool_name=tool_name,
                description=description,
                manager=manager,
                always_available=tool_cfg.get("always_available", False),
            )

            tools.append(wrapper)
            LOGGER.info(f"    ✓ Loaded MCP tool: {final_name} (server: {server_id})")

    return tools


def _resolve_tool_name(
    server_id: str,
    tool_name: str,
    tool_cfg: dict,
    namespace_strategy: str
) -> str:
    """
    Determine final tool name based on configuration.

    Args:
        server_id: Server identifier
        tool_name: Original tool name
        tool_cfg: Tool configuration dict
        namespace_strategy: "prefix" or "alias"

    Returns:
        Final tool name
    """
    # Priority 1: Use configured alias if available
    if "alias" in tool_cfg:
        return tool_cfg["alias"]

    # Priority 2: Use namespace strategy
    if namespace_strategy == "prefix":
        return f"mcp__{server_id}__{tool_name}"

    # Priority 3: Use original name (may conflict with local tools)
    return tool_name
