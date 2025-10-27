"""Environment-bound configuration objects.

This module provides Pydantic BaseSettings-based configuration loading from .env files.
All settings classes automatically load from environment variables with support for
multiple alias names (e.g., MODEL_BASIC_* and MODEL_BASE_* both work).

Example:
    from generalAgent.config.settings import get_settings

    settings = get_settings()  # Cached singleton
    api_key = settings.models.reason_api_key
    max_loops = settings.governance.max_loops
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class ModelRoutingSettings(BaseSettings):
    """Vendor-neutral model identifiers and credentials.

    Automatically loads from .env file with support for multiple alias names:
    - MODEL_BASE, MODEL_BASE_ID, MODEL_BASIC_ID (DeepSeek/generic base model)
    - MODEL_REASON, MODEL_REASON_ID, MODEL_REASONING_ID (reasoning model)
    - MODEL_VISION, MODEL_VISION_ID, MODEL_MULTIMODAL_ID (vision model)
    - MODEL_CODE, MODEL_CODE_ID (code generation model)
    - MODEL_CHAT, MODEL_CHAT_ID (chat model)

    Each model slot has three fields: id, api_key, base_url.
    """

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
    base_context_window: int = Field(
        default=128000,
        validation_alias=AliasChoices("MODEL_BASE_CONTEXT_WINDOW", "MODEL_BASIC_CONTEXT_WINDOW"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
    reason_context_window: int = Field(
        default=128000,
        validation_alias=AliasChoices("MODEL_REASON_CONTEXT_WINDOW", "MODEL_REASONING_CONTEXT_WINDOW"),
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
    vision_context_window: int = Field(
        default=64000,
        validation_alias=AliasChoices("MODEL_VISION_CONTEXT_WINDOW", "MODEL_MULTIMODAL_CONTEXT_WINDOW"),
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
    code_context_window: int = Field(
        default=200000,
        validation_alias=AliasChoices("MODEL_CODE_CONTEXT_WINDOW"),
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
    chat_context_window: int = Field(
        default=256000,
        validation_alias=AliasChoices("MODEL_CHAT_CONTEXT_WINDOW"),
    )


class GovernanceSettings(BaseSettings):
    """Runtime governance and control settings.

    Controls agent behavior limits and policies:
    - auto_approve_writes: Skip HITL approval for file writes (default: False)
    - max_loops: Maximum agent loop iterations (1-500, default: 100)
    - max_message_history: Message history window size (10-100, default: 40)
    """

    auto_approve_writes: bool = Field(default=False, alias="AUTO_APPROVE_WRITES")
    max_loops: int = Field(default=100, ge=1, le=500)
    max_message_history: int = Field(default=40, ge=10, le=100, alias="MAX_MESSAGE_HISTORY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ObservabilitySettings(BaseSettings):
    """Tracing, logging, and persistence configuration.

    Controls observability features:
    - LangSmith tracing (LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT, etc.)
    - Logging settings (LOG_PROMPT_MAX_LENGTH)
    - Session persistence (SESSION_DB_PATH for SQLite storage)
    """

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class DocumentSettings(BaseModel):
    """Document extraction and search configuration.

    These settings control how documents (PDF/DOCX/XLSX/PPTX) are read,
    extracted, and indexed for search.
    """

    # Text file limits
    text_file_max_size: int = 100_000  # 100KB - full read threshold
    text_preview_chars: int = 50_000   # 50K chars - preview size for large text files

    # PDF preview limits
    pdf_preview_pages: int = 10
    pdf_preview_chars: int = 30_000

    # DOCX preview limits
    docx_preview_pages: int = 10
    docx_preview_chars: int = 30_000

    # XLSX preview limits
    xlsx_preview_sheets: int = 3
    xlsx_preview_chars: int = 20_000

    # PPTX preview limits
    pptx_preview_slides: int = 15
    pptx_preview_chars: int = 25_000

    # Search settings
    search_max_results_default: int = 5

    # Index settings
    index_stale_threshold_hours: int = 24  # Rebuild index if file modified within 24h


class Settings(BaseSettings):
    """Root application settings loaded from .env file.

    Hierarchical structure containing four nested settings groups:
    - models: Model routing and API credentials (ModelRoutingSettings)
    - governance: Agent behavior controls (GovernanceSettings)
    - observability: Tracing and logging (ObservabilitySettings)
    - documents: Document processing settings (DocumentSettings)

    All values are automatically loaded from .env via Pydantic BaseSettings.
    Use get_settings() to obtain a cached singleton instance.
    """

    environment: str = Field(default="dev", alias="APP_ENV")
    models: ModelRoutingSettings = Field(default_factory=ModelRoutingSettings)
    governance: GovernanceSettings = Field(default_factory=GovernanceSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    documents: DocumentSettings = Field(default_factory=DocumentSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Uses LRU cache to ensure only one Settings object is created per process.
    All configuration is automatically loaded from .env file.

    Returns:
        Settings: Cached application settings instance
    """
    return Settings()
