"""Task complexity analyzer node."""

from __future__ import annotations

import json
import logging
from typing import Dict

from langchain_core.messages import SystemMessage, ToolMessage

from agentgraph.graph.state import AppState
from agentgraph.utils.logging_utils import log_node_entry, log_node_exit
from agentgraph.utils.error_handler import with_error_boundary

LOGGER = logging.getLogger("agentgraph.analyze")


ANALYSIS_SYSTEM_PROMPT = """Analyze the task complexity based on tool execution results.

Determine if the task is "simple" or "complex":

SIMPLE tasks:
- Single tool call satisfied the request
- No dependencies between operations
- Direct question/answer
- Simple calculations or data formatting
- Tool already returned complete result

COMPLEX tasks:
- Requires multiple different tools
- Has sequential dependencies ("first A, then B")
- Needs intermediate result validation
- Involves multiple data sources or APIs
- User explicitly requested multi-step process

Respond with ONLY a JSON object:
{
  "complex": true/false,
  "reason": "Brief explanation in Chinese (under 50 chars)"
}
"""


def build_analyze_node():
    """Create the task complexity analyzer node."""

    @with_error_boundary("analyze")
    def analyze_node(state: AppState) -> AppState:
        """Analyze whether the task needs multi-step planning or continuation.

        This node runs AFTER the initial tool execution to determine:
        1. If a plan was created → enter loop phase
        2. If LLM has more tool_calls pending → continue (return to plan)
        3. If task is complete → finish
        """
        log_node_entry(LOGGER, "analyze", state)

        # Check if plan was already created via create_plan tool
        if state.get("plan"):
            # Plan exists, mark as complex and proceed
            LOGGER.info("Plan already exists in state, marking as complex")
            updates = {
                "task_complexity": "complex",
                "complexity_reason": "Plan created by LLM",
                "execution_phase": "loop",
                "step_idx": 0,
                "step_calls": 0,
                "loops": 0,
            }
            log_node_exit(LOGGER, "analyze", updates)
            return updates

        # Check if last AI message has tool_calls (LLM wants to continue)
        messages = state.get("messages", [])
        LOGGER.info(f"Analyzing {len(messages)} messages for task complexity...")

        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                # Check if AI has pending tool calls
                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls and len(tool_calls) > 0:
                    # AI wants to call more tools, return "continue"
                    LOGGER.info(f"Last AI message has {len(tool_calls)} pending tool calls, continuing...")
                    updates = {
                        "task_complexity": "continue",
                        "complexity_reason": "AI has pending tool calls",
                        "execution_phase": "initial",
                    }
                    log_node_exit(LOGGER, "analyze", updates)
                    return updates
                # Found last AI message, stop searching
                LOGGER.info("Last AI message has no pending tool calls")
                break

        # Extract recent tool executions for pattern analysis
        tool_results = []
        for msg in reversed(messages[-10:]):
            if isinstance(msg, ToolMessage):
                tool_results.append({
                    "name": msg.name,
                    "content": msg.content[:200]
                })

        LOGGER.info(f"Found {len(tool_results)} recent tool executions")
        if tool_results:
            tool_names = [t["name"] for t in tool_results]
            LOGGER.info(f"  - Tools called: {tool_names}")

        # Check if create_plan was called (should have been handled by post)
        for result in tool_results:
            if result["name"] == "create_plan":
                LOGGER.info("Found create_plan call in tool results, extracting plan...")
                try:
                    payload = json.loads(result["content"])
                    if payload.get("ok"):
                        # Plan was successfully created (post should have extracted it)
                        plan = payload.get("plan")
                        LOGGER.info(f"Plan extracted with {len(plan.get('steps', []))} steps")
                        updates = {
                            "plan": plan,
                            "task_complexity": "complex",
                            "complexity_reason": "Multi-step plan created",
                            "execution_phase": "loop",
                            "step_idx": 0,
                            "step_calls": 0,
                            "loops": 0,
                        }
                        log_node_exit(LOGGER, "analyze", updates)
                        return updates
                except (json.JSONDecodeError, KeyError) as e:
                    LOGGER.warning(f"Failed to parse create_plan result: {e}")

        # No plan, no pending calls → task complete
        LOGGER.info("No plan, no pending calls → task is simple and complete")
        updates = {
            "task_complexity": "simple",
            "complexity_reason": "Task completed",
            "execution_phase": "initial",
        }
        log_node_exit(LOGGER, "analyze", updates)
        return updates

    return analyze_node
