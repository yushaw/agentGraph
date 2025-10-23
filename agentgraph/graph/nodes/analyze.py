"""Task complexity analyzer node."""

from __future__ import annotations

import json
from typing import Dict

from langchain_core.messages import SystemMessage, ToolMessage

from agentgraph.graph.state import AppState


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

    def analyze_node(state: AppState) -> AppState:
        """Analyze whether the task needs multi-step planning or continuation.

        This node runs AFTER the initial tool execution to determine:
        1. If a plan was created → enter loop phase
        2. If LLM has more tool_calls pending → continue (return to plan)
        3. If task is complete → finish
        """

        # Check if plan was already created via create_plan tool
        if state.get("plan"):
            # Plan exists, mark as complex and proceed
            return {
                "task_complexity": "complex",
                "complexity_reason": "Plan created by LLM",
                "execution_phase": "loop",
                "step_idx": 0,
                "step_calls": 0,
                "loops": 0,
            }

        # Check if last AI message has tool_calls (LLM wants to continue)
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                # Check if AI has pending tool calls
                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls and len(tool_calls) > 0:
                    # AI wants to call more tools, return "continue"
                    return {
                        "task_complexity": "continue",
                        "complexity_reason": "AI has pending tool calls",
                        "execution_phase": "initial",
                    }
                # Found last AI message, stop searching
                break

        # Extract recent tool executions for pattern analysis
        tool_results = []
        for msg in reversed(messages[-10:]):
            if isinstance(msg, ToolMessage):
                tool_results.append({
                    "name": msg.name,
                    "content": msg.content[:200]
                })

        # Check if create_plan was called (should have been handled by post)
        for result in tool_results:
            if result["name"] == "create_plan":
                try:
                    payload = json.loads(result["content"])
                    if payload.get("ok"):
                        # Plan was successfully created (post should have extracted it)
                        plan = payload.get("plan")
                        return {
                            "plan": plan,
                            "task_complexity": "complex",
                            "complexity_reason": "Multi-step plan created",
                            "execution_phase": "loop",
                            "step_idx": 0,
                            "step_calls": 0,
                            "loops": 0,
                        }
                except (json.JSONDecodeError, KeyError):
                    pass

        # No plan, no pending calls → task complete
        return {
            "task_complexity": "simple",
            "complexity_reason": "Task completed",
            "execution_phase": "initial",
        }

    return analyze_node
