"""
上下文管理器 - 统一入口

负责：
1. 监控 token 使用
2. 决定响应级别
3. 执行压缩或截断
4. 生成用户报告
"""

from typing import List, Optional, Literal, Callable
from langchain_core.messages import BaseMessage, AIMessage
from dataclasses import dataclass
import logging

from .token_tracker import TokenTracker, ContextStatus
from .compressor import ContextCompressor, CompressionResult
from .truncator import MessageTruncator

logger = logging.getLogger(__name__)


@dataclass
class ContextManagementReport:
    """上下文管理操作报告"""
    action: Literal["none", "warning", "compression", "emergency_truncation"]
    status: Optional[ContextStatus]
    compression_result: Optional[CompressionResult] = None
    user_message: Optional[str] = None


class ContextManager:
    """
    上下文管理器 - 统一入口

    职责：
    1. 监控 token 使用
    2. 决定响应级别
    3. 执行压缩或截断
    4. 生成用户报告
    """

    def __init__(self, settings):
        self.settings = settings
        self.tracker = TokenTracker(settings)
        self.compressor = ContextCompressor(settings)
        self.truncator = MessageTruncator(settings)

    def extract_and_check(
        self,
        response: AIMessage,
        cumulative_prompt_tokens: int,
        model_id: str
    ) -> ContextManagementReport:
        """
        提取 token 使用并检查状态

        Args:
            response: LLM 响应
            cumulative_prompt_tokens: 当前累积 prompt tokens
            model_id: 模型 ID

        Returns:
            包含状态和建议的报告
        """
        # 1. 提取 token 使用
        token_usage = self.tracker.extract_token_usage(response)

        if not token_usage:
            return ContextManagementReport(
                action="none",
                status=None
            )

        # 2. 更新累积 token
        new_cumulative = cumulative_prompt_tokens + token_usage.prompt_tokens

        # 3. 检查状态
        status = self.tracker.check_status(
            cumulative_prompt_tokens=new_cumulative,
            model_id=model_id
        )

        # 4. 日志记录
        logger.info(
            f"Token usage - Prompt: {token_usage.prompt_tokens:,} "
            f"(cumulative: {new_cumulative:,} / {status.context_window:,}, "
            f"{status.usage_ratio:.1%}) - Level: {status.level}"
        )

        # 5. 决定响应
        if status.level == "normal":
            return ContextManagementReport(
                action="none",
                status=status
            )
        elif status.level in ["info", "warning"]:
            return ContextManagementReport(
                action="warning",
                status=status,
                user_message=status.message
            )
        else:  # critical
            return ContextManagementReport(
                action="compression",  # 需要强制压缩
                status=status,
                user_message=status.message
            )

    async def compress_context(
        self,
        messages: List[BaseMessage],
        model_invoker: Callable,
        context_window: int = 128000
    ) -> CompressionResult:
        """
        执行上下文压缩（带降级策略）

        Args:
            messages: 当前消息历史
            model_invoker: LLM 调用函数（接受 prompt 和 max_tokens）
            context_window: 模型的 context window 大小

        Returns:
            压缩结果
        """
        try:
            # 尝试智能压缩
            result = await self.compressor.compress_messages(
                messages=messages,
                model_invoker=model_invoker,
                context_window=context_window
            )

            return result

        except Exception as e:
            logger.error(f"Context compression failed: {e}")
            logger.warning("Falling back to simple truncation")

            # 降级：简单截断
            truncated = self.truncator.truncate(messages)

            return CompressionResult(
                messages=truncated,
                before_count=len(messages),
                after_count=len(truncated),
                before_tokens=self.compressor._estimate_tokens(messages),
                after_tokens=self.compressor._estimate_tokens(truncated),
                strategy="emergency_truncate",
                compression_ratio=len(truncated) / len(messages) if messages else 1.0
            )

    def check_message_length(
        self,
        messages: List[BaseMessage],
        context_window: int
    ) -> bool:
        """
        检查当前消息是否已经太长（预防式检查）

        Returns:
            True 如果需要立即压缩，False 如果安全
        """
        estimated_tokens = self.compressor._estimate_tokens(messages)
        threshold = context_window * 0.9

        if estimated_tokens > threshold:
            logger.warning(
                f"Current messages {estimated_tokens} tokens exceed 90% of context window "
                f"({context_window} tokens)"
            )
            return True

        return False

    def format_compression_report(self, result: CompressionResult) -> str:
        """
        生成压缩报告（用户可见）

        Returns:
            格式化的报告文本
        """
        saved_messages = result.before_count - result.after_count
        saved_tokens = result.before_tokens - result.after_tokens

        strategy_name = {
            "compact": "详细摘要",
            "summarize": "极简摘要",
            "emergency_truncate": "紧急截断"
        }.get(result.strategy, result.strategy)

        return f"""✅ 上下文已压缩

压缩前: {result.before_count} 条消息 (~{result.before_tokens:,} tokens)
压缩后: {result.after_count} 条消息 (~{result.after_tokens:,} tokens)
策略: {strategy_name}
节省: {saved_messages} 条消息, ~{saved_tokens:,} tokens ({(1-result.compression_ratio):.1%})
""".strip()
