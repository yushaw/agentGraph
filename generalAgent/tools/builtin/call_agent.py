"""Call agent tool - 基于 Agent Card 标准的统一 agent 调用接口

遵循 LangGraph 最佳实践：
- 使用 InjectedState 获取父状态
- 返回 Command 对象（而不是 JSON 字符串）
- 支持按 skill/tag/capability 查询 agents
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated, Optional

from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

LOGGER = logging.getLogger(__name__)

# 全局 agent_registry（由 runtime 注入）
_agent_registry = None


def set_agent_registry(registry):
    """设置全局 agent registry

    Args:
        registry: AgentRegistry 实例
    """
    global _agent_registry
    _agent_registry = registry


@tool
async def call_agent(
    agent_id: str,
    task: str,
    max_loops: Optional[int] = None,
    template: Optional[str] = None,
    tools: Optional[list[str]] = None,
    model_type: Optional[str] = None,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """调用其他 agent 执行任务（基于 Agent Card 标准）

    **Agent 类型：**
    - @simple: SimpleAgent（轻量级，单次调用，无状态）
      - Skills: quick_analysis, reasoning_task, code_review
    - @general: GeneralAgent（完整功能，多轮对话，有状态）- 默认禁用
      - Skills: complex_document_analysis, skill_based_task, multi_step_research

    **何时使用：**
    1. 需要不同类型 agent 的能力（如简单任务用 simple，复杂任务用 general）
    2. 需要专用 agent 的特定 skill（如 quick_analysis, reasoning_task）
    3. 任务需要独立上下文（避免污染主对话历史）

    **与 delegate_task 的区别：**
    - delegate_task: 调用自身的副本（相同类型的子 agent）
    - call_agent: 调用其他类型的 agent（可能有不同的能力）

    Args:
        agent_id: Agent ID（如 "simple", "general"）
        task: 任务描述（必须详细，目标 agent 无法访问调用者的历史）
        max_loops: 最大循环次数（可选，仅对支持多轮的 agent 有效）
        template: Prompt 模板（可选，仅对 SimpleAgent 有效）
        tools: 工具列表（可选，仅对 SimpleAgent 有效）
        model_type: 模型类型（可选，如 "base", "reasoning", "code"）

    Returns:
        Command 对象（更新父状态）

    Examples:
        # 调用 SimpleAgent 快速分析代码
        call_agent(
            agent_id="simple",
            task="分析 uploads/script.py 的复杂度",
            template="你是代码审查专家。分析代码并给出建议。"
        )

        # 调用 SimpleAgent 使用推理模型
        call_agent(
            agent_id="simple",
            task="计算 fibonacci(100)",
            model_type="reasoning"
        )
    """
    try:
        # 检查 agent_registry 是否初始化
        if _agent_registry is None:
            error_msg = "AgentRegistry not initialized. Please ensure agents system is enabled."
            LOGGER.error(error_msg)
            return _create_error_command(error_msg, tool_call_id)

        # 检查 agent 是否存在
        if not _agent_registry.is_discovered(agent_id):
            available_agents = [card.id for card in _agent_registry.list_discovered()]
            error_msg = f"Agent '{agent_id}' not found. Available agents: {available_agents}"
            LOGGER.error(error_msg)
            return _create_error_command(error_msg, tool_call_id)

        # 按需加载 agent（如果未启用）
        if not _agent_registry.is_enabled(agent_id):
            LOGGER.info(f"Loading agent on-demand: {agent_id}")
            _agent_registry.load_on_demand(agent_id)

        # 获取 agent card
        agent_card = _agent_registry.get(agent_id)

        # 根据 agent 类型分派
        if agent_id == "simple":
            result_text = await _call_simple_agent(
                task=task,
                template=template,
                tools=tools,
                model_type=model_type,
                state=state,
            )
        elif agent_id == "general":
            result_text = await _call_general_agent(
                task=task,
                max_loops=max_loops or 100,
                state=state,
            )
        else:
            # 未来扩展：其他 agent 类型
            error_msg = f"Agent type '{agent_id}' not yet implemented"
            LOGGER.error(error_msg)
            return _create_error_command(error_msg, tool_call_id)

        # 返回 Command，更新父状态
        return _create_success_command(
            agent_id=agent_id,
            result=result_text,
            tool_call_id=tool_call_id,
            state=state,
        )

    except Exception as e:
        LOGGER.error(f"call_agent failed: {e}", exc_info=True)
        error_msg = f"Agent execution failed: {str(e)}"
        return _create_error_command(error_msg, tool_call_id)


def _create_success_command(
    agent_id: str,
    result: str,
    tool_call_id: str,
    state: dict,
) -> Command:
    """创建成功的 Command 对象

    Args:
        agent_id: Agent ID
        result: Agent 执行结果
        tool_call_id: Tool call ID
        state: 父状态

    Returns:
        Command 对象
    """
    # 创建 ToolMessage
    tool_message = ToolMessage(
        content=result,
        tool_call_id=tool_call_id,
        name="call_agent",
    )

    # 更新 agent 调用历史
    agent_call_history = state.get("agent_call_history", []) if state else []
    agent_call_history = agent_call_history + [agent_id]

    return Command(
        update={
            "messages": [tool_message],
            "agent_call_history": agent_call_history,
        }
    )


def _create_error_command(
    error_msg: str,
    tool_call_id: str,
) -> Command:
    """创建错误的 Command 对象

    Args:
        error_msg: 错误消息
        tool_call_id: Tool call ID

    Returns:
        Command 对象
    """
    tool_message = ToolMessage(
        content=f"❌ Error: {error_msg}",
        tool_call_id=tool_call_id,
        name="call_agent",
        status="error",
    )

    return Command(
        update={
            "messages": [tool_message],
        }
    )


async def _call_simple_agent(
    task: str,
    template: Optional[str],
    tools: Optional[list[str]],
    model_type: Optional[str],
    state: Optional[dict],
) -> str:
    """调用 SimpleAgent 的内部实现

    Args:
        task: 任务描述
        template: Prompt 模板
        tools: 工具列表
        model_type: 模型类型
        state: 父状态（用于继承 workspace）

    Returns:
        SimpleAgent 的响应文本
    """
    # 获取 SimpleAgent 实例
    agent = _agent_registry.get_instance("simple")

    # 可选：从父状态继承 workspace_path
    params = {}
    if state:
        workspace = state.get("workspace_path")
        if workspace:
            params["workspace_path"] = workspace

    # 运行 SimpleAgent
    LOGGER.info(f"[call_agent→simple] Starting execution...")
    result = await agent.run(
        template=template,
        params=params,
        user_message=task,
        tools=tools,
        model_type=model_type,
    )
    LOGGER.info(f"[call_agent→simple] Completed")

    return result


async def _call_general_agent(
    task: str,
    max_loops: int,
    state: Optional[dict],
) -> str:
    """调用 GeneralAgent 的内部实现

    Args:
        task: 任务描述
        max_loops: 最大循环次数
        state: 父状态

    Returns:
        GeneralAgent 的最终响应文本
    """
    # 懒加载 GeneralAgent 的 runtime
    from generalAgent.runtime.app import build_application

    # 构建 GeneralAgent 应用
    # TODO: 优化为单例（避免重复构建）
    app, initial_state_factory = build_application()

    # 创建独立的 context_id
    context_id = f"call-agent-{uuid.uuid4().hex[:8]}"

    # 构建初始状态
    initial_state = initial_state_factory()
    initial_state["messages"] = [HumanMessage(content=task)]
    initial_state["max_loops"] = max_loops
    initial_state["context_id"] = context_id

    # 可选：从父状态继承 workspace
    if state:
        workspace = state.get("workspace_path")
        if workspace:
            initial_state["workspace_path"] = workspace

    # 运行 GeneralAgent
    config = {"configurable": {"thread_id": context_id}}

    LOGGER.info(f"[call_agent→general] Starting execution...")

    final_state = await app.ainvoke(initial_state, config)

    # 提取结果
    last_message = final_state["messages"][-1]
    result_text = getattr(last_message, "content", "No response")

    LOGGER.info(f"[call_agent→general] Completed")

    return result_text


__all__ = ["call_agent", "set_agent_registry"]
