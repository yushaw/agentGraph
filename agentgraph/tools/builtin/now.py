"""Get current UTC datetime."""

from datetime import datetime, timezone
from langchain_core.tools import tool


@tool
def now() -> str:
    """Return current UTC datetime in ISO format.

    Use this tool to get the current date and time in UTC timezone.
    Useful for timestamps, logging, or time-based operations.

    Returns:
        Current UTC datetime as ISO 8601 string (e.g., "2025-10-23T10:30:00+00:00")

    Example:
        now() -> "2025-10-23T10:30:00.123456+00:00"
    """
    return datetime.now(timezone.utc).isoformat()


__all__ = ["now"]
