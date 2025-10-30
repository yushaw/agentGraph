"""Agent scanner - 从 agents.yaml 扫描并注册 agents

类似于 tools/scanner.py 和 skills/loader.py，负责：
1. 从 agents.yaml 读取 Agent Card 配置
2. 动态导入 agent 工厂函数
3. 创建 AgentCard 实例并注册到 AgentRegistry
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Dict, Any, Callable

import yaml

from .registry import AgentRegistry
from .schema import AgentCard, AgentSkill, AgentCapability, AgentProvider, InputMode, OutputMode
from generalAgent.config.project_root import resolve_project_path

LOGGER = logging.getLogger(__name__)


def import_factory(factory_path: str) -> Callable:
    """动态导入 agent 工厂函数

    Args:
        factory_path: 工厂函数路径（格式: "module.path:ClassName" 或 "module.path:function_name"）

    Returns:
        工厂函数或类

    Raises:
        ImportError: 导入失败
        AttributeError: 工厂函数/类不存在

    Examples:
        >>> factory = import_factory("simpleAgent.simple_agent:SimpleAgent")
        >>> agent = factory()  # 创建 SimpleAgent 实例
    """
    try:
        module_path, attr_name = factory_path.split(":")
        module = importlib.import_module(module_path)
        factory = getattr(module, attr_name)
        return factory
    except (ValueError, ImportError, AttributeError) as e:
        LOGGER.error(f"Failed to import agent factory '{factory_path}': {e}")
        raise


def parse_agent_card_from_config(
    agent_id: str,
    config: Dict[str, Any],
) -> AgentCard:
    """从 YAML 配置解析 Agent Card

    Args:
        agent_id: Agent ID
        config: Agent 配置字典

    Returns:
        AgentCard 实例

    Raises:
        KeyError: 缺少必需的配置字段
        ImportError: 工厂函数导入失败
    """
    # ========== Identity ==========
    name = config["name"]
    description = config["description"]
    provider = AgentProvider(config.get("provider", "local"))
    version = config.get("version", "1.0.0")

    # ========== Service Endpoint ==========
    factory = None
    endpoint = None

    if provider == AgentProvider.LOCAL:
        factory_path = config["factory_path"]
        factory = import_factory(factory_path)
    elif provider == AgentProvider.REMOTE:
        endpoint = config["endpoint"]

    # ========== Capabilities ==========
    capabilities = []
    for cap_config in config.get("capabilities", []):
        capability = AgentCapability(
            name=cap_config["name"],
            description=cap_config["description"],
        )
        capabilities.append(capability)

    # ========== Skills ==========
    skills = []
    for skill_config in config.get("skills", []):
        skill = AgentSkill(
            name=skill_config["name"],
            description=skill_config["description"],
            input_mode=InputMode(skill_config.get("input_mode", "text")),
            output_mode=OutputMode(skill_config.get("output_mode", "text")),
            examples=skill_config.get("examples", []),
            parameters=skill_config.get("parameters", {}),
        )
        skills.append(skill)

    # ========== Metadata ==========
    tags = config.get("tags", [])
    enabled = config.get("enabled", False)
    always_available = config.get("always_available", False)
    available_to_subagent = config.get("available_to_subagent", False)

    # ========== Authentication ==========
    requires_auth = config.get("requires_auth", False)
    auth_scheme = config.get("auth_scheme")

    return AgentCard(
        id=agent_id,
        name=name,
        description=description,
        provider=provider,
        version=version,
        factory=factory,
        endpoint=endpoint,
        capabilities=capabilities,
        skills=skills,
        tags=tags,
        enabled=enabled,
        always_available=always_available,
        available_to_subagent=available_to_subagent,
        requires_auth=requires_auth,
        auth_scheme=auth_scheme,
    )


def load_agents_config(config_path: Path | str) -> Dict[str, Any]:
    """加载 agents.yaml 配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 解析错误
    """
    if isinstance(config_path, str):
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    LOGGER.debug(f"Loaded agent config from {config_path}")
    return config


def scan_agents_from_config(config_path: Path | str = None) -> AgentRegistry:
    """从 agents.yaml 扫描并注册 agents

    Args:
        config_path: agents.yaml 路径（可选，默认使用项目配置）

    Returns:
        填充好的 AgentRegistry

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 解析错误
    """
    registry = AgentRegistry()

    # 使用默认配置路径
    if config_path is None:
        config_path = resolve_project_path("generalAgent/config/agents.yaml")

    # 加载配置
    config = load_agents_config(config_path)

    # 检查全局开关
    if not config.get("global", {}).get("enabled", True):
        LOGGER.info("Agents system is disabled in config")
        return registry

    # 扫描 core agents
    core_agents = config.get("core", {})
    for agent_id, agent_config in core_agents.items():
        try:
            card = parse_agent_card_from_config(agent_id, agent_config)
            registry.register_discovered(card)
            # Core agents are always enabled
            registry.enable_agent(agent_id)
            LOGGER.info(f"Registered core agent: {agent_id} ({card.name})")
        except Exception as e:
            LOGGER.error(f"Failed to register core agent '{agent_id}': {e}")

    # 扫描 optional agents
    optional_agents = config.get("optional", {})
    for agent_id, agent_config in optional_agents.items():
        try:
            card = parse_agent_card_from_config(agent_id, agent_config)
            registry.register_discovered(card)

            # 如果配置为 enabled=true，则启用
            if card.enabled:
                registry.enable_agent(agent_id)
                LOGGER.info(f"Registered and enabled optional agent: {agent_id} ({card.name})")
            else:
                LOGGER.info(f"Registered optional agent (disabled): {agent_id} ({card.name})")
        except Exception as e:
            LOGGER.error(f"Failed to register optional agent '{agent_id}': {e}")

    # 输出统计信息
    stats = registry.get_stats()
    LOGGER.info(
        f"Agent scan complete: {stats['discovered']} discovered, "
        f"{stats['enabled']} enabled, "
        f"{stats['available_to_subagent']} available to subagent"
    )

    return registry


def load_default_agent_registry() -> AgentRegistry:
    """加载默认的 agent registry（快捷方式）

    Returns:
        AgentRegistry 实例
    """
    return scan_agents_from_config()
