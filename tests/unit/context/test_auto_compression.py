"""
测试自动压缩功能

测试场景：
1. Token 达到 critical 阈值（95%）时自动触发压缩
2. 自动压缩成功后更新 state
3. 防止同一请求中多次自动压缩
4. 自动压缩失败时降级处理
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from generalAgent.graph.state import AppState
from generalAgent.config.settings import get_settings
from generalAgent.context.compressor import CompressionResult


@pytest.fixture
def settings():
    """模拟settings"""
    return get_settings()


@pytest.fixture
def mock_tool_registry():
    """Mock tool registry"""
    registry = Mock()
    registry._discovered = {"compact_context": Mock()}
    registry.is_discovered = Mock(return_value=True)
    registry.load_on_demand = Mock(return_value=None)
    return registry


@pytest.fixture
def mock_skill_registry():
    """Mock skill registry"""
    return Mock()


@pytest.fixture
def mock_model_resolver():
    """Mock model resolver"""
    return Mock()


@pytest.fixture
def sample_messages():
    """生成足够多的消息以模拟高 token 使用"""
    messages = [SystemMessage(content="System prompt")]

    # 添加大量对话消息
    for i in range(100):
        messages.append(HumanMessage(content=f"User message {i}"))
        messages.append(AIMessage(content=f"AI response {i}"))

    return messages


class TestAutoCompression:
    """测试自动压缩功能"""

    @pytest.mark.asyncio
    async def test_auto_compress_triggered_at_critical_threshold(
        self, settings, mock_tool_registry, mock_skill_registry, sample_messages
    ):
        """测试在 critical 阈值时自动触发压缩"""
        from generalAgent.graph.nodes import build_planner_node

        # 构建 planner node
        planner = build_planner_node(
            model_registry=Mock(),
            model_resolver=Mock(),
            tool_registry=mock_tool_registry,
            persistent_global_tools=[],
            skill_registry=mock_skill_registry,
            skill_config=Mock(get_enabled_skills=Mock(return_value=[])),
            settings=settings,
        )

        # 创建 state，累积 token 达到 96%（超过 95% critical 阈值）
        state = {
            "messages": sample_messages,
            "cumulative_prompt_tokens": 123000,  # 96% of 128k
            "cumulative_completion_tokens": 0,
            "compact_count": 0,
            "auto_compressed_this_request": False,
            "mentioned_agents": [],
            "new_mentioned_agents": [],
            "active_skill": None,
            "allowed_tools": [],
            "persistent_tools": [],
            "context_id": "main",
            "loops": 0,
            "max_loops": 100,
        }

        # Mock compress_context 方法
        with patch("generalAgent.graph.nodes.planner.ContextManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.compress_context = AsyncMock(return_value=CompressionResult(
                messages=sample_messages[:50],  # 压缩到 50 条消息
                before_count=len(sample_messages),
                after_count=50,
                before_tokens=123000,
                after_tokens=60000,
                strategy="compact",
                compression_ratio=0.49
            ))

            # Mock model invocation
            with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
                mock_model = AsyncMock()
                mock_model.ainvoke = AsyncMock(return_value=AIMessage(
                    content="压缩完成后的回复",
                    response_metadata={}
                ))
                mock_registry.get_model = Mock(return_value=mock_model)

                # 执行 planner node
                result = await planner(state)

                # 验证自动压缩被触发
                assert result["auto_compressed_this_request"] is True
                assert result["compact_count"] == 1
                assert result["cumulative_prompt_tokens"] == 0
                assert result["cumulative_completion_tokens"] == 0
                assert len(result["messages"]) == 50

    @pytest.mark.asyncio
    async def test_auto_compress_not_triggered_below_threshold(
        self, settings, mock_tool_registry, mock_skill_registry, sample_messages
    ):
        """测试在阈值以下不触发自动压缩"""
        from generalAgent.graph.nodes import build_planner_node

        planner = build_planner_node(
            model_registry=Mock(),
            model_resolver=Mock(),
            tool_registry=mock_tool_registry,
            persistent_global_tools=[],
            skill_registry=mock_skill_registry,
            skill_config=Mock(get_enabled_skills=Mock(return_value=[])),
            settings=settings,
        )

        # 创建 state，累积 token 为 80%（低于 95% critical 阈值）
        state = {
            "messages": sample_messages[:50],
            "cumulative_prompt_tokens": 102000,  # 80% of 128k
            "cumulative_completion_tokens": 0,
            "compact_count": 0,
            "auto_compressed_this_request": False,
            "mentioned_agents": [],
            "new_mentioned_agents": [],
            "active_skill": None,
            "allowed_tools": [],
            "persistent_tools": [],
            "context_id": "main",
            "loops": 0,
            "max_loops": 100,
        }

        # Mock model invocation
        with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
            mock_model = AsyncMock()
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(
                content="正常回复",
                response_metadata={"token_usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}}
            ))
            mock_registry.get_model = Mock(return_value=mock_model)

            # 执行 planner node
            result = await planner(state)

            # 验证没有触发自动压缩
            assert result.get("auto_compressed_this_request", False) is False
            assert result.get("compact_count", 0) == 0

    @pytest.mark.asyncio
    async def test_auto_compress_skip_if_already_compressed(
        self, settings, mock_tool_registry, mock_skill_registry, sample_messages
    ):
        """测试同一请求中不会多次自动压缩"""
        from generalAgent.graph.nodes import build_planner_node

        planner = build_planner_node(
            model_registry=Mock(),
            model_resolver=Mock(),
            tool_registry=mock_tool_registry,
            persistent_global_tools=[],
            skill_registry=mock_skill_registry,
            skill_config=Mock(get_enabled_skills=Mock(return_value=[])),
            settings=settings,
        )

        # State 已经在本次请求中自动压缩过
        state = {
            "messages": sample_messages,
            "cumulative_prompt_tokens": 123000,  # 96% (still critical)
            "cumulative_completion_tokens": 0,
            "compact_count": 1,
            "auto_compressed_this_request": True,  # 已经压缩过
            "mentioned_agents": [],
            "new_mentioned_agents": [],
            "active_skill": None,
            "allowed_tools": [],
            "persistent_tools": [],
            "context_id": "main",
            "loops": 0,
            "max_loops": 100,
        }

        # Mock model invocation
        with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
            mock_model = AsyncMock()
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(
                content="回复",
                response_metadata={}
            ))
            mock_registry.get_model = Mock(return_value=mock_model)

            # 执行 planner node
            result = await planner(state)

            # 验证没有再次触发压缩（compact_count 仍然是 1）
            assert result["compact_count"] == 1

    @pytest.mark.asyncio
    async def test_auto_compress_fallback_on_error(
        self, settings, mock_tool_registry, mock_skill_registry, sample_messages
    ):
        """测试自动压缩失败时的降级处理"""
        from generalAgent.graph.nodes import build_planner_node

        planner = build_planner_node(
            model_registry=Mock(),
            model_resolver=Mock(),
            tool_registry=mock_tool_registry,
            persistent_global_tools=[],
            skill_registry=mock_skill_registry,
            skill_config=Mock(get_enabled_skills=Mock(return_value=[])),
            settings=settings,
        )

        state = {
            "messages": sample_messages,
            "cumulative_prompt_tokens": 123000,  # 96%
            "cumulative_completion_tokens": 0,
            "compact_count": 0,
            "auto_compressed_this_request": False,
            "mentioned_agents": [],
            "new_mentioned_agents": [],
            "active_skill": None,
            "allowed_tools": [],
            "persistent_tools": [],
            "context_id": "main",
            "loops": 0,
            "max_loops": 100,
        }

        # Mock compress_context 方法抛出异常
        with patch("generalAgent.graph.nodes.planner.ContextManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.compress_context = AsyncMock(side_effect=Exception("Compression failed"))

            # Mock model invocation
            with patch("generalAgent.graph.nodes.planner.model_registry") as mock_registry:
                mock_model = AsyncMock()
                mock_model.ainvoke = AsyncMock(return_value=AIMessage(
                    content="回复",
                    response_metadata={}
                ))
                mock_registry.get_model = Mock(return_value=mock_model)

                # 执行 planner node
                result = await planner(state)

                # 验证压缩失败，但不影响流程
                assert result.get("auto_compressed_this_request", False) is False
                assert result.get("compact_count", 0) == 0
                # 应该仍然返回正常响应
                assert len(result["messages"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
