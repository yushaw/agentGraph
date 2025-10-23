"""Finalize node that produces a closing assistant response."""

from __future__ import annotations

from typing import List

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

from agentgraph.agents import ModelResolver, invoke_planner
from agentgraph.graph.message_utils import clean_message_history
from agentgraph.graph.prompts import PLANNER_SYSTEM_PROMPT
from agentgraph.graph.state import AppState
from agentgraph.models import ModelRegistry

FINALIZE_PROMPT = (
    "You are finishing the conversation. Summarize the tool results for the user. "
    "Do not call any tools. Respond in the user's language."
)


def build_finalize_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
):
    def finalize_node(state: AppState) -> AppState:
        history: List[BaseMessage] = list(state.get("messages") or [])
        if not history or not isinstance(history[-1], ToolMessage):
            return {}
        if history[-1].name in {"list_skills", "select_skill"}:
            return {}

        # Clean message history to remove AI messages with unanswered tool_calls
        # This is critical for OpenAI API compatibility
        cleaned_history = _clean_message_history(history)

        prompt_messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            SystemMessage(content=FINALIZE_PROMPT),
            *cleaned_history
        ]
        output = invoke_planner(
            model_registry=model_registry,
            model_resolver=model_resolver,
            tools=[],
            messages=prompt_messages,
            need_code=False,
            preference=state.get("model_pref"),
        )
        return {"messages": [output]}

    return finalize_node
