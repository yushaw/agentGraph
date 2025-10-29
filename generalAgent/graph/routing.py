"""Conditional routing helpers for Agent Loop architecture."""

from __future__ import annotations

import logging
from typing import Literal

from .state import AppState
from generalAgent.utils.logging_utils import log_routing_decision

LOGGER = logging.getLogger("agentgraph.routing")


def agent_route(state: AppState) -> Literal["tools", "summarization", "finalize"]:
    """Route after agent node based on token usage and tool calls.

    Agent Loop architecture with automatic context compression:
    1. Check token usage - if critical (>95%), compress first
    2. Check tool calls - if present, execute them
    3. Otherwise, finalize

    Returns:
        "summarization": Token usage >95%, compress context first
        "tools": LLM requested tool calls, execute them
        "finalize": No tool calls (LLM finished) or loop limit reached
    """
    loops = state.get("loops", 0)
    max_loops = state.get("max_loops", 42)

    # Check loop limit first
    if loops >= max_loops:
        decision = "finalize"
        reason = f"Loop limit reached ({loops}/{max_loops})"
        log_routing_decision(LOGGER, "agent", decision, reason)
        return decision

    # Check if planner set needs_compression flag (when token usage was critical)
    needs_compression = state.get("needs_compression", False)
    auto_compressed = state.get("auto_compressed_this_request", False)

    if needs_compression and not auto_compressed:
        decision = "summarization"
        reason = "Planner detected critical token usage, triggering compression"
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


def summarization_route(state: AppState) -> Literal["agent"]:
    """Route after summarization node - always return to agent.

    After compression, return to agent to continue processing the original request.

    Returns:
        "agent": Always return to agent for continued execution
    """
    decision = "agent"
    reason = "Context compression complete, returning to agent"
    log_routing_decision(LOGGER, "summarization", decision, reason)
    return decision
