"""Verifier node that validates step deliverables and manages step progression."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Callable, Dict

from langchain_core.messages import ToolMessage, SystemMessage

from agentgraph.graph.state import AppState

DeliverableChecker = Callable[[dict], bool]

logger = logging.getLogger(__name__)


def build_verify_node(*, deliverable_checkers: Dict[str, DeliverableChecker]):
    """Create the post-step verification node that validates deliverables."""

    def verify_node(state: AppState) -> AppState:
        """Verify step deliverables and decide whether to continue, retry, or advance.

        This node is called AFTER tools execute in the loop phase.
        It checks if the current step's deliverables were satisfied.
        """

        plan = state.get("plan") or {}
        steps = plan.get("steps", [])
        idx = state.get("step_idx", 0)

        # No current step to verify
        if idx >= len(steps):
            return {}

        step = steps[idx]
        step_id = step.get("id", f"step-{idx}")

        # ========== Check deliverables ==========
        success = False
        evidence_updates = list(state.get("evidence", []))

        # Look at recent tool messages (last 5)
        messages = state.get("messages", [])
        recent_tool_msgs = []

        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                recent_tool_msgs.append(msg)
                if len(recent_tool_msgs) >= 5:
                    break

        # Check each deliverable against recent tool outputs
        for tool_msg in recent_tool_msgs:
            try:
                payload = json.loads(tool_msg.content or "{}")
            except json.JSONDecodeError:
                payload = {"_raw": tool_msg.content}

            for deliverable in step.get("deliverables", []):
                checker = deliverable_checkers.get(deliverable)

                if checker and checker(payload):
                    # Deliverable found!
                    evidence_updates.append({
                        "step_id": step_id,
                        "step_idx": idx,
                        "deliverable": deliverable,
                        "result": payload,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "tool": tool_msg.name,
                    })
                    success = True
                    logger.info(f"✓ Step {step_id}: deliverable '{deliverable}' verified via {tool_msg.name}")
                    break

            if success:
                break

        # ========== Decision logic ==========
        max_calls = min(
            step.get("max_calls", 3),
            state.get("max_step_calls", 3)
        )

        current_calls = state.get("step_calls", 0)

        updates: Dict[str, object] = {}

        # Always update evidence if it changed
        if len(evidence_updates) != len(state.get("evidence", [])):
            updates["evidence"] = evidence_updates

        if success:
            # ✅ Success: Advance to next step
            updates["step_idx"] = idx + 1
            updates["step_calls"] = 0
            updates["messages"] = [SystemMessage(
                content=f"✓ Step '{step_id}' completed successfully. "
                        f"Deliverables: {', '.join(step.get('deliverables', []))}"
            )]
            logger.info(f"Step {idx} completed successfully, advancing to step {idx + 1}")

        elif current_calls >= max_calls:
            # ⚠️ Budget exhausted: Mark as failed and advance
            updates["step_idx"] = idx + 1
            updates["step_calls"] = 0
            updates["messages"] = [SystemMessage(
                content=f"✗ Step '{step_id}' failed after {current_calls} attempts. "
                        f"Expected deliverables: {', '.join(step.get('deliverables', []))}. "
                        f"Moving to next step."
            )]
            logger.warning(f"Step {idx} failed after {current_calls} attempts, advancing anyway")

        else:
            # 🔄 Continue retrying current step
            # Don't update step_idx or step_calls - let step_executor handle increment
            logger.info(f"Step {idx} incomplete ({current_calls}/{max_calls} calls), will retry")

        return updates

    return verify_node
