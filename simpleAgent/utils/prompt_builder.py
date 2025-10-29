"""Prompt Template Builder

支持两种模板格式：
- f-string: 安全、快速（推荐用于代码调用）
- jinja2: 功能强大（推荐用于配置文件）
"""
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate


class PromptBuilder:
    """Prompt 模板构建器"""

    @staticmethod
    def build_from_template(
        template: str,
        params: Optional[dict] = None,
        format: str = "f-string",
    ) -> ChatPromptTemplate:
        """从模板构建 ChatPromptTemplate

        Args:
            template: 模板字符串
            params: 模板参数
            format: 模板格式 ("f-string" 或 "jinja2")

        Returns:
            ChatPromptTemplate 实例

        Examples:
            >>> # f-string 格式
            >>> prompt = PromptBuilder.build_from_template(
            ...     "你是 {role}。任务: {task}",
            ...     {"role": "分析师", "task": "分析数据"},
            ...     format="f-string"
            ... )

            >>> # Jinja2 格式
            >>> prompt = PromptBuilder.build_from_template(
            ...     "你是 {{ role }}。{% if urgent %}紧急{% endif %}任务: {{ task }}",
            ...     {"role": "分析师", "task": "分析数据", "urgent": True},
            ...     format="jinja2"
            ... )
        """
        params = params or {}

        if format == "f-string":
            return PromptBuilder._build_fstring(template, params)
        elif format == "jinja2":
            return PromptBuilder._build_jinja2(template, params)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'f-string' or 'jinja2'")

    @staticmethod
    def _build_fstring(template: str, params: dict) -> ChatPromptTemplate:
        """使用 f-string 格式构建

        安全、快速，LangChain 推荐方式
        """
        # 使用 LangChain PromptTemplate.from_template
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", template),
                ("placeholder", "{messages}"),  # 历史消息占位符
            ]
        )

        # 使用 partial 预填充参数
        if params:
            prompt = prompt.partial(**params)

        return prompt

    @staticmethod
    def _build_jinja2(template: str, params: dict) -> ChatPromptTemplate:
        """使用 Jinja2 格式构建

        功能强大但需要注意安全性（使用 SandboxedEnvironment）
        """
        from jinja2.sandbox import SandboxedEnvironment

        # 使用沙箱环境渲染模板（安全性）
        env = SandboxedEnvironment()
        rendered = env.from_string(template).render(**params)

        # 构建 ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", rendered),
                ("placeholder", "{messages}"),  # 历史消息占位符
            ]
        )

        return prompt

    @staticmethod
    def load_from_file(
        template_path: str, params: Optional[dict] = None, format: str = "jinja2"
    ) -> ChatPromptTemplate:
        """从文件加载模板

        Args:
            template_path: 模板文件路径
            params: 模板参数
            format: 模板格式（文件默认用 jinja2）

        Returns:
            ChatPromptTemplate 实例
        """
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        return PromptBuilder.build_from_template(template, params, format)
