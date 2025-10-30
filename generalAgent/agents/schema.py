"""Agent Card Schema - Based on A2A Protocol Standard

参考：https://a2a-protocol.org/latest/topics/agent-discovery/

Agent Card 是 agent 的标准化元数据描述，类似于 "数字名片"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any, Dict
from enum import Enum


class AgentProvider(str, Enum):
    """Agent 提供者类型"""
    LOCAL = "local"  # 本地 agent（通过工厂函数创建）
    REMOTE = "remote"  # 远程 agent（通过 HTTP endpoint 调用）


class InputMode(str, Enum):
    """输入模式"""
    TEXT = "text"  # 纯文本输入
    JSON = "json"  # JSON 结构化输入
    STRUCTURED = "structured"  # Pydantic 结构化输入
    MULTIMODAL = "multimodal"  # 支持图片/文件等


class OutputMode(str, Enum):
    """输出模式"""
    TEXT = "text"  # 纯文本输出
    JSON = "json"  # JSON 结构化输出
    MARKDOWN = "markdown"  # Markdown 格式输出
    STREAM = "stream"  # 流式输出


@dataclass(frozen=True, slots=True)
class AgentSkill:
    """Agent 的一个技能描述（类似 Tool 的功能描述）

    这是 Agent Card 中最重要的部分，描述 agent 能做什么任务。
    LLM 会根据这些 skills 来选择合适的 agent。

    Attributes:
        name: 技能名称（唯一标识符）
        description: 技能描述（告诉 LLM 这个技能能做什么）
        input_mode: 输入模式
        output_mode: 输出模式
        examples: 使用示例（帮助 LLM 理解何时使用）
        parameters: 参数描述（可选）
    """

    name: str
    description: str
    input_mode: InputMode = InputMode.TEXT
    output_mode: OutputMode = OutputMode.TEXT
    examples: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)  # {param_name: param_description}


@dataclass(frozen=True, slots=True)
class AgentCapability:
    """Agent 的能力特性（非功能性特征）

    描述 agent 的技术特性，而非具体能做什么任务。

    常见能力：
    - streaming: 支持流式输出
    - push_notifications: 支持推送通知
    - multi_turn: 支持多轮对话
    - stateful: 有状态（保留会话历史）
    - stateless: 无状态（单次调用）
    """

    name: str
    description: str


@dataclass(frozen=True)
class AgentCard:
    """Agent Card - 基于 A2A Protocol 标准的 Agent 元数据

    这是 agent 的 "数字名片"，包含 agent 的身份、能力、技能等信息。

    Attributes:
        # ========== Identity (身份信息) ==========
        id: Agent 唯一标识符（如 "simple", "general"）
        name: Agent 显示名称
        description: Agent 功能描述（简短摘要）
        provider: Agent 提供者类型
        version: Agent 版本号

        # ========== Service Endpoint (服务端点) ==========
        factory: 本地 agent 的工厂函数（provider=local 时使用）
        endpoint: 远程 agent 的 HTTP endpoint（provider=remote 时使用）

        # ========== Capabilities (能力特性) ==========
        capabilities: Agent 的技术能力列表

        # ========== Skills (技能清单) ⭐ 核心部分 ==========
        skills: Agent 能执行的任务列表

        # ========== Metadata (元数据) ==========
        tags: 标签列表（用于分类和搜索）
        enabled: 是否在启动时启用
        always_available: 是否对所有会话可用
        available_to_subagent: 子 agent 是否可以调用

        # ========== Authentication (认证信息) ==========
        requires_auth: 是否需要认证（远程 agent）
        auth_scheme: 认证方案（如 "bearer", "api_key"）

    Examples:
        >>> # SimpleAgent 的 Agent Card
        >>> simple_card = AgentCard(
        ...     id="simple",
        ...     name="SimpleAgent",
        ...     description="轻量级 Agent，适合快速执行简单任务",
        ...     provider=AgentProvider.LOCAL,
        ...     factory=lambda: SimpleAgent(),
        ...     capabilities=[
        ...         AgentCapability("stateless", "无状态，单次调用"),
        ...         AgentCapability("fast", "快速响应，无需初始化"),
        ...     ],
        ...     skills=[
        ...         AgentSkill(
        ...             name="quick_analysis",
        ...             description="快速分析单个文件（<100 行代码）",
        ...             input_mode=InputMode.TEXT,
        ...             output_mode=OutputMode.MARKDOWN,
        ...             examples=[
        ...                 "分析 script.py 的复杂度",
        ...                 "审查 config.json 的语法错误",
        ...             ]
        ...         ),
        ...         AgentSkill(
        ...             name="reasoning_task",
        ...             description="使用推理模型解决数学/逻辑问题",
        ...             input_mode=InputMode.TEXT,
        ...             output_mode=OutputMode.TEXT,
        ...             examples=[
        ...                 "计算 fibonacci(100)",
        ...                 "证明费马大定理",
        ...             ]
        ...         ),
        ...     ],
        ...     tags=["lightweight", "stateless", "single-turn"],
        ... )
    """

    # ========== Identity ==========
    id: str
    name: str
    description: str
    provider: AgentProvider = AgentProvider.LOCAL
    version: str = "1.0.0"

    # ========== Service Endpoint ==========
    factory: Optional[Callable[[], Any]] = None  # For local agents
    endpoint: Optional[str] = None  # For remote agents (future use)

    # ========== Capabilities ==========
    capabilities: List[AgentCapability] = field(default_factory=list)

    # ========== Skills (核心) ==========
    skills: List[AgentSkill] = field(default_factory=list)

    # ========== Metadata ==========
    tags: List[str] = field(default_factory=list)
    enabled: bool = False
    always_available: bool = False
    available_to_subagent: bool = False

    # ========== Authentication (for remote agents) ==========
    requires_auth: bool = False
    auth_scheme: Optional[str] = None  # "bearer" | "api_key" | "oauth2"

    def has_skill(self, skill_name: str) -> bool:
        """检查是否具有指定技能

        Args:
            skill_name: 技能名称

        Returns:
            True 如果具有该技能
        """
        return any(skill.name == skill_name for skill in self.skills)

    def has_capability(self, capability_name: str) -> bool:
        """检查是否具有指定能力

        Args:
            capability_name: 能力名称

        Returns:
            True 如果具有该能力
        """
        return any(cap.name == capability_name for cap in self.capabilities)

    def has_tag(self, tag: str) -> bool:
        """检查是否具有指定标签

        Args:
            tag: 标签名称

        Returns:
            True 如果具有该标签
        """
        return tag in self.tags

    def get_catalog_text(self) -> str:
        """生成该 agent 的目录文本（用于 SystemMessage）

        Returns:
            Markdown 格式的 agent 描述
        """
        lines = [f"## @{self.id} - {self.name}"]
        lines.append(f"{self.description}")
        lines.append("")

        if self.skills:
            lines.append("**技能：**")
            for skill in self.skills:
                lines.append(f"- **{skill.name}**: {skill.description}")
                if skill.examples:
                    lines.append(f"  - 示例: `{skill.examples[0]}`")
            lines.append("")

        if self.capabilities:
            cap_names = [cap.name for cap in self.capabilities]
            lines.append(f"**特性**: {', '.join(cap_names)}")
            lines.append("")

        if self.tags:
            lines.append(f"**标签**: {', '.join(self.tags)}")
            lines.append("")

        return "\n".join(lines)
