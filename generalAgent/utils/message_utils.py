"""Message formatting utilities."""

from __future__ import annotations

from typing import Any


def _stringify_content(content: Any) -> str:
    """Convert message content to string.

    Handles:
    - List content (multimodal messages)
    - Dict content with "text" field
    - Simple string content

    Args:
        content: Message content (any format)

    Returns:
        String representation
    """
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                pieces.append(str(item["text"]))
            else:
                pieces.append(str(item))
        return "\n".join(pieces)
    return str(content)


__all__ = ["_stringify_content"]
