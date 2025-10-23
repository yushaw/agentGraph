"""Step executor node coordinating subagents for plan execution."""

from __future__ import annotations

import json
from typing import Dict, Iterable, List

from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage

from agentgraph.agents import ModelResolver, invoke_subagent
from agentgraph.graph.message_utils import clean_message_history
from agentgraph.graph.prompts import SUBAGENT_TEMPLATE
from agentgraph.graph.state import AppState
from agentgraph.models import ModelRegistry
from agentgraph.tools import ToolRegistry


def _resolve_tool_set(tool_registry: ToolRegistry, names: Iterable[str]) -> List[BaseTool]:
    """Helper to resolve tool names to tool instances."""
    tools = []
    for name in names:
        try:
            tools.append(tool_registry.get_tool(name))
        except KeyError:
            continue
    return tools


def _is_user_approval(message: BaseMessage) -> bool:
    """Check if message is user approval."""
    if not isinstance(message, (HumanMessage, tuple)):
        return False

    content = ""
    if isinstance(message, HumanMessage):
        content = str(message.content).lower()
    elif isinstance(message, tuple) and len(message) >= 2:
        content = str(message[1]).lower()

    approval_keywords = ["确认", "同意", "批准", "yes", "approve", "ok", "好的", "继续"]
    return any(kw in content for kw in approval_keywords)


def build_step_executor_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: Iterable[BaseTool],
    subagent_catalog: Dict[str, List[str]],
):
    """Create a step executor node capable of running subagents for each plan step."""

    persistent_global_tools = list(persistent_global_tools)

    def step_executor_node(state: AppState) -> AppState:
        """Execute the current step in the plan."""

        plan = state.get("plan") or {}
        steps = plan.get("steps", [])
        idx = state.get("step_idx", 0)

        # No more steps to execute
        if idx >= len(steps):
            return {}

        step = steps[idx]

        # ========== Handle approval flow ==========
        if state.get("awaiting_approval"):
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]

                if _is_user_approval(last_msg):
                    # User approved, clear approval state
                    return {
                        "awaiting_approval": False,
                        "pending_calls": [],
                        "messages": [SystemMessage(content="User approved. Proceeding with execution.")],
                    }
                else:
                    # User declined, skip current step
                    return {
                        "step_idx": idx + 1,
                        "step_calls": 0,
                        "awaiting_approval": False,
                        "pending_calls": [],
                        "messages": [SystemMessage(
                            content=f"User declined step '{step.get('id')}'. Skipping to next step."
                        )],
                    }

        # ========== Check step budget ==========
        max_calls = min(
            step.get("max_calls", 3),
            state.get("max_step_calls", 3)
        )

        current_calls = state.get("step_calls", 0)

        if current_calls >= max_calls:
            # Step exceeded budget, move to next
            return {
                "step_idx": idx + 1,
                "step_calls": 0,
                "messages": [SystemMessage(
                    content=f"Step '{step.get('id')}' exceeded max calls ({max_calls}). Moving to next step."
                )],
            }

        # ========== Assemble visible tools ==========
        agent_name = step.get("agent", "generic")
        visible_tools: List[BaseTool] = list(persistent_global_tools)

        # Add subagent-specific tools
        if agent_name in subagent_catalog:
            visible_tools.extend(_resolve_tool_set(tool_registry, subagent_catalog[agent_name]))

        # Add skill-specific allowed tools
        if state.get("allowed_tools"):
            visible_tools.extend(tool_registry.allowed_tools(state["allowed_tools"]))

        # Deduplicate
        deduped: List[BaseTool] = []
        seen = set()
        for tool in visible_tools:
            if tool.name not in seen:
                seen.add(tool.name)
                deduped.append(tool)
        visible_tools = deduped

        # ========== Determine capability requirements ==========
        need_code = False
        need_vision = False
        for tool in visible_tools:
            metadata = tool_registry.get_meta_optional(tool.name)
            if metadata:
                if "code" in metadata.tags:
                    need_code = True
                if "vision" in metadata.tags:
                    need_vision = True

        # ========== Build step-specific system prompt ==========
        system_prompt = SUBAGENT_TEMPLATE.format(
            agent_name=agent_name,
            step_id=step.get("id"),
            description=step.get("description"),
            inputs=json.dumps(step.get("inputs", {}), ensure_ascii=False),
            deliverables=step.get("deliverables", []),
            success=step.get("success_criteria", "N/A"),
        )

        history: List[BaseMessage] = list(state.get("messages", []))
        # Clean message history to remove AI messages with unanswered tool_calls
        cleaned_history = clean_message_history(history)
        prompt_messages = [SystemMessage(content=system_prompt), *cleaned_history]

        # ========== Invoke subagent ==========
        output = invoke_subagent(
            model_registry=model_registry,
            model_resolver=model_resolver,
            tools=visible_tools,
            messages=prompt_messages,
            need_code=need_code,
            need_vision=need_vision,
        )

        # ========== Update state ==========
        return {
            "messages": [output],
            "step_calls": current_calls + 1,
            "loops": state.get("loops", 0) + 1,
            "execution_phase": "loop",
        }

    return step_executor_node
