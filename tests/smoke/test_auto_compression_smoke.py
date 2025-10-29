"""
Smoke 测试：自动压缩快速验证

目标：< 10 秒内验证关键功能
- Critical 阈值检测
- 压缩功能基本可用
- 不触发无限循环

运行：pytest tests/smoke/test_auto_compression_smoke.py -v
"""

import pytest
from unittest.mock import AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from generalAgent.context.token_tracker import TokenTracker
from generalAgent.context.manager import ContextManager
from generalAgent.config.settings import get_settings


@pytest.fixture
def settings():
    return get_settings()


class TestAutoCompressionSmoke:
    """Smoke test for auto-compression"""

    def test_critical_threshold_detection_smoke(self, settings):
        """Smoke: Critical 阈值检测"""
        tracker = TokenTracker(settings)

        # Test critical (96%)
        status = tracker.check_status(123000, "deepseek-chat")
        assert status.level == "critical"
        assert status.needs_compression is True

        # Test non-critical (80%)
        status = tracker.check_status(102000, "deepseek-chat")
        assert status.level != "critical"
        assert status.needs_compression is False

    @pytest.mark.asyncio
    async def test_compression_basic_functionality_smoke(self, settings):
        """Smoke: 压缩基本功能"""
        manager = ContextManager(settings)

        # Create messages
        messages = [SystemMessage(content="System")]
        for i in range(50):
            messages.append(HumanMessage(content=f"Q{i}"))
            messages.append(AIMessage(content=f"A{i}"))

        # Mock invoker
        async def mock_invoker(prompt, max_tokens=2048):
            return "Summary"

        # Execute compression
        result = await manager.compress_context(
            messages=messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # Basic assertions
        assert result.after_count < result.before_count
        assert len(result.messages) < len(messages)
        assert result.strategy in ["compact", "emergency_truncate"]

    def test_duplicate_compression_prevention_smoke(self):
        """Smoke: 防止重复压缩"""
        state = {"auto_compressed_this_request": False}

        # First check - should allow compression
        should_compress_1 = not state.get("auto_compressed_this_request", False)
        assert should_compress_1 is True

        # Mark as compressed
        state["auto_compressed_this_request"] = True

        # Second check - should prevent compression
        should_compress_2 = not state.get("auto_compressed_this_request", False)
        assert should_compress_2 is False

    @pytest.mark.asyncio
    async def test_compression_with_max_tokens_smoke(self, settings):
        """Smoke: 压缩使用 max_tokens 限制"""
        manager = ContextManager(settings)
        messages = [HumanMessage(content="test")] * 20

        captured_max_tokens = None

        async def capturing_invoker(prompt, max_tokens=2048):
            nonlocal captured_max_tokens
            captured_max_tokens = max_tokens
            return "Summary"

        await manager.compress_context(
            messages=messages,
            model_invoker=capturing_invoker,
            context_window=128000
        )

        # Verify max_tokens = 1440 (2000 chars + 20% buffer)
        assert captured_max_tokens == 1440


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
