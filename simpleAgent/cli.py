"""SimpleCLI - Command-Line Interface for SimpleAgent

继承 BaseCLI，实现 SimpleAgent 的 CLI 功能
"""
import logging
from typing import Optional
from langchain_core.messages import HumanMessage

from shared.cli.base_cli import BaseCLI
from shared.session.manager import SessionManager
from simpleAgent.simple_agent import SimpleAgent

LOGGER = logging.getLogger(__name__)


class SimpleCLI(BaseCLI):
    """SimpleAgent 的 CLI 接口

    特点：
    - 继承 BaseCLI 的基础命令（/quit, /help, /sessions, /load, /reset, /current）
    - 无状态模式（每次消息独立处理）
    - 支持交互式对话
    """

    def __init__(
        self,
        session_manager: SessionManager,
        agent: SimpleAgent,
        template: Optional[str] = None,
        params: Optional[dict] = None,
        tools: Optional[list[str]] = None,
    ):
        """初始化 SimpleCLI

        Args:
            session_manager: 会话管理器
            agent: SimpleAgent 实例
            template: Prompt 模板（可选）
            params: 模板参数（可选）
            tools: 允许的工具列表（可选）
        """
        super().__init__(session_manager)
        self.agent = agent
        self.template = template
        self.params = params or {}
        self.tools = tools

    # ========== Abstract Methods Implementation ==========

    def print_welcome(self):
        """打印欢迎消息"""
        print("\n" + "=" * 60)
        print("  SimpleAgent - 轻量级垂直领域 Agent")
        print("=" * 60)
        print(f"\n配置:")
        print(f"  - 模型类型: {self.agent.settings.model_type}")
        print(f"  - 最大迭代: {self.agent.settings.max_iterations}")
        print(f"  - 可用工具: {len(self.tools) if self.tools else '所有启用的工具'}")

        if self.template:
            print(f"  - Prompt 模板: 自定义")
        elif self.agent.template_path:
            print(f"  - Prompt 模板: {self.agent.template_path}")

        print(f"\n可用命令: {', '.join(self.commands.keys())}")
        print("=" * 60 + "\n")

    async def handle_user_message(self, user_input: str):
        """处理用户消息（核心逻辑）

        Args:
            user_input: 用户输入
        """
        try:
            # 调用 SimpleAgent.run()
            response = await self.agent.run(
                template=self.template,
                params=self.params,
                user_message=user_input,
                tools=self.tools,
            )

            # 打印响应
            print(f"\nA> {response}\n")

        except Exception as e:
            LOGGER.error(f"Error processing message: {e}", exc_info=True)
            print(f"\n❌ 处理消息时出错: {e}\n")

    # ========== Optional: Custom Commands ==========

    def _build_command_handlers(self):
        """扩展命令处理器（如果需要自定义命令）"""
        handlers = super()._build_command_handlers()

        # 示例：添加自定义命令
        # handlers["/config"] = self._handle_config

        return handlers

    # async def _handle_config(self, args: str):
    #     """显示当前配置（示例自定义命令）"""
    #     print(f"\n当前配置:")
    #     print(f"  模型类型: {self.agent.settings.model_type}")
    #     print(f"  最大迭代: {self.agent.settings.max_iterations}")
    #     print()
