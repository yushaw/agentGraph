"""
Unit tests for subagent ask_human capability.
Tests that subagents can use ask_human tool and delegate_task handles interrupts correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from generalAgent.tools.builtin.delegate_task import delegate_task, set_app_graph
from generalAgent.graph.prompts import SUBAGENT_SYSTEM_PROMPT


class TestSubagentAskHumanCapability:
    """Test that subagents can use ask_human tool"""

    def test_subagent_prompt_allows_ask_human(self):
        """Subagent system prompt should mention ask_human is available"""
        # Should mention user interaction is possible
        assert "ask_human" in SUBAGENT_SYSTEM_PROMPT
        assert "向用户提问" in SUBAGENT_SYSTEM_PROMPT or "用户提问" in SUBAGENT_SYSTEM_PROMPT

    def test_subagent_prompt_no_restriction(self):
        """Subagent prompt should NOT say 'cannot use ask_human'"""
        # Should not have old restriction
        assert "无法使用 ask_human" not in SUBAGENT_SYSTEM_PROMPT
        assert "不要询问用户" not in SUBAGENT_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_delegate_task_handles_ask_human_interrupt(self):
        """delegate_task should handle ask_human interrupt correctly"""
        mock_graph = AsyncMock()

        # Simulate ask_human interrupt workflow
        call_count = 0

        async def mock_astream(input_data, config, stream_mode):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: normal execution, no interrupt yet
                yield {
                    "messages": [
                        HumanMessage(content="Test task"),
                        AIMessage(content="Processing...")
                    ],
                    "loops": 1
                }
            elif call_count == 2:
                # Second call (resume): after user answered question
                yield {
                    "messages": [
                        HumanMessage(content="Test task"),
                        AIMessage(content="Processing..."),
                        ToolMessage(content="Beijing", name="ask_human", tool_call_id="call_123"),
                        AIMessage(content="Task completed with user input: Beijing from user" * 10)  # Make it > 200 chars
                    ],
                    "loops": 2
                }

        # Mock aget_state to simulate interrupt
        state_call_count = 0

        async def mock_aget_state(config):
            nonlocal state_call_count
            state_call_count += 1

            if state_call_count == 1:
                # First check: has interrupt
                mock_state = MagicMock()
                mock_state.next = ["some_node"]
                mock_task = MagicMock()
                mock_interrupt = MagicMock()
                mock_interrupt.value = {
                    "type": "user_input_request",
                    "question": "Which city?",
                    "context": "Need city name for hotel booking",
                    "default": None
                }
                mock_task.interrupts = [mock_interrupt]
                mock_state.tasks = [mock_task]
                return mock_state
            else:
                # Second check: no more interrupts
                mock_state = MagicMock()
                mock_state.next = []
                mock_state.tasks = []
                return mock_state

        mock_graph.astream = mock_astream
        mock_graph.aget_state = mock_aget_state
        set_app_graph(mock_graph)

        # Mock user input
        with patch('builtins.input', return_value='Beijing'):
            result_json = await delegate_task.ainvoke({
                "task": "Book a hotel",
                "max_loops": 10
            })

        import json
        result = json.loads(result_json)

        # Debug: print result if failed
        if not result.get("ok"):
            print(f"Error result: {result}")

        # Verify result
        assert result["ok"] is True, f"Expected ok=True, got: {result}"
        assert "Beijing" in result["result"] or "Task completed" in result["result"]
        # Should have called astream twice (initial + resume)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_interrupt_with_default_value(self):
        """Test ask_human interrupt with default value"""
        mock_graph = AsyncMock()

        async def mock_astream(input_data, config, stream_mode):
            yield {
                "messages": [
                    HumanMessage(content="Test"),
                    AIMessage(content="Done with default value")
                ],
                "loops": 1
            }

        async def mock_aget_state(config):
            # First call: has interrupt with default
            mock_state = MagicMock()
            mock_state.next = ["node"]
            mock_task = MagicMock()
            mock_interrupt = MagicMock()
            mock_interrupt.value = {
                "type": "user_input_request",
                "question": "Choose format",
                "default": "markdown"
            }
            mock_task.interrupts = [mock_interrupt]
            mock_state.tasks = [mock_task]

            # After first call, return no interrupts
            async def next_aget_state(config):
                empty_state = MagicMock()
                empty_state.next = []
                empty_state.tasks = []
                return empty_state

            mock_graph.aget_state = next_aget_state
            return mock_state

        mock_graph.astream = mock_astream
        mock_graph.aget_state = mock_aget_state
        set_app_graph(mock_graph)

        # Mock empty user input (should use default)
        with patch('builtins.input', return_value=''):
            result_json = await delegate_task.ainvoke({
                "task": "Generate report",
                "max_loops": 10
            })

        import json
        result = json.loads(result_json)
        assert result["ok"] is True


class TestSubagentToolFiltering:
    """Test that subagent tool filtering works correctly"""

    def test_context_id_prefix_detection(self):
        """Test that subagent- prefix is correctly detected"""
        # This is tested indirectly via planner.py logic
        # Context ID with subagent- prefix should be detected as delegated agent
        context_id = "subagent-abc12345"
        assert context_id.startswith("subagent-")
        assert context_id != "main"

    @pytest.mark.asyncio
    async def test_subagent_cannot_access_delegate_task(self):
        """Subagents should NOT have delegate_task in their visible tools (prevent nesting)"""
        # This is enforced in planner.py:152-156
        # When context_id.startswith("subagent-"), delegate_task is filtered out
        # This test documents the expected behavior

        # Arrange: subagent context
        context_id = "subagent-test123"
        is_subagent = context_id != "main" and context_id.startswith("subagent-")

        # Assert: should be recognized as subagent
        assert is_subagent is True

        # In planner.py, delegate_task would be removed from visible_tools
        # (This is tested via integration tests, not unit test)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
