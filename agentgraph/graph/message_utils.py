"""Utilities for cleaning and processing message histories."""

from __future__ import annotations

from typing import List, Set

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


def clean_message_history(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Remove AI messages with unanswered tool_calls to fix OpenAI API validation.

    OpenAI requires that every AI message with tool_calls must be followed by
    corresponding ToolMessages. This function removes AI messages whose tool_calls
    were never answered.

    Args:
        messages: List of conversation messages

    Returns:
        Cleaned list with unanswered tool_calls removed
    """
    # First pass: collect all tool_call_ids that have responses
    answered_call_ids: Set[str] = set()
    for msg in messages:
        if isinstance(msg, ToolMessage):
            # ToolMessage.tool_call_id contains the id being responded to
            call_id = getattr(msg, "tool_call_id", None)
            if call_id:
                answered_call_ids.add(call_id)

    # Second pass: filter out AI messages with unanswered tool_calls
    cleaned: List[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                # Check if all tool_calls have responses
                unanswered = []
                for tc in tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id and tc_id not in answered_call_ids:
                        unanswered.append(tc_id)

                if unanswered:
                    # Skip this AI message - it has unanswered tool_calls
                    continue

        cleaned.append(msg)

    return cleaned
