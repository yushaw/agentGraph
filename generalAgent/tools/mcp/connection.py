"""MCP server connection implementations (stdio and SSE modes)."""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


class MCPConnection(ABC):
    """Abstract base class for MCP server connections."""

    def __init__(self, server_id: str, command: str, args: List[str], env: Dict[str, str]):
        self.server_id = server_id
        self.command = command
        self.args = args
        self.env = env
        self._initialized = False

    @abstractmethod
    async def start(self):
        """Start the server and establish connection."""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the server."""
        pass

    @abstractmethod
    async def list_tools(self) -> List[Any]:
        """List all tools provided by the server."""
        pass

    @abstractmethod
    async def close(self):
        """Close the connection and cleanup resources."""
        pass

    async def get_tool_info(self, tool_name: str):
        """Get detailed information about a specific tool."""
        tools = await self.list_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool
        raise ValueError(f"Tool not found on server '{self.server_id}': {tool_name}")


class StdioMCPConnection(MCPConnection):
    """MCP connection using stdio (standard input/output) mode."""

    def __init__(self, server_id: str, command: str, args: List[str], env: Dict[str, str]):
        super().__init__(server_id, command, args, env)
        self._process = None
        self._client = None
        self._read_stream = None
        self._write_stream = None
        self._stdio_context = None  # Keep reference to context manager

    async def start(self):
        """Start the server process and establish stdio connection."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise ImportError(
                "MCP SDK not installed. Install with: pip install mcp"
            )

        # Merge environment variables
        full_env = os.environ.copy()
        # Resolve environment variable references like ${GITHUB_TOKEN}
        resolved_env = {}
        for key, value in self.env.items():
            if value.startswith("${") and value.endswith("}"):
                env_var_name = value[2:-1]
                resolved_env[key] = os.environ.get(env_var_name, "")
            else:
                resolved_env[key] = value
        full_env.update(resolved_env)

        LOGGER.debug(f"  Starting stdio server: {self.command} {' '.join(self.args)}")

        # Create server parameters
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=full_env
        )

        # Start server and create client session (stdio_client is a context manager)
        stdio_context = stdio_client(server_params)
        self._read_stream, self._write_stream = await stdio_context.__aenter__()
        self._stdio_context = stdio_context  # Keep reference for cleanup

        self._client = ClientSession(self._read_stream, self._write_stream)

        # Initialize session
        await self._client.__aenter__()
        self._initialized = True

        LOGGER.debug(f"  ✓ Stdio connection established for server: {self.server_id}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool via stdio."""
        if not self._initialized:
            raise RuntimeError(f"Server not initialized: {self.server_id}")

        LOGGER.debug(f"  Calling tool: {tool_name} on server {self.server_id}")
        result = await self._client.call_tool(tool_name, arguments)

        # MCP returns CallToolResult with content list
        # Content can be TextContent or ImageContent
        if result.content:
            text_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    text_parts.append(item.text)
            return "\n".join(text_parts)

        return ""

    async def list_tools(self) -> List[Any]:
        """List tools via stdio."""
        if not self._initialized:
            raise RuntimeError(f"Server not initialized: {self.server_id}")

        result = await self._client.list_tools()
        return result.tools

    async def close(self):
        """Close stdio connection."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"  Error closing client session for {self.server_id}: {e}")
            self._client = None

        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"  Error closing stdio context for {self.server_id}: {e}")
            self._stdio_context = None

        self._initialized = False
        LOGGER.debug(f"  ✓ Closed stdio connection for server: {self.server_id}")


class SSEMCPConnection(MCPConnection):
    """MCP connection using SSE (Server-Sent Events) mode over HTTP."""

    def __init__(
        self,
        server_id: str,
        command: str,
        args: List[str],
        env: Dict[str, str],
        url: Optional[str] = None
    ):
        super().__init__(server_id, command, args, env)
        self.url = url or "http://localhost:8000/sse"
        self._client = None
        self._session = None
        self._sse_context = None  # Keep reference to context manager
        self._process = None

    async def start(self):
        """Start the server process and establish SSE connection."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            import aiohttp
        except ImportError:
            raise ImportError(
                "MCP SDK with SSE support not installed. Install with: pip install mcp aiohttp"
            )

        # Merge environment variables
        full_env = os.environ.copy()
        resolved_env = {}
        for key, value in self.env.items():
            if value.startswith("${") and value.endswith("}"):
                env_var_name = value[2:-1]
                resolved_env[key] = os.environ.get(env_var_name, "")
            else:
                resolved_env[key] = value
        full_env.update(resolved_env)

        LOGGER.debug(f"  Starting SSE server: {self.command} {' '.join(self.args)}")

        # Start the server process in background
        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            env=full_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait a bit for server to start
        await asyncio.sleep(2)

        # Create SSE client connection (sse_client is a context manager)
        self._session = aiohttp.ClientSession()
        sse_context = sse_client(self.url, self._session)
        self._read_stream, self._write_stream = await sse_context.__aenter__()
        self._sse_context = sse_context  # Keep reference for cleanup

        self._client = ClientSession(self._read_stream, self._write_stream)

        # Initialize session
        await self._client.__aenter__()
        self._initialized = True

        LOGGER.debug(f"  ✓ SSE connection established for server: {self.server_id}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool via SSE."""
        if not self._initialized:
            raise RuntimeError(f"Server not initialized: {self.server_id}")

        LOGGER.debug(f"  Calling tool: {tool_name} on server {self.server_id}")
        result = await self._client.call_tool(tool_name, arguments)

        if result.content:
            text_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    text_parts.append(item.text)
            return "\n".join(text_parts)

        return ""

    async def list_tools(self) -> List[Any]:
        """List tools via SSE."""
        if not self._initialized:
            raise RuntimeError(f"Server not initialized: {self.server_id}")

        result = await self._client.list_tools()
        return result.tools

    async def close(self):
        """Close SSE connection and terminate process."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"  Error closing client session for {self.server_id}: {e}")
            self._client = None

        if self._sse_context:
            try:
                await self._sse_context.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"  Error closing SSE context for {self.server_id}: {e}")
            self._sse_context = None

        if self._session:
            await self._session.close()
            self._session = None

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
            except Exception as e:
                LOGGER.warning(f"  Error terminating process for {self.server_id}: {e}")
            self._process = None

        self._initialized = False
        LOGGER.debug(f"  ✓ Closed SSE connection for server: {self.server_id}")


def create_connection(
    server_id: str,
    command: str,
    args: List[str],
    env: Dict[str, str],
    mode: str = "stdio",
    url: Optional[str] = None
) -> MCPConnection:
    """Factory function to create appropriate connection type."""
    if mode == "stdio":
        return StdioMCPConnection(server_id, command, args, env)
    elif mode == "sse":
        return SSEMCPConnection(server_id, command, args, env, url)
    else:
        raise ValueError(f"Unknown connection mode: {mode}")
