"""Default model resolver wiring using environment-derived settings.

This module provides functions to convert Pydantic settings into actual model instances.
It builds a ModelResolver function that creates ChatOpenAI instances on demand.

Key Functions:
    - resolve_model_configs(): Extract model configs from settings
    - build_model_resolver(): Create a resolver function that returns model instances

The resolver pattern allows lazy instantiation of models and supports dependency
injection for testing.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, Optional, TypedDict

from langchain_openai import ChatOpenAI

from generalAgent.agents import ModelResolver
from generalAgent.config import Settings


class ModelConfig(TypedDict):
    id: str
    api_key: Optional[str]
    base_url: Optional[str]
    context_window: int


def _resolved_value(preferred: Optional[str], *env_names: str) -> Optional[str]:
    """Return preferred value if it's not a default placeholder.

    This allows env vars to override default placeholders via Settings validation_alias.
    Default placeholders are: base-quick, reasoner-pro, vision-omni, code-pro, chat-mid.

    Args:
        preferred: Value from settings (may be a placeholder or actual model ID)
        *env_names: Fallback environment variable names to check

    Returns:
        Actual model ID or the placeholder if no override found
    """
    if preferred and preferred not in {"base-quick", "reasoner-pro", "vision-omni", "code-pro", "chat-mid"}:
        return preferred
    # If still a placeholder, check env directly as a last resort
    for name in env_names:
        value = os.getenv(name)
        if value:
            return value
    return preferred


def resolve_model_configs(settings: Settings) -> Dict[str, ModelConfig]:
    """Build normalized model configs (id + credentials) from settings.

    Extracts model configurations for all five slots: base, reason, vision, code, chat.
    Each config contains model ID, API key, and optional base URL.

    Args:
        settings: Application settings loaded from .env

    Returns:
        Dict mapping slot names to ModelConfig dicts with keys: id, api_key, base_url

    Note:
        Settings now correctly load from environment variables via BaseSettings,
        so no manual os.getenv fallback is needed.
    """

    return {
        "base": {
            "id": _resolved_value(settings.models.base, "MODEL_BASIC_ID", "MODEL_BASE_ID", "MODEL_BASE") or "base-quick",
            "api_key": settings.models.base_api_key,
            "base_url": settings.models.base_base_url,
            "context_window": settings.models.base_context_window,
        },
        "reason": {
            "id": _resolved_value(settings.models.reason, "MODEL_REASONING_ID", "MODEL_REASON_ID", "MODEL_REASON") or "reasoner-pro",
            "api_key": settings.models.reason_api_key,
            "base_url": settings.models.reason_base_url,
            "context_window": settings.models.reason_context_window,
        },
        "vision": {
            "id": _resolved_value(settings.models.vision, "MODEL_MULTIMODAL_ID", "MODEL_VISION_ID", "MODEL_VISION") or "vision-omni",
            "api_key": settings.models.vision_api_key,
            "base_url": settings.models.vision_base_url,
            "context_window": settings.models.vision_context_window,
        },
        "code": {
            "id": _resolved_value(settings.models.code, "MODEL_CODE_ID", "MODEL_CODE") or "code-pro",
            "api_key": settings.models.code_api_key,
            "base_url": settings.models.code_base_url,
            "context_window": settings.models.code_context_window,
        },
        "chat": {
            "id": _resolved_value(settings.models.chat, "MODEL_CHAT_ID", "MODEL_CHAT") or "chat-mid",
            "api_key": settings.models.chat_api_key,
            "base_url": settings.models.chat_base_url,
            "context_window": settings.models.chat_context_window,
        },
    }


def _chat_kwargs(model: str, api_key: Optional[str], base_url: Optional[str]) -> Dict[str, object]:
    if not api_key:
        raise RuntimeError(f"缺少模型 {model} 的 API Key，请在 .env 中配置。")
    kwargs: Dict[str, object] = {"model": model, "api_key": api_key, "temperature": 0.2}
    if base_url:
        kwargs["base_url"] = base_url
    return kwargs


def build_model_resolver(model_configs: Dict[str, ModelConfig]) -> ModelResolver:
    """Construct a resolver that returns ChatOpenAI-compatible clients.

    Creates a function that takes a model ID and returns a configured ChatOpenAI instance.
    The resolver uses lazy instantiation - models are only created when requested.

    Args:
        model_configs: Dict of model configurations from resolve_model_configs()

    Returns:
        ModelResolver: Function that takes model_id and returns ChatOpenAI instance

    Raises:
        KeyError: If requested model_id is not in the configuration
        RuntimeError: If API key is missing for the requested model

    Example:
        >>> resolver = build_model_resolver(model_configs)
        >>> chat_model = resolver("deepseek-chat")
        >>> response = chat_model.invoke("Hello!")
    """

    catalog: Dict[str, Callable[[], ChatOpenAI]] = {}
    for config in model_configs.values():
        model_id = config["id"]
        catalog[model_id] = lambda cfg=config: ChatOpenAI(**_chat_kwargs(cfg["id"], cfg["api_key"], cfg["base_url"]))

    def resolver(model_id: str):
        if model_id not in catalog:
            raise KeyError(f"模型 {model_id} 未在配置中注册。")
        return catalog[model_id]()

    return resolver
