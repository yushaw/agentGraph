"""
简单消息截断器（Kimi-style 后备策略）

负责：
1. 提供简单的消息截断功能
2. 作为智能压缩失败时的降级策略
3. 保证系统永不因上下文过长而中断
"""

from typing import List, Optional
from langchain_core.messages import BaseMessage, SystemMessage
import logging

logger = logging.getLogger(__name__)


class MessageTruncator:
    """
    简单消息截断器（Kimi-style 后备策略）

    当智能压缩失败时使用，保证系统永不中断
    """

    def __init__(self, settings):
        self.settings = settings
        self.context_settings = settings.context

    def truncate(
        self,
        messages: List[BaseMessage],
        max_messages: Optional[int] = None
    ) -> List[BaseMessage]:
        """
        简单截断：保留 SystemMessage + 最近 N 条消息

        Args:
            messages: 消息列表
            max_messages: 最大保留消息数（不包括 SystemMessage）

        Returns:
            截断后的消息列表
        """
        if max_messages is None:
            max_messages = self.context_settings.max_history_messages

        # 分离 SystemMessage
        system = [m for m in messages if isinstance(m, SystemMessage)]
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]

        if len(non_system) <= max_messages:
            return messages

        # 保留最近的消息
        recent = non_system[-max_messages:]

        logger.warning(
            f"Truncated messages: {len(messages)} → {len(system) + len(recent)} "
            f"(kept {len(system)} system + {len(recent)} recent)"
        )

        return system + recent
