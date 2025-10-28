"""
上下文管理模块

提供智能的上下文压缩和 Token 管理功能，支持：
- 精确的 Token 监控（基于 API 返回值）
- 分层压缩策略（Recent 完整保留 → Middle Compact → Old Summarize）
- 渐进式响应机制（75% 提示 → 85% 警告 → 95% 强制）
- 降级策略（LLM 压缩失败时自动降级到简单截断）
"""

from .token_tracker import TokenTracker, TokenUsage, ContextStatus
from .compressor import ContextCompressor, CompressionResult
from .truncator import MessageTruncator
from .manager import ContextManager, ContextManagementReport

__all__ = [
    "TokenTracker",
    "TokenUsage",
    "ContextStatus",
    "ContextCompressor",
    "CompressionResult",
    "MessageTruncator",
    "ContextManager",
    "ContextManagementReport",
]
