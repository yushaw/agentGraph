"""
Unit tests for delegate_task improvements:
1. Subagent system prompt contains summary requirements
2. Continuation mechanism triggers for short responses (< 200 chars)
3. Context ID uses 'subagent-' prefix to trigger correct prompt
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from generalAgent.tools.builtin.delegate_task import delegate_task, set_app_graph
from generalAgent.graph.prompts import SUBAGENT_SYSTEM_PROMPT


class TestSubagentSystemPrompt:
    """Test that subagent system prompt contains summary requirements"""

    def test_prompt_mentions_last_message_only(self):
        """Subagent prompt must emphasize main agent only sees last message"""
        assert "只能看到你的最后一条消息" in SUBAGENT_SYSTEM_PROMPT
        assert "主 Agent" in SUBAGENT_SYSTEM_PROMPT

    def test_prompt_requires_comprehensive_summary(self):
        """Subagent prompt must require comprehensive summary"""
        assert "完整摘要" in SUBAGENT_SYSTEM_PROMPT
        assert "最后消息必须包含" in SUBAGENT_SYSTEM_PROMPT

    def test_prompt_specifies_summary_content(self):
        """Subagent prompt must specify what to include in summary"""
        # Must specify 3 key elements
        assert "做了什么" in SUBAGENT_SYSTEM_PROMPT
        assert "发现了什么" in SUBAGENT_SYSTEM_PROMPT
        assert "结果是什么" in SUBAGENT_SYSTEM_PROMPT

    def test_prompt_mentions_file_modifications(self):
        """Subagent prompt must mention file modifications requirement"""
        assert "修改了文件" in SUBAGENT_SYSTEM_PROMPT or "修改了哪些文件" in SUBAGENT_SYSTEM_PROMPT

    def test_prompt_includes_example_summary(self):
        """Subagent prompt should include example summary"""
        assert "示例" in SUBAGENT_SYSTEM_PROMPT or "任务完成" in SUBAGENT_SYSTEM_PROMPT


class TestDelegateTaskDocstring:
    """Test that delegate_task docstring is clear about isolation"""

    def test_docstring_mentions_last_message_only(self):
        """Docstring must mention main agent only sees last message"""
        docstring = delegate_task.description
        # Check for isolation mention (看不到 or 只能看到)
        assert ("看不到" in docstring or "只能看到" in docstring)
        # Check mentions history or context
        assert ("历史" in docstring or "上下文" in docstring)

    def test_docstring_mentions_independent_context(self):
        """Docstring must mention independent context"""
        docstring = delegate_task.description
        assert "独立" in docstring or "隔离" in docstring

    def test_docstring_requires_self_contained_task(self):
        """Docstring must emphasize task description must be self-contained"""
        docstring = delegate_task.description
        assert "自包含" in docstring

    def test_docstring_includes_examples(self):
        """Docstring should include usage examples"""
        docstring = delegate_task.description
        assert "Examples:" in docstring or "示例" in docstring


class TestContinuationMechanism:
    """Test continuation mechanism for short responses"""

    @pytest.mark.asyncio
    async def test_continuation_not_triggered_for_long_response(self):
        """Continuation should NOT trigger if response >= 200 chars"""
        # Mock app graph
        mock_graph = AsyncMock()

        # Create a long response (>= 200 chars)
        long_response = "任务完成！" + "这是一个很长的回复。" * 20
        assert len(long_response) >= 200

        final_state = {
            "messages": [
                HumanMessage(content="Test task"),
                AIMessage(content=long_response)
            ],
            "loops": 5
        }

        # Mock astream to return the final state
        async def mock_astream(*args, **kwargs):
            yield final_state

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Execute delegate_task
        result_json = await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        import json
        result = json.loads(result_json)

        # Should succeed without continuation
        assert result["ok"] is True
        assert result["result"] == long_response
        assert "loops" in result

    @pytest.mark.asyncio
    async def test_continuation_triggered_for_short_response(self):
        """Continuation SHOULD trigger if response < 200 chars"""
        mock_graph = AsyncMock()

        # Create a short response (< 200 chars)
        short_response = "完成了。"
        assert len(short_response) < 200

        # Create a longer response for continuation
        detailed_response = "详细摘要：任务完成！使用了 find_files 和 read_file 工具搜索了 src/ 目录。" + "找到了相关代码，共计 8 处匹配。详细信息如下：文件1路径、文件2路径、文件3路径。" * 4
        assert len(detailed_response) >= 200

        call_count = 0

        async def mock_astream(state, config, stream_mode):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: return short response
                yield {
                    "messages": [
                        HumanMessage(content="Test task"),
                        AIMessage(content=short_response)
                    ],
                    "loops": 3
                }
            else:
                # Second call (continuation): return detailed response
                yield {
                    "messages": [
                        HumanMessage(content="Test task"),
                        AIMessage(content=short_response),
                        HumanMessage(content="你的上一次回复太简短了"),
                        AIMessage(content=detailed_response)
                    ],
                    "loops": 4
                }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Execute delegate_task
        result_json = await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        import json
        result = json.loads(result_json)

        # Should trigger continuation
        assert call_count == 2  # Called twice (initial + continuation)
        assert result["ok"] is True
        assert result["result"] == detailed_response

    @pytest.mark.asyncio
    async def test_continuation_prompt_content(self):
        """Continuation prompt should emphasize main agent can't see history"""
        mock_graph = AsyncMock()

        short_response = "完成。"
        continuation_messages = []

        async def mock_astream(state, config, stream_mode):
            messages = state.get("messages", [])
            continuation_messages.extend(messages)

            # Return short response first time
            yield {
                "messages": messages + [AIMessage(content=short_response)],
                "loops": 1
            }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Execute delegate_task
        await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        # Check continuation prompt
        human_messages = [m for m in continuation_messages if isinstance(m, HumanMessage)]
        continuation_prompt = next((m.content for m in human_messages if "简短" in m.content), None)

        if continuation_prompt:
            assert "主 Agent" in continuation_prompt or "主agent" in continuation_prompt.lower()
            assert "工具调用" in continuation_prompt or "历史" in continuation_prompt


class TestContextIdPrefix:
    """Test that context_id uses 'subagent-' prefix"""

    @pytest.mark.asyncio
    async def test_context_id_uses_subagent_prefix(self):
        """Context ID should use 'subagent-' prefix to trigger subagent prompt"""
        mock_graph = AsyncMock()

        captured_context_id = None

        async def mock_astream(state, config, stream_mode):
            nonlocal captured_context_id
            captured_context_id = state.get("context_id")

            yield {
                "messages": [
                    HumanMessage(content="Test"),
                    AIMessage(content="Test response that is long enough to avoid continuation" * 5)
                ],
                "loops": 1
            }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Execute delegate_task
        await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        # Check context_id prefix
        assert captured_context_id is not None
        assert captured_context_id.startswith("subagent-")

    @pytest.mark.asyncio
    async def test_thread_id_matches_context_id(self):
        """Thread ID should match context_id for isolation"""
        mock_graph = AsyncMock()

        captured_state = None

        async def mock_astream(state, config, stream_mode):
            nonlocal captured_state
            captured_state = state

            yield {
                "messages": [
                    HumanMessage(content="Test"),
                    AIMessage(content="Test response that is long enough" * 10)
                ],
                "loops": 1
            }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Execute delegate_task
        await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        # Check thread_id matches context_id
        assert captured_state is not None
        assert captured_state["thread_id"] == captured_state["context_id"]
        assert captured_state["thread_id"].startswith("subagent-")


class TestMaxOneContinuation:
    """Test that continuation only happens once (max 1 retry)"""

    @pytest.mark.asyncio
    async def test_continuation_only_once(self):
        """Continuation should only happen once even if still too short"""
        mock_graph = AsyncMock()

        short_response_1 = "完成。"
        short_response_2 = "还是很短。"  # Still < 200 chars
        assert len(short_response_2) < 200

        call_count = 0

        async def mock_astream(state, config, stream_mode):
            nonlocal call_count
            call_count += 1

            messages = state.get("messages", [])

            if call_count == 1:
                # First call: return short response
                yield {
                    "messages": messages + [AIMessage(content=short_response_1)],
                    "loops": 1
                }
            elif call_count == 2:
                # Continuation: still return short response
                yield {
                    "messages": messages + [AIMessage(content=short_response_2)],
                    "loops": 2
                }

        mock_graph.astream = mock_astream
        set_app_graph(mock_graph)

        # Execute delegate_task
        result_json = await delegate_task.ainvoke({"task": "Test task", "max_loops": 10})

        import json
        result = json.loads(result_json)

        # Should only call twice (initial + 1 continuation)
        assert call_count == 2
        assert result["ok"] is True
        # Result is still short, but we don't retry again
        assert result["result"] == short_response_2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
