"""MCP server lifecycle manager with lazy startup support."""

import logging
from typing import Dict, Optional

from .connection import MCPConnection, create_connection

LOGGER = logging.getLogger(__name__)


class MCPServerManager:
    """
    Manages lifecycle of MCP servers with lazy startup.

    Features:
    - Lazy startup: servers only started on first tool call
    - Automatic cleanup: all servers closed on shutdown
    - Connection pooling: reuse existing connections
    """

    def __init__(self, config: dict):
        """
        Initialize manager with configuration.

        Args:
            config: MCP configuration dict loaded from mcp_servers.yaml
        """
        self.config = config
        self._servers: Dict[str, MCPConnection] = {}  # server_id -> connection
        self._server_configs: Dict[str, dict] = {}    # server_id -> config

        # Parse configuration and register enabled servers
        for server_id, server_cfg in config.get("servers", {}).items():
            if server_cfg.get("enabled", True):
                self._server_configs[server_id] = server_cfg
                LOGGER.debug(f"  Registered MCP server config: {server_id}")

    async def get_server(self, server_id: str) -> MCPConnection:
        """
        Get server connection (lazy startup).

        Args:
            server_id: Server identifier

        Returns:
            MCPConnection instance

        Raises:
            ValueError: If server not configured
            RuntimeError: If server fails to start
        """
        # Already started, return cached connection
        if server_id in self._servers:
            return self._servers[server_id]

        # Check if server is configured
        if server_id not in self._server_configs:
            raise ValueError(f"MCP server not configured: {server_id}")

        # Start server (lazy startup)
        LOGGER.info(f"🚀 Starting MCP server: {server_id}")
        connection = await self._start_server(server_id)
        self._servers[server_id] = connection

        return connection

    async def _start_server(self, server_id: str) -> MCPConnection:
        """
        Start MCP server process and establish connection.

        Args:
            server_id: Server identifier

        Returns:
            MCPConnection instance

        Raises:
            RuntimeError: If server fails to start
        """
        cfg = self._server_configs[server_id]

        # Determine connection mode
        connection_mode = cfg.get(
            "connection_mode",
            self.config.get("settings", {}).get("default_connection_mode", "stdio")
        )

        # Create connection
        connection = create_connection(
            server_id=server_id,
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env", {}),
            mode=connection_mode,
            url=cfg.get("url")  # For SSE mode
        )

        # Start server with timeout
        startup_timeout = self.config.get("settings", {}).get("startup_timeout", 30)

        try:
            import asyncio
            await asyncio.wait_for(connection.start(), timeout=startup_timeout)
            LOGGER.info(f"  ✓ MCP server started: {server_id} (mode: {connection_mode})")
            return connection
        except asyncio.TimeoutError:
            raise RuntimeError(f"MCP server startup timeout: {server_id}")
        except Exception as e:
            raise RuntimeError(f"Failed to start MCP server '{server_id}': {e}")

    async def shutdown(self):
        """
        Shutdown all MCP servers and cleanup resources.

        This should be called when the application exits.
        """
        if not self._servers:
            return

        LOGGER.info(f"Shutting down {len(self._servers)} MCP server(s)...")

        for server_id, connection in self._servers.items():
            try:
                await connection.close()
                LOGGER.info(f"  ✓ Closed: {server_id}")
            except Exception as e:
                LOGGER.error(f"  ✗ Failed to close {server_id}: {e}")

        self._servers.clear()

    def is_server_started(self, server_id: str) -> bool:
        """Check if a server has been started."""
        return server_id in self._servers

    def list_configured_servers(self) -> list:
        """List all configured server IDs."""
        return list(self._server_configs.keys())

    def list_started_servers(self) -> list:
        """List all started server IDs."""
        return list(self._servers.keys())
