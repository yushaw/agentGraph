"""Conditional routing helpers for Agent Loop architecture."""

from __future__ import annotations

import logging
from typing import Literal

from .state import AppState
from agentgraph.utils.logging_utils import log_routing_decision

LOGGER = logging.getLogger("agentgraph.routing")


def agent_route(state: AppState) -> Literal["tools", "finalize"]:
    """Route after agent node based on whether LLM wants to call tools.

    Agent Loop architecture: LLM decides its own flow by choosing to call tools or stop.

    Returns:
        "tools": LLM requested tool calls, execute them
        "finalize": No tool calls (LLM finished) or loop limit reached
    """
    loops = state.get("loops", 0)
    max_loops = state.get("max_loops", 20)

    # Check loop limit first
    if loops >= max_loops:
        decision = "finalize"
        reason = f"Loop limit reached ({loops}/{max_loops})"
        log_routing_decision(LOGGER, "agent", decision, reason)
        return decision

    # Check if last message has tool calls
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            decision = "tools"
            reason = f"LLM requested {len(last_message.tool_calls)} tool call(s)"
        else:
            decision = "finalize"
            reason = "No tool calls, LLM decided to finish"
    else:
        decision = "finalize"
        reason = "No messages in state"

    log_routing_decision(LOGGER, "agent", decision, reason)
    return decision


def tools_route(state: AppState) -> Literal["agent"]:
    """Route after tools node - always return to agent.

    Simple loop: agent → tools → agent → ...

    Returns:
        "agent": Always return to agent for next decision
    """
    decision = "agent"
    reason = "Tool execution complete, returning to agent"
    log_routing_decision(LOGGER, "tools", decision, reason)
    return decision
