"""Finalize Node - Final Response Processing

终止节点，处理最终响应
"""
from simpleAgent.graph.state import SimpleState


async def finalize_node(state: SimpleState) -> dict:
    """Finalize 节点：处理最终响应

    Args:
        state: 当前状态

    Returns:
        空字典（不修改状态）
    """
    # SimpleAgent 简化版：无需特殊处理
    # 未来可扩展：格式化输出、日志记录等
    return {}
