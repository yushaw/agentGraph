"""
TokenTracker 单元测试
"""

import pytest
from unittest.mock import Mock
from langchain_core.messages import AIMessage
from pydantic_settings import BaseSettings

from generalAgent.context.token_tracker import (
    TokenTracker,
    TokenUsage,
    ContextStatus,
    MODEL_CONTEXT_WINDOWS
)


# Mock Settings
class MockContextSettings(BaseSettings):
    info_threshold: float = 0.75
    warning_threshold: float = 0.85
    critical_threshold: float = 0.95
    compression_ratio_threshold: float = 0.4
    compact_cycle_limit: int = 3

    class Config:
        extra = "ignore"


class MockSettings:
    def __init__(self):
        self.context = MockContextSettings()


@pytest.fixture
def tracker():
    """创建 TokenTracker 实例"""
    settings = MockSettings()
    return TokenTracker(settings)


class TestTokenUsageExtraction:
    """测试 token 使用量提取"""

    def test_extract_from_standard_response(self, tracker):
        """测试从标准 API 响应提取 token"""
        response = AIMessage(
            content="Test response",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                },
                "model_name": "deepseek-chat"
            }
        )

        usage = tracker.extract_token_usage(response)

        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model_name == "deepseek-chat"

    def test_extract_with_usage_key(self, tracker):
        """测试使用 'usage' 键的响应"""
        response = AIMessage(
            content="Test",
            response_metadata={
                "usage": {  # Some APIs use "usage" instead of "token_usage"
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                    "total_tokens": 300
                },
                "model_name": "gpt-4"
            }
        )

        usage = tracker.extract_token_usage(response)

        assert usage is not None
        assert usage.prompt_tokens == 200
        assert usage.completion_tokens == 100

    def test_extract_no_usage_data(self, tracker):
        """测试没有 usage 数据的响应"""
        response = AIMessage(
            content="Test",
            response_metadata={"model_name": "test"}
        )

        usage = tracker.extract_token_usage(response)

        assert usage is None


class TestContextWindowLookup:
    """测试上下文窗口查找"""

    def test_exact_match(self, tracker):
        """测试精确匹配"""
        assert tracker.get_context_window("deepseek-chat") == 128_000
        assert tracker.get_context_window("gpt-4") == 8_192
        assert tracker.get_context_window("claude-3-opus") == 200_000

    def test_prefix_match(self, tracker):
        """测试前缀匹配"""
        assert tracker.get_context_window("deepseek-chat-v2") == 128_000
        assert tracker.get_context_window("gpt-4-0125-preview") == 8_192

    def test_unknown_model_returns_default(self, tracker):
        """测试未知模型返回默认值"""
        window = tracker.get_context_window("unknown-model")
        assert window == MODEL_CONTEXT_WINDOWS["default"]


class TestStatusChecking:
    """测试状态检查"""

    def test_normal_status(self, tracker):
        """测试正常状态 (< 75%)"""
        status = tracker.check_status(
            cumulative_prompt_tokens=50_000,
            model_id="deepseek-chat",  # 128k context
            compact_count=0
        )

        assert status.level == "normal"
        assert not status.needs_compression
        assert status.compression_strategy is None
        assert status.message is None
        assert status.usage_ratio < 0.75

    def test_info_status(self, tracker):
        """测试提示状态 (75-85%)"""
        status = tracker.check_status(
            cumulative_prompt_tokens=100_000,  # 78% of 128k
            model_id="deepseek-chat",
            compact_count=0
        )

        assert status.level == "info"
        assert not status.needs_compression
        assert status.compression_strategy == "compact"
        assert status.message is not None
        assert "💡" in status.message
        assert 0.75 <= status.usage_ratio < 0.85

    def test_warning_status(self, tracker):
        """测试警告状态 (85-95%)"""
        status = tracker.check_status(
            cumulative_prompt_tokens=110_000,  # 86% of 128k
            model_id="deepseek-chat",
            compact_count=0
        )

        assert status.level == "warning"
        assert not status.needs_compression
        assert status.compression_strategy == "compact"
        assert status.message is not None
        assert "⚠️" in status.message
        assert 0.85 <= status.usage_ratio < 0.95

    def test_critical_status(self, tracker):
        """测试危险状态 (>= 95%)"""
        status = tracker.check_status(
            cumulative_prompt_tokens=122_000,  # 95.3% of 128k
            model_id="deepseek-chat",
            compact_count=0
        )

        assert status.level == "critical"
        assert status.needs_compression
        assert status.compression_strategy == "summarize"  # 强制使用激进策略
        assert status.message is not None
        assert "🚨" in status.message
        assert status.usage_ratio >= 0.95


class TestStrategyDecision:
    """测试压缩策略决策"""

    def test_default_strategy_is_compact(self, tracker):
        """测试默认策略为 compact"""
        strategy = tracker._decide_strategy(compact_count=0, last_compression_ratio=None)
        assert strategy == "compact"

    def test_switch_to_summarize_on_poor_compression(self, tracker):
        """测试压缩效果不好时切换到 summarize"""
        # 上次压缩率 > 40% (压缩效果差)
        strategy = tracker._decide_strategy(compact_count=1, last_compression_ratio=0.5)
        assert strategy == "summarize"

    def test_switch_to_summarize_on_cycle_limit(self, tracker):
        """测试连续 compact 次数达到限制时切换"""
        # compact_count 是 3 的倍数
        strategy = tracker._decide_strategy(compact_count=3, last_compression_ratio=0.2)
        assert strategy == "summarize"

        strategy = tracker._decide_strategy(compact_count=6, last_compression_ratio=0.2)
        assert strategy == "summarize"

    def test_continue_compact_on_good_compression(self, tracker):
        """测试压缩效果好时继续 compact"""
        # 压缩率 < 40% 且未达到周期限制
        strategy = tracker._decide_strategy(compact_count=1, last_compression_ratio=0.3)
        assert strategy == "compact"

        strategy = tracker._decide_strategy(compact_count=2, last_compression_ratio=0.2)
        assert strategy == "compact"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
