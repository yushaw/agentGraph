"""Unit tests for SimpleAgent"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from simpleAgent.simple_agent import SimpleAgent
from simpleAgent.utils.prompt_builder import PromptBuilder


class TestPromptBuilder:
    """测试 PromptBuilder"""

    def test_build_fstring_template(self):
        """测试 f-string 模板构建"""
        prompt = PromptBuilder.build_from_template(
            "你是 {role}。任务: {task}",
            {"role": "分析师", "task": "分析数据"},
            format="f-string",
        )

        assert prompt is not None
        result = prompt.invoke({"messages": []})
        assert "分析师" in str(result)
        assert "分析数据" in str(result)

    def test_build_jinja2_template(self):
        """测试 Jinja2 模板构建"""
        prompt = PromptBuilder.build_from_template(
            "你是 {{ role }}。{% if urgent %}紧急{% endif %}任务: {{ task }}",
            {"role": "分析师", "task": "分析数据", "urgent": True},
            format="jinja2",
        )

        assert prompt is not None
        result = prompt.invoke({"messages": []})
        content = str(result)
        assert "分析师" in content
        assert "紧急" in content
        assert "分析数据" in content

    def test_invalid_format(self):
        """测试无效格式"""
        with pytest.raises(ValueError, match="Unsupported format"):
            PromptBuilder.build_from_template(
                "test", {}, format="invalid"
            )


class TestSimpleAgent:
    """测试 SimpleAgent（需要 mock）"""

    @pytest.fixture
    def mock_agent(self, mocker):
        """创建 mock 的 SimpleAgent"""
        # Mock build_simple_app
        mock_app = MagicMock()
        mock_app.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="测试响应")]
        })

        mock_state_factory = MagicMock()
        mock_model_registry = MagicMock()
        mock_tool_registry = MagicMock()

        mocker.patch(
            "simpleAgent.simple_agent.build_simple_app",
            return_value=(mock_app, mock_state_factory, mock_model_registry, mock_tool_registry),
        )

        agent = SimpleAgent()
        return agent

    @pytest.mark.asyncio
    async def test_run_with_template(self, mock_agent):
        """测试使用模板运行"""
        response = await mock_agent.run(
            template="你是 {role}",
            params={"role": "助手"},
            user_message="你好",
        )

        assert response == "测试响应"
        assert mock_agent.app.ainvoke.called

    @pytest.mark.asyncio
    async def test_run_with_tools(self, mock_agent):
        """测试指定工具运行"""
        response = await mock_agent.run(
            user_message="测试",
            tools=["read_file", "write_file"],
        )

        assert response == "测试响应"
