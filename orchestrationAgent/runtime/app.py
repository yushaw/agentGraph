"""Application assembly for OrchestrationAgent.

This module builds the complete Host (Orchestration) application by:
1. Loading settings
2. Building model registry
3. Loading ORCHESTRATION TOOLS ONLY (done_and_report, delegate_task, etc.)
4. Loading HITL approval checker
5. Building graph with strict tool restrictions
6. Setting up persistence

Key Difference from generalAgent:
- Tool registry is STRICTLY FILTERED to orchestration tools only
- No skill loading
- No @mention support
- Simpler state initialization
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from generalAgent.config.project_root import resolve_project_path
from generalAgent.config.settings import get_settings
from generalAgent.hitl import ApprovalChecker
from generalAgent.models import build_default_registry
from generalAgent.persistence import build_checkpointer
from generalAgent.runtime.model_resolver import resolve_model_configs, build_model_resolver
from generalAgent.tools import ToolRegistry
from orchestrationAgent.graph.builder import build_host_graph
from orchestrationAgent.graph.state import OrchestrationState

# Import orchestration-specific tools
from orchestrationAgent.tools.done_and_report import done_and_report
from orchestrationAgent.tools.delegate_task_wrapper import delegate_task, set_app_graph  # Use wrapper version
from generalAgent.tools.builtin.ask_human import ask_human
from generalAgent.tools.builtin.todo_write import todo_write
from generalAgent.tools.builtin.now import now

LOGGER = logging.getLogger(__name__)


async def build_orchestration_app(
    model_registry=None,
    enable_persistence: bool = True,
    enable_hitl: bool = True,
):
    """Build OrchestrationAgent application.

    Args:
        model_registry: Optional model registry (auto-built if None)
        enable_persistence: Enable session persistence (default: True)
        enable_hitl: Enable HITL approval (default: True)

    Returns:
        Tuple of (app, initial_state_factory, model_registry, tool_registry)
    """
    # ========== Step 1: Load Settings ==========
    settings = get_settings()

    # ========== Step 2: Build Model Registry ==========
    if model_registry is None:
        model_configs = resolve_model_configs(settings)
        model_registry = build_default_registry(model_configs)

    model_resolver = build_model_resolver(resolve_model_configs(settings))

    # ========== Step 3: Build Tool Registry (ORCHESTRATION TOOLS ONLY) ==========
    tool_registry = _build_orchestration_tool_registry(settings)

    # ========== Step 4: Build HITL Approval Checker ==========
    approval_checker = None
    if enable_hitl:
        hitl_rules_path = resolve_project_path("orchestrationAgent/config/hitl_rules.yaml")
        if hitl_rules_path.exists():
            approval_checker = ApprovalChecker(hitl_rules_path)  # Pass Path object, not str
            LOGGER.info("[Orchestration App] HITL approval checker loaded")
        else:
            LOGGER.warning(f"[Orchestration App] HITL rules not found: {hitl_rules_path}")

    # ========== Step 5: Build Persistence ==========
    checkpointer = None
    if enable_persistence:
        checkpointer = build_checkpointer(settings.observability)

    # ========== Step 6: Build Graph ==========
    app = build_host_graph(
        model_registry=model_registry,
        model_resolver=model_resolver,
        tool_registry=tool_registry,
        settings=settings,
        checkpointer=checkpointer,
        approval_checker=approval_checker,
    )

    # ========== Step 7: Set app graph for delegate_task tool ==========
    # IMPORTANT: This allows delegate_task to call the Worker graph
    # We reuse the generalAgent graph as the Worker
    from generalAgent.runtime.app import build_application

    # Build Worker app (async)
    LOGGER.info("[Orchestration App] Initializing Worker app (GeneralAgent)...")
    worker_app, *_ = await build_application()
    set_app_graph(worker_app)
    LOGGER.info("[Orchestration App] Worker app initialized successfully")

    # ========== Step 8: Build Initial State Factory ==========
    initial_state_factory = _build_initial_state_factory(settings)

    LOGGER.info("[Orchestration App] Application built successfully")
    LOGGER.info(f"[Orchestration App] Tools: {list(tool_registry._tools.keys())}")

    return app, initial_state_factory, model_registry, tool_registry


def _build_orchestration_tool_registry(settings) -> ToolRegistry:
    """Build tool registry with ORCHESTRATION TOOLS ONLY.

    This is the KEY DIFFERENCE from generalAgent:
    - We manually register ONLY the tools Host needs
    - We do NOT scan generalAgent/tools/ directory
    - We do NOT load skills

    Allowed tools:
    - done_and_report (signal tool)
    - delegate_task (delegation tool)
    - ask_human (user interaction)
    - todo_write (progress tracking)
    - now (utility)
    """
    registry = ToolRegistry()

    # Register orchestration tools manually
    orchestration_tools = {
        "done_and_report": done_and_report,
        "delegate_task": delegate_task,
        "ask_human": ask_human,
        "todo_write": todo_write,
        "now": now,
    }

    for name, tool in orchestration_tools.items():
        # Register as discovered (simple API - just the tool)
        registry.register_discovered(tool)

        # Enable immediately
        registry.register_tool(tool)

        LOGGER.info(f"[Tool Registry] Registered orchestration tool: {name}")

    return registry


def _build_initial_state_factory(settings) -> Callable:
    """Build initial state factory for OrchestrationAgent.

    Returns a function that creates a fresh OrchestrationState.
    """
    def initial_state_factory(
        thread_id: str,
        user_id: str = None,
        workspace_path: str = None,
    ) -> OrchestrationState:
        """Create initial state for a new session.

        Args:
            thread_id: Session thread ID
            user_id: User ID (optional)
            workspace_path: Workspace path (optional)

        Returns:
            Fresh OrchestrationState
        """
        return OrchestrationState(
            messages=[],
            todos=[],
            loops=0,
            max_loops=settings.governance.max_loops,
            needs_compression=False,
            auto_compressed_this_request=False,
            cumulative_prompt_tokens=0,
            workspace_path=workspace_path or "",
            uploaded_files=[],
            context_id=thread_id,
            parent_context=None,
            thread_id=thread_id,
            user_id=user_id,
        )

    return initial_state_factory


__all__ = ["build_orchestration_app"]
