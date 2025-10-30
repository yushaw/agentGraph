"""GeneralAgent - Self-contained CLI entrypoint."""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

# Add project root to path to support direct execution
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from generalAgent.runtime import build_application
from generalAgent.cli import GeneralAgentCLI
from generalAgent.utils import get_logger
from generalAgent.config.project_root import resolve_project_path
from generalAgent.config.skill_config_loader import load_skill_config
from shared.session.manager import SessionManager
from shared.session.store import SessionStore
from shared.workspace.manager import WorkspaceManager


async def async_main():
    """Async entrypoint for GeneralAgent CLI."""
    # Initialize logger
    logger = get_logger()
    logger.info("=" * 60)
    logger.info("AgentGraph starting...")

    # Initialize MCP manager (if configured)
    mcp_manager = None
    mcp_tools = []

    try:
        # Load MCP configuration
        mcp_config_path = resolve_project_path("generalAgent/config/mcp_servers.yaml")

        if mcp_config_path.exists():
            logger.info("Loading MCP configuration...")
            from generalAgent.tools.mcp import load_mcp_config, load_mcp_tools, MCPServerManager

            mcp_config = load_mcp_config(mcp_config_path)

            # Create MCP manager (servers not started yet, lazy mode)
            mcp_manager = MCPServerManager(mcp_config)
            logger.info(f"  MCP servers configured: {len(mcp_manager.list_configured_servers())}")

            # Create MCP tool wrappers (servers still not started)
            mcp_tools = load_mcp_tools(mcp_config, mcp_manager)
            logger.info(f"  MCP tools loaded: {len(mcp_tools)}")
        else:
            logger.info("No MCP configuration found, skipping MCP integration")

        # Build application (LangGraph + registries)
        app, initial_state_factory, skill_registry, tool_registry, skill_config, agent_registry = await build_application(
            mcp_tools=mcp_tools
        )
        logger.info("Application built successfully")
        logger.info(f"  - Agent Registry: {agent_registry.get_stats() if agent_registry else 'disabled'}")

        # Initialize shared infrastructure
        session_store = SessionStore()
        workspace_manager = WorkspaceManager(skill_registry=skill_registry)
        session_manager = SessionManager(
            session_store=session_store,
            workspace_manager=workspace_manager,
            initial_state_factory=initial_state_factory
        )
        logger.info("Shared infrastructure initialized")

        # Create initial session
        session_id, state = session_manager.create_session()
        logger.info(f"Initial session created: {session_id[:16]}...")

        # Setup signal handlers for graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler(sig, frame):
            logger.info(f"\nReceived signal {sig}, initiating graceful shutdown...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Launch CLI
        cli = GeneralAgentCLI(
            app=app,
            session_manager=session_manager,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
            skill_config=skill_config,
            logger=logger
        )

        try:
            await cli.run()
        except KeyboardInterrupt:
            logger.info("\nKeyboardInterrupt received, shutting down...")
        finally:
            # Cleanup MCP servers
            if mcp_manager:
                logger.info("Cleaning up MCP servers...")
                await mcp_manager.shutdown()
                logger.info("✅ MCP cleanup completed")

    except Exception as e:
        logger.error(f"Fatal error during startup: {e}", exc_info=True)
        print(f"\n❌ 启动失败: {e}")
        print("请查看日志文件获取详细信息")
    finally:
        # Final cleanup (just in case)
        if mcp_manager and mcp_manager._servers:
            try:
                await mcp_manager.shutdown()
            except Exception as e:
                logger.warning(f"Error during final cleanup: {e}")


def main():
    """Synchronous wrapper for async_main."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
