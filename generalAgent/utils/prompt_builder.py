"""Prompt Template Builder for GeneralAgent

支持 Jinja2 模板格式，允许开发者自定义 Prompt 模板。
"""
from pathlib import Path
from typing import Optional
from jinja2.sandbox import SandboxedEnvironment

from generalAgent.config.project_root import resolve_project_path


class PromptBuilder:
    """Prompt 模板构建器（GeneralAgent 专用）"""

    # 模板文件路径
    TEMPLATE_DIR = "generalAgent/config/prompt_templates"
    CHARLIE_IDENTITY_TEMPLATE = f"{TEMPLATE_DIR}/charlie_identity.jinja2"
    PLANNER_TEMPLATE = f"{TEMPLATE_DIR}/planner.jinja2"
    SUBAGENT_TEMPLATE = f"{TEMPLATE_DIR}/subagent.jinja2"
    FINALIZE_TEMPLATE = f"{TEMPLATE_DIR}/finalize.jinja2"

    @staticmethod
    def _load_template(template_path: str) -> str:
        """加载模板文件内容

        Args:
            template_path: 模板文件相对路径（相对于项目根）

        Returns:
            模板内容字符串
        """
        full_path = resolve_project_path(template_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _render_template(template: str, params: dict) -> str:
        """使用 Jinja2 渲染模板

        使用沙箱环境确保安全性

        Args:
            template: 模板字符串
            params: 模板参数

        Returns:
            渲染后的字符串
        """
        env = SandboxedEnvironment()
        return env.from_string(template).render(**params)

    @classmethod
    def load_charlie_identity(cls, **params) -> str:
        """加载 Charlie 基础身份模板

        Returns:
            渲染后的 Charlie 身份描述
        """
        template = cls._load_template(cls.CHARLIE_IDENTITY_TEMPLATE)
        return cls._render_template(template, params)

    @classmethod
    def load_planner_prompt(cls, **params) -> str:
        """加载 Planner 系统提示

        Args:
            **params: 模板参数（可选）

        Returns:
            渲染后的 Planner 系统提示
        """
        # 加载 Charlie 身份
        charlie_identity = cls.load_charlie_identity()

        # 加载 Planner 模板
        template = cls._load_template(cls.PLANNER_TEMPLATE)

        # 渲染模板
        params["charlie_identity"] = charlie_identity
        return cls._render_template(template, params)

    @classmethod
    def load_subagent_prompt(cls, **params) -> str:
        """加载 Subagent 系统提示

        Args:
            **params: 模板参数（可选）

        Returns:
            渲染后的 Subagent 系统提示
        """
        template = cls._load_template(cls.SUBAGENT_TEMPLATE)
        return cls._render_template(template, params)

    @classmethod
    def load_finalize_prompt(cls, **params) -> str:
        """加载 Finalize 系统提示

        Args:
            **params: 模板参数（可选）

        Returns:
            渲染后的 Finalize 系统提示
        """
        # 加载 Charlie 身份
        charlie_identity = cls.load_charlie_identity()

        # 加载 Finalize 模板
        template = cls._load_template(cls.FINALIZE_TEMPLATE)

        # 渲染模板
        params["charlie_identity"] = charlie_identity
        return cls._render_template(template, params)

    @classmethod
    def load_custom_prompt(cls, template_path: str, **params) -> str:
        """加载自定义模板

        Args:
            template_path: 自定义模板文件路径（相对于项目根）
            **params: 模板参数

        Returns:
            渲染后的自定义 Prompt
        """
        template = cls._load_template(template_path)
        return cls._render_template(template, params)
