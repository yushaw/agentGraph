"""Environment-bound configuration objects."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class ModelRoutingSettings(BaseModel):
    """Vendor-neutral model identifiers pulled from env."""

    base: str = Field(
        default="base-quick",
        validation_alias=AliasChoices("MODEL_BASE", "MODEL_BASE_ID", "MODEL_BASIC_ID"),
    )
    base_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_BASE_API_KEY", "MODEL_BASIC_API_KEY"),
    )
    base_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_BASE_URL", "MODEL_BASIC_BASE_URL"),
    )

    reason: str = Field(
        default="reasoner-pro",
        validation_alias=AliasChoices("MODEL_REASON", "MODEL_REASON_ID", "MODEL_REASONING_ID"),
    )
    reason_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_REASON_API_KEY", "MODEL_REASONING_API_KEY"),
    )
    reason_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_REASON_URL", "MODEL_REASONING_BASE_URL"),
    )

    vision: str = Field(
        default="vision-omni",
        validation_alias=AliasChoices("MODEL_VISION", "MODEL_VISION_ID", "MODEL_MULTIMODAL_ID"),
    )
    vision_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_VISION_API_KEY", "MODEL_MULTIMODAL_API_KEY"),
    )
    vision_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_VISION_URL", "MODEL_MULTIMODAL_BASE_URL"),
    )

    code: str = Field(
        default="code-pro",
        validation_alias=AliasChoices("MODEL_CODE", "MODEL_CODE_ID"),
    )
    code_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_CODE_API_KEY", "MODEL_CODEKIT_API_KEY"),
    )
    code_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_CODE_URL", "MODEL_CODE_BASE_URL"),
    )

    chat: str = Field(
        default="chat-mid",
        validation_alias=AliasChoices("MODEL_CHAT", "MODEL_CHAT_ID"),
    )
    chat_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_CHAT_API_KEY", "MODEL_DEFAULT_CHAT_API_KEY"),
    )
    chat_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_CHAT_URL", "MODEL_CHAT_BASE_URL"),
    )


class GovernanceSettings(BaseModel):
    """Runtime governance toggles."""

    auto_approve_writes: bool = Field(default=False, alias="AUTO_APPROVE_WRITES")
    max_loops: int = Field(default=100, ge=1, le=500)
    max_message_history: int = Field(default=40, ge=10, le=100, alias="MAX_MESSAGE_HISTORY")


class ObservabilitySettings(BaseModel):
    """Tracing & persistence feature flags."""

    langsmith_project: Optional[str] = Field(default=None, alias="LANGCHAIN_PROJECT")
    langsmith_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY")
    )
    langsmith_endpoint: Optional[str] = Field(default=None, alias="LANGCHAIN_ENDPOINT")
    tracing_enabled: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")

    # Logging settings
    log_prompt_max_length: int = Field(default=500, ge=100, le=5000, alias="LOG_PROMPT_MAX_LENGTH")

    # Session persistence database path
    # Default: ./data/sessions.db (SQLite)
    # Set to empty string to disable persistence
    session_db_path: Optional[str] = Field(default=None, alias="SESSION_DB_PATH")


class Settings(BaseSettings):
    """Application settings rooted in `.env`."""

    environment: str = Field(default="dev", alias="APP_ENV")
    models: ModelRoutingSettings = Field(default_factory=ModelRoutingSettings)
    governance: GovernanceSettings = Field(default_factory=GovernanceSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()
