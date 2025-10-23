"""Interfaces for agent factory dependencies."""

from __future__ import annotations

from typing import Protocol


class ModelResolver(Protocol):
    """Callable that returns a LangChain-compatible model runnable."""

    def __call__(self, model_id: str):
        ...
