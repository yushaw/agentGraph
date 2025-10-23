"""Post-tool bookkeeping node."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import ToolMessage

from agentgraph.graph.state import AppState
from agentgraph.utils.logging_utils import log_node_entry, log_node_exit, log_plan_created
from agentgraph.utils.error_handler import with_error_boundary

LOGGER = logging.getLogger("agentgraph.post")


def build_post_node():
    """Create the node that updates state after tool executions."""

    @with_error_boundary("post")
    def post_node(state: AppState) -> AppState:
        """Extract and apply tool results to state.

        Handles:
        - select_skill: Updates active_skill and allowed_tools
        - create_plan: Extracts the plan and initializes execution state
        """
        log_node_entry(LOGGER, "post", state)

        updates: dict = {}
        messages = state.get("messages", [])
        LOGGER.info(f"Processing {len(messages)} messages for tool results...")

        for message in reversed(messages):
            if not isinstance(message, ToolMessage):
                continue

            # Handle create_plan tool
            if message.name == "create_plan":
                LOGGER.info("Found create_plan tool result")
                try:
                    payload = json.loads(message.content or "{}")
                except json.JSONDecodeError as e:
                    LOGGER.warning(f"Failed to parse create_plan result: {e}")
                    continue

                if payload.get("ok") and payload.get("plan"):
                    plan = payload["plan"]
                    LOGGER.info(f"Extracting plan with {len(plan.get('steps', []))} steps")
                    log_plan_created(LOGGER, plan)

                    updates["plan"] = plan
                    updates["step_idx"] = 0
                    updates["step_calls"] = 0
                    updates["loops"] = 0
                    updates["execution_phase"] = "loop"
                    updates["task_complexity"] = "complex"
                    updates["complexity_reason"] = "Plan created by LLM via create_plan tool"
                else:
                    LOGGER.warning("create_plan tool did not return a valid plan")
                break

            # Handle select_skill tool
            if message.name == "select_skill":
                LOGGER.info("Found select_skill tool result")
                try:
                    payload = json.loads(message.content or "{}")
                except json.JSONDecodeError as e:
                    LOGGER.warning(f"Failed to parse select_skill result: {e}")
                    continue

                if payload.get("ok"):
                    skill_id = payload["skill"]["id"]
                    allowed_tools = payload.get("allowed_tools", [])
                    LOGGER.info(f"Activating skill '{skill_id}' with {len(allowed_tools)} tools")
                    updates["active_skill"] = skill_id
                    updates["allowed_tools"] = allowed_tools
                else:
                    LOGGER.warning("select_skill tool did not succeed")
                break

        if not updates:
            LOGGER.info("No state updates from post processing")

        log_node_exit(LOGGER, "post", updates)
        return updates

    return post_node
