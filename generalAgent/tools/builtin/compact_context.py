"""Context compression tool for managing token usage.

This tool allows the LLM to compress conversation history when
approaching token limits.
"""

from __future__ import annotations

from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from generalAgent.context.compressor import ContextCompressor
from generalAgent.context.token_tracker import TokenTracker
from generalAgent.graph.state import AppState


@tool
async def compact_context(
    state: Annotated[AppState, InjectedState],
    strategy: Literal["auto", "compact", "summarize"] = "auto",
) -> Command:
    """压缩会话上下文以释放 token 空间

    当 token 使用量接近限制时，使用此工具压缩消息历史。

    Args:
        strategy:
            - "auto": 自动决定（基于 compact_count 周期）
            - "compact": 详细压缩（保留技术细节、代码、文件名）
            - "summarize": 极简压缩（紧急情况，压缩率更高）

    Returns:
        压缩后的消息历史和更新的状态

    Example:
        当收到 token 警告时：
        ```
        compact_context(strategy="auto")
        ```

        紧急情况（token 即将耗尽）：
        ```
        compact_context(strategy="summarize")
        ```
    """
    from generalAgent.config.settings import get_settings
    from generalAgent.agents.factory import invoke_planner
    from generalAgent.models.registry import ModelRegistry
    from generalAgent.runtime.model_resolver import build_model_resolver

    settings = get_settings()

    # Get current state
    messages = state.get("messages", [])
    compact_count = state.get("compact_count", 0)
    last_compact_strategy = state.get("last_compact_strategy")

    # Determine strategy
    if strategy == "auto":
        # Use cycle to decide: every Nth compact, use summarize
        cycle = settings.context.summarize_cycle
        if (compact_count + 1) % cycle == 0:
            actual_strategy = "summarize"
        else:
            actual_strategy = "compact"
    else:
        actual_strategy = strategy

    # Initialize compressor
    compressor = ContextCompressor(settings.context)

    # Estimate compression before actually doing it
    estimate = compressor.estimate_compression_ratio(messages, actual_strategy)

    try:
        # Build model invoker for compression
        # TODO: This is a workaround - ideally we'd pass model_registry and resolver as dependencies
        # For now, rebuild them here (they're lightweight)
        model_configs = {}
        for slot in ["base", "reason", "vision", "code", "chat"]:
            model_id = getattr(settings.models, slot)
            api_key = getattr(settings.models, f"{slot}_api_key", None)
            base_url = getattr(settings.models, f"{slot}_base_url", None)
            model_configs[slot] = {
                "id": model_id,
                "api_key": api_key,
                "base_url": base_url,
            }

        model_registry = ModelRegistry(model_configs)
        model_resolver = build_model_resolver(model_configs)

        async def model_invoker(messages, tools=None):
            """Wrapper for invoke_planner"""
            spec = model_registry.prefer(
                phase="plan",
                require_tools=False,
                need_code=False,
                need_vision=False,
            )
            return await invoke_planner(
                model_registry=model_registry,
                model_resolver=model_resolver,
                tools=tools or [],
                messages=messages,
            )

        # Perform compression
        compressed_messages = await compressor.compress_messages(
            messages=messages,
            strategy=actual_strategy,
            model_invoker=model_invoker,
        )

        # Calculate token savings (estimate)
        original_chars = estimate["original_chars"]
        final_chars = estimate["estimated_final_chars"]
        saved_chars = original_chars - final_chars
        compression_ratio = estimate["compression_ratio"]

        # Build success message
        success_msg = f"""✅ 上下文压缩成功

策略: {actual_strategy}
消息数: {estimate['messages_before']} → {len(compressed_messages)}
预估大小: {original_chars:,} → {final_chars:,} 字符
压缩率: {compression_ratio:.1%}
节省: ~{saved_chars:,} 字符

压缩后的历史已更新，可以继续对话。"""

        # Update state
        return Command(
            update={
                "messages": compressed_messages,  # Replace entire message history
                "compact_count": compact_count + 1,
                "last_compact_strategy": actual_strategy,
                # Reset token counters (since we're starting fresh)
                "cumulative_prompt_tokens": 0,
                "cumulative_completion_tokens": 0,
                "last_prompt_tokens": 0,
            },
            # Note: No additional ToolMessage needed - the update is self-describing
        )

    except Exception as e:
        # Compression failed
        error_msg = f"""❌ 上下文压缩失败

错误: {str(e)}

建议:
1. 检查模型配置是否正确
2. 尝试使用 "summarize" 策略（更激进的压缩）
3. 如果问题持续，请联系管理员"""

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=error_msg,
                        tool_call_id="compact_context_error",
                    )
                ]
            }
        )
