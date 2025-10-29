"""SimpleAgent State Definition (Simplified)

精简版状态定义，只保留核心字段
"""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SimpleState(TypedDict):
    """SimpleAgent 状态定义（精简版）

    相比 GeneralAgent，移除了：
    - todos（任务追踪）
    - mentioned_agents（@mention 系统）
    - context_id/parent_context（委派代理）
    - active_skill（技能加载）
    - needs_compression（上下文压缩）

    保留核心字段：
    - messages: 对话历史
    - iterations: 循环计数
    - allowed_tools: 工具白名单
    """

    # 核心字段
    messages: Annotated[Sequence[BaseMessage], add_messages]
    """对话消息历史（LangChain 消息格式）"""

    # 循环控制
    iterations: int
    """当前迭代次数"""

    max_iterations: int
    """最大迭代次数限制"""

    # 工具管理
    allowed_tools: list[str]
    """允许使用的工具名称列表"""
