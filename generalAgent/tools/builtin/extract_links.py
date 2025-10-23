"""Link extraction tool."""

import json
from langchain_core.tools import tool


@tool
def extract_links(html: str) -> str:
    """Extract links from HTML content (stub implementation).

    NOTE: This is a placeholder that returns demo data.
    In production, use BeautifulSoup or similar HTML parser.

    Args:
        html: HTML content to parse

    Returns:
        JSON with array of extracted links

    Example:
        extract_links("<html>...</html>") -> {
            "links": ["https://example.com/demo"]
        }

    TODO: Implement actual HTML parsing and link extraction
    """
    return json.dumps({"links": ["https://example.com/demo"]}, ensure_ascii=False)


__all__ = ["extract_links"]
