"""
上下文压缩系统的完整单元测试

测试覆盖：
1. Token 监控和警告触发
2. 分层逻辑（混合策略：Token 比例 + 消息数）
3. 压缩执行和结果结构
4. 降级策略
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from generalAgent.context.token_tracker import TokenTracker, ContextStatus, TokenUsage
from generalAgent.context.compressor import ContextCompressor, CompressionResult
from generalAgent.context.manager import ContextManager
from generalAgent.config.settings import get_settings


# ========== Fixtures ==========

@pytest.fixture
def settings():
    """获取测试配置"""
    return get_settings()


@pytest.fixture
def tracker(settings):
    """创建 TokenTracker 实例"""
    return TokenTracker(settings)


@pytest.fixture
def compressor(settings):
    """创建 ContextCompressor 实例"""
    return ContextCompressor(settings)


@pytest.fixture
def manager(settings):
    """创建 ContextManager 实例"""
    return ContextManager(settings)


@pytest.fixture
def sample_messages():
    """创建测试消息列表（50 条）"""
    messages = [SystemMessage(content="System prompt")]

    for i in range(49):
        messages.append(HumanMessage(content=f"User question {i}"))
        messages.append(AIMessage(content=f"AI response {i}" * 50))  # 较长的回复

    return messages


# ========== Test TokenTracker ==========

class TestTokenTracker:
    """测试 Token 监控器"""

    def test_extract_token_usage_from_response_metadata(self, tracker):
        """测试从 response_metadata 提取 token 使用量"""
        response = AIMessage(
            content="test",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "total_tokens": 1500
                }
            }
        )

        usage = tracker.extract_token_usage(response)

        assert usage is not None
        assert usage.prompt_tokens == 1000
        assert usage.completion_tokens == 500
        assert usage.total_tokens == 1500

    def test_extract_token_usage_from_usage_subfield(self, tracker):
        """测试从 response_metadata.usage 提取 token 使用量"""
        response = AIMessage(
            content="test",
            response_metadata={
                "usage": {
                    "prompt_tokens": 2000,
                    "completion_tokens": 800,
                    "total_tokens": 2800
                }
            }
        )

        usage = tracker.extract_token_usage(response)

        assert usage is not None
        assert usage.prompt_tokens == 2000
        assert usage.completion_tokens == 800

    def test_extract_token_usage_no_metadata(self, tracker):
        """测试没有 metadata 时返回 None"""
        response = AIMessage(content="test")

        usage = tracker.extract_token_usage(response)

        assert usage is None

    def test_get_context_window(self, tracker):
        """测试获取模型 context window"""
        # 精确匹配
        assert tracker.get_context_window("deepseek-chat") == 128000
        assert tracker.get_context_window("kimi-k2-0905-preview") == 200000

        # 前缀匹配
        assert tracker.get_context_window("deepseek-chat-v2") == 128000
        assert tracker.get_context_window("gpt-4o") == 128000

        # 未知模型返回默认值
        assert tracker.get_context_window("unknown-model") == 128000

    def test_check_status_normal(self, tracker):
        """测试正常状态（< 75%）"""
        status = tracker.check_status(
            cumulative_prompt_tokens=50000,
            model_id="deepseek-chat"  # 128k
        )

        assert status.level == "normal"
        assert status.usage_ratio == pytest.approx(50000 / 128000)
        assert status.needs_compression is False
        assert status.message is None

    def test_check_status_info(self, tracker):
        """测试信息提示状态（75-85%）"""
        status = tracker.check_status(
            cumulative_prompt_tokens=100000,  # 78%
            model_id="deepseek-chat"
        )

        assert status.level == "info"
        assert status.usage_ratio == pytest.approx(100000 / 128000)
        assert status.needs_compression is False
        assert "💡 Token 使用提示" in status.message
        assert "compact_context 工具" in status.message

    def test_check_status_warning(self, tracker):
        """测试警告状态（85-95%）"""
        status = tracker.check_status(
            cumulative_prompt_tokens=115000,  # 89.8%
            model_id="deepseek-chat"
        )

        assert status.level == "warning"
        assert status.usage_ratio == pytest.approx(115000 / 128000)
        assert status.needs_compression is False
        assert "⚠️ Token 使用警告" in status.message

    def test_check_status_critical(self, tracker):
        """测试危险状态（≥ 95%）"""
        status = tracker.check_status(
            cumulative_prompt_tokens=122000,  # 95.3%
            model_id="deepseek-chat"
        )

        assert status.level == "critical"
        assert status.usage_ratio == pytest.approx(122000 / 128000)
        assert status.needs_compression is True
        assert "🚨 Token 使用严重警告" in status.message


# ========== Test ContextCompressor ==========

class TestContextCompressor:
    """测试上下文压缩器"""

    def test_estimate_single_message_tokens(self, compressor):
        """测试单条消息 token 估算"""
        msg = HumanMessage(content="Hello world" * 100)  # ~1100 chars

        tokens = compressor._estimate_single_message_tokens(msg)

        # 1100 chars / 2 ≈ 550 tokens
        assert tokens == 550

    def test_partition_messages_small_dataset(self, compressor):
        """测试小数据集分层（不足 recent 阈值）"""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Q1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"),
            AIMessage(content="A2"),
        ]

        partitioned = compressor._partition_messages(messages, context_window=128000)

        assert len(partitioned["system"]) == 1
        assert len(partitioned["old"]) == 0
        assert len(partitioned["middle"]) == 0
        assert len(partitioned["recent"]) == 4  # 全部在 recent

    def test_partition_messages_mixed_strategy(self, compressor, sample_messages):
        """测试混合策略分层（Token 比例 + 消息数）"""
        # sample_messages: 1 System + 98 条对话
        # 默认配置：keep_recent_ratio=0.15, keep_recent_messages=10
        #           compact_middle_ratio=0.30, compact_middle_messages=30

        partitioned = compressor._partition_messages(sample_messages, context_window=128000)

        # 验证 system
        assert len(partitioned["system"]) == 1

        # 验证 recent（应该达到 10 条或 19.2k tokens 的限制）
        assert len(partitioned["recent"]) <= 10
        assert len(partitioned["recent"]) > 0

        # 验证 middle（应该达到 30 条或 38.4k tokens 的限制）
        assert len(partitioned["middle"]) <= 30

        # 验证 old（剩余消息）
        non_system_count = len(sample_messages) - 1
        recent_count = len(partitioned["recent"])
        middle_count = len(partitioned["middle"])
        assert len(partitioned["old"]) == non_system_count - recent_count - middle_count

    def test_partition_messages_with_large_context_window(self, compressor, sample_messages):
        """测试大 context window 的分层（Kimi 200k）"""
        partitioned = compressor._partition_messages(sample_messages, context_window=200000)

        # 200k * 0.15 = 30k tokens (Recent)
        # 200k * 0.30 = 60k tokens (Middle)
        # 由于 sample_messages 总共约 50k tokens，应该大部分在 recent/middle

        assert len(partitioned["system"]) == 1
        assert len(partitioned["recent"]) > 0
        # Old 可能为空或很少（因为 context window 很大）

    @pytest.mark.asyncio
    async def test_compress_messages_success(self, compressor, sample_messages):
        """测试成功压缩"""
        # Mock LLM 调用
        async def mock_invoker(prompt, max_tokens=2048):
            return "## 用户请求和意图\n用户进行了多轮对话\n\n## 工具调用记录\n无"

        result = await compressor.compress_messages(
            messages=sample_messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        assert result.strategy == "compact"
        assert result.before_count == len(sample_messages)
        assert result.after_count < result.before_count
        assert result.compression_ratio < 1.0

        # 验证压缩后的消息结构
        assert isinstance(result.messages[0], SystemMessage)  # 原始 system
        # 应该有 Old/Middle 的压缩摘要（SystemMessage）
        # 加上 Recent 的完整消息

    @pytest.mark.asyncio
    async def test_compress_messages_with_max_tokens_limit(self, compressor, sample_messages):
        """测试 max_tokens 限制生效"""
        call_args = []

        async def mock_invoker(prompt, max_tokens=2048):
            call_args.append({"prompt": prompt, "max_tokens": max_tokens})
            return "Compressed summary"

        await compressor.compress_messages(
            messages=sample_messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # 验证 max_tokens=1440 被传递
        assert len(call_args) > 0
        for call in call_args:
            assert call["max_tokens"] == 1440

    def test_format_messages_for_summary(self, compressor):
        """测试消息格式化"""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(
                content="Hi",
                tool_calls=[{"name": "test_tool", "args": {}, "id": "call_123"}]
            ),
            ToolMessage(content="Result", name="test_tool", tool_call_id="call_123")
        ]

        formatted = compressor._format_messages_for_summary(messages)

        assert "[Human] Hello" in formatted
        assert "调用工具: test_tool" in formatted
        assert "[Tool:test_tool]" in formatted


# ========== Test ContextManager ==========

class TestContextManager:
    """测试上下文管理器"""

    def test_extract_and_check_no_usage(self, manager):
        """测试没有 token 使用信息的响应"""
        response = AIMessage(content="test")

        report = manager.extract_and_check(
            response=response,
            cumulative_prompt_tokens=0,
            model_id="deepseek-chat"
        )

        assert report.action == "none"
        assert report.status is None

    def test_extract_and_check_normal(self, manager):
        """测试正常状态"""
        response = AIMessage(
            content="test",
            response_metadata={"token_usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
        )

        report = manager.extract_and_check(
            response=response,
            cumulative_prompt_tokens=50000,
            model_id="deepseek-chat"
        )

        assert report.action == "none"
        assert report.status.level == "normal"

    def test_extract_and_check_warning(self, manager):
        """测试警告状态"""
        response = AIMessage(
            content="test",
            response_metadata={"token_usage": {"prompt_tokens": 50000, "completion_tokens": 500}}
        )

        report = manager.extract_and_check(
            response=response,
            cumulative_prompt_tokens=60000,  # 累积到 110k (85.9%)
            model_id="deepseek-chat"
        )

        assert report.action == "warning"
        assert report.status.level == "warning"
        assert report.user_message is not None

    @pytest.mark.asyncio
    async def test_compress_context_success(self, manager, sample_messages):
        """测试压缩成功"""
        async def mock_invoker(prompt, max_tokens=2048):
            return "Compressed content"

        result = await manager.compress_context(
            messages=sample_messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        assert result.strategy == "compact"
        assert result.after_count < result.before_count

    @pytest.mark.asyncio
    async def test_compress_context_fallback_on_error(self, manager, sample_messages):
        """测试压缩失败时降级"""
        async def mock_invoker_fail(prompt, max_tokens=2048):
            raise RuntimeError("LLM call failed")

        result = await manager.compress_context(
            messages=sample_messages,
            model_invoker=mock_invoker_fail,
            context_window=128000
        )

        # 应该降级到 emergency_truncate
        assert result.strategy == "emergency_truncate"
        assert result.after_count == min(len(sample_messages), 100)  # 默认保留 100 条

    def test_format_compression_report(self, manager):
        """测试压缩报告格式化"""
        result = CompressionResult(
            messages=[SystemMessage(content="test")],
            before_count=141,
            after_count=14,
            before_tokens=105000,
            after_tokens=18000,
            strategy="compact",
            compression_ratio=18000 / 105000
        )

        report = manager.format_compression_report(result)

        assert "✅ 上下文已压缩" in report
        assert "141 条消息" in report
        assert "14 条消息" in report
        assert "详细摘要" in report
        assert "127 条消息" in report  # 节省的消息数


# ========== Integration Test: Full Compression Flow ==========

class TestCompressionIntegration:
    """集成测试：完整压缩流程"""

    @pytest.mark.asyncio
    async def test_full_compression_workflow(self, manager, sample_messages):
        """测试完整压缩工作流"""
        # 模拟 LLM 调用，返回结构化摘要
        async def mock_llm_invoker(prompt, max_tokens=2048):
            return """## 用户请求和意图
用户进行了多轮问答

## 关键信息
- 测试对话
- 多次交互

## 工具调用记录
无

## 当前工作
对话进行中"""

        # 执行压缩
        result = await manager.compress_context(
            messages=sample_messages,
            model_invoker=mock_llm_invoker,
            context_window=128000
        )

        # 验证结果
        assert result.strategy == "compact"
        assert result.compression_ratio < 0.3  # 应该压缩到 < 30%

        # 验证压缩后的消息结构
        compressed_messages = result.messages

        # 第一条应该是原始 SystemMessage
        assert isinstance(compressed_messages[0], SystemMessage)
        assert compressed_messages[0].content == "System prompt"

        # 后续应该有压缩摘要（SystemMessage）
        summary_messages = [
            m for m in compressed_messages[1:]
            if isinstance(m, SystemMessage) and "摘要" in m.content
        ]
        assert len(summary_messages) >= 1  # 至少有 Old 或 Middle 的摘要

        # 最后应该有 Recent 的完整消息
        recent_messages = [
            m for m in compressed_messages
            if not isinstance(m, SystemMessage)
        ]
        assert len(recent_messages) > 0
        assert len(recent_messages) <= 10  # 默认保留 10 条

    @pytest.mark.asyncio
    async def test_compressed_context_structure(self, compressor):
        """测试压缩后的上下文结构"""
        # 创建大量消息
        messages = [SystemMessage(content="System")]
        for i in range(100):
            messages.append(HumanMessage(content=f"Q{i}"))
            messages.append(AIMessage(content=f"A{i}" * 100))  # 长回复

        async def mock_invoker(prompt, max_tokens=2048):
            # 返回符合要求的结构化摘要
            return """## 用户请求和意图
测试

## 关键信息
- 测试数据

## 文件操作
无

## 工具调用记录
无

## 当前工作
测试中"""

        result = await compressor.compress_messages(
            messages=messages,
            model_invoker=mock_invoker,
            context_window=128000
        )

        # 验证结构
        compressed = result.messages

        # 1. 第一条是原始 SystemMessage
        assert compressed[0].content == "System"

        # 2. 中间有压缩摘要
        summary_count = sum(
            1 for m in compressed[1:]
            if isinstance(m, SystemMessage) and "摘要" in m.content
        )
        assert summary_count >= 1

        # 3. 摘要内容包含必需章节
        for msg in compressed[1:]:
            if isinstance(msg, SystemMessage) and "摘要" in msg.content:
                assert "用户请求" in msg.content or "关键信息" in msg.content
                assert "系统自动生成" in msg.content

        # 4. Recent 消息保持完整
        recent_start_idx = None
        for i, msg in enumerate(compressed):
            if not isinstance(msg, SystemMessage):
                recent_start_idx = i
                break

        if recent_start_idx:
            recent_messages = compressed[recent_start_idx:]
            assert len(recent_messages) <= 10
            # 验证内容未被压缩
            assert any("Q" in str(m.content) for m in recent_messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
