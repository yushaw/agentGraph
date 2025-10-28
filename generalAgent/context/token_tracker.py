"""Token usage tracking and monitoring.

This module provides utilities for tracking token usage from LLM API responses
and determining when context compression is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import AIMessage

from generalAgent.config.settings import ContextManagementSettings, ModelRoutingSettings


@dataclass
class TokenUsage:
    """Token usage information from a single LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_name: str


@dataclass
class ContextStatus:
    """Current context window status."""

    cumulative_prompt_tokens: int
    cumulative_completion_tokens: int
    context_window: int
    usage_ratio: float  # 0.0 to 1.0
    needs_warning: bool
    needs_compression: bool
    compression_strategy: Optional[Literal["compact", "summarize"]]


class TokenTracker:
    """Tracks token usage and determines when compression is needed.

    This class:
    1. Extracts token usage from LLM API responses
    2. Maintains cumulative token counts
    3. Determines when to trigger warnings or compression
    4. Selects appropriate compression strategy (compact vs summarize)
    """

    def __init__(
        self,
        context_settings: ContextManagementSettings,
        model_settings: ModelRoutingSettings,
    ):
        self.context_settings = context_settings
        self.model_settings = model_settings

    def extract_token_usage(self, response: AIMessage) -> Optional[TokenUsage]:
        """Extract token usage from LLM API response.

        Args:
            response: AIMessage from LLM API call

        Returns:
            TokenUsage object if metadata available, None otherwise
        """
        metadata = getattr(response, "response_metadata", {})
        token_usage = metadata.get("token_usage")

        if not token_usage:
            return None

        return TokenUsage(
            prompt_tokens=token_usage.get("prompt_tokens", 0),
            completion_tokens=token_usage.get("completion_tokens", 0),
            total_tokens=token_usage.get("total_tokens", 0),
            model_name=metadata.get("model_name", "unknown"),
        )

    def get_context_window(self, model_id: str) -> int:
        """Get context window size for a given model.

        Args:
            model_id: Model identifier (e.g., "deepseek-chat")

        Returns:
            Context window size in tokens
        """
        # Map model_id to context window from settings
        # Use base model as fallback
        if "reason" in model_id.lower():
            return self.model_settings.reason_context_window
        elif "vision" in model_id.lower() or "multimodal" in model_id.lower():
            return self.model_settings.vision_context_window
        elif "code" in model_id.lower():
            return self.model_settings.code_context_window
        elif "chat" in model_id.lower() or "kimi" in model_id.lower():
            return self.model_settings.chat_context_window
        else:
            return self.model_settings.base_context_window

    def check_status(
        self,
        cumulative_prompt_tokens: int,
        cumulative_completion_tokens: int,
        last_model_id: str,
        compact_count: int,
    ) -> ContextStatus:
        """Check current context status and determine if action is needed.

        Args:
            cumulative_prompt_tokens: Total prompt tokens used so far
            cumulative_completion_tokens: Total completion tokens used so far
            last_model_id: Model ID from last call (to get context window)
            compact_count: Number of times context has been compacted

        Returns:
            ContextStatus with current status and recommendations
        """
        if not self.context_settings.enabled:
            # Context management disabled
            return ContextStatus(
                cumulative_prompt_tokens=cumulative_prompt_tokens,
                cumulative_completion_tokens=cumulative_completion_tokens,
                context_window=0,
                usage_ratio=0.0,
                needs_warning=False,
                needs_compression=False,
                compression_strategy=None,
            )

        context_window = self.get_context_window(last_model_id)

        # Use prompt tokens for usage calculation (they represent the current context)
        usage_ratio = cumulative_prompt_tokens / context_window if context_window > 0 else 0.0

        needs_warning = usage_ratio >= self.context_settings.warning_threshold
        needs_compression = usage_ratio >= self.context_settings.force_compact_threshold

        # Determine compression strategy
        compression_strategy: Optional[Literal["compact", "summarize"]] = None
        if needs_compression or needs_warning:
            # Every Nth compact, use summarize instead
            if (compact_count + 1) % self.context_settings.summarize_cycle == 0:
                compression_strategy = "summarize"
            else:
                compression_strategy = "compact"

        return ContextStatus(
            cumulative_prompt_tokens=cumulative_prompt_tokens,
            cumulative_completion_tokens=cumulative_completion_tokens,
            context_window=context_window,
            usage_ratio=usage_ratio,
            needs_warning=needs_warning,
            needs_compression=needs_compression,
            compression_strategy=compression_strategy,
        )

    def format_warning_message(self, status: ContextStatus) -> str:
        """Format a user-facing warning message about token usage.

        Args:
            status: Current context status

        Returns:
            Formatted warning message for system reminder
        """
        percent = int(status.usage_ratio * 100)
        used = status.cumulative_prompt_tokens
        total = status.context_window

        return f"""<system_reminder>
⚠️ Token 使用警告

当前使用: {used:,} / {total:,} tokens ({percent}%)
建议: 使用 compact_context 工具压缩上下文以避免达到限制

压缩策略: {status.compression_strategy or 'compact'}
</system_reminder>"""
