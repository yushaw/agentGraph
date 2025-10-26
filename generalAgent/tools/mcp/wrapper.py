"""MCP tool wrapper for LangChain BaseTool integration."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from langchain_core.tools import BaseTool
from pydantic import Field

if TYPE_CHECKING:
    from .manager import MCPServerManager

LOGGER = logging.getLogger(__name__)


class MCPToolWrapper(BaseTool):
    """
    LangChain BaseTool wrapper for MCP tools.

    Features:
    - Lazy server startup: server only starts on first tool call
    - Automatic argument validation
    - Error handling with helpful messages
    """

    # Tool metadata
    server_id: str = Field(description="MCP server identifier")
    original_tool_name: str = Field(description="Original tool name on MCP server")
    manager: Any = Field(description="MCPServerManager instance", exclude=True)
    always_available: bool = Field(default=False, description="Always in agent context")

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        server_id: str,
        tool_name: str,
        original_tool_name: str,
        description: str,
        manager: "MCPServerManager",
        always_available: bool = False,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize MCP tool wrapper.

        Args:
            server_id: MCP server identifier
            tool_name: Final tool name (may be aliased)
            original_tool_name: Original tool name on MCP server
            description: Tool description
            manager: MCPServerManager instance
            always_available: Whether tool is always in context
            input_schema: Pydantic schema for tool arguments (optional)
        """
        super().__init__(
            name=tool_name,
            description=description,
            server_id=server_id,
            original_tool_name=original_tool_name,
            manager=manager,
            always_available=always_available,
        )

        # Set input schema if provided
        if input_schema:
            self.args_schema = input_schema

    async def _arun(self, **kwargs) -> str:
        """
        Async execution of MCP tool.

        Args:
            **kwargs: Tool arguments

        Returns:
            Tool execution result as string
        """
        try:
            # Get server connection (triggers lazy startup if needed)
            connection = await self.manager.get_server(self.server_id)

            LOGGER.debug(
                f"Executing MCP tool: {self.name} "
                f"(server: {self.server_id}, tool: {self.original_tool_name})"
            )

            # Call tool on server
            result = await connection.call_tool(self.original_tool_name, kwargs)

            return result

        except Exception as e:
            error_msg = (
                f"MCP tool execution failed:\n"
                f"  Tool: {self.name}\n"
                f"  Server: {self.server_id}\n"
                f"  Error: {str(e)}"
            )
            LOGGER.error(error_msg)
            return error_msg

    def _run(self, **kwargs) -> str:
        """
        Sync execution wrapper (required by LangChain).

        Args:
            **kwargs: Tool arguments

        Returns:
            Tool execution result as string
        """
        # Run async function in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, create task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._arun(**kwargs))
                    return future.result()
            else:
                # Not in async context, run normally
                return asyncio.run(self._arun(**kwargs))
        except Exception as e:
            error_msg = f"MCP tool sync execution failed: {e}"
            LOGGER.error(error_msg)
            return error_msg
