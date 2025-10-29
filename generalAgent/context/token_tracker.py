"""
Token 追踪和状态评估器

负责：
1. 从 API 响应提取精确 token 使用量
2. 计算累积使用量和上下文状态
3. 判断响应级别（正常/提示/警告/强制）
4. 动态决定压缩策略
"""

from dataclasses import dataclass
from typing import Optional, Literal, Dict
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """单次 API 调用的 Token 使用情况"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_name: str


@dataclass
class ContextStatus:
    """上下文状态评估结果"""
    # 基础信息
    cumulative_prompt_tokens: int
    context_window: int
    usage_ratio: float  # 0.0 to 1.0

    # 响应级别
    level: Literal["normal", "info", "warning", "critical"]

    # 压缩建议
    needs_compression: bool

    # 用户提示消息
    message: Optional[str]


# 模型上下文窗口配置（支持动态扩展）
MODEL_CONTEXT_WINDOWS: Dict[str, int] = {
    # DeepSeek
    "deepseek-chat": 128_000,
    "deepseek-reasoner": 128_000,

    # Kimi (Moonshot)
    "moonshot-v1-8k": 8_000,
    "moonshot-v1-32k": 32_000,
    "moonshot-v1-128k": 128_000,
    "kimi-k2-0905-preview": 200_000,

    # GLM
    "glm-4": 128_000,
    "glm-4-plus": 128_000,
    "glm-4.5v": 128_000,

    # OpenAI
    "gpt-4": 8_192,
    "gpt-4-32k": 32_768,
    "gpt-4-turbo": 128_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,

    # Claude
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3.5-sonnet": 200_000,

    # 默认值
    "default": 128_000
}


class TokenTracker:
    """Token 追踪和状态评估器"""

    def __init__(self, settings):
        self.settings = settings
        self.context_settings = settings.context

    def extract_token_usage(self, response: AIMessage) -> Optional[TokenUsage]:
        """
        从 API 响应提取 token 使用量

        Args:
            response: LLM 返回的 AIMessage

        Returns:
            TokenUsage 对象，如果无法提取则返回 None
        """
        try:
            metadata = response.response_metadata
            usage = metadata.get("token_usage") or metadata.get("usage")

            if not usage:
                logger.warning("No token usage found in response metadata")
                return None

            return TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                model_name=metadata.get("model_name", "unknown")
            )
        except Exception as e:
            logger.error(f"Failed to extract token usage: {e}")
            return None

    def get_context_window(self, model_id: str) -> int:
        """
        获取模型的上下文窗口大小

        支持精确匹配和前缀匹配（如 "gpt-4-0125-preview" 匹配 "gpt-4"）
        """
        # 精确匹配
        if model_id in MODEL_CONTEXT_WINDOWS:
            return MODEL_CONTEXT_WINDOWS[model_id]

        # 前缀匹配（如 "deepseek-chat-v2" → "deepseek-chat"）
        for key, window in MODEL_CONTEXT_WINDOWS.items():
            if model_id.startswith(key):
                return window

        # 默认值
        logger.warning(
            f"Unknown model '{model_id}', using default context window "
            f"{MODEL_CONTEXT_WINDOWS['default']}"
        )
        return MODEL_CONTEXT_WINDOWS["default"]

    def check_status(
        self,
        cumulative_prompt_tokens: int,
        model_id: str
    ) -> ContextStatus:
        """
        检查当前上下文状态并给出响应建议

        响应级别：
        - normal (0-75%): 正常运行，无需任何操作
        - info (75-85%): 温和提示，可选压缩
        - warning (85-95%): 强烈警告，建议立即压缩
        - critical (95%+): 危险状态，需要强制压缩
        """
        context_window = self.get_context_window(model_id)
        usage_ratio = cumulative_prompt_tokens / context_window if context_window > 0 else 0

        # 判断响应级别
        if usage_ratio < self.context_settings.info_threshold:
            level = "normal"
            needs_compression = False
            message = None

        elif usage_ratio < self.context_settings.warning_threshold:
            level = "info"
            needs_compression = False
            message = self._format_info_message(
                cumulative_prompt_tokens, context_window, usage_ratio
            )

        elif usage_ratio < self.context_settings.critical_threshold:
            level = "warning"
            needs_compression = False
            message = self._format_warning_message(
                cumulative_prompt_tokens, context_window, usage_ratio
            )

        else:  # >= 95%
            level = "critical"
            needs_compression = True
            message = self._format_critical_message(
                cumulative_prompt_tokens, context_window, usage_ratio
            )

        return ContextStatus(
            cumulative_prompt_tokens=cumulative_prompt_tokens,
            context_window=context_window,
            usage_ratio=usage_ratio,
            level=level,
            needs_compression=needs_compression,
            message=message
        )


    def _format_info_message(self, current: int, total: int, ratio: float) -> str:
        """75-85%: 温和提示"""
        return f"""<system_reminder>
💡 Token 使用提示

当前累积: {current:,} / {total:,} tokens ({ratio:.1%})

如果对话还将继续，可以考虑使用 compact_context 工具压缩上下文。
</system_reminder>"""

    def _format_warning_message(self, current: int, total: int, ratio: float) -> str:
        """85-95%: 强烈警告"""
        return f"""<system_reminder>
⚠️ Token 使用警告

当前累积: {current:,} / {total:,} tokens ({ratio:.1%})

⚠️ 强烈建议立即使用 compact_context 工具压缩上下文！
如果不压缩，对话可能很快中断。
</system_reminder>"""

    def _format_critical_message(self, current: int, total: int, ratio: float) -> str:
        """95%+: 危险状态（通常不会显示给 LLM，因为会自动压缩）"""
        return f"""<system_reminder>
🚨 Token 使用严重警告

当前累积: {current:,} / {total:,} tokens ({ratio:.1%})

🚨 已达到临界阈值，系统将自动压缩上下文以避免对话中断。
</system_reminder>"""
