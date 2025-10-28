"""Smoke tests for context management system.

Quick validation tests to ensure basic functionality works.
Run these before commits to catch obvious breakage.
"""

import pytest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from generalAgent.config.settings import get_settings
from generalAgent.context import TokenTracker, ContextCompressor, TokenUsage, ContextStatus


class TestBasicImports:
    """Verify all components can be imported."""

    def test_import_settings(self):
        """Should import settings successfully."""
        settings = get_settings()
        assert settings is not None
        assert hasattr(settings, "context")
        assert hasattr(settings, "models")

    def test_import_token_tracker(self):
        """Should import TokenTracker."""
        from generalAgent.context import TokenTracker

        assert TokenTracker is not None

    def test_import_context_compressor(self):
        """Should import ContextCompressor."""
        from generalAgent.context import ContextCompressor

        assert ContextCompressor is not None

    def test_import_compact_tool(self):
        """Should import compact_context tool."""
        from generalAgent.tools.builtin.compact_context import compact_context

        assert compact_context is not None


class TestBasicInitialization:
    """Verify components can be initialized."""

    def test_token_tracker_initialization(self):
        """Should initialize TokenTracker without errors."""
        settings = get_settings()
        tracker = TokenTracker(settings.context, settings.models)
        assert tracker is not None

    def test_context_compressor_initialization(self):
        """Should initialize ContextCompressor without errors."""
        settings = get_settings()
        compressor = ContextCompressor(settings.context)
        assert compressor is not None


class TestTokenTrackerSmoke:
    """Quick smoke tests for TokenTracker."""

    def test_extract_tokens_from_response(self):
        """Should extract tokens from AIMessage."""
        settings = get_settings()
        tracker = TokenTracker(settings.context, settings.models)

        response = AIMessage(
            content="Test",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
                "model_name": "test-model",
            },
        )

        usage = tracker.extract_token_usage(response)
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 20

    def test_check_status_no_warning(self):
        """Should not trigger warning when below threshold."""
        settings = get_settings()
        tracker = TokenTracker(settings.context, settings.models)

        status = tracker.check_status(
            cumulative_prompt_tokens=1000,  # Very low
            cumulative_completion_tokens=100,
            last_model_id="test-model",
            compact_count=0,
        )

        assert not status.needs_warning
        assert not status.needs_compression

    def test_check_status_with_warning(self):
        """Should trigger warning when above threshold."""
        settings = get_settings()
        tracker = TokenTracker(settings.context, settings.models)

        # Use 85% of context window
        context_window = settings.models.base_context_window
        high_usage = int(context_window * 0.85)

        status = tracker.check_status(
            cumulative_prompt_tokens=high_usage,
            cumulative_completion_tokens=1000,
            last_model_id="test-model",
            compact_count=0,
        )

        assert status.needs_warning
        assert status.compression_strategy is not None


class TestContextCompressorSmoke:
    """Quick smoke tests for ContextCompressor."""

    def test_partition_messages(self):
        """Should partition messages without errors."""
        settings = get_settings()
        compressor = ContextCompressor(settings.context)

        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="User 1"),
            AIMessage(content="AI 1"),
            HumanMessage(content="User 2"),
            AIMessage(content="AI 2"),
        ]

        partitions = compressor.partition_messages(messages, strategy="compact")

        assert "system" in partitions
        assert "old" in partitions
        assert "middle" in partitions
        assert "recent" in partitions

    def test_estimate_compression(self):
        """Should estimate compression without errors."""
        settings = get_settings()
        compressor = ContextCompressor(settings.context)

        messages = [SystemMessage(content="System")] + [
            HumanMessage(content=f"Message {i}") for i in range(50)
        ]

        estimate = compressor.estimate_compression_ratio(messages, strategy="compact")

        assert "compression_ratio" in estimate
        assert 0 <= estimate["compression_ratio"] <= 1


class TestConfigurationSmoke:
    """Verify configuration is loaded correctly."""

    def test_context_settings_loaded(self):
        """Should load context management settings."""
        settings = get_settings()

        assert settings.context.enabled is not None
        assert 0 < settings.context.warning_threshold < 1
        assert 0 < settings.context.force_compact_threshold < 1
        assert settings.context.keep_recent_messages > 0
        assert settings.context.compact_middle_messages > 0
        assert settings.context.summarize_cycle > 0

    def test_model_context_windows_configured(self):
        """Should have context windows configured for all models."""
        settings = get_settings()

        assert settings.models.base_context_window > 0
        assert settings.models.reason_context_window > 0
        assert settings.models.vision_context_window > 0
        assert settings.models.code_context_window > 0
        assert settings.models.chat_context_window > 0


# Run smoke tests with: python tests/run_tests.py smoke
# Or: uv run pytest tests/smoke/test_context_management_smoke.py -v
