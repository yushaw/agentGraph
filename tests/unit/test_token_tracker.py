"""Unit tests for TokenTracker.

Tests token usage extraction, context window calculation, and status checking.
"""

import pytest
from unittest.mock import Mock

from langchain_core.messages import AIMessage

from generalAgent.config.settings import ContextManagementSettings, ModelRoutingSettings
from generalAgent.context.token_tracker import TokenTracker, TokenUsage, ContextStatus


@pytest.fixture
def context_settings():
    """Create test context management settings."""
    return ContextManagementSettings(
        enabled=True,
        warning_threshold=0.8,
        force_compact_threshold=0.95,
        keep_recent_messages=10,
        compact_middle_messages=30,
        summarize_cycle=4,
    )


@pytest.fixture
def model_settings():
    """Create test model settings."""
    return ModelRoutingSettings(
        base_context_window=128000,
        reason_context_window=128000,
        vision_context_window=64000,
        code_context_window=200000,
        chat_context_window=256000,
    )


@pytest.fixture
def tracker(context_settings, model_settings):
    """Create TokenTracker instance."""
    return TokenTracker(context_settings, model_settings)


class TestTokenUsageExtraction:
    """Test token usage extraction from API responses."""

    def test_extract_from_valid_response(self, tracker):
        """Should extract token usage from response metadata."""
        response = AIMessage(
            content="Test response",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 1500,
                    "completion_tokens": 250,
                    "total_tokens": 1750,
                },
                "model_name": "deepseek-chat",
            },
        )

        usage = tracker.extract_token_usage(response)

        assert usage is not None
        assert usage.prompt_tokens == 1500
        assert usage.completion_tokens == 250
        assert usage.total_tokens == 1750
        assert usage.model_name == "deepseek-chat"

    def test_extract_from_response_without_metadata(self, tracker):
        """Should return None if no metadata available."""
        response = AIMessage(content="Test response")

        usage = tracker.extract_token_usage(response)

        assert usage is None

    def test_extract_from_response_without_token_usage(self, tracker):
        """Should return None if metadata exists but no token_usage."""
        response = AIMessage(
            content="Test response",
            response_metadata={"model_name": "test-model"},
        )

        usage = tracker.extract_token_usage(response)

        assert usage is None


class TestContextWindowCalculation:
    """Test context window size calculation for different models."""

    def test_base_model_context_window(self, tracker):
        """Should return base model context window."""
        window = tracker.get_context_window("deepseek-chat")
        assert window == 128000

    def test_reasoning_model_context_window(self, tracker):
        """Should return reasoning model context window."""
        window = tracker.get_context_window("deepseek-reasoner")
        assert window == 128000

    def test_vision_model_context_window(self, tracker):
        """Should return vision model context window."""
        window = tracker.get_context_window("glm-4.5v")
        assert window == 64000

    def test_code_model_context_window(self, tracker):
        """Should return code model context window."""
        window = tracker.get_context_window("some-code-model")
        assert window == 200000

    def test_chat_model_context_window(self, tracker):
        """Should return chat model context window."""
        window = tracker.get_context_window("kimi-k2-0905-preview")
        assert window == 256000

    def test_unknown_model_defaults_to_base(self, tracker):
        """Should default to base model context window for unknown models."""
        window = tracker.get_context_window("unknown-model")
        assert window == 128000


class TestContextStatusChecking:
    """Test context status checking and warning/compression decisions."""

    def test_status_below_warning_threshold(self, tracker):
        """Should not trigger warnings when below threshold."""
        status = tracker.check_status(
            cumulative_prompt_tokens=50000,  # 50k / 128k = 39%
            cumulative_completion_tokens=10000,
            last_model_id="deepseek-chat",
            compact_count=0,
        )

        assert status.usage_ratio == pytest.approx(50000 / 128000)
        assert not status.needs_warning
        assert not status.needs_compression
        assert status.compression_strategy is None

    def test_status_at_warning_threshold(self, tracker):
        """Should trigger warning at 80% threshold."""
        status = tracker.check_status(
            cumulative_prompt_tokens=102400,  # 102.4k / 128k = 80%
            cumulative_completion_tokens=20000,
            last_model_id="deepseek-chat",
            compact_count=0,
        )

        assert status.usage_ratio == pytest.approx(0.8)
        assert status.needs_warning
        assert not status.needs_compression
        assert status.compression_strategy == "compact"  # First compact

    def test_status_above_warning_below_force(self, tracker):
        """Should trigger warning but not force compression between 80-95%."""
        status = tracker.check_status(
            cumulative_prompt_tokens=115000,  # 115k / 128k = 90%
            cumulative_completion_tokens=25000,
            last_model_id="deepseek-chat",
            compact_count=1,
        )

        assert status.usage_ratio == pytest.approx(115000 / 128000)
        assert status.needs_warning
        assert not status.needs_compression
        assert status.compression_strategy == "compact"

    def test_status_at_force_threshold(self, tracker):
        """Should trigger force compression at 95% threshold."""
        status = tracker.check_status(
            cumulative_prompt_tokens=121600,  # 121.6k / 128k = 95%
            cumulative_completion_tokens=30000,
            last_model_id="deepseek-chat",
            compact_count=2,
        )

        assert status.usage_ratio == pytest.approx(0.95)
        assert status.needs_warning
        assert status.needs_compression
        assert status.compression_strategy == "compact"

    def test_compression_strategy_cycles(self, tracker):
        """Should cycle between compact and summarize strategies."""
        # compact_count=0 → compact (1st)
        status1 = tracker.check_status(
            cumulative_prompt_tokens=102400,
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=0,
        )
        assert status1.compression_strategy == "compact"

        # compact_count=1 → compact (2nd)
        status2 = tracker.check_status(
            cumulative_prompt_tokens=102400,
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=1,
        )
        assert status2.compression_strategy == "compact"

        # compact_count=2 → compact (3rd)
        status3 = tracker.check_status(
            cumulative_prompt_tokens=102400,
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=2,
        )
        assert status3.compression_strategy == "compact"

        # compact_count=3 → summarize (4th, every 4 compacts)
        status4 = tracker.check_status(
            cumulative_prompt_tokens=102400,
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=3,
        )
        assert status4.compression_strategy == "summarize"

        # compact_count=4 → compact (5th, cycle restarts)
        status5 = tracker.check_status(
            cumulative_prompt_tokens=102400,
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=4,
        )
        assert status5.compression_strategy == "compact"

    def test_status_with_disabled_context_management(self, tracker):
        """Should return inactive status when context management disabled."""
        tracker.context_settings.enabled = False

        status = tracker.check_status(
            cumulative_prompt_tokens=200000,  # Way over limit
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=0,
        )

        assert status.usage_ratio == 0.0
        assert not status.needs_warning
        assert not status.needs_compression
        assert status.compression_strategy is None


class TestWarningMessageFormatting:
    """Test warning message formatting."""

    def test_format_warning_message(self, tracker):
        """Should format a user-friendly warning message."""
        status = ContextStatus(
            cumulative_prompt_tokens=102400,
            cumulative_completion_tokens=20000,
            context_window=128000,
            usage_ratio=0.8,
            needs_warning=True,
            needs_compression=False,
            compression_strategy="compact",
        )

        message = tracker.format_warning_message(status)

        assert "⚠️ Token 使用警告" in message
        assert "102,400 / 128,000 tokens" in message
        assert "80%" in message
        assert "compact_context" in message
        assert "压缩策略: compact" in message

    def test_format_warning_with_summarize_strategy(self, tracker):
        """Should show summarize strategy in warning."""
        status = ContextStatus(
            cumulative_prompt_tokens=121600,
            cumulative_completion_tokens=30000,
            context_window=128000,
            usage_ratio=0.95,
            needs_warning=True,
            needs_compression=True,
            compression_strategy="summarize",
        )

        message = tracker.format_warning_message(status)

        assert "压缩策略: summarize" in message
        assert "95%" in message
