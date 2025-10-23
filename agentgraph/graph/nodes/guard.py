"""Governance guard node."""

from __future__ import annotations

from typing import Dict, List

from langchain_core.messages import AIMessage, SystemMessage

from agentgraph.graph.state import AppState
from agentgraph.tools import ToolRegistry


def build_guard_node(*, tool_registry: ToolRegistry, default_policy: Dict[str, bool]):
    """Create a guard node that enforces tool risk policies."""

    risky_levels = {"write", "finance", "pii"}

    def guard_node(state: AppState) -> AppState:
        policy = {**default_policy, **(state.get("policy") or {})}
        updates: Dict[str, object] = {"policy": policy, "awaiting_approval": False, "pending_calls": []}

        tool_calls: List[Dict] = []
        last_message = state.get("messages", [])[-1] if state.get("messages") else None

        if last_message is None:
            return state

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            tool_calls = list(last_message.tool_calls)
        elif isinstance(last_message, dict) and last_message.get("tool_calls"):
            tool_calls = list(last_message["tool_calls"])

        blocked: List[str] = []
        for call in tool_calls:
            name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
            if not name:
                continue
            meta = tool_registry.get_meta_optional(name)
            if meta and meta.risk in risky_levels and not policy.get("auto_approve_writes", False):
                blocked.append(name)

        if blocked:
            updates["awaiting_approval"] = True
            updates["pending_calls"] = tool_calls
            updates["messages"] = [SystemMessage(content=f"安全拦截：检测到需要批准的工具调用 {blocked} 。请确认后继续。")]

        return updates

    return guard_node
