"""Finalize node that produces a closing assistant response - Charlie MVP Edition."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

from generalAgent.agents import ModelResolver, invoke_planner
from generalAgent.graph.message_utils import clean_message_history, truncate_messages_safely
from generalAgent.graph.prompts import FINALIZE_SYSTEM_PROMPT, get_current_datetime_tag
from generalAgent.graph.state import AppState
from generalAgent.models import ModelRegistry
from generalAgent.utils.logging_utils import (
    log_node_entry,
    log_node_exit,
    log_prompt,
)
from generalAgent.utils.error_handler import with_error_boundary, handle_model_error, ModelInvocationError

LOGGER = logging.getLogger("agentgraph.finalize")


def build_finalize_node(
    *,
    model_registry: ModelRegistry,
    model_resolver: ModelResolver,
    settings,
):
    max_message_history = settings.governance.max_message_history

    # ========== Build static finalize prompt (with fixed datetime) ==========
    # Generate datetime tag once at initialization (minute precision)
    now = datetime.now(timezone.utc)
    static_datetime_tag = f"<current_datetime>{now.strftime('%Y-%m-%d %H:%M UTC')}</current_datetime>"

    # Datetime tag is placed at the bottom
    static_finalize_prompt = f"{FINALIZE_SYSTEM_PROMPT}\n\n{static_datetime_tag}"

    LOGGER.info(f"Built static finalize prompt with datetime: {static_datetime_tag}")

    @with_error_boundary("finalize")
    async def finalize_node(state: AppState) -> AppState:
        log_node_entry(LOGGER, "finalize", state)

        history: List[BaseMessage] = list(state.get("messages") or [])

        # Skip finalize if no messages or last message is not a tool result
        if not history:
            LOGGER.info("No messages in history, skipping finalize")
            return {}

        if not isinstance(history[-1], ToolMessage):
            LOGGER.info(f"Last message is not a tool result (type={type(history[-1]).__name__}), skipping finalize")
            return {}

        LOGGER.info(f"Generating final response (last tool: {history[-1].name})...")

        # Clean and safely truncate message history (configurable via MAX_MESSAGE_HISTORY)
        cleaned_history = clean_message_history(history)
        recent_history = truncate_messages_safely(cleaned_history, keep_recent=max_message_history)
        LOGGER.info(f"  - Message history: {len(history)} → {len(cleaned_history)} (cleaned) → {len(recent_history)} (kept)")

        # Use static finalize prompt (datetime is already at the bottom)
        finalize_prompt = static_finalize_prompt

        # Log the finalize prompt with truncation
        log_prompt(LOGGER, "finalize", finalize_prompt, max_length=500)

        prompt_messages = [
            SystemMessage(content=finalize_prompt),
            *recent_history
        ]

        LOGGER.info("Invoking finalize LLM (no tools)...")

        try:
            output = await invoke_planner(
                model_registry=model_registry,
                model_resolver=model_resolver,
                tools=[],  # No tools in finalize stage
                messages=prompt_messages,
                need_code=False,
                need_vision=False,
                preference=state.get("model_pref"),
            )
        except Exception as e:
            LOGGER.error(f"Finalize model invocation failed: {e}")
            error_msg = handle_model_error(e)
            raise ModelInvocationError(str(e), user_message=error_msg)

        LOGGER.info("Finalize completed, returning final response")
        updates = {"messages": [output]}
        log_node_exit(LOGGER, "finalize", updates)
        return updates

    return finalize_node
