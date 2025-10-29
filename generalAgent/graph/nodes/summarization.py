"""Summarization node for automatic context compression."""

from __future__ import annotations

import logging
from typing import List

from langchain_core.messages import BaseMessage, RemoveMessage, SystemMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from generalAgent.context.manager import ContextManager
from generalAgent.context.token_tracker import TokenTracker
from generalAgent.graph.state import AppState
from generalAgent.utils.logging_utils import log_node_entry, log_node_exit
from generalAgent.utils.error_handler import with_error_boundary

LOGGER = logging.getLogger("agentgraph.summarization")


def build_summarization_node(*, settings):
    """Build the summarization node for automatic context compression.

    This node is triggered when token usage exceeds 95% of context window.
    After compression, execution automatically returns to agent node.
    """

    @with_error_boundary("summarization")
    async def summarization_node(state: AppState) -> dict:
        """Compress conversation history when token usage is critical.

        This node:
        1. Compresses the message history using LLM summarization
        2. Resets token counters
        3. Adds a notification message
        4. Returns to agent node for continued execution
        """
        log_node_entry(LOGGER, "summarization", state)

        # Check if context management is enabled
        if not settings.context.enabled:
            LOGGER.warning("Context management disabled, skipping summarization")
            return {}

        # Check if already compressed in this request
        auto_compressed = state.get("auto_compressed_this_request", False)
        if auto_compressed:
            LOGGER.info("Already auto-compressed in this request, skipping")
            return {}

        # Get current state
        messages: List[BaseMessage] = list(state.get("messages", []))
        compact_count = state.get("compact_count", 0)
        cumulative_prompt_tokens = state.get("cumulative_prompt_tokens", 0)

        LOGGER.info(f"Starting auto-compression:")
        LOGGER.info(f"  - Current messages: {len(messages)}")
        LOGGER.info(f"  - Cumulative tokens: {cumulative_prompt_tokens:,}")
        LOGGER.info(f"  - Compact count: {compact_count}")

        # Check if there are enough messages to compress
        min_messages = settings.context.min_messages_to_compress
        if len(messages) < min_messages:
            LOGGER.warning(f"Not enough messages to compress (< {min_messages}), skipping")
            return {
                "auto_compressed_this_request": True,  # Prevent retry
            }

        try:
            # Import compression helper
            from generalAgent.tools.builtin.compact_context import _invoke_model_for_compression

            # Initialize context manager
            context_manager = ContextManager(settings)
            tracker = TokenTracker(settings)

            # Get context window for the model
            model_id = settings.models.base
            context_window = tracker.get_context_window(model_id)

            # Execute compression
            LOGGER.info("Executing LLM-based compression...")
            result = await context_manager.compress_context(
                messages=messages,
                model_invoker=_invoke_model_for_compression,
                context_window=context_window
            )

            LOGGER.info(f"Compression successful:")
            LOGGER.info(f"  - Messages: {result.before_count} → {result.after_count}")
            LOGGER.info(f"  - Compression ratio: {result.compression_ratio:.1%}")
            LOGGER.info(f"  - Strategy: {result.strategy}")

            # Return compressed state (no user notification)
            updates = {
                "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + result.messages,
                "compact_count": compact_count + 1,
                "last_compact_strategy": result.strategy,
                "last_compression_ratio": result.compression_ratio,
                "cumulative_prompt_tokens": 0,  # Reset token counter
                "cumulative_completion_tokens": 0,
                "auto_compressed_this_request": True,  # Prevent duplicate compression
                "needs_compression": False,  # Clear the flag
                "new_uploaded_files": [],  # Clear reminders
                "new_mentioned_agents": [],
            }

            log_node_exit(LOGGER, "summarization", updates)
            return updates

        except Exception as e:
            LOGGER.error(f"Compression failed: {e}", exc_info=True)

            # Emergency fallback: truncate to last 100 messages
            LOGGER.warning("Falling back to emergency truncation (last 100 messages)")

            # Keep system messages and last 100 messages
            system_messages = [m for m in messages if m.type == "system"]
            recent_messages = [m for m in messages if m.type != "system"][-100:]

            truncated = system_messages + recent_messages

            updates = {
                "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + truncated,
                "compact_count": compact_count + 1,
                "cumulative_prompt_tokens": 0,
                "cumulative_completion_tokens": 0,
                "auto_compressed_this_request": True,
                "needs_compression": False,  # Clear the flag
            }

            log_node_exit(LOGGER, "summarization", updates)
            return updates

    return summarization_node
