"""Agent Registry - 基于 Agent Card 标准的注册表

类似于 ToolRegistry 和 SkillRegistry，但使用 Agent Card 标准。
支持多种查询模式：by ID、by skill、by tag、by capability。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any

from .schema import AgentCard, AgentCapability

LOGGER = logging.getLogger(__name__)


class AgentRegistry:
    """Agent 注册表 - 支持 Agent Card 标准

    架构（三层加载）：
    - _discovered: 所有扫描到的 agents（不论是否启用）
    - _enabled: 已启用的 agents（启动时加载或 @mention 加载）
    - _instances: Agent 实例缓存（单例模式）

    查询模式（Query Pattern）：
    - get(agent_id): 按 ID 查询
    - query_by_skill(skill_name): 按技能查询
    - query_by_tag(tags): 按标签查询
    - query_by_capability(capability): 按能力查询

    发现策略（Discovery Strategy）：
    - Curated Registry: 从 agents.yaml 加载（当前实现）
    - Well-Known URI: 从 /.well-known/agent-card.json 加载（未来扩展）
    - Direct Configuration: 硬编码（不推荐）
    """

    def __init__(self):
        self._discovered: Dict[str, AgentCard] = {}  # All discovered agents
        self._enabled: Dict[str, AgentCard] = {}  # Enabled agents
        self._instances: Dict[str, Any] = {}  # Cached agent instances

    # ========== Registration Methods ==========

    def register_discovered(self, card: AgentCard) -> None:
        """注册发现的 agent（不论是否启用）

        Args:
            card: Agent Card
        """
        self._discovered[card.id] = card
        LOGGER.debug(f"Discovered agent: {card.id} ({card.name})")

    def enable_agent(self, agent_id: str) -> AgentCard:
        """启用一个 agent（将其从 discovered 移到 enabled）

        Args:
            agent_id: Agent ID

        Returns:
            Agent Card

        Raises:
            KeyError: Agent 未被发现
        """
        if agent_id not in self._discovered:
            raise KeyError(f"Agent not found in discovered agents: {agent_id}")

        card = self._discovered[agent_id]
        self._enabled[agent_id] = card
        LOGGER.info(f"Enabled agent: {agent_id} ({card.name})")
        return card

    def load_on_demand(self, agent_id: str) -> AgentCard:
        """按需加载 agent（@mention 触发）

        Args:
            agent_id: Agent ID

        Returns:
            Agent Card

        Raises:
            KeyError: Agent 未被发现
        """
        if agent_id in self._enabled:
            # Already enabled
            return self._enabled[agent_id]

        if agent_id not in self._discovered:
            raise KeyError(f"Agent not found in discovered agents: {agent_id}")

        # Enable and return
        return self.enable_agent(agent_id)

    # ========== Query Methods (by ID) ==========

    def get(self, agent_id: str) -> Optional[AgentCard]:
        """获取已启用的 agent card

        Args:
            agent_id: Agent ID

        Returns:
            Agent Card，如果未启用则返回 None
        """
        return self._enabled.get(agent_id)

    def get_discovered(self, agent_id: str) -> Optional[AgentCard]:
        """获取 agent card（从 discovered 中查找）

        Args:
            agent_id: Agent ID

        Returns:
            Agent Card，如果未发现则返回 None
        """
        return self._discovered.get(agent_id)

    def is_discovered(self, agent_id: str) -> bool:
        """检查 agent 是否被发现

        Args:
            agent_id: Agent ID

        Returns:
            True 如果 agent 在 discovered 池中
        """
        return agent_id in self._discovered

    def is_enabled(self, agent_id: str) -> bool:
        """检查 agent 是否已启用

        Args:
            agent_id: Agent ID

        Returns:
            True 如果 agent 已启用
        """
        return agent_id in self._enabled

    # ========== Query Methods (by Skill) ⭐ 核心功能 ==========

    def query_by_skill(self, skill_name: str) -> List[AgentCard]:
        """按技能查询 agents

        这是 LLM 最常用的查询方式：根据需要完成的任务，找到具有相应技能的 agents。

        Args:
            skill_name: 技能名称

        Returns:
            具有该技能的 agent cards 列表

        Examples:
            >>> # 查找能做 "quick_analysis" 的 agents
            >>> agents = registry.query_by_skill("quick_analysis")
            >>> # 返回: [SimpleAgent, ...]
        """
        return [
            card for card in self._enabled.values()
            if card.has_skill(skill_name)
        ]

    def query_by_skill_fuzzy(self, skill_description: str) -> List[AgentCard]:
        """按技能描述模糊查询 agents（未来扩展）

        使用语义相似度匹配技能描述。

        Args:
            skill_description: 技能描述（如 "分析代码复杂度"）

        Returns:
            匹配的 agent cards 列表

        Note:
            当前实现为简单的关键词匹配，未来可以使用向量相似度。
        """
        keywords = skill_description.lower().split()
        results = []

        for card in self._enabled.values():
            for skill in card.skills:
                skill_text = f"{skill.name} {skill.description}".lower()
                if any(keyword in skill_text for keyword in keywords):
                    results.append(card)
                    break  # 只添加一次

        return results

    # ========== Query Methods (by Tag) ==========

    def query_by_tags(self, tags: List[str], match_all: bool = False) -> List[AgentCard]:
        """按标签查询 agents

        Args:
            tags: 标签列表
            match_all: 是否要求匹配所有标签（默认 False，匹配任一即可）

        Returns:
            匹配的 agent cards 列表

        Examples:
            >>> # 查找有 "lightweight" 或 "stateless" 标签的 agents
            >>> agents = registry.query_by_tags(["lightweight", "stateless"])

            >>> # 查找同时有 "lightweight" 和 "stateless" 标签的 agents
            >>> agents = registry.query_by_tags(["lightweight", "stateless"], match_all=True)
        """
        if match_all:
            # 必须包含所有标签
            return [
                card for card in self._enabled.values()
                if all(card.has_tag(tag) for tag in tags)
            ]
        else:
            # 包含任一标签即可
            return [
                card for card in self._enabled.values()
                if any(card.has_tag(tag) for tag in tags)
            ]

    # ========== Query Methods (by Capability) ==========

    def query_by_capability(self, capability: str) -> List[AgentCard]:
        """按能力查询 agents

        Args:
            capability: 能力名称（如 "streaming", "stateful"）

        Returns:
            具有该能力的 agent cards 列表

        Examples:
            >>> # 查找支持流式输出的 agents
            >>> agents = registry.query_by_capability("streaming")
        """
        return [
            card for card in self._enabled.values()
            if card.has_capability(capability)
        ]

    # ========== List Methods ==========

    def list_enabled(self) -> List[AgentCard]:
        """列出所有已启用的 agents

        Returns:
            Agent cards 列表
        """
        return list(self._enabled.values())

    def list_discovered(self) -> List[AgentCard]:
        """列出所有发现的 agents

        Returns:
            Agent cards 列表
        """
        return list(self._discovered.values())

    def list_available_to_subagent(self) -> List[AgentCard]:
        """列出可供子 agent 使用的 agents

        Returns:
            Agent cards 列表
        """
        return [
            card for card in self._enabled.values()
            if card.available_to_subagent
        ]

    # ========== Instance Management ==========

    def get_instance(self, agent_id: str) -> Any:
        """获取 agent 实例（单例模式，避免重复初始化）

        Args:
            agent_id: Agent ID

        Returns:
            Agent 实例

        Raises:
            KeyError: Agent 未启用
            ValueError: Agent 没有工厂函数（远程 agent）
        """
        if agent_id not in self._enabled:
            raise KeyError(f"Agent not enabled: {agent_id}")

        # Check cache
        if agent_id in self._instances:
            return self._instances[agent_id]

        # Create new instance
        card = self._enabled[agent_id]

        if card.factory is None:
            raise ValueError(f"Agent '{agent_id}' has no factory function (remote agent?)")

        instance = card.factory()
        self._instances[agent_id] = instance
        LOGGER.info(f"Created agent instance: {agent_id}")
        return instance

    # ========== Catalog Generation ==========

    def get_catalog_text(self, detailed: bool = False) -> str:
        """生成 agents 目录文本（用于 SystemMessage）

        按照 Agent Card 标准格式化输出，包含每个 agent 的技能和能力描述。

        Args:
            detailed: 是否显示详细信息（技能、能力等），默认 True

        Returns:
            Markdown 格式的 agents 目录
        """
        if not self._enabled:
            return ""

        if detailed:
            # 详细模式：显示所有技能和能力
            lines = ["# 可用 Agents（Agents）\n"]
            for card in self._enabled.values():
                lines.append(card.get_catalog_text())
            return "\n".join(lines)
        else:
            # 精简模式：只显示 ID 和描述
            lines = ["# 可用 Agents（Agents）\n"]
            for card in self._enabled.values():
                lines.append(f"- **@{card.id}**: {card.description}")
            lines.append("\n提示：使用 @agent_id 来查看详细技能信息并调用该 agent。")
            return "\n".join(lines)

    # ========== Statistics ==========

    def get_stats(self) -> Dict[str, int]:
        """获取注册表统计信息

        Returns:
            统计信息字典
        """
        return {
            "discovered": len(self._discovered),
            "enabled": len(self._enabled),
            "cached_instances": len(self._instances),
            "available_to_subagent": len(self.list_available_to_subagent()),
        }
