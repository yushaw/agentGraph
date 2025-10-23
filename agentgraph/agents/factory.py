"""Helpers that build LangGraph-compatible agents."""

from __future__ import annotations

from typing import Iterable, List

from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from agentgraph.models import ModelRegistry

from .interfaces import ModelResolver


async def invoke_planner(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tools: Iterable[BaseTool],
    messages: List[BaseMessage],
    need_code: bool = False,
    need_vision: bool = False,
    preference: str | None = None,
):
    """Run the planner model with the provided messages and tools."""

    spec = model_registry.prefer(
        phase="plan",
        require_tools=True,
        need_code=need_code,
        need_vision=need_vision,
        preference=preference,
    )
    model = model_resolver(spec.model_id)
    runnable = model.bind_tools(list(tools))
    return await runnable.ainvoke(messages)


async def invoke_subagent(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    tools: Iterable[BaseTool],
    messages: List[BaseMessage],
    need_code: bool = False,
    need_vision: bool = False,
):
    """Execute a delegated subagent step."""

    spec = model_registry.prefer(
        phase="delegate",
        require_tools=True,
        need_code=need_code,
        need_vision=need_vision,
    )
    model = model_resolver(spec.model_id)
    runnable = model.bind_tools(list(tools))
    return await runnable.ainvoke(messages)


# def get_decomposer_model(
#     *,
#     model_registry: ModelRegistry,
#     model_resolver: ModelResolver,
#     preference: str | None = None,
# ):
#     """Return a tool-free model for plan generation."""

#     spec = model_registry.prefer(
#         phase="decompose",
#         require_tools=False,
#         preference=preference,
#     )
#     return model_resolver(spec.model_id)
