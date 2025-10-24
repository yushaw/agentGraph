"""GeneralAgent - Self-contained CLI entrypoint."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path to support direct execution
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from generalAgent.runtime import build_application
from generalAgent.cli import GeneralAgentCLI
from generalAgent.utils import get_logger
from shared.session.manager import SessionManager
from shared.session.store import SessionStore
from shared.workspace.manager import WorkspaceManager


async def async_main():
    """Async entrypoint for GeneralAgent CLI."""
    # Initialize logger
    logger = get_logger()
    logger.info("=" * 60)
    logger.info("AgentGraph starting...")

    try:
        # Build application (LangGraph + registries)
        app, initial_state_factory, skill_registry, tool_registry = build_application()
        logger.info("Application built successfully")

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

        # Launch CLI
        cli = GeneralAgentCLI(
            app=app,
            session_manager=session_manager,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
            logger=logger
        )

        await cli.run()

    except Exception as e:
        logger.error(f"Fatal error during startup: {e}", exc_info=True)
        print(f"\n❌ 启动失败: {e}")
        print("请查看日志文件获取详细信息")


def main():
    """Synchronous wrapper for async_main."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
