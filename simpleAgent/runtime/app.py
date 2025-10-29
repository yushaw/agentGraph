"""Runtime Assembly for SimpleAgent

简化版应用组装（复用 GeneralAgent 的基础设施）
"""
import logging
from pathlib import Path
from typing import Optional

from generalAgent.config.project_root import resolve_project_path
from generalAgent.models import build_default_registry, ModelRegistry
from generalAgent.tools import ToolRegistry
from generalAgent.tools.scanner import scan_multiple_directories
from generalAgent.tools.config_loader import load_tool_config
from simpleAgent.config.settings import get_settings
from simpleAgent.graph.builder import build_simple_graph

LOGGER = logging.getLogger(__name__)


def _create_tool_registry() -> tuple[ToolRegistry, list]:
    """创建工具注册表（简化版）

    复用 GeneralAgent 的工具扫描和配置加载机制

    Returns:
        (ToolRegistry, enabled_tools) 元组
    """
    registry = ToolRegistry()

    # 扫描工具目录（复用 GeneralAgent 的工具）
    builtin_dir = resolve_project_path("generalAgent/tools/builtin")
    custom_dir = resolve_project_path("generalAgent/tools/custom")

    discovered = scan_multiple_directories([builtin_dir, custom_dir])
    LOGGER.info(f"Discovered {len(discovered)} tools")

    # 注册所有工具到 _discovered
    for meta in discovered:
        registry._discovered[meta.name] = meta

    # 加载配置
    settings = get_settings()
    tools_config_path = resolve_project_path(settings.tools_config_path)
    config = load_tool_config(tools_config_path)

    # 启用配置中 enabled=true 的工具
    enabled_tools = []
    for tool_name, tool_config in {**config.get("core", {}), **config.get("optional", {})}.items():
        if tool_config.get("enabled", False):
            if tool_name in registry._discovered:
                tool_meta = registry._discovered[tool_name]
                registry.register_tool(tool_meta.name, tool_meta.tool)
                enabled_tools.append(tool_meta.tool)
                LOGGER.info(f"Enabled tool: {tool_name}")
            else:
                LOGGER.warning(f"Tool '{tool_name}' not found in discovered tools")

    LOGGER.info(f"Enabled {len(enabled_tools)} tools for SimpleAgent")
    return registry, enabled_tools


def build_simple_app(
    model_registry: Optional[ModelRegistry] = None,
) -> tuple:
    """构建 SimpleAgent 应用

    Args:
        model_registry: 可选的模型注册表（如果为 None 则自动构建）

    Returns:
        (app, initial_state_factory, model_registry, tool_registry) 元组
    """
    settings = get_settings()

    # 1. 构建模型注册表
    if model_registry is None:
        model_registry = build_default_registry()
        LOGGER.info("Built default model registry")

    # 2. 创建工具注册表
    tool_registry, enabled_tools = _create_tool_registry()

    # 3. 构建 LangGraph
    app = build_simple_graph(enabled_tools)
    LOGGER.info("Built SimpleAgent graph")

    # 4. 初始状态工厂
    def initial_state_factory(user_message: str, allowed_tools: Optional[list[str]] = None):
        """创建初始状态

        Args:
            user_message: 用户消息
            allowed_tools: 允许的工具列表（如果为 None 则使用所有启用的工具）

        Returns:
            初始状态字典
        """
        from langchain_core.messages import HumanMessage

        if allowed_tools is None:
            allowed_tools = [t.name for t in enabled_tools]

        return {
            "messages": [HumanMessage(content=user_message)],
            "iterations": 0,
            "max_iterations": settings.max_iterations,
            "allowed_tools": allowed_tools,
        }

    return app, initial_state_factory, model_registry, tool_registry
