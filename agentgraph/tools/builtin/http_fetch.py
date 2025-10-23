"""HTTP fetching tool (stub implementation)."""

import json
from langchain_core.tools import tool


@tool
def http_fetch(url: str) -> str:
    """Fetch an HTML page (stub implementation).

    NOTE: This is a placeholder implementation that returns demo HTML.
    In production, this should use actual HTTP client like requests or httpx.

    Args:
        url: URL to fetch

    Returns:
        JSON with URL and HTML content

    Example:
        http_fetch("https://example.com") -> {
            "url": "https://example.com",
            "html": "<html><body>demo</body></html>"
        }

    TODO: Implement actual HTTP fetching
    """
    return json.dumps({"url": url, "html": "<html><body>demo</body></html>"}, ensure_ascii=False)


__all__ = ["http_fetch"]
