"""
compact_context 工具

提供 Agent 调用接口来压缩对话上下文，释放 token 空间。
"""

from typing import Annotated, Literal, Optional
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import RemoveMessage, ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from generalAgent.graph.state import AppState
from generalAgent.config.settings import get_settings
from generalAgent.context.manager import ContextManager
import logging

logger = logging.getLogger(__name__)


async def _invoke_model_for_compression(prompt: str, max_tokens: int = 1440) -> str:
    """
    为压缩调用 LLM 的辅助函数

    Args:
        prompt: 压缩 prompt（包含历史消息）
        max_tokens: 最大输出 token 数

    Returns:
        LLM 返回的摘要文本
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()

    # 使用基础模型配置创建临时 LLM 实例
    model = ChatOpenAI(
        model=settings.models.base,
        api_key=settings.models.base_api_key,
        base_url=settings.models.base_base_url,
        max_tokens=max_tokens,
        temperature=0.3
    )

    # 调用 LLM
    response = await model.ainvoke(prompt)

    return response.content


@tool
async def compact_context(
    state: Annotated[AppState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    strategy: Literal["auto", "compact", "summarize"] = "auto"
) -> Command:
    """压缩会话上下文以释放 token 空间

    当对话历史过长时，使用此工具压缩上下文。支持两种策略：
    - compact: 详细摘要，保留技术细节、文件路径、工具调用等
    - summarize: 极简摘要，200字以内，仅保留核心信息
    - auto: 自动选择策略（默认，基于历史压缩效果和次数）

    **压缩效果：**
    - 压缩后的摘要会保留关键信息，不影响后续对话

    **注意事项：**
    - 压缩是不可逆的，旧消息会被摘要替代
    - 建议在完成阶段性任务后压缩，避免丢失进行中的细节
    - 如果压缩失败，系统会自动降级到简单截断（保留最近 150 条消息）

    Args:
        strategy: 压缩策略 (auto/compact/summarize)

    Returns:
        压缩结果报告
    """
    settings = get_settings()

    # 检查是否启用上下文管理
    if not settings.context.enabled:
        return Command(
            update={
                "messages": [ToolMessage(
                    content="⚠️ 上下文管理功能未启用。请在配置中启用 CONTEXT_MANAGEMENT_ENABLED=true",
                    tool_call_id=tool_call_id
                )]
            }
        )

    # 获取当前消息历史
    messages = state.get("messages", [])
    compact_count = state.get("compact_count", 0)
    last_compression_ratio = state.get("last_compression_ratio")

    logger.info(
        f"compact_context called: strategy={strategy}, "
        f"current_messages={len(messages)}, compact_count={compact_count}"
    )

    # 检查是否有足够的消息需要压缩
    if len(messages) < 15:
        return Command(
            update={
                "messages": [ToolMessage(
                    content="💡 当前消息数量较少（< 15 条），暂不需要压缩。",
                    tool_call_id=tool_call_id
                )]
            }
        )

    # 执行压缩
    try:
        context_manager = ContextManager(settings)

        # Get context window from token tracker
        from generalAgent.context.token_tracker import TokenTracker
        tracker = TokenTracker(settings)
        context_window = tracker.get_context_window(settings.models.base)

        result = await context_manager.compress_context(
            messages=messages,
            model_invoker=_invoke_model_for_compression,
            context_window=context_window
        )

        # 生成用户可见报告
        report = context_manager.format_compression_report(result)

        logger.info(
            f"Compression successful: {result.before_count} → {result.after_count} messages, "
            f"ratio={result.compression_ratio:.1%}, strategy={result.strategy}"
        )

        # ✅ Use official LangGraph API: RemoveMessage(id=REMOVE_ALL_MESSAGES)
        # 更新 state
        return Command(
            update={
                "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + result.messages,  # Clear all, then add compressed
                "compact_count": compact_count + 1,
                "last_compact_strategy": result.strategy,
                "last_compression_ratio": result.compression_ratio,
                "cumulative_prompt_tokens": 0,  # 重置累积 token 计数
                "cumulative_completion_tokens": 0,
            },
            # 追加工具返回消息（告知用户压缩结果）
            graph=Command.PARENT
        )

    except Exception as e:
        logger.error(f"Compression failed: {e}", exc_info=True)

        return Command(
            update={
                "messages": [ToolMessage(
                    content=f"❌ 上下文压缩失败: {str(e)}\n\n系统已尝试降级策略，但仍然失败。请联系管理员检查日志。",
                    tool_call_id=tool_call_id
                )]
            }
        )


__all__ = ["compact_context"]
