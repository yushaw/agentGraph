"""Planner node implementation."""

from __future__ import annotations

from typing import Iterable, List

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import BaseTool

from agentgraph.agents import ModelResolver, invoke_planner
from agentgraph.graph.message_utils import clean_message_history
from agentgraph.graph.prompts import PLANNER_SYSTEM_PROMPT
from agentgraph.graph.state import AppState
from agentgraph.models import ModelRegistry
from agentgraph.tools import ToolRegistry

def build_planner_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tool_registry: ToolRegistry,
    persistent_global_tools: Iterable[BaseTool],
):
    """Create a planner node bound to runtime registries."""

    persistent_global_tools = list(persistent_global_tools)

    def planner_node(state: AppState) -> AppState:
        visible_tools: List[BaseTool] = list(persistent_global_tools)
        allowed = state.get("allowed_tools")
        if allowed:
            visible_tools.extend(tool_registry.allowed_tools(allowed))

        deduped: List[BaseTool] = []
        seen = set()
        for tool in visible_tools:
            if tool.name in seen:
                continue
            seen.add(tool.name)
            deduped.append(tool)
        visible_tools = deduped

        need_code = False
        for tool in visible_tools:
            metadata = tool_registry.get_meta_optional(tool.name)
            if metadata and "code" in metadata.tags:
                need_code = True
                break
        preference = state.get("model_pref")

        history: List[BaseMessage] = list(state.get("messages") or [])
        # Clean message history to remove AI messages with unanswered tool_calls
        cleaned_history = clean_message_history(history)

        prompt_messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT), *cleaned_history]
        output = invoke_planner(
            model_registry=model_registry,
            model_resolver=model_resolver,
            tools=visible_tools,
            messages=prompt_messages,
            need_code=need_code,
            preference=preference,
        )

        return {"messages": [output]}

    return planner_node
