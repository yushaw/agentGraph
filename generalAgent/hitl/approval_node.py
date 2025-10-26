"""Approval-enabled ToolNode wrapper."""

from typing import Any, Dict, List, Union

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from .approval_checker import ApprovalChecker


class ApprovalToolNode:
    """带审批功能的 ToolNode 包装器

    在工具执行前拦截并检查是否需要用户审批。
    审批过程对 LLM 透明（不会污染对话历史）。
    """

    def __init__(
        self,
        tools: List,
        approval_checker: ApprovalChecker,
        enable_approval: bool = True,
    ):
        """
        Args:
            tools: 工具列表
            approval_checker: 审批检测器
            enable_approval: 是否启用审批（可用于临时关闭）
        """
        self.tool_node = ToolNode(tools)
        self.approval_checker = approval_checker
        self.enable_approval = enable_approval

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具节点（带审批检查）

        Args:
            state: Graph state

        Returns:
            更新后的 state
        """
        if not self.enable_approval:
            # 审批功能关闭，直接执行工具
            return await self.tool_node.ainvoke(state)

        messages = state.get("messages", [])
        if not messages:
            return await self.tool_node.ainvoke(state)

        last_msg = messages[-1]

        # 只处理 AIMessage 的 tool_calls
        if not isinstance(last_msg, AIMessage) or not hasattr(last_msg, "tool_calls"):
            return await self.tool_node.ainvoke(state)

        if not last_msg.tool_calls:
            return await self.tool_node.ainvoke(state)

        # 检查每个 tool_call 是否需要审批
        rejected_calls = []

        for tool_call in last_msg.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

            # 检查是否需要审批
            decision = self.approval_checker.check(tool_name, tool_args)

            if decision.needs_approval:
                # 触发 interrupt（审批对 LLM 透明）
                user_decision = interrupt(
                    {
                        "type": "tool_approval",
                        "tool": tool_name,
                        "args": tool_args,
                        "reason": decision.reason,
                        "risk_level": decision.risk_level,
                    }
                )

                # 处理用户决策
                if user_decision == "reject":
                    rejected_calls.append(
                        {
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "reason": decision.reason,
                        }
                    )

        # 如果有被拒绝的工具调用，返回拒绝消息
        if rejected_calls:
            # 为每个被拒绝的调用创建 ToolMessage
            tool_messages = []
            for rejected in rejected_calls:
                tool_messages.append(
                    ToolMessage(
                        content=f"❌ 操作已取消: {rejected['reason']}",
                        tool_call_id=rejected["tool_call_id"],
                        name=rejected["tool_name"],
                    )
                )

            return {"messages": tool_messages}

        # 所有工具都通过审批，正常执行
        return await self.tool_node.ainvoke(state)
