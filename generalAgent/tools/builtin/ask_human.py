"""ask_human tool - Agent actively requests user input."""

from typing import List, Literal, Optional, Union

from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class AskHumanInput(BaseModel):
    """ask_human 工具的输入参数"""

    question: str = Field(..., description="要问用户的问题")
    context: str = Field(default="", description="问题的上下文（可选）")
    input_type: Literal["text", "choice", "multi_choice"] = Field(
        default="text",
        description="输入类型: text=文本输入, choice=单选, multi_choice=多选",
    )
    choices: Optional[List[str]] = Field(
        default=None, description="选项列表（仅当 input_type 为 choice 或 multi_choice 时使用）"
    )
    default: Optional[str] = Field(default=None, description="默认值（用户直接回车时使用）")
    required: bool = Field(default=True, description="是否必须回答")


@tool(args_schema=AskHumanInput)
def ask_human(
    question: str,
    context: str = "",
    input_type: Literal["text", "choice", "multi_choice"] = "text",
    choices: Optional[List[str]] = None,
    default: Optional[str] = None,
    required: bool = True,
) -> Union[str, List[str]]:
    """向用户询问信息

    当你缺少必要信息无法继续任务时，使用此工具向用户提问。
    用户会看到你的问题并提供回答，然后你可以继续执行任务。

    何时使用：
    - 需要用户确认细节（如：确认删除操作）
    - 需要用户做选择（如：选择城市、日期）
    - 缺少关键参数（如：不知道用户想要什么）
    - 需要用户提供额外信息才能完成任务

    Args:
        question: 要问用户的问题（清晰、具体）
        context: 问题的背景说明（可选，解释为什么需要这个信息）
        input_type: 输入类型（目前仅支持 "text" 文本输入）
        choices: 选项列表（暂未启用）
        default: 默认值（可选）
        required: 是否必须回答（默认 True）

    Returns:
        用户的文本回答

    使用建议：
    - 提出清晰、具体的问题
    - 如果问题需要背景说明，使用 context 参数
    - 用户的回答会作为字符串返回给你

    Examples:
        ask_human("您想预订哪个城市的酒店？", "需要知道城市才能搜索酒店")
        # 用户回答: "北京"
        # 返回: "北京"

        ask_human("请确认是否删除该文件？")
        # 用户回答: "是的"
        # 返回: "是的"
    """
    # V1: 只实现 text 类型
    if input_type != "text":
        raise NotImplementedError(
            f"input_type='{input_type}' 将在未来版本支持。"
            f"当前版本仅支持 input_type='text'"
        )

    # 构建 interrupt 数据
    interrupt_data = {
        "type": "user_input_request",
        "question": question,
        "context": context,
        "input_type": input_type,
        "choices": choices,
        "default": default,
        "required": required,
    }

    # 触发 interrupt，等待用户输入
    answer = interrupt(interrupt_data)

    # 处理默认值
    if not answer and default:
        return default

    # 处理必填
    if required and not answer:
        return "（用户未提供答案）"

    return answer or ""
