"""
E2E 测试：自动压缩完整业务流程

测试场景：
1. 用户长对话导致 token 达到 critical → 自动压缩 → 继续对话
2. 压缩后 token 重置 → 新的累积
3. 多次自动压缩的场景

依赖：
- 真实的 LangGraph app
- 真实的 LLM 调用（或 mock）
- 完整的 planner → tools → finalize 流程
"""

import pytest
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from unittest.mock import AsyncMock, patch

from generalAgent.runtime.app import build_application


@pytest.fixture
async def app_with_context():
    """构建带 context management 的应用"""
    app, initial_state, skill_registry, tool_registry, skill_config = await build_application()
    return app, initial_state


class TestAutoCompressionE2E:
    """E2E: 自动压缩完整流程"""

    @pytest.mark.asyncio
    async def test_auto_compress_triggered_in_real_conversation(self, app_with_context):
        """
        E2E: 模拟真实对话触发自动压缩

        流程：
        1. 构建包含大量消息的 state（96% token usage）
        2. 用户发送新消息
        3. Planner 检测到 critical → 自动压缩
        4. 验证压缩后 state 更新
        """
        app, initial_state_factory = app_with_context

        # 1. 创建 state，模拟长对话
        state = initial_state_factory()
        messages = [SystemMessage(content="You are a helpful assistant.")]

        # 添加 150 条对话（每条约 400 chars）
        for i in range(150):
            messages.append(HumanMessage(content=f"Question {i}: " + "x" * 200))
            messages.append(AIMessage(content=f"Answer {i}: " + "y" * 200))

        state["messages"] = messages
        state["cumulative_prompt_tokens"] = 123000  # 96% of 128k
        state["compact_count"] = 0
        state["auto_compressed_this_request"] = False

        initial_message_count = len(state["messages"])
        print(f"\n[E2E] 初始消息数: {initial_message_count}")
        print(f"[E2E] 初始 token 使用: 96.1%")

        # 2. 添加新的用户消息
        state["messages"].append(HumanMessage(content="Please summarize our conversation"))

        # 3. Mock LLM 调用（避免真实 API 调用）
        with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
            mock_model = AsyncMock()
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(
                content="I'll help summarize after auto-compression.",
                response_metadata={
                    "token_usage": {
                        "prompt_tokens": 1000,
                        "completion_tokens": 100,
                        "total_tokens": 1100
                    }
                }
            ))
            mock_registry.get_model = lambda x: mock_model

            # 4. 执行一次 agent 循环
            config = {"configurable": {"thread_id": "e2e_auto_compress"}}

            try:
                # 运行到第一个 checkpoint（planner 完成）
                final_state = None
                step_count = 0
                max_steps = 5  # 限制步数防止无限循环

                async for event in app.astream(state, config, stream_mode="values"):
                    final_state = event
                    step_count += 1
                    print(f"[E2E] Step {step_count}: messages={len(event.get('messages', []))}, "
                          f"auto_compressed={event.get('auto_compressed_this_request', False)}")

                    if step_count >= max_steps:
                        break

                # 5. 验证自动压缩执行
                if final_state:
                    final_message_count = len(final_state.get("messages", []))
                    auto_compressed = final_state.get("auto_compressed_this_request", False)
                    compact_count = final_state.get("compact_count", 0)

                    print(f"\n[E2E] 最终消息数: {final_message_count}")
                    print(f"[E2E] auto_compressed: {auto_compressed}")
                    print(f"[E2E] compact_count: {compact_count}")

                    # 断言：应该触发自动压缩
                    assert auto_compressed is True, "应该触发自动压缩"
                    assert compact_count > 0, "compact_count 应该增加"
                    assert final_message_count < initial_message_count, "消息数应该减少"

                    print("[E2E] ✅ 自动压缩成功触发")
                else:
                    pytest.fail("未能获取最终 state")

            except Exception as e:
                print(f"[E2E] ❌ 测试失败: {e}")
                raise

    @pytest.mark.asyncio
    async def test_no_auto_compress_below_threshold_e2e(self, app_with_context):
        """
        E2E: Token 低于阈值时不触发自动压缩

        流程：
        1. 构建 state（80% token usage，低于 95% critical）
        2. 用户发送消息
        3. 验证没有自动压缩
        """
        app, initial_state_factory = app_with_context

        state = initial_state_factory()
        messages = [SystemMessage(content="System")]

        # 添加 50 条对话（约 80% token usage）
        for i in range(50):
            messages.append(HumanMessage(content=f"Q{i}"))
            messages.append(AIMessage(content=f"A{i}"))

        state["messages"] = messages
        state["cumulative_prompt_tokens"] = 102000  # 80% of 128k
        state["compact_count"] = 0
        state["auto_compressed_this_request"] = False

        print(f"\n[E2E] Token 使用: 80% (低于 95% critical)")

        state["messages"].append(HumanMessage(content="Hello"))

        # Mock LLM
        with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
            mock_model = AsyncMock()
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Hi there!"))
            mock_registry.get_model = lambda x: mock_model

            config = {"configurable": {"thread_id": "e2e_no_compress"}}

            final_state = None
            async for event in app.astream(state, config, stream_mode="values"):
                final_state = event
                break  # 只执行一步

            # 验证：不应该触发自动压缩
            if final_state:
                auto_compressed = final_state.get("auto_compressed_this_request", False)
                assert auto_compressed is False, "不应该触发自动压缩"
                print("[E2E] ✅ 正确：低于阈值未触发压缩")


    @pytest.mark.asyncio
    async def test_multiple_auto_compressions_e2e(self, app_with_context):
        """
        E2E: 多次触发自动压缩

        模拟长时间对话中多次自动压缩的场景
        """
        app, initial_state_factory = app_with_context

        state = initial_state_factory()
        state["messages"] = [SystemMessage(content="System")]
        state["compact_count"] = 0

        # 模拟第一次压缩
        for i in range(150):
            state["messages"].append(HumanMessage(content=f"Q1-{i}"))
            state["messages"].append(AIMessage(content=f"A1-{i}"))

        state["cumulative_prompt_tokens"] = 123000  # 96%
        state["auto_compressed_this_request"] = False

        print(f"\n[E2E] 第一次压缩前: {len(state['messages'])} messages")

        # Mock LLM
        with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
            mock_model = AsyncMock()
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))
            mock_registry.get_model = lambda x: mock_model

            # 第一次压缩
            state["messages"].append(HumanMessage(content="Continue"))
            config = {"configurable": {"thread_id": "e2e_multiple"}}

            final_state = None
            async for event in app.astream(state, config, stream_mode="values"):
                final_state = event
                break

            first_compact_count = final_state.get("compact_count", 0)
            print(f"[E2E] 第一次压缩后: compact_count={first_compact_count}")

            # 模拟继续对话，再次达到 critical
            for i in range(150):
                final_state["messages"].append(HumanMessage(content=f"Q2-{i}"))
                final_state["messages"].append(AIMessage(content=f"A2-{i}"))

            final_state["cumulative_prompt_tokens"] = 123000  # 再次达到 96%
            final_state["auto_compressed_this_request"] = False  # Reset flag

            print(f"[E2E] 第二次压缩前: {len(final_state['messages'])} messages")

            # 第二次压缩
            final_state["messages"].append(HumanMessage(content="Continue again"))

            final_state_2 = None
            async for event in app.astream(final_state, config, stream_mode="values"):
                final_state_2 = event
                break

            second_compact_count = final_state_2.get("compact_count", 0)
            print(f"[E2E] 第二次压缩后: compact_count={second_compact_count}")

            # 验证：compact_count 应该递增
            assert second_compact_count > first_compact_count, "compact_count 应该递增"
            print(f"[E2E] ✅ 多次自动压缩成功: {first_compact_count} → {second_compact_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
