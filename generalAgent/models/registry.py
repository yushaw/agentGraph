"""Model management utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from .typing import ModelKey


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Normalized description of an LLM/VLM endpoint."""

    key: ModelKey
    model_id: str
    can_tools: bool
    multimodal: bool
    domain: str  # general | reasoning | code | chat
    speed: str  # fast | normal | slow
    quality: str  # low | med | high
    context_window: int  # Maximum context window size in tokens


class ModelRegistry:
    """Central registry for model specs and routing heuristics."""

    def __init__(self, specs: Optional[Iterable[ModelSpec]] = None) -> None:
        self._specs: Dict[ModelKey, ModelSpec] = {}
        if specs:
            for spec in specs:
                self.register(spec)

    def register(self, spec: ModelSpec) -> None:
        """Store a spec under its key."""

        self._specs[spec.key] = spec

    def get(self, key: ModelKey) -> ModelSpec:
        """Return the spec for a given key."""

        if key not in self._specs:
            raise KeyError(f"Unknown model key: {key}")
        return self._specs[key]

    def prefer(
        self,
        *,
        phase: str,
        require_tools: bool,
        need_code: bool = False,
        need_vision: bool = False,
        preference: Optional[str] = None,
    ) -> ModelSpec:
        """Choose a model spec according to the routing heuristics."""

        # Vision-first selection
        if need_vision and not require_tools:
            return self.get("vision")

        if require_tools:
            if need_code:
                return self.get("code")
            if preference == "reasoning":
                return self.get("reason")
            return self.get("chat")

        if preference == "reasoning":
            return self.get("reason")
        return self.get("base")


def build_default_registry(model_configs: Dict[str, Dict[str, object]]) -> ModelRegistry:
    """Instantiate the registry with defaults drawn from configuration.

    Args:
        model_configs: Dictionary mapping slot names to model configuration dicts.
                      Each config dict must have 'id' and 'context_window' keys.
    """

    registry = ModelRegistry(
        [
            ModelSpec(
                key="base",
                model_id=str(model_configs["base"]["id"]),
                can_tools=False,
                multimodal=False,
                domain="general",
                speed="fast",
                quality="low",
                context_window=int(model_configs["base"]["context_window"]),
            ),
            ModelSpec(
                key="reason",
                model_id=str(model_configs["reason"]["id"]),
                can_tools=True,
                multimodal=False,
                domain="reasoning",
                speed="slow",
                quality="high",
                context_window=int(model_configs["reason"]["context_window"]),
            ),
            ModelSpec(
                key="vision",
                model_id=str(model_configs["vision"]["id"]),
                can_tools=False,
                multimodal=True,
                domain="general",
                speed="normal",
                quality="med",
                context_window=int(model_configs["vision"]["context_window"]),
            ),
            ModelSpec(
                key="code",
                model_id=str(model_configs["code"]["id"]),
                can_tools=True,
                multimodal=False,
                domain="code",
                speed="normal",
                quality="high",
                context_window=int(model_configs["code"]["context_window"]),
            ),
            ModelSpec(
                key="chat",
                model_id=str(model_configs["chat"]["id"]),
                can_tools=True,
                multimodal=False,
                domain="chat",
                speed="normal",
                quality="med",
                context_window=int(model_configs["chat"]["context_window"]),
            ),
        ]
    )
    return registry
