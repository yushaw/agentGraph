"""Unit tests for max_completion_tokens configuration."""

import os
import pytest
from generalAgent.config.settings import get_settings, ModelRoutingSettings


class TestMaxCompletionTokensConfig:
    """Test max_completion_tokens configuration loading and defaults."""

    def test_default_fallback_values(self):
        """Test that default fallback values are set correctly."""
        settings = ModelRoutingSettings()

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

        settings = ModelRoutingSettings()

        assert settings.base_max_completion_tokens == 4096
        assert settings.reason_max_completion_tokens == 8192
        assert settings.vision_max_completion_tokens == 4096
        assert settings.code_max_completion_tokens == 8192
        assert settings.chat_max_completion_tokens == 4096

    def test_backward_compatibility_old_names(self, monkeypatch):
        """Test backward compatibility with old MAX_TOKENS naming."""
        monkeypatch.setenv("MODEL_BASIC_MAX_TOKENS", "3072")
        monkeypatch.setenv("MODEL_REASONING_MAX_TOKENS", "6144")
        monkeypatch.setenv("MODEL_MULTIMODAL_MAX_TOKENS", "3072")
        monkeypatch.setenv("MODEL_CODE_MAX_TOKENS", "6144")
        monkeypatch.setenv("MODEL_CHAT_MAX_TOKENS", "3072")

        settings = ModelRoutingSettings()

        # Old names should still work via AliasChoices
        assert settings.base_max_completion_tokens == 3072
        assert settings.reason_max_completion_tokens == 6144
        assert settings.vision_max_completion_tokens == 3072
        assert settings.code_max_completion_tokens == 6144
        assert settings.chat_max_completion_tokens == 3072

    def test_validation_bounds(self):
        """Test that values are validated within allowed range (512-16384)."""
        # Test lower bound
        with pytest.raises(ValueError):
            ModelRoutingSettings(base_max_completion_tokens=256)  # Too low

        # Test upper bound
        with pytest.raises(ValueError):
            ModelRoutingSettings(base_max_completion_tokens=20000)  # Too high

        # Test valid values
        settings = ModelRoutingSettings(base_max_completion_tokens=512)
        assert settings.base_max_completion_tokens == 512

        settings = ModelRoutingSettings(base_max_completion_tokens=16384)
        assert settings.base_max_completion_tokens == 16384

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
            assert 512 <= configs[model_slot]["max_completion_tokens"] <= 16384

    def test_context_window_vs_max_completion_tokens_distinction(self, monkeypatch):
        """Test that context_window and max_completion_tokens are distinct."""
        monkeypatch.setenv("MODEL_CHAT_CONTEXT_WINDOW", "256000")
        monkeypatch.setenv("MODEL_CHAT_MAX_COMPLETION_TOKENS", "4096")

        settings = ModelRoutingSettings()

        # context_window is total capacity (input + output)
        assert settings.chat_context_window == 256000

        # max_completion_tokens is output limit only
        assert settings.chat_max_completion_tokens == 4096

        # They should be different concepts
        assert settings.chat_context_window != settings.chat_max_completion_tokens
        assert settings.chat_max_completion_tokens < settings.chat_context_window
