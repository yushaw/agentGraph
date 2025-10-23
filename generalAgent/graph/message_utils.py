"""Utilities for cleaning and processing message histories."""

from __future__ import annotations

from typing import List, Set

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, HumanMessage, SystemMessage


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


def truncate_messages_safely(messages: List[BaseMessage], keep_recent: int = 10) -> List[BaseMessage]:
    """Safely truncate message history while preserving AIMessage-ToolMessage pairs.

    This function ensures that:
    1. If we keep a ToolMessage, we also keep its corresponding AIMessage
    2. We don't break the tool_call_id chain
    3. We keep system messages and recent user messages for context

    Args:
        messages: List of conversation messages
        keep_recent: Number of recent messages to attempt to keep

    Returns:
        Truncated message list that's safe for OpenAI API
    """
    if len(messages) <= keep_recent:
        return messages

    # First, identify AIMessage -> ToolMessage pairs
    tool_call_pairs = {}  # tool_call_id -> (ai_msg_index, tool_msg_index)

    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if tc_id:
                    tool_call_pairs[tc_id] = {"ai_idx": i, "tool_idx": None}

        elif isinstance(msg, ToolMessage):
            call_id = getattr(msg, "tool_call_id", None)
            if call_id and call_id in tool_call_pairs:
                tool_call_pairs[call_id]["tool_idx"] = i

    # Find the cutoff point (keep last keep_recent messages)
    cutoff_idx = len(messages) - keep_recent

    # Find all indices we must keep
    must_keep_indices = set()

    for i in range(cutoff_idx, len(messages)):
        must_keep_indices.add(i)

        # If this is a ToolMessage, include its AIMessage
        msg = messages[i]
        if isinstance(msg, ToolMessage):
            call_id = getattr(msg, "tool_call_id", None)
            if call_id and call_id in tool_call_pairs:
                ai_idx = tool_call_pairs[call_id].get("ai_idx")
                if ai_idx is not None:
                    must_keep_indices.add(ai_idx)

    # Also keep all SystemMessages (they're usually important)
    for i, msg in enumerate(messages):
        if isinstance(msg, SystemMessage):
            must_keep_indices.add(i)

    # Build result preserving order
    result = []
    for i in sorted(must_keep_indices):
        result.append(messages[i])

    return result
