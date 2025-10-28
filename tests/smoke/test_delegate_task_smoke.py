"""
Smoke tests for delegate_task improvements.
Fast critical-path tests to verify basic functionality works.
"""

import pytest
from unittest.mock import AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from generalAgent.tools.builtin.delegate_task import delegate_task, set_app_graph
from generalAgent.graph.prompts import SUBAGENT_SYSTEM_PROMPT


class TestDelegateTaskSmoke:
    """Critical smoke tests for delegate_task"""

    def test_subagent_prompt_has_summary_requirements(self):
        """CRITICAL: Subagent prompt must mention summary requirements"""
        # This is the most critical change - ensure it exists
        assert "最后一条消息" in SUBAGENT_SYSTEM_PROMPT
        assert "完整摘要" in SUBAGENT_SYSTEM_PROMPT

    def test_delegate_task_docstring_exists(self):
        """CRITICAL: delegate_task must have docstring"""
        # delegate_task is a StructuredTool, check description
        assert delegate_task.description is not None
        assert len(delegate_task.description) > 100

    @pytest.mark.asyncio
    async def test_delegate_task_basic_execution(self):
        """CRITICAL: delegate_task basic execution works"""
        mock_graph = AsyncMock()

        # Simple successful execution
        async def mock_astream(state, config, stream_mode):
            yield {
                "messages": [
                    HumanMessage(content="Test task"),
                    AIMessage(content="Task completed successfully with a detailed response that is long enough")
                ],
                "loops": 1
            }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Should not raise exception
        result_json = await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        import json
        result = json.loads(result_json)

        assert result["ok"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_continuation_basic_functionality(self):
        """CRITICAL: Continuation mechanism works for short responses"""
        mock_graph = AsyncMock()

        call_count = 0

        async def mock_astream(state, config, stream_mode):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # Return short response
                yield {
                    "messages": [AIMessage(content="OK")],
                    "loops": 1
                }
            else:
                # Return longer response on continuation
                yield {
                    "messages": [AIMessage(content="Detailed response: " + "x" * 200)],
                    "loops": 2
                }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        result_json = await delegate_task.ainvoke({"task": "Test", "max_loops": 10})

        import json
        result = json.loads(result_json)

        # Should have triggered continuation
        assert call_count == 2
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_context_id_format(self):
        """CRITICAL: Context ID uses correct prefix"""
        mock_graph = AsyncMock()

        captured_context_id = None

        async def mock_astream(state, config, stream_mode):
            nonlocal captured_context_id
            captured_context_id = state.get("context_id")

            yield {
                "messages": [AIMessage(content="Response " * 50)],
                "loops": 1
            }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        await delegate_task.ainvoke({"task": "Test", "max_loops": 10})

        # Must use subagent- prefix
        assert captured_context_id.startswith("subagent-")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
