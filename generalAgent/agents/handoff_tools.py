"""Generate handoff tools for agent-to-agent communication.

Based on LangGraph best practices:
- Each agent gets a transfer_to_{agent_id} tool
- Tools return Command objects for routing
- Supports dynamic agent discovery via AgentRegistry
"""

from __future__ import annotations

import logging
from typing import Annotated, List

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

LOGGER = logging.getLogger(__name__)


def create_agent_handoff_tools(agent_registry) -> List[BaseTool]:
    """为所有 enabled agents 创建 handoff tools

    每个 agent 会生成一个 transfer_to_{agent_id} tool，用于将控制权
    移交给该 agent。

    Args:
        agent_registry: AgentRegistry 实例

    Returns:
        List[BaseTool]: handoff tools 列表

    Example:
        >>> registry = scan_agents_from_config()
        >>> handoff_tools = create_agent_handoff_tools(registry)
        >>> # 生成: [transfer_to_simple, transfer_to_general, ...]
    """
    if not agent_registry:
        LOGGER.warning("AgentRegistry is None, no handoff tools created")
        return []

    handoff_tools = []

    for card in agent_registry.list_enabled():
        agent_id = card.id
        agent_name = card.name
        description = card.description

        # 动态创建 handoff tool
        handoff_tool = _create_single_handoff_tool(
            agent_id=agent_id,
            agent_name=agent_name,
            description=description,
            skills=[s.name for s in card.skills],
        )

        handoff_tools.append(handoff_tool)
        LOGGER.info(f"Created handoff tool: {handoff_tool.name}")

    return handoff_tools


def _create_single_handoff_tool(
    agent_id: str,
    agent_name: str,
    description: str,
    skills: List[str],
) -> BaseTool:
    """创建单个 handoff tool

    Args:
        agent_id: Agent ID (e.g., "simple")
        agent_name: Agent 名称 (e.g., "SimpleAgent")
        description: Agent 描述
        skills: Agent 技能列表

    Returns:
        BaseTool: handoff tool
    """
    tool_name = f"transfer_to_{agent_id}"
    skills_str = ", ".join(skills) if skills else "通用任务"

    tool_description = f"""Transfer control to {agent_name}

{description}

**技能:** {skills_str}

**何时使用:**
当任务需要该 agent 的专业能力时，将任务完全移交给它处理。

**注意:**
- 任务描述必须详细，目标 agent 无法访问当前对话历史
- 移交后，该 agent 将接管对话直到任务完成
- 完成后会自动返回结果
"""

    # Create the tool function
    def handoff_tool_func(
        task: str,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Handoff tool execution function"""
        LOGGER.info(f"Transferring to {agent_name} (@{agent_id})")
        LOGGER.debug(f"Task: {task}")

        # 准备状态更新
        current_messages = state.get("messages", [])
        agent_call_stack = state.get("agent_call_stack", [])  # 当前调用栈
        agent_call_history = state.get("agent_call_history", [])  # 历史记录

        # ========== 防循环检测 ==========
        # 规则1: 检查调用栈中是否已经有该 agent（防止嵌套循环）
        # 例如: agent → simple → agent (simple 调用 agent 时检测到 agent 在栈中)
        if agent_id in agent_call_stack:
            error_msg = (
                f"⚠️ 循环检测: Agent '{agent_id}' 已在当前调用栈中\n"
                f"调用栈: {' → '.join(agent_call_stack)} → {agent_id}\n"
                f"这会导致无限递归，已拒绝此次 handoff。\n\n"
                f"💡 提示: 如果需要多次调用同一个 agent 处理不同任务，"
                f"请等待当前任务完成后再调用。"
            )
            LOGGER.warning(error_msg)

            # 返回错误消息，不执行 handoff
            error_response = ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
                name=tool_name,
            )

            return Command(
                update={"messages": current_messages + [error_response]},
                # 不跳转，继续在当前 agent
            )

        # 规则2: 检查调用栈深度（防止过深的嵌套）
        MAX_CALL_STACK_DEPTH = 5  # 最大嵌套深度
        if len(agent_call_stack) >= MAX_CALL_STACK_DEPTH:
            error_msg = (
                f"⚠️ 调用栈深度超限: 已达到最大嵌套深度 ({MAX_CALL_STACK_DEPTH})\n"
                f"当前调用栈: {' → '.join(agent_call_stack)} → {agent_id}\n"
                f"为防止栈溢出，已拒绝此次 handoff。\n\n"
                f"💡 提示: 尝试将复杂任务拆分为更小的独立子任务。"
            )
            LOGGER.warning(error_msg)

            error_response = ToolMessage(
                content=error_msg,
                tool_call_id=tool_call_id,
                name=tool_name,
            )

            return Command(
                update={"messages": current_messages + [error_response]},
            )

        # 创建 handoff message
        handoff_msg = ToolMessage(
            content=f"✓ Transferred to {agent_name}",
            tool_call_id=tool_call_id,
            name=tool_name,
        )

        # 创建新任务 message
        task_msg = HumanMessage(content=task)

        update = {
            "messages": current_messages + [handoff_msg, task_msg],
            "agent_call_stack": agent_call_stack + [agent_id],  # 压入调用栈
            "agent_call_history": agent_call_history + [agent_id],  # 记录历史
            "current_agent": agent_id,  # 记录当前 agent
        }

        # 返回 Command 对象
        return Command(
            goto=agent_id,  # 跳转到目标 agent 节点
            update=update,
        )

    # Wrap with @tool decorator
    handoff_tool = tool(tool_description)(handoff_tool_func)

    # Set tool name and description manually
    handoff_tool.name = tool_name
    handoff_tool.description = tool_description

    return handoff_tool
