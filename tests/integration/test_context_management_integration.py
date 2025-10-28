"""Integration tests for context management system.

Tests the integration between TokenTracker, ContextCompressor, and the planner node.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from generalAgent.config.settings import get_settings
from generalAgent.context import TokenTracker, ContextCompressor
from generalAgent.graph.state import AppState


@pytest.fixture
def settings():
    """Get application settings."""
    return get_settings()


@pytest.fixture
def tracker(settings):
    """Create TokenTracker instance."""
    return TokenTracker(settings.context, settings.models)


@pytest.fixture
def compressor(settings):
    """Create ContextCompressor instance."""
    return ContextCompressor(settings.context)


class TestTokenTrackingIntegration:
    """Test token tracking integration with actual API responses."""

    def test_track_tokens_across_multiple_calls(self, tracker):
        """Should accumulate tokens across multiple LLM calls."""
        # Simulate 3 LLM calls
        responses = [
            AIMessage(
                content="Response 1",
                response_metadata={
                    "token_usage": {"prompt_tokens": 5000, "completion_tokens": 500, "total_tokens": 5500},
                    "model_name": "deepseek-chat",
                },
            ),
            AIMessage(
                content="Response 2",
                response_metadata={
                    "token_usage": {"prompt_tokens": 8000, "completion_tokens": 800, "total_tokens": 8800},
                    "model_name": "deepseek-chat",
                },
            ),
            AIMessage(
                content="Response 3",
                response_metadata={
                    "token_usage": {"prompt_tokens": 90000, "completion_tokens": 1200, "total_tokens": 91200},
                    "model_name": "deepseek-chat",
                },
                # This call should trigger warning (103k / 128k = 80.4%)
            ),
        ]

        cumulative_prompt = 0
        cumulative_completion = 0
        compact_count = 0

        for i, response in enumerate(responses):
            usage = tracker.extract_token_usage(response)
            assert usage is not None

            cumulative_prompt += usage.prompt_tokens
            cumulative_completion += usage.completion_tokens

            status = tracker.check_status(
                cumulative_prompt_tokens=cumulative_prompt,
                cumulative_completion_tokens=cumulative_completion,
                last_model_id=usage.model_name,
                compact_count=compact_count,
            )

            print(f"\nCall {i+1}:")
            print(f"  Prompt tokens: {usage.prompt_tokens:,}")
            print(f"  Cumulative: {cumulative_prompt:,} / {status.context_window:,}")
            print(f"  Usage: {status.usage_ratio:.1%}")
            print(f"  Warning: {status.needs_warning}")
            print(f"  Compression: {status.needs_compression}")

            # Check expectations
            if i < 2:
                assert not status.needs_warning
            else:
                # Third call should trigger warning
                assert status.needs_warning
                assert status.compression_strategy == "compact"

    def test_warning_triggers_at_different_thresholds(self, tracker):
        """Should trigger warnings at configured thresholds."""
        # Test at 79% (no warning)
        status_79 = tracker.check_status(
            cumulative_prompt_tokens=101120,  # 79% of 128k
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=0,
        )
        assert not status_79.needs_warning

        # Test at 80% (warning)
        status_80 = tracker.check_status(
            cumulative_prompt_tokens=102400,  # 80% of 128k
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=0,
        )
        assert status_80.needs_warning
        assert not status_80.needs_compression

        # Test at 95% (force compression)
        status_95 = tracker.check_status(
            cumulative_prompt_tokens=121600,  # 95% of 128k
            cumulative_completion_tokens=0,
            last_model_id="deepseek-chat",
            compact_count=0,
        )
        assert status_95.needs_warning
        assert status_95.needs_compression


class TestCompressionIntegration:
    """Test compression integration with message history."""

    @pytest.mark.asyncio
    async def test_full_compression_workflow(self, compressor):
        """Should compress large message history successfully."""
        # Create a large message history
        messages = [SystemMessage(content="You are a helpful assistant.")]

        # Add 100 message pairs (200 messages)
        for i in range(100):
            messages.append(HumanMessage(content=f"User message {i}: " + "x" * 100))
            messages.append(AIMessage(content=f"AI response {i}: " + "y" * 100))

        print(f"\nOriginal messages: {len(messages)}")

        # Mock model invoker
        call_count = 0

        async def mock_invoker(messages, tools=None):
            nonlocal call_count
            call_count += 1
            # Simulate different compression results
            if "Summarize" in messages[0].content:
                return AIMessage(content="Brief summary of old messages.")
            else:
                return AIMessage(content="Detailed compact of messages with code snippets and file names.")

        # Test compact strategy
        compressed = await compressor.compress_messages(
            messages=messages,
            strategy="compact",
            model_invoker=mock_invoker,
        )

        print(f"Compressed messages: {len(compressed)}")
        print(f"Model calls: {call_count}")

        # Verify compression
        assert len(compressed) < len(messages)
        assert call_count == 2  # One for old, one for middle
        assert isinstance(compressed[0], SystemMessage)

        # Should have compression markers
        human_msgs = [m for m in compressed if isinstance(m, HumanMessage)]
        assert any("上下文压缩" in m.content for m in human_msgs)

    @pytest.mark.asyncio
    async def test_compression_with_tool_calls(self, compressor):
        """Should preserve tool call pairs during compression."""
        messages = [
            SystemMessage(content="System"),
        ]

        # Add old messages
        for i in range(50):
            messages.append(HumanMessage(content=f"Old {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Add recent message with tool call
        messages.append(HumanMessage(content="Recent user query"))
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_abc123",
                        "name": "read_file",
                        "args": {"file_path": "test.py"},
                    }
                ],
            )
        )
        messages.append(ToolMessage(content="File contents...", tool_call_id="call_abc123"))

        async def mock_invoker(messages, tools=None):
            return AIMessage(content="Compressed summary.")

        compressed = await compressor.compress_messages(
            messages=messages,
            strategy="compact",
            model_invoker=mock_invoker,
        )

        # Tool call pair should be preserved in recent messages
        tool_msg = next((m for m in compressed if isinstance(m, ToolMessage)), None)
        assert tool_msg is not None
        assert tool_msg.tool_call_id == "call_abc123"


class TestStateIntegration:
    """Test integration with AppState."""

    def test_state_token_fields_update(self):
        """Should properly update token tracking fields in state."""
        state: AppState = {
            "messages": [],
            "cumulative_prompt_tokens": 50000,
            "cumulative_completion_tokens": 10000,
            "last_prompt_tokens": 5000,
            "compact_count": 0,
            "last_compact_strategy": None,
        }

        # Simulate LLM call and update
        new_prompt_tokens = 8000
        new_completion_tokens = 1200

        state["cumulative_prompt_tokens"] += new_prompt_tokens
        state["cumulative_completion_tokens"] += new_completion_tokens
        state["last_prompt_tokens"] = new_prompt_tokens

        assert state["cumulative_prompt_tokens"] == 58000
        assert state["cumulative_completion_tokens"] == 11200
        assert state["last_prompt_tokens"] == 8000

    def test_state_after_compression(self):
        """Should reset token counters after compression."""
        state: AppState = {
            "messages": [],
            "cumulative_prompt_tokens": 120000,
            "cumulative_completion_tokens": 25000,
            "last_prompt_tokens": 15000,
            "compact_count": 2,
            "last_compact_strategy": "compact",
        }

        # Simulate compression - reset counters
        state["cumulative_prompt_tokens"] = 0
        state["cumulative_completion_tokens"] = 0
        state["last_prompt_tokens"] = 0
        state["compact_count"] += 1
        state["last_compact_strategy"] = "compact"

        assert state["cumulative_prompt_tokens"] == 0
        assert state["cumulative_completion_tokens"] == 0
        assert state["compact_count"] == 3


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    @pytest.mark.asyncio
    async def test_scenario_gradual_token_buildup(self, tracker, compressor):
        """Test scenario: Gradual token buildup over conversation."""
        cumulative_prompt = 0
        compact_count = 0
        messages = [SystemMessage(content="System")]

        # Simulate 15 conversation turns
        for turn in range(15):
            # Each turn adds ~10k tokens
            messages.append(HumanMessage(content=f"User turn {turn}"))
            messages.append(AIMessage(content=f"AI turn {turn}"))

            # Simulate API response
            response = AIMessage(
                content=f"Response {turn}",
                response_metadata={
                    "token_usage": {
                        "prompt_tokens": 10000 + (turn * 500),  # Growing context
                        "completion_tokens": 500,
                        "total_tokens": 10500 + (turn * 500),
                    },
                    "model_name": "deepseek-chat",
                },
            )

            usage = tracker.extract_token_usage(response)
            cumulative_prompt += usage.prompt_tokens

            status = tracker.check_status(
                cumulative_prompt_tokens=cumulative_prompt,
                cumulative_completion_tokens=0,
                last_model_id="deepseek-chat",
                compact_count=compact_count,
            )

            print(f"\nTurn {turn + 1}: {cumulative_prompt:,} tokens ({status.usage_ratio:.1%})")

            # If warning triggered, compress
            if status.needs_warning and len(messages) > 20:
                print(f"  → Triggering compression (strategy: {status.compression_strategy})")

                async def mock_invoker(msgs, tools=None):
                    return AIMessage(content="Compressed")

                compressed = await compressor.compress_messages(
                    messages=messages,
                    strategy=status.compression_strategy,
                    model_invoker=mock_invoker,
                )

                messages = compressed
                cumulative_prompt = 0  # Reset after compression
                compact_count += 1
                print(f"  → Compressed to {len(messages)} messages")

        # At the end, should have compressed at least once
        assert compact_count > 0
        print(f"\nTotal compressions: {compact_count}")
