"""Unit tests for max_completion_tokens configuration."""

import os
import pytest
from pydantic_settings import SettingsConfigDict
from generalAgent.config.settings import get_settings, ModelRoutingSettings


class TestMaxCompletionTokensConfig:
    """Test max_completion_tokens configuration loading and defaults."""

    def test_default_fallback_values(self, monkeypatch):
        """Test that default fallback values are set correctly."""
        # Clear all existing MODEL_ environment variables
        import os
        for key in list(os.environ.keys()):
            if key.startswith("MODEL_"):
                monkeypatch.delenv(key, raising=False)

        # Set only required model fields
        monkeypatch.setenv("MODEL_BASE", "test-model")
        monkeypatch.setenv("MODEL_REASON", "test-model")
        monkeypatch.setenv("MODEL_VISION", "test-model")
        monkeypatch.setenv("MODEL_CODE", "test-model")
        monkeypatch.setenv("MODEL_CHAT", "test-model")

        # Don't set max_completion_tokens, should use defaults
        settings = ModelRoutingSettings(_env_file=None)

        assert settings.base_max_completion_tokens == 2048
        assert settings.reason_max_completion_tokens == 2048
        assert settings.vision_max_completion_tokens == 2048
        assert settings.code_max_completion_tokens == 2048
        assert settings.chat_max_completion_tokens == 2048

    def test_load_from_env_new_names(self, monkeypatch):
        """Test loading max_completion_tokens from .env with new naming convention."""
        monkeypatch.setenv("MODEL_BASIC_MAX_COMPLETION_TOKENS", "4096")
        monkeypatch.setenv("MODEL_REASONING_MAX_COMPLETION_TOKENS", "8192")
        monkeypatch.setenv("MODEL_MULTIMODAL_MAX_COMPLETION_TOKENS", "4096")
        monkeypatch.setenv("MODEL_CODE_MAX_COMPLETION_TOKENS", "8192")
        monkeypatch.setenv("MODEL_CHAT_MAX_COMPLETION_TOKENS", "4096")

        settings = ModelRoutingSettings(_env_file=None)

        assert settings.base_max_completion_tokens == 4096
        assert settings.reason_max_completion_tokens == 8192
        assert settings.vision_max_completion_tokens == 4096
        assert settings.code_max_completion_tokens == 8192
        assert settings.chat_max_completion_tokens == 4096

    def test_backward_compatibility_old_names(self, monkeypatch):
        """Test backward compatibility with old MAX_TOKENS naming."""
        # Clear all existing MODEL_ environment variables
        import os
        for key in list(os.environ.keys()):
            if key.startswith("MODEL_"):
                monkeypatch.delenv(key, raising=False)

        # Set required model fields
        monkeypatch.setenv("MODEL_BASE", "test-model")
        monkeypatch.setenv("MODEL_REASON", "test-model")
        monkeypatch.setenv("MODEL_VISION", "test-model")
        monkeypatch.setenv("MODEL_CODE", "test-model")
        monkeypatch.setenv("MODEL_CHAT", "test-model")

        # Test old MAX_TOKENS naming (backward compatibility)
        monkeypatch.setenv("MODEL_BASIC_MAX_TOKENS", "3072")
        monkeypatch.setenv("MODEL_REASONING_MAX_TOKENS", "6144")
        monkeypatch.setenv("MODEL_MULTIMODAL_MAX_TOKENS", "3072")
        monkeypatch.setenv("MODEL_CODE_MAX_TOKENS", "6144")
        monkeypatch.setenv("MODEL_CHAT_MAX_TOKENS", "3072")

        settings = ModelRoutingSettings(_env_file=None)

        # Old names should still work via AliasChoices
        assert settings.base_max_completion_tokens == 3072
        assert settings.reason_max_completion_tokens == 6144
        assert settings.vision_max_completion_tokens == 3072
        assert settings.code_max_completion_tokens == 6144
        assert settings.chat_max_completion_tokens == 3072

    def test_validation_bounds(self, monkeypatch):
        """Test that values are validated within allowed range (512-204800)."""
        from pydantic import ValidationError

        # Clear all existing MODEL_ environment variables
        import os
        for key in list(os.environ.keys()):
            if key.startswith("MODEL_"):
                monkeypatch.delenv(key, raising=False)

        # Set required model fields
        monkeypatch.setenv("MODEL_BASE", "test-model")
        monkeypatch.setenv("MODEL_REASON", "test-model")
        monkeypatch.setenv("MODEL_VISION", "test-model")
        monkeypatch.setenv("MODEL_CODE", "test-model")
        monkeypatch.setenv("MODEL_CHAT", "test-model")

        # Test lower bound - use environment variable to trigger validation
        monkeypatch.setenv("MODEL_BASE_MAX_COMPLETION_TOKENS", "256")  # Too low
        with pytest.raises(ValidationError):
            ModelRoutingSettings(_env_file=None)

        # Test upper bound
        monkeypatch.setenv("MODEL_BASE_MAX_COMPLETION_TOKENS", "300000")  # Too high
        with pytest.raises(ValidationError):
            ModelRoutingSettings(_env_file=None)

        # Test valid values
        monkeypatch.setenv("MODEL_BASE_MAX_COMPLETION_TOKENS", "512")
        settings = ModelRoutingSettings(_env_file=None)
        assert settings.base_max_completion_tokens == 512

        monkeypatch.setenv("MODEL_BASE_MAX_COMPLETION_TOKENS", "204800")
        settings = ModelRoutingSettings(_env_file=None)
        assert settings.base_max_completion_tokens == 204800

    def test_model_resolver_receives_config(self):
        """Test that model_resolver receives max_completion_tokens from config."""
        from generalAgent.runtime.model_resolver import resolve_model_configs
        from generalAgent.config.settings import get_settings

        settings = get_settings()
        configs = resolve_model_configs(settings)

        # Check that all model configs include max_completion_tokens
        for model_slot in ["base", "reason", "vision", "code", "chat"]:
            assert "max_completion_tokens" in configs[model_slot]
            assert isinstance(configs[model_slot]["max_completion_tokens"], int)
            assert 512 <= configs[model_slot]["max_completion_tokens"] <= 204800

    def test_context_window_vs_max_completion_tokens_distinction(self, monkeypatch):
        """Test that context_window and max_completion_tokens are distinct."""
        monkeypatch.setenv("MODEL_CHAT_CONTEXT_WINDOW", "256000")
        monkeypatch.setenv("MODEL_CHAT_MAX_COMPLETION_TOKENS", "4096")

        settings = ModelRoutingSettings(_env_file=None)

        # context_window is total capacity (input + output)
        assert settings.chat_context_window == 256000

        # max_completion_tokens is output limit only
        assert settings.chat_max_completion_tokens == 4096

        # They should be different concepts
        assert settings.chat_context_window != settings.chat_max_completion_tokens
        assert settings.chat_max_completion_tokens < settings.chat_context_window
