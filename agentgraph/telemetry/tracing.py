"""Observability helpers (LangSmith / custom tracing)."""

from __future__ import annotations

import os

from agentgraph.config.settings import ObservabilitySettings


def configure_tracing(settings: ObservabilitySettings) -> None:
    """Configure environment variables for tracing integrations."""

    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    if settings.tracing_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
