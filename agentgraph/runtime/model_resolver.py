"""Default model resolver wiring using environment-derived settings."""

from __future__ import annotations

import os
from typing import Callable, Dict, Optional, TypedDict

from langchain_openai import ChatOpenAI

from agentgraph.agents import ModelResolver
from agentgraph.config import Settings


class ModelConfig(TypedDict):
    id: str
    api_key: Optional[str]
    base_url: Optional[str]


def _env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _resolved_value(preferred: Optional[str], *env_names: str) -> Optional[str]:
    if preferred and preferred not in {"base-quick", "reasoner-pro", "vision-omni", "code-pro", "chat-mid"}:
        return preferred
    return _env(*env_names) or preferred


def resolve_model_configs(settings: Settings) -> Dict[str, ModelConfig]:
    """Build normalized model configs (id + credentials) using settings and env fallbacks."""

    return {
        "base": {
            "id": _resolved_value(settings.models.base, "MODEL_BASIC_ID", "MODEL_BASE_ID", "MODEL_BASE") or "base-quick",
            "api_key": settings.models.base_api_key or _env("MODEL_BASIC_API_KEY", "MODEL_BASE_API_KEY"),
            "base_url": settings.models.base_base_url or _env("MODEL_BASIC_BASE_URL", "MODEL_BASE_URL"),
        },
        "reason": {
            "id": _resolved_value(settings.models.reason, "MODEL_REASONING_ID", "MODEL_REASON_ID", "MODEL_REASON") or "reasoner-pro",
            "api_key": settings.models.reason_api_key or _env("MODEL_REASONING_API_KEY", "MODEL_REASON_API_KEY"),
            "base_url": settings.models.reason_base_url or _env("MODEL_REASONING_BASE_URL", "MODEL_REASON_URL"),
        },
        "vision": {
            "id": _resolved_value(settings.models.vision, "MODEL_MULTIMODAL_ID", "MODEL_VISION_ID", "MODEL_VISION") or "vision-omni",
            "api_key": settings.models.vision_api_key or _env("MODEL_MULTIMODAL_API_KEY", "MODEL_VISION_API_KEY"),
            "base_url": settings.models.vision_base_url or _env("MODEL_MULTIMODAL_BASE_URL", "MODEL_VISION_URL"),
        },
        "code": {
            "id": _resolved_value(settings.models.code, "MODEL_CODE_ID", "MODEL_CODE") or "code-pro",
            "api_key": settings.models.code_api_key or _env("MODEL_CODE_API_KEY"),
            "base_url": settings.models.code_base_url or _env("MODEL_CODE_BASE_URL", "MODEL_CODE_URL"),
        },
        "chat": {
            "id": _resolved_value(settings.models.chat, "MODEL_CHAT_ID", "MODEL_CHAT") or "chat-mid",
            "api_key": settings.models.chat_api_key or _env("MODEL_CHAT_API_KEY"),
            "base_url": settings.models.chat_base_url or _env("MODEL_CHAT_BASE_URL", "MODEL_CHAT_URL"),
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
    """Construct a resolver that returns ChatOpenAI-compatible clients."""

    catalog: Dict[str, Callable[[], ChatOpenAI]] = {}
    for config in model_configs.values():
        model_id = config["id"]
        catalog[model_id] = lambda cfg=config: ChatOpenAI(**_chat_kwargs(cfg["id"], cfg["api_key"], cfg["base_url"]))

    def resolver(model_id: str):
        if model_id not in catalog:
            raise KeyError(f"模型 {model_id} 未在配置中注册。")
        return catalog[model_id]()

    return resolver
