"""SimpleAgent - Core Agent Class

可以被 GeneralAgent 或其他代码调用的简化版 Agent
"""
import logging
from pathlib import Path
from typing import Optional, Literal
from langchain_core.messages import HumanMessage

from generalAgent.config.project_root import resolve_project_path
from generalAgent.models import ModelRegistry
from simpleAgent.config.settings import SimpleAgentSettings
from simpleAgent.runtime.app import build_simple_app
from simpleAgent.utils.prompt_builder import PromptBuilder

LOGGER = logging.getLogger(__name__)


class SimpleAgent:
    """SimpleAgent - 简化版 Agent（支持函数调用）

    特点：
    - 无状态（不保存会话历史）
    - 轻量级（精简 Graph）
    - 可配置（支持模板和工具定制）
    - 可调用（供 GeneralAgent 等调用）

    Examples:
        >>> # 方式 1: 使用代码调用
        >>> agent = SimpleAgent()
        >>> result = await agent.run(
        ...     template="你是 {role}。任务: {task}",
        ...     params={"role": "分析师", "task": "分析数据"},
        ...     tools=["read_file", "write_file"]
        ... )

        >>> # 方式 2: 使用配置文件
        >>> agent = SimpleAgent(config_path="configs/data_analyst.yaml")
        >>> result = await agent.run(user_message="分析 sales.csv")

        >>> # 方式 3: 使用预定义模板
        >>> agent = SimpleAgent(template_path="simpleAgent/config/prompt_templates/data_analyst.jinja2")
        >>> result = await agent.run(
        ...     params={"task": "分析季度销售数据"},
        ...     user_message="开始分析"
        ... )
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        template_path: Optional[str] = None,
        model_registry: Optional[ModelRegistry] = None,
    ):
        """初始化 SimpleAgent

        Args:
            config_path: 配置文件路径（YAML，可选）
            template_path: Prompt 模板文件路径（可选）
            model_registry: 模型注册表（可选，默认自动构建）
        """
        self.settings = SimpleAgentSettings()

        # 加载配置文件（如果提供）
        if config_path:
            # TODO: 实现 YAML 配置加载
            pass

        # 加载模板（如果提供）
        self.template_path = template_path

        # 构建应用
        self.app, self.initial_state_factory, self.model_registry, self.tool_registry = (
            build_simple_app(model_registry)
        )

        LOGGER.info(f"SimpleAgent initialized: {self.settings.name}")

    async def run(
        self,
        template: Optional[str] = None,
        params: Optional[dict] = None,
        user_message: Optional[str] = None,
        tools: Optional[list[str]] = None,
        max_iterations: Optional[int] = None,
        model_type: Optional[Literal["base", "reasoning", "vision", "code", "chat"]] = None,
        format: str = "f-string",
    ) -> str:
        """运行 SimpleAgent（单次调用，无状态）

        Args:
            template: Prompt 模板字符串（优先级高于 template_path）
            params: 模板参数
            user_message: 用户消息（如果未提供，则只有系统 Prompt）
            tools: 允许使用的工具列表（如果为 None 则使用所有启用的工具）
            max_iterations: 最大迭代次数（可选）
            model_type: 使用的模型类型（可选，默认使用配置中的 model_type）
            format: 模板格式 ("f-string" 或 "jinja2")

        Returns:
            Agent 的最终响应文本
        """
        params = params or {}

        # 1. 构建 System Prompt
        if template:
            # 使用传入的模板
            prompt_template = PromptBuilder.build_from_template(template, params, format)
        elif self.template_path:
            # 使用文件模板
            template_path = resolve_project_path(self.template_path)
            prompt_template = PromptBuilder.load_from_file(str(template_path), params, format)
        else:
            # 使用默认模板
            default_template = resolve_project_path(
                "simpleAgent/config/prompt_templates/default.jinja2"
            )
            prompt_template = PromptBuilder.load_from_file(str(default_template), params, "jinja2")

        # 2. 构建初始消息
        messages = []

        # 添加系统消息（从模板生成）
        system_msg = prompt_template.invoke({"messages": []})
        messages.extend(system_msg.messages)

        # 添加用户消息（如果提供）
        if user_message:
            messages.append(HumanMessage(content=user_message))

        # 3. 创建初始状态
        initial_state = {
            "messages": messages,
            "iterations": 0,
            "max_iterations": max_iterations or self.settings.max_iterations,
            "allowed_tools": tools,  # None 表示使用所有工具
        }

        # 4. 选择模型
        model_type = model_type or self.settings.model_type
        model = self._get_model(model_type)

        # 5. 运行 Graph
        config = {
            "configurable": {
                "model": model,
                "tools": self._get_tools(tools),
            }
        }

        LOGGER.info(f"Running SimpleAgent with model_type={model_type}, max_iterations={initial_state['max_iterations']}")

        final_state = await self.app.ainvoke(initial_state, config)

        # 6. 提取最终响应
        last_message = final_state["messages"][-1]
        response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

        return response_text

    def _get_model(self, model_type: str):
        """获取模型实例

        Args:
            model_type: 模型类型

        Returns:
            LangChain ChatModel 实例
        """
        if model_type == "base":
            return self.model_registry.base_model
        elif model_type == "reasoning":
            return self.model_registry.reasoning_model
        elif model_type == "vision":
            return self.model_registry.vision_model
        elif model_type == "code":
            return self.model_registry.code_model
        elif model_type == "chat":
            return self.model_registry.chat_model
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

    def _get_tools(self, tool_names: Optional[list[str]]) -> list:
        """获取工具列表

        Args:
            tool_names: 工具名称列表（如果为 None 则返回所有启用的工具）

        Returns:
            工具对象列表
        """
        if tool_names is None:
            # 返回所有启用的工具
            return list(self.tool_registry._tools.values())
        else:
            # 返回指定的工具
            tools = []
            for name in tool_names:
                tool = self.tool_registry.get_tool(name)
                if tool:
                    tools.append(tool)
                else:
                    LOGGER.warning(f"Tool '{name}' not found in registry")
            return tools
