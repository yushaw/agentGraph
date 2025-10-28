"""Unit tests for ContextCompressor.

Tests message partitioning, compression, and estimation.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from generalAgent.config.settings import ContextManagementSettings
from generalAgent.context.compressor import ContextCompressor


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
def compressor(context_settings):
    """Create ContextCompressor instance."""
    return ContextCompressor(context_settings)


@pytest.fixture
def sample_messages():
    """Create sample message history for testing."""
    messages = []

    # System message (always kept)
    messages.append(SystemMessage(content="You are a helpful assistant."))

    # Old messages (50 messages)
    for i in range(50):
        messages.append(HumanMessage(content=f"Old user message {i}"))
        messages.append(AIMessage(content=f"Old AI response {i}"))

    # Middle messages (30 messages = 15 pairs)
    for i in range(15):
        messages.append(HumanMessage(content=f"Middle user message {i}"))
        messages.append(AIMessage(content=f"Middle AI response {i}"))

    # Recent messages (10 messages = 5 pairs)
    for i in range(5):
        messages.append(HumanMessage(content=f"Recent user message {i}"))
        messages.append(AIMessage(content=f"Recent AI response {i}"))

    # Total: 1 system + 100 old + 30 middle + 10 recent = 141 messages
    return messages


class TestMessagePartitioning:
    """Test message partitioning logic."""

    def test_partition_with_compact_strategy(self, compressor, sample_messages):
        """Should partition messages correctly for compact strategy."""
        partitions = compressor.partition_messages(sample_messages, strategy="compact")

        # System messages
        assert len(partitions["system"]) == 1
        assert isinstance(partitions["system"][0], SystemMessage)

        # Recent messages (10, cleaned and truncated)
        assert len(partitions["recent"]) == 10

        # Middle messages (30)
        assert len(partitions["middle"]) == 30

        # Old messages (everything else)
        # Total non-system = 140, recent = 10, middle = 30, so old = 100
        assert len(partitions["old"]) == 100

    def test_partition_with_summarize_strategy(self, compressor, sample_messages):
        """Should partition messages correctly for summarize strategy."""
        partitions = compressor.partition_messages(sample_messages, strategy="summarize")

        # System messages
        assert len(partitions["system"]) == 1

        # Recent messages (10)
        assert len(partitions["recent"]) == 10

        # No middle messages in summarize
        assert len(partitions["middle"]) == 0

        # All non-recent goes to old
        assert len(partitions["old"]) == 130  # 140 - 10

    def test_partition_with_few_messages(self, compressor):
        """Should handle cases with fewer messages than keep_recent."""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="User 1"),
            AIMessage(content="AI 1"),
            HumanMessage(content="User 2"),
            AIMessage(content="AI 2"),
        ]

        partitions = compressor.partition_messages(messages, strategy="compact")

        assert len(partitions["system"]) == 1
        assert len(partitions["recent"]) == 4  # All non-system messages
        assert len(partitions["middle"]) == 0
        assert len(partitions["old"]) == 0

    def test_partition_preserves_ai_tool_pairs(self, compressor):
        """Should preserve AIMessage-ToolMessage pairs in recent."""
        messages = [
            SystemMessage(content="System"),
        ]

        # Add old messages
        for i in range(20):
            messages.append(HumanMessage(content=f"Old {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Add a recent AI message with tool call + ToolMessage
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"id": "call_123", "name": "test_tool", "args": {}}],
        )
        tool_msg = ToolMessage(content="Tool result", tool_call_id="call_123")

        messages.append(HumanMessage(content="Recent user"))
        messages.append(ai_msg)
        messages.append(tool_msg)
        messages.append(HumanMessage(content="Latest user"))

        partitions = compressor.partition_messages(messages, strategy="compact")

        # Recent should contain the AI-Tool pair even if it exceeds keep_recent
        recent_messages = partitions["recent"]
        assert any(isinstance(m, AIMessage) and getattr(m, "tool_calls", None) for m in recent_messages)
        assert any(isinstance(m, ToolMessage) for m in recent_messages)


class TestCompressionEstimation:
    """Test compression ratio estimation."""

    def test_estimate_compression_compact(self, compressor, sample_messages):
        """Should estimate compression ratio for compact strategy."""
        estimate = compressor.estimate_compression_ratio(sample_messages, strategy="compact")

        assert "original_chars" in estimate
        assert "estimated_final_chars" in estimate
        assert "compression_ratio" in estimate
        assert "messages_before" in estimate
        assert "messages_after_estimate" in estimate

        # Original message count
        assert estimate["messages_before"] == len(sample_messages)

        # Compression ratio should be between 0 and 1
        assert 0 < estimate["compression_ratio"] < 1

        # Final size should be smaller
        assert estimate["estimated_final_chars"] < estimate["original_chars"]

    def test_estimate_compression_summarize(self, compressor, sample_messages):
        """Should estimate more aggressive compression for summarize."""
        compact_estimate = compressor.estimate_compression_ratio(sample_messages, strategy="compact")
        summarize_estimate = compressor.estimate_compression_ratio(sample_messages, strategy="summarize")

        # Summarize should have better compression ratio
        assert summarize_estimate["compression_ratio"] < compact_estimate["compression_ratio"]
        assert summarize_estimate["estimated_final_chars"] < compact_estimate["estimated_final_chars"]

    def test_estimate_with_few_messages(self, compressor):
        """Should handle estimation with few messages."""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="User"),
            AIMessage(content="AI"),
        ]

        estimate = compressor.estimate_compression_ratio(messages, strategy="compact")

        # No compression needed for few messages
        assert estimate["compression_ratio"] >= 0.9  # Minimal compression


class TestCompressionExecution:
    """Test actual message compression."""

    @pytest.mark.asyncio
    async def test_compress_with_compact_strategy(self, compressor, sample_messages):
        """Should compress messages using compact strategy."""
        # Mock model invoker
        async def mock_invoker(messages, tools=None):
            return AIMessage(content="[Compressed summary of conversation]")

        compressed = await compressor.compress_messages(
            messages=sample_messages,
            strategy="compact",
            model_invoker=mock_invoker,
        )

        # Should contain: system + old summary + middle summary + recent
        assert len(compressed) > 0

        # First should be system
        assert isinstance(compressed[0], SystemMessage)

        # Should have HumanMessages with compressed content
        human_msgs = [m for m in compressed if isinstance(m, HumanMessage)]
        assert any("[上下文压缩" in m.content for m in human_msgs)

    @pytest.mark.asyncio
    async def test_compress_with_summarize_strategy(self, compressor, sample_messages):
        """Should compress messages using summarize strategy."""
        async def mock_invoker(messages, tools=None):
            return AIMessage(content="Brief summary.")

        compressed = await compressor.compress_messages(
            messages=sample_messages,
            strategy="summarize",
            model_invoker=mock_invoker,
        )

        # Should contain: system + old summary + recent
        assert len(compressed) > 0

        # First should be system
        assert isinstance(compressed[0], SystemMessage)

        # Should have summarize marker
        human_msgs = [m for m in compressed if isinstance(m, HumanMessage)]
        assert any("Summarize" in m.content for m in human_msgs)

    @pytest.mark.asyncio
    async def test_compress_preserves_system_messages(self, compressor, sample_messages):
        """Should always preserve system messages."""
        async def mock_invoker(messages, tools=None):
            return AIMessage(content="Summary")

        compressed = await compressor.compress_messages(
            messages=sample_messages,
            strategy="compact",
            model_invoker=mock_invoker,
        )

        # System message should be first
        assert isinstance(compressed[0], SystemMessage)
        assert compressed[0].content == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_compress_with_no_old_messages(self, compressor):
        """Should handle compression when there are no old messages."""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Recent 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Recent 2"),
            AIMessage(content="Response 2"),
        ]

        async def mock_invoker(messages, tools=None):
            return AIMessage(content="Summary")

        compressed = await compressor.compress_messages(
            messages=messages,
            strategy="compact",
            model_invoker=mock_invoker,
        )

        # Should just return system + recent (no compression needed)
        assert len(compressed) == len(messages)
        assert compressed[0].content == "System"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_partition_empty_messages(self, compressor):
        """Should handle empty message list."""
        partitions = compressor.partition_messages([], strategy="compact")

        assert len(partitions["system"]) == 0
        assert len(partitions["old"]) == 0
        assert len(partitions["middle"]) == 0
        assert len(partitions["recent"]) == 0

    def test_partition_only_system_messages(self, compressor):
        """Should handle only system messages."""
        messages = [
            SystemMessage(content="System 1"),
            SystemMessage(content="System 2"),
        ]

        partitions = compressor.partition_messages(messages, strategy="compact")

        assert len(partitions["system"]) == 2
        assert len(partitions["recent"]) == 0

    def test_estimate_empty_messages(self, compressor):
        """Should handle estimation with empty messages."""
        estimate = compressor.estimate_compression_ratio([], strategy="compact")

        assert estimate["original_chars"] == 0
        assert estimate["compression_ratio"] == 1.0  # No compression possible
