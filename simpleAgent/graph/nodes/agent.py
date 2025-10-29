"""Agent Node - LLM Decision Making

SimpleAgent 的核心推理节点
"""
from typing import Any
from langchain_core.messages import AIMessage
from simpleAgent.graph.state import SimpleState


async def agent_node(state: SimpleState, config: dict[str, Any]) -> dict:
    """Agent 节点：LLM 决策是否调用工具

    Args:
        state: 当前状态
        config: LangGraph 配置（包含 model 等）

    Returns:
        更新后的状态（包含 AI 响应消息）
    """
    model = config["configurable"].get("model")
    allowed_tools = state.get("allowed_tools", [])

    # 获取可用工具（从 config 传入）
    tools = config["configurable"].get("tools", [])

    # 过滤工具（仅保留 allowed_tools）
    if allowed_tools:
        filtered_tools = [t for t in tools if t.name in allowed_tools]
    else:
        filtered_tools = tools

    # 绑定工具到模型
    model_with_tools = model.bind_tools(filtered_tools)

    # 调用 LLM
    messages = state["messages"]
    response: AIMessage = await model_with_tools.ainvoke(messages)

    # 增加迭代计数
    iterations = state.get("iterations", 0) + 1

    return {
        "messages": [response],
        "iterations": iterations,
    }
