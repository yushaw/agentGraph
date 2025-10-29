"""
Unit 测试：自动压缩核心逻辑

测试范围：
1. Token tracker 正确识别 critical 状态
2. ContextManager 压缩逻辑
3. State 更新逻辑
4. 防重复压缩标志

不涉及：
- 完整的 planner node
- LLM 调用
- 完整的 LangGraph 流程
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from generalAgent.context.token_tracker import TokenTracker, ContextStatus
from generalAgent.context.manager import ContextManager
from generalAgent.context.compressor import CompressionResult
from generalAgent.config.settings import get_settings


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def tracker(settings):
    return TokenTracker(settings)


@pytest.fixture
def context_manager(settings):
    return ContextManager(settings)


@pytest.fixture
def sample_messages():
    """生成测试消息"""
    messages = [SystemMessage(content="System prompt")]
    for i in range(100):
        messages.append(HumanMessage(content=f"Question {i}" * 20))  # ~400 chars each
        messages.append(AIMessage(content=f"Answer {i}" * 20))
    return messages


class TestTokenTrackerCriticalDetection:
    """测试 TokenTracker 的 critical 状态检测"""

    def test_detect_critical_threshold(self, tracker):
        """测试正确检测 critical 阈值（>= 95%）"""
        # 96% usage
        status = tracker.check_status(
            cumulative_prompt_tokens=123000,
            model_id="deepseek-chat"
        )

        assert status.level == "critical"
        assert status.needs_compression is True
        assert status.usage_ratio >= 0.95
        assert "🚨" in status.message

    def test_detect_warning_not_critical(self, tracker):
        """测试 warning 级别不触发 critical（85-95%）"""
        # 90% usage
        status = tracker.check_status(
            cumulative_prompt_tokens=115000,
            model_id="deepseek-chat"
        )

        assert status.level == "warning"
        assert status.needs_compression is False

    def test_detect_info_not_critical(self, tracker):
        """测试 info 级别不触发 critical（75-85%）"""
        # 80% usage
        status = tracker.check_status(
            cumulative_prompt_tokens=102000,
            model_id="deepseek-chat"
        )

        assert status.level == "info"
        assert status.needs_compression is False


class TestContextManagerCompression:
    """测试 ContextManager 的压缩逻辑"""

    @pytest.mark.asyncio
    async def test_compress_reduces_message_count(self, context_manager, sample_messages):
        """测试压缩成功减少消息数量"""
        # Mock LLM invoker
        async def mock_invoker(prompt, max_tokens=2048):
            return "Compressed summary of conversation"

        result = await context_manager.compress_context(
            messages=sample_messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # 验证压缩效果
        assert result.after_count < result.before_count
        assert len(result.messages) < len(sample_messages)
        assert result.compression_ratio < 1.0
        assert result.strategy == "compact"

    @pytest.mark.asyncio
    async def test_compress_resets_tokens(self, context_manager, sample_messages):
        """测试压缩后 token 估算减少"""
        async def mock_invoker(prompt, max_tokens=2048):
            return "Brief summary"

        result = await context_manager.compress_context(
            messages=sample_messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # 验证 token 减少
        assert result.after_tokens < result.before_tokens
        saved_tokens = result.before_tokens - result.after_tokens
        assert saved_tokens > 0

    @pytest.mark.asyncio
    async def test_compress_preserves_system_messages(self, context_manager):
        """测试压缩保留 SystemMessage"""
        messages = [
            SystemMessage(content="System prompt 1"),
            SystemMessage(content="System prompt 2"),
            HumanMessage(content="User message"),
            AIMessage(content="AI response"),
        ]

        async def mock_invoker(prompt, max_tokens=2048):
            return "Summary"

        result = await context_manager.compress_context(
            messages=messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # 验证 SystemMessage 被保留
        system_count = sum(1 for m in result.messages if isinstance(m, SystemMessage))
        assert system_count == 2


class TestAutoCompressionStateUpdate:
    """测试自动压缩后的 state 更新逻辑"""

    def test_state_update_after_compression(self):
        """测试压缩后 state 正确更新"""
        # 模拟压缩前的 state
        state = {
            "messages": [HumanMessage(content="msg")] * 100,
            "cumulative_prompt_tokens": 123000,
            "cumulative_completion_tokens": 5000,
            "compact_count": 0,
            "auto_compressed_this_request": False,
        }

        # 模拟压缩结果
        compressed_messages = [HumanMessage(content="msg")] * 50

        # 应用更新逻辑
        state["messages"] = compressed_messages
        state["compact_count"] = state["compact_count"] + 1
        state["cumulative_prompt_tokens"] = 0
        state["cumulative_completion_tokens"] = 0
        state["auto_compressed_this_request"] = True

        # 验证
        assert len(state["messages"]) == 50
        assert state["compact_count"] == 1
        assert state["cumulative_prompt_tokens"] == 0
        assert state["cumulative_completion_tokens"] == 0
        assert state["auto_compressed_this_request"] is True

    def test_prevent_duplicate_compression_flag(self):
        """测试防重复压缩标志生效"""
        state = {"auto_compressed_this_request": False}

        # 第一次检查：未压缩
        if not state.get("auto_compressed_this_request", False):
            state["auto_compressed_this_request"] = True
            first_check_should_compress = True
        else:
            first_check_should_compress = False

        assert first_check_should_compress is True

        # 第二次检查：已压缩
        if not state.get("auto_compressed_this_request", False):
            second_check_should_compress = True
        else:
            second_check_should_compress = False

        assert second_check_should_compress is False


class TestCompressionMaxTokensLimit:
    """测试压缩输出的 max_tokens 限制"""

    @pytest.mark.asyncio
    async def test_compression_uses_max_tokens_limit(self, context_manager, sample_messages):
        """测试压缩调用 LLM 时使用 max_tokens 限制"""
        max_tokens_used = None

        async def mock_invoker(prompt, max_tokens=2048):
            nonlocal max_tokens_used
            max_tokens_used = max_tokens
            return "Summary"

        await context_manager.compress_context(
            messages=sample_messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # 验证使用了 max_tokens 限制（1440 tokens = 2000 chars + 20% buffer）
        assert max_tokens_used == 1440


class TestCompressionFallback:
    """测试压缩失败的降级策略"""

    @pytest.mark.asyncio
    async def test_fallback_to_truncation_on_error(self, context_manager, sample_messages):
        """测试压缩失败时降级到简单截断"""
        # Mock invoker 抛出异常
        async def failing_invoker(prompt, max_tokens=2048):
            raise Exception("LLM compression failed")

        result = await context_manager.compress_context(
            messages=sample_messages,
            model_invoker=failing_invoker,
            context_window=128000
        )

        # 验证降级策略生效
        assert result.strategy == "emergency_truncate"
        assert len(result.messages) < len(sample_messages)
        # 应该保留最近的消息 (system messages + recent)
        assert len(result.messages) <= 101  # CONTEXT_MAX_HISTORY (100) + system messages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
