"""Unified error handling for AgentGraph nodes and tools."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from langchain_core.messages import SystemMessage

from generalAgent.graph.state import AppState

LOGGER = logging.getLogger(__name__)


class AgentGraphError(Exception):
    """Base exception for AgentGraph errors."""

    def __init__(self, message: str, user_message: str = None):
        super().__init__(message)
        self.user_message = user_message or message


class ToolExecutionError(AgentGraphError):
    """Error during tool execution."""
    pass


class ModelInvocationError(AgentGraphError):
    """Error during model invocation."""
    pass


class TimeoutError(AgentGraphError):
    """Operation timeout error."""
    pass


class RateLimitError(AgentGraphError):
    """Rate limit exceeded error."""
    pass


def with_error_boundary(node_name: str):
    """Decorator to add error boundary to graph nodes.

    Catches exceptions and converts them to user-friendly messages.

    Args:
        node_name: Name of the node for logging and error messages

    Example:
        @with_error_boundary("planner")
        def planner_node(state: AppState) -> AppState:
            # node logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(state: AppState) -> AppState:
            try:
                return func(state)
            except TimeoutError as e:
                LOGGER.error(f"{node_name} timeout: {e}")
                return {
                    "messages": [SystemMessage(
                        content=f"⏱️ {node_name} 响应超时，请稍后重试。"
                    )]
                }
            except RateLimitError as e:
                LOGGER.error(f"{node_name} rate limit: {e}")
                return {
                    "messages": [SystemMessage(
                        content="🚦 请求过于频繁，请 1 分钟后再试。"
                    )]
                }
            except ModelInvocationError as e:
                LOGGER.error(f"{node_name} model error: {e}")
                user_msg = getattr(e, 'user_message', str(e))
                return {
                    "messages": [SystemMessage(
                        content=f"🤖 AI 模型调用失败：{user_msg}"
                    )]
                }
            except ToolExecutionError as e:
                LOGGER.error(f"{node_name} tool error: {e}")
                user_msg = getattr(e, 'user_message', str(e))
                return {
                    "messages": [SystemMessage(
                        content=f"🔧 工具执行失败：{user_msg}"
                    )]
                }
            except Exception as e:
                LOGGER.exception(f"{node_name} unexpected error", exc_info=e)
                # Don't expose internal error details to users
                return {
                    "messages": [SystemMessage(
                        content=f"❌ 执行出错，请重试。如果问题持续，请联系支持。"
                    )]
                }

        @functools.wraps(func)
        async def async_wrapper(state: AppState) -> AppState:
            try:
                return await func(state)
            except TimeoutError as e:
                LOGGER.error(f"{node_name} timeout: {e}")
                return {
                    "messages": [SystemMessage(
                        content=f"⏱️ {node_name} 响应超时，请稍后重试。"
                    )]
                }
            except RateLimitError as e:
                LOGGER.error(f"{node_name} rate limit: {e}")
                return {
                    "messages": [SystemMessage(
                        content="🚦 请求过于频繁，请 1 分钟后再试。"
                    )]
                }
            except ModelInvocationError as e:
                LOGGER.error(f"{node_name} model error: {e}")
                user_msg = getattr(e, 'user_message', str(e))
                return {
                    "messages": [SystemMessage(
                        content=f"🤖 AI 模型调用失败：{user_msg}"
                    )]
                }
            except ToolExecutionError as e:
                LOGGER.error(f"{node_name} tool error: {e}")
                user_msg = getattr(e, 'user_message', str(e))
                return {
                    "messages": [SystemMessage(
                        content=f"🔧 工具执行失败：{user_msg}"
                    )]
                }
            except Exception as e:
                LOGGER.exception(f"{node_name} unexpected error", exc_info=e)
                return {
                    "messages": [SystemMessage(
                        content=f"❌ 执行出错，请重试。如果问题持续，请联系支持。"
                    )]
                }

        # Return appropriate wrapper based on whether func is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def safe_tool_call(tool_name: str):
    """Decorator for safe tool execution with error handling.

    Args:
        tool_name: Name of the tool for logging

    Example:
        @tool
        @safe_tool_call("get_weather")
        def get_weather(city: str) -> str:
            # tool logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> str:
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                LOGGER.exception(f"Tool {tool_name} failed", exc_info=e)
                import json
                return json.dumps({
                    "ok": False,
                    "error": f"工具执行失败：{str(e)}"
                }, ensure_ascii=False)
        return wrapper
    return decorator


def handle_model_error(error: Exception) -> str:
    """Convert model invocation errors to user-friendly messages.

    Args:
        error: Exception raised during model invocation

    Returns:
        User-friendly error message
    """
    error_str = str(error).lower()

    # OpenAI specific errors
    if "rate_limit" in error_str or "429" in error_str:
        return "请求过于频繁，请稍后再试"

    if "timeout" in error_str:
        return "AI 响应超时，请重试"

    if "context_length" in error_str or "token" in error_str:
        return "对话历史过长，请开启新会话"

    if "invalid_api_key" in error_str or "authentication" in error_str:
        return "API 密钥无效，请联系管理员"

    if "quota" in error_str or "insufficient" in error_str:
        return "AI 服务配额不足，请联系管理员"

    # Generic error
    return f"AI 服务暂时不可用：{str(error)}"
