"""SimpleAgent Settings

配置系统（简化版）
"""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimpleAgentSettings(BaseSettings):
    """SimpleAgent 配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Agent 基本信息
    name: str = Field(default="SimpleAgent", description="Agent 名称")
    description: str = Field(default="简化版 Agent", description="Agent 描述")

    # 模型配置
    model_type: Literal["base", "reasoning", "vision", "code", "chat"] = Field(
        default="base", description="使用的模型类型"
    )

    # 运行时控制
    max_iterations: int = Field(default=15, ge=1, le=100, description="最大迭代次数")
    max_loops: int = Field(default=3, ge=1, le=20, description="最大循环次数")

    # Prompt 模板配置
    prompt_template: str = Field(default="", description="Prompt 模板字符串")
    prompt_format: Literal["f-string", "jinja2"] = Field(
        default="f-string", description="模板格式"
    )

    # 工具配置
    tools_config_path: str = Field(
        default="simpleAgent/config/tools.yaml", description="工具配置文件路径"
    )


_settings_instance: SimpleAgentSettings | None = None


def get_settings() -> SimpleAgentSettings:
    """获取配置单例

    Returns:
        SimpleAgentSettings 实例
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = SimpleAgentSettings()
    return _settings_instance
