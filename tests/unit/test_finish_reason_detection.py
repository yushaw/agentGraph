"""Unit tests for finish_reason detection in planner node."""

import pytest
from unittest.mock import Mock, MagicMock
from langchain_core.messages import AIMessage


class TestFinishReasonDetection:
    """Test finish_reason detection and warning logic."""

    def test_normal_completion_no_warning(self, caplog):
        """Test that normal completion (finish_reason=stop) doesn't trigger warnings."""
        # Create mock AIMessage with normal completion
        output = AIMessage(
            content="Normal response",
            response_metadata={
                "finish_reason": "stop",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                }
            }
        )

        # Simulate planner logic
        finish_reason = output.response_metadata.get("finish_reason")

        # Should not trigger warning
        assert finish_reason == "stop"
        assert finish_reason != "length"

    def test_truncation_detected(self, caplog):
        """Test that finish_reason=length is detected and logged."""
        import logging

        # Create mock AIMessage with truncated output
        output = AIMessage(
            content="Truncated...",
            response_metadata={
                "finish_reason": "length",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 1024,  # Hit max_tokens limit
                    "total_tokens": 1124
                }
            }
        )

        finish_reason = output.response_metadata.get("finish_reason")

        # Should detect truncation
        assert finish_reason == "length"

        # Simulate warning log
        logger = logging.getLogger("test")
        with caplog.at_level(logging.WARNING):
            if finish_reason == "length":
                logger.warning(
                    "⚠️ Model output truncated due to max_tokens limit (finish_reason='length'). "
                    "This may cause incomplete tool calls or responses."
                )

        # Verify warning was logged
        assert "Model output truncated" in caplog.text
        assert "max_tokens limit" in caplog.text

    def test_invalid_tool_calls_detected(self, caplog):
        """Test that invalid tool calls due to truncation are detected."""
        import logging

        # Create mock AIMessage with invalid tool calls
        output = AIMessage(
            content="",
            response_metadata={
                "finish_reason": "length",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 1024,
                    "total_tokens": 1124
                }
            },
            invalid_tool_calls=[
                {
                    "name": "write_file",
                    "args": '{"path": "test.txt", "content": "incomplete...',
                    "error": "JSONDecodeError: Unterminated string"
                }
            ]
        )

        finish_reason = output.response_metadata.get("finish_reason")

        # Simulate error log
        logger = logging.getLogger("test")
        with caplog.at_level(logging.ERROR):
            if finish_reason == "length":
                if hasattr(output, "invalid_tool_calls") and output.invalid_tool_calls:
                    logger.error(
                        f"❌ {len(output.invalid_tool_calls)} invalid tool call(s) detected. "
                        "Likely caused by JSON truncation. "
                        "Consider: (1) Increase MODEL_*_MAX_COMPLETION_TOKENS in .env, "
                        "(2) Use edit_file instead of write_file for long content"
                    )

        # Verify error was logged
        assert "invalid tool call(s) detected" in caplog.text
        assert "JSON truncation" in caplog.text
        assert "MODEL_*_MAX_COMPLETION_TOKENS" in caplog.text

    def test_no_false_positives_for_valid_tool_calls(self):
        """Test that valid tool calls don't trigger false warnings."""
        # Create mock AIMessage with valid tool calls
        output = AIMessage(
            content="",
            response_metadata={
                "finish_reason": "stop",  # Normal completion
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 500,
                    "total_tokens": 600
                }
            },
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"path": "test.txt", "content": "Complete content"},
                    "id": "call_valid123"  # Required by LangChain
                }
            ]
        )

        finish_reason = output.response_metadata.get("finish_reason")

        # Should not trigger warning
        assert finish_reason != "length"
        assert not hasattr(output, "invalid_tool_calls") or not output.invalid_tool_calls

    def test_completion_tokens_at_limit_boundary(self):
        """Test detection when completion_tokens exactly hits the limit."""
        # Simulate exact boundary case (common with Kimi default 1024)
        output = AIMessage(
            content="",
            response_metadata={
                "finish_reason": "length",
                "token_usage": {
                    "prompt_tokens": 30680,
                    "completion_tokens": 1024,  # Exactly at limit
                    "total_tokens": 31704
                }
            },
            invalid_tool_calls=[
                {
                    "name": "write_file",
                    "error": "JSONDecodeError"
                }
            ]
        )

        finish_reason = output.response_metadata.get("finish_reason")
        completion_tokens = output.response_metadata["token_usage"]["completion_tokens"]

        # Should detect this as truncation
        assert finish_reason == "length"
        assert completion_tokens == 1024
        assert hasattr(output, "invalid_tool_calls")
        assert len(output.invalid_tool_calls) > 0


class TestMaxTokensConfiguration:
    """Test that max_tokens configuration prevents truncation."""

    def test_max_tokens_applied_to_model_call(self):
        """Test that max_tokens is properly applied to ChatOpenAI."""
        from generalAgent.runtime.model_resolver import _chat_kwargs

        # Test with default fallback
        kwargs = _chat_kwargs(
            model="test-model",
            api_key="test-key",
            base_url=None,
            max_tokens=2048  # fallback
        )

        assert kwargs["max_tokens"] == 2048
        assert kwargs["model"] == "test-model"
        assert kwargs["api_key"] == "test-key"

    def test_per_model_max_tokens_config(self, monkeypatch):
        """Test that each model can have different max_tokens."""
        from generalAgent.config.settings import ModelRoutingSettings
        import os

        # Clear all existing MODEL_ environment variables
        for key in list(os.environ.keys()):
            if key.startswith("MODEL_"):
                monkeypatch.delenv(key, raising=False)

        # Set required model fields
        monkeypatch.setenv("MODEL_BASE", "test-model")
        monkeypatch.setenv("MODEL_REASON", "test-model")
        monkeypatch.setenv("MODEL_VISION", "test-model")
        monkeypatch.setenv("MODEL_CODE", "test-model")
        monkeypatch.setenv("MODEL_CHAT", "test-model")

        # Set different max_completion_tokens for different models
        monkeypatch.setenv("MODEL_BASE_MAX_COMPLETION_TOKENS", "4096")
        monkeypatch.setenv("MODEL_REASON_MAX_COMPLETION_TOKENS", "8192")
        monkeypatch.setenv("MODEL_CHAT_MAX_COMPLETION_TOKENS", "4096")

        settings = ModelRoutingSettings(_env_file=None)

        assert settings.base_max_completion_tokens == 4096
        assert settings.reason_max_completion_tokens == 8192
        assert settings.chat_max_completion_tokens == 4096

    def test_reasoning_models_get_higher_limits(self, monkeypatch):
        """Test that reasoning models are configured with higher max_tokens."""
        from generalAgent.runtime.model_resolver import resolve_model_configs
        from generalAgent.config.settings import Settings, ModelRoutingSettings
        from unittest.mock import Mock
        import os

        # Clear all existing MODEL_ environment variables
        for key in list(os.environ.keys()):
            if key.startswith("MODEL_"):
                monkeypatch.delenv(key, raising=False)

        # Set required model fields
        monkeypatch.setenv("MODEL_BASE", "test-model")
        monkeypatch.setenv("MODEL_REASON", "test-model")
        monkeypatch.setenv("MODEL_VISION", "test-model")
        monkeypatch.setenv("MODEL_CODE", "test-model")
        monkeypatch.setenv("MODEL_CHAT", "test-model")

        # Set different max_completion_tokens
        monkeypatch.setenv("MODEL_BASE_MAX_COMPLETION_TOKENS", "4096")
        monkeypatch.setenv("MODEL_REASON_MAX_COMPLETION_TOKENS", "8192")

        # Mock settings with reasoning model having higher limit
        mock_settings = Mock(spec=Settings)
        mock_settings.models = ModelRoutingSettings(_env_file=None)

        # Get configs
        configs = resolve_model_configs(mock_settings)

        # Reasoning model should have higher limit
        assert configs["reason"]["max_completion_tokens"] == 8192
        assert configs["base"]["max_completion_tokens"] == 4096
        assert configs["reason"]["max_completion_tokens"] > configs["base"]["max_completion_tokens"]
