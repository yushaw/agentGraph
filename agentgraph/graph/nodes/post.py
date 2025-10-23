"""Post-tool bookkeeping node."""

from __future__ import annotations

import json

from langchain_core.messages import ToolMessage

from agentgraph.graph.state import AppState


def build_post_node():
    """Create the node that updates state after tool executions."""

    def post_node(state: AppState) -> AppState:
        """Extract and apply tool results to state.

        Handles:
        - select_skill: Updates active_skill and allowed_tools
        - create_plan: Extracts the plan and initializes execution state
        """
        updates: dict = {}

        for message in reversed(state.get("messages", [])):
            if not isinstance(message, ToolMessage):
                continue

            # Handle create_plan tool
            if message.name == "create_plan":
                try:
                    payload = json.loads(message.content or "{}")
                except json.JSONDecodeError:
                    continue

                if payload.get("ok") and payload.get("plan"):
                    plan = payload["plan"]
                    updates["plan"] = plan
                    updates["step_idx"] = 0
                    updates["step_calls"] = 0
                    updates["loops"] = 0
                    updates["execution_phase"] = "loop"
                    updates["task_complexity"] = "complex"
                    updates["complexity_reason"] = "Plan created by LLM via create_plan tool"
                break

            # Handle select_skill tool
            if message.name == "select_skill":
                try:
                    payload = json.loads(message.content or "{}")
                except json.JSONDecodeError:
                    continue

                if payload.get("ok"):
                    updates["active_skill"] = payload["skill"]["id"]
                    updates["allowed_tools"] = payload.get("allowed_tools", [])
                break

        return updates

    return post_node
