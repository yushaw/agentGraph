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
    ask_vision,
    build_skill_tools,
    calc,
    draft_outline,
    extract_links,
    format_json,
    generate_pptx,
    get_weather,
    http_fetch,
    now,
)
from .model_resolver import build_model_resolver, resolve_model_configs

LOGGER = logging.getLogger(__name__)


def _create_skill_registry(skills_root: Path) -> SkillRegistry:
    skills_root.mkdir(parents=True, exist_ok=True)
    return SkillRegistry(skills_root)


def _create_tool_registry(skill_registry: SkillRegistry) -> tuple[ToolRegistry, List]:
    registry = ToolRegistry()

    for tool in [
        now,
        calc,
        format_json,
        draft_outline,
        generate_pptx,
        http_fetch,
        extract_links,
        ask_vision,
        get_weather,
    ]:
        registry.register_tool(tool)

    skill_tools = build_skill_tools(skill_registry)
    for skill_tool in skill_tools:
        registry.register_tool(skill_tool)

    metadata = [
        ToolMeta("now", "meta", ["meta"], always_available=True),
        ToolMeta("format_json", "meta", ["meta"], always_available=True),
        ToolMeta("list_skills", "meta", ["meta"], always_available=True),
        ToolMeta("select_skill", "meta", ["meta"], always_available=True),
        ToolMeta("create_plan", "meta", ["plan"], always_available=True),
        ToolMeta("draft_outline", "compute", ["read"], always_available=False),
        ToolMeta("generate_pptx", "write", ["file", "write"]),
        ToolMeta("http_fetch", "network", ["network", "read"]),
        ToolMeta("extract_links", "read", ["read"]),
        ToolMeta("ask_vision", "read", ["vision"]),
        ToolMeta("get_weather", "network", ["network", "read"]),
    ]
    for item in metadata:
        registry.register_meta(item)

    persistent = [
        registry.get_tool("now"),
        registry.get_tool("calc"),
        registry.get_tool("format_json"),
        registry.get_tool("list_skills"),
        registry.get_tool("select_skill"),
        registry.get_tool("create_plan"),
    ]
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

    subagent_catalog = {
        "research": ["ask_vision", "http_fetch", "extract_links", "get_weather", "now", "calc", "format_json"],
        "writer": ["draft_outline", "generate_pptx", "now", "calc", "format_json"],
        "weather": ["get_weather", "now", "calc", "format_json"],
    }

    deliverable_checkers: Dict[str, Callable[[dict], bool]] = {
        "analysis_notes": lambda payload: bool(payload.get("notes")) if isinstance(payload, dict) else False,
        "outline_json": lambda payload: isinstance(payload, dict)
        and isinstance(payload.get("outline"), list)
        and len(payload.get("outline", [])) >= 5,
        "file": lambda payload: isinstance(payload, dict) and isinstance(payload.get("file"), str),
        "weather_report": lambda payload: isinstance(payload, dict)
        and payload.get("ok")
        and isinstance(payload.get("weather"), dict)
        and "city" in payload["weather"]
        and "temperature_c" in payload["weather"],
    }

    default_policy = {"auto_approve_writes": settings.governance.auto_approve_writes}
    max_loops = settings.governance.max_loops
    max_step_calls = settings.governance.max_step_calls

    checkpointer = None
    if settings.observability.postgres_dsn:
        try:
            checkpointer = build_checkpointer(settings.observability.postgres_dsn)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Postgres checkpointer disabled: %s", exc)

    resolver = model_resolver or build_model_resolver(model_configs)

    app = graph.build_state_graph(
        model_registry=model_registry,
        model_resolver=resolver,
        tool_registry=tool_registry,
        persistent_global_tools=persistent_global_tools,
        subagent_catalog=subagent_catalog,
        deliverable_checkers=deliverable_checkers,
        default_policy=default_policy,
        skill_registry=skill_registry,
        checkpointer=checkpointer,
    )

    def initial_state() -> dict:
        return {
            "messages": [],
            "images": [],
            "active_skill": None,
            "allowed_tools": [],
            "evidence": [],
            "model_pref": None,
            "plan": None,
            "step_idx": 0,
            "step_calls": 0,
            "max_step_calls": max_step_calls,
            "loops": 0,
            "max_loops": max_loops,
            "execution_phase": "initial",  # NEW: Track which phase we're in
            "task_complexity": "unknown",   # NEW: Track task complexity
            "complexity_reason": None,      # NEW: Why complex/simple
            "policy": {"auto_approve_writes": settings.governance.auto_approve_writes},
            "awaiting_approval": False,
            "pending_calls": [],
        }

    return app, initial_state
