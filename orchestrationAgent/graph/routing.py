"""Routing logic for OrchestrationAgent graph.

Host routing is SIMPLER than generalAgent:
- No handoff pattern (only one agent)
- No agent nodes (just planner + tools)
- Forced feedback loop (tools always return to planner)
"""

from __future__ import annotations

import logging
from typing import Literal

from orchestrationAgent.graph.state import OrchestrationState
from generalAgent.utils.logging_utils import log_routing_decision

LOGGER = logging.getLogger("orchestration.routing")


def host_agent_route(state: OrchestrationState) -> Literal["tools", "summarization", "end"]:
    """Route after planner node.

    Decision logic:
    1. Check loop limit - if exceeded, end
    2. Check compression need - if critical token usage, compress first
    3. Check for done_and_report tool call - if present, end directly
    4. Check for other tool calls - if present, execute them
    5. Otherwise, end (LLM decided to finish without calling done_and_report)

    Returns:
        "summarization": Token usage >95%, compress first
        "tools": LLM requested tool calls (delegate_task, ask_human, etc.)
        "end": LLM called done_and_report OR no tool calls OR loop limit reached
    """
    loops = state.get("loops", 0)
    max_loops = state.get("max_loops", 100)

    # Check loop limit
    if loops >= max_loops:
        decision = "end"
        reason = f"Loop limit reached ({loops}/{max_loops})"
        log_routing_decision(LOGGER, "planner", decision, reason)
        return decision

    # Check compression flag
    needs_compression = state.get("needs_compression", False)
    auto_compressed = state.get("auto_compressed_this_request", False)

    if needs_compression and not auto_compressed:
        decision = "summarization"
        reason = "Critical token usage detected, triggering compression"
        log_routing_decision(LOGGER, "planner", decision, reason)
        return decision

    # Check tool calls
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            tool_names = [tc["name"] for tc in last_message.tool_calls]

            # Check if done_and_report was called
            if "done_and_report" in tool_names:
                # Execute the tool first (to get final_result in ToolMessage)
                # Then end directly without finalize node
                decision = "tools"  # Execute done_and_report tool
                reason = "LLM called done_and_report, will execute then end"
                log_routing_decision(LOGGER, "planner", decision, reason)
                return decision

            # Other tool calls (delegate_task, ask_human, etc.)
            decision = "tools"
            reason = f"LLM requested {len(last_message.tool_calls)} tool call(s): {', '.join(tool_names)}"
            log_routing_decision(LOGGER, "planner", decision, reason)
            return decision

    # No tool calls - LLM decided to finish (edge case)
    decision = "end"
    reason = "No tool calls, LLM decided to finish"
    log_routing_decision(LOGGER, "planner", decision, reason)
    return decision


def host_tools_route(state: OrchestrationState) -> Literal["planner", "end"]:
    """Route after tools node.

    Decision logic:
    - If done_and_report was just executed, end directly
    - Otherwise, return to planner (forced feedback loop)

    Returns:
        "planner": Continue feedback loop
        "end": done_and_report was executed, task complete
    """
    # Check if last ToolMessage is from done_and_report
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "name") and last_message.name == "done_and_report":
            decision = "end"
            reason = "done_and_report executed, ending task"
            log_routing_decision(LOGGER, "tools", decision, reason)
            return decision

    # Default: return to planner
    decision = "planner"
    reason = "Tool execution complete, returning to planner (forced feedback loop)"
    log_routing_decision(LOGGER, "tools", decision, reason)
    return decision


def host_summarization_route(state: OrchestrationState) -> Literal["planner"]:
    """Route after summarization node.

    After compression, always return to planner to continue processing.

    Returns:
        "planner": Always return to planner
    """
    decision = "planner"
    reason = "Context compression complete, returning to planner"
    log_routing_decision(LOGGER, "summarization", decision, reason)
    return decision


__all__ = ["host_agent_route", "host_tools_route", "host_summarization_route"]
