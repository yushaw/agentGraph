"""Step executor node coordinating subagents for plan execution - Charlie MVP Edition."""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, List

from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, SystemMessage

from agentgraph.agents import ModelResolver, invoke_subagent
from agentgraph.graph.message_utils import clean_message_history, truncate_messages_safely
from agentgraph.graph.prompts import STEP_EXECUTOR_TEMPLATE, build_dynamic_reminder
from agentgraph.graph.state import AppState
from agentgraph.models import ModelRegistry
from agentgraph.tools import ToolRegistry
from agentgraph.utils.logging_utils import (
    log_node_entry,
    log_node_exit,
    log_step_execution,
    log_visible_tools,
    log_prompt,
)
from agentgraph.utils.error_handler import with_error_boundary, handle_model_error, ModelInvocationError

LOGGER = logging.getLogger("agentgraph.step_executor")


def _resolve_tool_set(tool_registry: ToolRegistry, names: Iterable[str]) -> List[BaseTool]:
    """Helper to resolve tool names to tool instances."""
    tools = []
    for name in names:
        try:
            tools.append(tool_registry.get_tool(name))
        except KeyError:
            continue
    return tools




def build_step_executor_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: Iterable[BaseTool],
    subagent_catalog: Dict[str, List[str]],
    skill_registry,
):
    """Create a step executor node capable of running subagents for each plan step."""

    persistent_global_tools = list(persistent_global_tools)

    @with_error_boundary("step_executor")
    async def step_executor_node(state: AppState) -> AppState:
        """Execute the current step in the plan."""
        log_node_entry(LOGGER, "step_executor", state)

        plan = state.get("plan") or {}
        steps = plan.get("steps", [])
        idx = state.get("step_idx", 0)

        # No more steps to execute
        if idx >= len(steps):
            LOGGER.info("No more steps to execute")
            return {}

        step = steps[idx]

        # ========== Check step budget ==========
        max_calls = min(
            step.get("max_calls", 3),
            state.get("max_step_calls", 3)
        )

        current_calls = state.get("step_calls", 0)

        # Log step execution details
        log_step_execution(LOGGER, idx, step, current_calls, max_calls)

        if current_calls >= max_calls:
            # Step exceeded budget, move to next
            LOGGER.warning(f"Step '{step.get('id')}' exceeded budget ({current_calls}/{max_calls}), moving to next step")
            updates = {
                "step_idx": idx + 1,
                "step_calls": 0,
                "messages": [SystemMessage(
                    content=f"步骤 '{step.get('id')}' 已达到最大调用次数 ({max_calls})，跳到下一步。"
                )],
            }
            log_node_exit(LOGGER, "step_executor", updates)
            return updates

        # ========== Assemble visible tools ==========
        agent_name = step.get("agent", "generic")
        visible_tools: List[BaseTool] = list(persistent_global_tools)
        LOGGER.info(f"Building visible tools for agent '{agent_name}'...")
        LOGGER.info(f"  - Starting with {len(persistent_global_tools)} persistent global tools")

        # Add subagent-specific tools
        if agent_name in subagent_catalog:
            subagent_tools = _resolve_tool_set(tool_registry, subagent_catalog[agent_name])
            visible_tools.extend(subagent_tools)
            LOGGER.info(f"  - Added {len(subagent_tools)} subagent-specific tools for '{agent_name}'")

        # Add skill-specific allowed tools (via select_skill)
        if state.get("allowed_tools"):
            skill_tools = tool_registry.allowed_tools(state["allowed_tools"])
            visible_tools.extend(skill_tools)
            LOGGER.info(f"  - Added {len(skill_tools)} tools from activated skills: {state['allowed_tools']}")

        # Add tools from @mentioned agents/skills/tools
        mentioned = state.get("mentioned_agents", [])
        if mentioned:
            LOGGER.info(f"  - Processing @mentions: {mentioned}")
            for mention in mentioned:
                # Try to find matching skill
                try:
                    skill = skill_registry.get(mention)
                    if skill and skill.allowed_tools:
                        mention_tools = tool_registry.allowed_tools(skill.allowed_tools)
                        visible_tools.extend(mention_tools)
                        LOGGER.info(f"    - @{mention} → skill with {len(mention_tools)} tools: {skill.allowed_tools}")
                except (KeyError, AttributeError):
                    LOGGER.debug(f"    - @{mention} not found as skill")

                # Try to find matching tool directly
                try:
                    tool = tool_registry.get_tool(mention)
                    visible_tools.append(tool)
                    LOGGER.info(f"    - @{mention} → direct tool: {tool.name}")
                except KeyError:
                    LOGGER.debug(f"    - @{mention} not found as tool")

        # Deduplicate
        deduped: List[BaseTool] = []
        seen = set()
        for tool in visible_tools:
            if tool.name not in seen:
                seen.add(tool.name)
                deduped.append(tool)
        visible_tools = deduped
        LOGGER.info(f"  - Final tool count after deduplication: {len(visible_tools)}")

        # ========== Determine capability requirements ==========
        need_code = False
        need_vision = False
        LOGGER.info("Detecting capability requirements from tools...")
        for tool in visible_tools:
            metadata = tool_registry.get_meta_optional(tool.name)
            if metadata:
                if "code" in metadata.tags:
                    need_code = True
                if "vision" in metadata.tags:
                    need_vision = True
        LOGGER.info(f"  - need_code: {need_code}, need_vision: {need_vision}")

        # ========== Build step-specific system prompt ==========
        base_prompt = STEP_EXECUTOR_TEMPLATE.format(
            agent_name=agent_name,
            step_id=step.get("id"),
            description=step.get("description"),
            inputs=json.dumps(step.get("inputs", {}), ensure_ascii=False),
            deliverables=", ".join(step.get("deliverables", [])),
            success=step.get("success_criteria", "N/A"),
        )

        # Add dynamic reminder
        active_skill = state.get("active_skill")
        mentioned_agents = state.get("mentioned_agents", [])

        LOGGER.info("Building system prompt...")
        dynamic_reminder = build_dynamic_reminder(
            active_skill=active_skill,
            mentioned_agents=mentioned_agents,
            has_images=need_vision,
            has_code=need_code,
        )

        if dynamic_reminder:
            system_prompt = f"{base_prompt}\n\n{dynamic_reminder}"
            LOGGER.info(f"  - Dynamic reminder added: {len(dynamic_reminder)} chars")
        else:
            system_prompt = base_prompt

        # Log the full system prompt
        log_prompt(LOGGER, "step_executor", system_prompt)

        # Log visible tools
        log_visible_tools(LOGGER, "step_executor", visible_tools)

        # ========== Prepare context (safely truncate for token efficiency) ==========
        history: List[BaseMessage] = list(state.get("messages", []))
        # Clean first, then safely truncate to keep last 10 messages (preserving pairs - token optimization)
        # Increased from 3 to 10 to provide more context for LLM to judge task completion
        cleaned_history = clean_message_history(history)
        recent_context = truncate_messages_safely(cleaned_history, keep_recent=10)
        LOGGER.info(f"  - Message history: {len(history)} → {len(cleaned_history)} (cleaned) → {len(recent_context)} (kept)")

        prompt_messages = [SystemMessage(content=system_prompt), *recent_context]

        # ========== Invoke subagent ==========
        LOGGER.info(f"Invoking subagent '{agent_name}' (need_code={need_code}, need_vision={need_vision})...")

        try:
            output = await invoke_subagent(
                model_registry=model_registry,
                model_resolver=model_resolver,
                tools=visible_tools,
                messages=prompt_messages,
                need_code=need_code,
                need_vision=need_vision,
            )
        except Exception as e:
            LOGGER.error(f"Subagent invocation failed: {e}")
            error_msg = handle_model_error(e)
            raise ModelInvocationError(str(e), user_message=error_msg)

        LOGGER.info("Subagent invocation completed")

        # ========== Check if step is complete (Claude Code natural stop mechanism) ==========
        if not output.tool_calls:
            # LLM didn't request any tool calls, step is complete
            LOGGER.info(f"Step '{step.get('id')}' completed naturally (no tool calls in response)")
            updates = {
                "messages": [output],
                "step_idx": idx + 1,  # Move to next step
                "step_calls": 0,      # Reset call counter
                "loops": state.get("loops", 0) + 1,
                "execution_phase": "loop",
            }
        else:
            # LLM still has tool calls, continue current step
            LOGGER.info(f"Step '{step.get('id')}' continuing (tool calls present)")
            updates = {
                "messages": [output],
                "step_calls": current_calls + 1,
                "loops": state.get("loops", 0) + 1,
                "execution_phase": "loop",
            }

            # Safety net: if reached max_calls, also move to next step
            if current_calls + 1 >= max_calls:
                LOGGER.warning(f"Step '{step.get('id')}' reached max_calls limit ({max_calls}), moving to next step")
                updates["step_idx"] = idx + 1
                updates["step_calls"] = 0

        log_node_exit(LOGGER, "step_executor", updates)
        return updates

    return step_executor_node
