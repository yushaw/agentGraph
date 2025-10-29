"""LangGraph Builder for SimpleAgent

构建简化版 Agent Loop:
START → agent ⇄ tools → finalize → END
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from simpleAgent.graph.state import SimpleState
from simpleAgent.graph.nodes import agent_node, finalize_node


def build_simple_graph(tools: list) -> StateGraph:
    """构建 SimpleAgent 的 LangGraph

    Args:
        tools: 工具列表

    Returns:
        编译后的 StateGraph
    """
    # 创建 StateGraph
    workflow = StateGraph(SimpleState)

    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))  # 自动执行工具
    workflow.add_node("finalize", finalize_node)

    # 设置入口点
    workflow.set_entry_point("agent")

    # 添加条件边：agent → tools 或 finalize
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",  # 有 tool_calls → 执行工具
            "end": "finalize",  # 无 tool_calls → 结束
        },
    )

    # 添加边：tools → agent（循环）
    workflow.add_edge("tools", "agent")

    # 添加边：finalize → END
    workflow.add_edge("finalize", END)

    # 编译并返回
    return workflow.compile()


def should_continue(state: SimpleState) -> Literal["continue", "end"]:
    """判断是否继续执行工具

    Args:
        state: 当前状态

    Returns:
        "continue" 或 "end"
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 检查最大迭代次数
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 15)

    if iterations >= max_iterations:
        return "end"

    # 检查是否有 tool_calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"

    return "end"
