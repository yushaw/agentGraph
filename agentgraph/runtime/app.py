"""Runtime assembly for the universal agent graph."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from agentgraph import graph
from agentgraph.agents import ModelResolver
from agentgraph.config import get_settings
from agentgraph.models import build_default_registry
from agentgraph.persistence import build_checkpointer
from agentgraph.skills import SkillRegistry
from agentgraph.telemetry import configure_tracing
from agentgraph.tools import (
    ToolMeta,
    ToolRegistry,
    build_skill_tools,
    set_app_graph,
)
from agentgraph.tools.scanner import scan_multiple_directories
from agentgraph.tools.config_loader import load_tool_config
from .model_resolver import build_model_resolver, resolve_model_configs

LOGGER = logging.getLogger(__name__)


def _create_skill_registry(skills_root: Path) -> SkillRegistry:
    skills_root.mkdir(parents=True, exist_ok=True)
    return SkillRegistry(skills_root)


def _create_tool_registry(skill_registry: SkillRegistry) -> tuple[ToolRegistry, List]:
    """Create tool registry using scanner and configuration.

    NEW: Uses automatic scanning and tools.yaml configuration instead of
    hardcoded tool imports. This enables hot-reload and plugin support.
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

    LOGGER.info(f"  - Persistent tools: {[t.name for t in persistent]}")

    return registry, persistent


def build_application(
    *,
    model_resolver: Optional[ModelResolver] = None,
    skills_root: Optional[Path] = None,
):
    """Return a compiled LangGraph application instance."""

    settings = get_settings()
    configure_tracing(settings.observability)

    model_configs = resolve_model_configs(settings)
    model_ids = {slot: cfg["id"] for slot, cfg in model_configs.items()}

    model_registry = build_default_registry(model_ids)

    skills_root = skills_root or Path("skills")
    skill_registry = _create_skill_registry(skills_root)

    tool_registry, persistent_global_tools = _create_tool_registry(skill_registry)

    max_loops = settings.governance.max_loops

    # Build SQLite checkpointer for session persistence (always enabled by default)
    # The checkpointer is a wrapper that implements async context manager
    checkpointer = build_checkpointer(settings.observability.session_db_path)
    if checkpointer:
        LOGGER.info("Session persistence enabled (SQLite)")

    resolver = model_resolver or build_model_resolver(model_configs)

    app = graph.build_state_graph(
        model_registry=model_registry,
        model_resolver=resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        skill_registry=skill_registry,
        checkpointer=checkpointer,
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
        }

    return app, initial_state
