"""Runtime assembly for the universal agent graph."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from generalAgent import graph
from generalAgent.agents import ModelResolver
from generalAgent.config import get_settings
from generalAgent.config.project_root import resolve_project_path
from generalAgent.hitl import ApprovalChecker
from generalAgent.models import build_default_registry
from generalAgent.persistence import build_checkpointer
from generalAgent.skills import SkillRegistry
from generalAgent.telemetry import configure_tracing
from generalAgent.tools import (
    ToolMeta,
    ToolRegistry,
    build_skill_tools,
    set_app_graph,
)
from generalAgent.tools.scanner import scan_multiple_directories
from generalAgent.tools.config_loader import load_tool_config
from .model_resolver import build_model_resolver, resolve_model_configs

LOGGER = logging.getLogger(__name__)


def _create_skill_registry(skills_root: Path) -> SkillRegistry:
    skills_root.mkdir(parents=True, exist_ok=True)
    return SkillRegistry(skills_root)


def _create_tool_registry(skill_registry: SkillRegistry, mcp_tools: Optional[List] = None) -> tuple[ToolRegistry, List]:
    """Create tool registry using scanner and configuration.

    NEW: Uses automatic scanning and tools.yaml configuration instead of
    hardcoded tool imports. This enables hot-reload and plugin support.

    Args:
        skill_registry: Skill registry instance
        mcp_tools: Optional list of MCP tools to register

    Returns:
        (ToolRegistry, persistent_tools) tuple
    """
    registry = ToolRegistry()

    # Load configuration
    tool_config = load_tool_config()
    LOGGER.info("Loading tools from configuration...")

    # Scan and load tools from directories
    scan_dirs = tool_config.get_scan_directories()
    discovered_tools = scan_multiple_directories(scan_dirs)
    LOGGER.info(f"  - Discovered {len(discovered_tools)} tools from scan")

    # Get enabled tools from config
    enabled_tools = tool_config.get_all_enabled_tools()
    LOGGER.info(f"  - Enabled tools from config: {sorted(enabled_tools)}")

    # Register ALL discovered tools for on-demand loading
    for tool_name, tool_instance in discovered_tools.items():
        registry.register_discovered(tool_instance)

    # Register enabled tools as immediately available
    registered_count = 0
    for tool_name, tool_instance in discovered_tools.items():
        if tool_name in enabled_tools:
            registry.register_tool(tool_instance)
            registered_count += 1
            LOGGER.info(f"    ✓ Enabled: {tool_name}")
        else:
            LOGGER.debug(f"    ○ Discovered (not enabled): {tool_name}")

    LOGGER.info(f"  - Registered {registered_count} tools from scan")

    # Register MCP tools (if provided)
    if mcp_tools:
        for mcp_tool in mcp_tools:
            registry.register_tool(mcp_tool)
            # Also register as discovered for @mention support
            registry.register_discovered(mcp_tool)
        LOGGER.info(f"  - Registered {len(mcp_tools)} MCP tools")

    # Register skill tools
    skill_tools = build_skill_tools(skill_registry)
    for skill_tool in skill_tools:
        registry.register_tool(skill_tool)
    LOGGER.info(f"  - Registered {len(skill_tools)} skill tools")

    # Register metadata from configuration (not hardcoded)
    all_metadata = tool_config.get_all_tool_metadata()
    LOGGER.info(f"Loading metadata for {len(all_metadata)} tools from config...")
    for meta in all_metadata:
        try:
            registry.register_meta(meta)
            LOGGER.debug(f"  ✓ Registered metadata for: {meta.name} (always_available={meta.always_available})")
        except KeyError:
            # Tool not registered, skip metadata
            LOGGER.warning(f"  ✗ Metadata found but tool not registered: {meta.name}")

    # Build persistent (always available) tools list from config
    persistent = []
    for tool_name in enabled_tools:
        if tool_config.is_always_available(tool_name):
            try:
                persistent.append(registry.get_tool(tool_name))
            except KeyError:
                LOGGER.warning(f"Tool '{tool_name}' configured but not found")

    # Add MCP tools that are always_available
    if mcp_tools:
        for mcp_tool in mcp_tools:
            if getattr(mcp_tool, "always_available", False):
                persistent.append(mcp_tool)

    LOGGER.info(f"  - Persistent tools: {[t.name for t in persistent]}")

    return registry, persistent


async def build_application(
    *,
    model_resolver: Optional[ModelResolver] = None,
    skills_root: Optional[Path] = None,
    mcp_tools: Optional[List] = None,
):
    """Return a compiled LangGraph application instance.

    Args:
        model_resolver: Optional custom model resolver
        skills_root: Optional custom skills directory
        mcp_tools: Optional list of MCP tools to register

    Returns:
        (app, initial_state_factory, skill_registry, tool_registry) tuple
    """

    settings = get_settings()
    configure_tracing(settings.observability)

    model_configs = resolve_model_configs(settings)

    model_registry = build_default_registry(model_configs)

    skills_root = skills_root or resolve_project_path("generalAgent/skills")
    skill_registry = _create_skill_registry(skills_root)

    tool_registry, persistent_global_tools = _create_tool_registry(skill_registry, mcp_tools)

    max_loops = settings.governance.max_loops

    # Build SQLite checkpointer for session persistence (always enabled by default)
    # The checkpointer is a wrapper that implements async context manager
    checkpointer = build_checkpointer(settings.observability.session_db_path)
    if checkpointer:
        LOGGER.info("Session persistence enabled (SQLite)")

    resolver = model_resolver or build_model_resolver(model_configs)

    # Initialize HITL approval checker
    hitl_config_path = resolve_project_path("generalAgent/config/hitl_rules.yaml")
    approval_checker = ApprovalChecker(config_path=hitl_config_path)
    LOGGER.info(f"HITL approval checker initialized with config: {hitl_config_path}")

    app = graph.build_state_graph(
        model_registry=model_registry,
        model_resolver=resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        skill_registry=skill_registry,
        settings=settings,
        checkpointer=checkpointer,
        approval_checker=approval_checker,
    )

    # Set app graph for call_subagent tool
    set_app_graph(app)
    LOGGER.info("Application graph registered for subagent execution")

    def initial_state() -> dict:
        return {
            "messages": [],
            "images": [],
            "active_skill": None,
            "allowed_tools": [],
            "mentioned_agents": [],
            "persistent_tools": [],
            "model_pref": None,
            "todos": [],
            "context_id": "main",
            "parent_context": None,
            "loops": 0,
            "max_loops": max_loops,
            "thread_id": None,
            "user_id": None,
            "workspace_path": None,  # Set by main.py when session starts
            "uploaded_files": [],  # Track uploaded files
        }

    return app, initial_state, skill_registry, tool_registry
