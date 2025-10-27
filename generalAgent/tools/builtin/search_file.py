"""Search for content within files (text and documents)."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Annotated, List, Dict

from langchain_core.tools import tool

from generalAgent.config.settings import get_settings
from generalAgent.utils.document_extractors import DOCUMENT_EXTENSIONS
from generalAgent.utils.text_indexer import (
    index_exists,
    create_index,
    search_in_index
)

LOGGER = logging.getLogger(__name__)

__all__ = ["search_file"]

# Text file extensions (same as file_ops.py)
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".jsx", ".tsx",
                   ".csv", ".log", ".sh", ".bash", ".xml", ".html", ".css", ".sql", ".ini", ".conf"}


@tool
def search_file(
    path: Annotated[str, "File path relative to workspace"],
    query: Annotated[str, "Search keywords or phrase"],
    max_results: Annotated[int, "Maximum results to return"] = 5
) -> str:
    """Search for content in a file (supports text files and documents).

    Automatically creates a searchable index on first use (takes 2-5 seconds for
    documents). Subsequent searches are instant (<100ms).

    Search strategies:
    - Text files: Line-by-line keyword matching with context
    - Documents (PDF/DOCX/XLSX/PPTX): Chunk-based multi-strategy matching

    Args:
        path: File path relative to workspace (e.g., "uploads/report.pdf")
        query: Search keywords or phrase
               "Q3 revenue"       : Find exact phrase
               "revenue growth"   : Find keywords
        max_results: Maximum results to return (default: 5)

    Returns:
        Matching sections with context (line/page numbers, surrounding text)

    Examples:
        search_file("uploads/error.log", "ERROR")
        search_file("uploads/report.pdf", "Q3 revenue growth")
        search_file("uploads/data.xlsx", "customer churn", max_results=3)

    Note: First search on a document creates an index (2-5s), subsequent
          searches are fast. Index is cached globally by file content (MD5).
    """
    try:
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured."

        # Security check
        if ".." in path or path.startswith("/"):
            return f"Error: Access denied. Invalid path: {path}"

        workspace_root = Path(workspace_root).resolve()
        file_path = workspace_root / path

        # Validate path is within workspace
        try:
            file_path.relative_to(workspace_root)
        except ValueError:
            return f"Error: Access denied: {path}"

        if not file_path.exists():
            return f"Error: File not found: {path}"

        if not file_path.is_file():
            return f"Error: Not a file: {path}"

        file_ext = file_path.suffix.lower()

        # Route to appropriate search strategy
        if file_ext in TEXT_EXTENSIONS:
            return _search_text_file(file_path, query, max_results)
        elif file_ext in DOCUMENT_EXTENSIONS:
            return _search_document_file(file_path, query, max_results)
        else:
            return f"Error: Search not supported for {file_ext} files"

    except Exception as e:
        LOGGER.error(f"Failed to search file {path}: {e}")
        return f"Error: {str(e)}"


def _search_text_file(file_path: Path, query: str, max_results: int) -> str:
    """Search in text file (real-time line scanning, no index)"""

    query_lower = query.lower()
    results = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error: Failed to read file - {str(e)}"

    # Scan line by line
    for line_num, line in enumerate(lines, 1):
        if query_lower in line.lower():
            # Extract context (1 line before and after)
            context_before = lines[line_num - 2].rstrip() if line_num > 1 else ""
            context_after = lines[line_num].rstrip() if line_num < len(lines) else ""

            results.append({
                "line": line_num,
                "content": line.rstrip(),
                "context_before": context_before,
                "context_after": context_after
            })

            if len(results) >= max_results:
                break

    if not results:
        return (
            f"=== {file_path.name} (Search: \"{query}\") ===\n"
            f"No matches found.\n\n"
            f"💡 Tip: Search is case-insensitive. Try different keywords."
        )

    # Format output
    lines_output = [
        f"=== {file_path.name} (Search: \"{query}\") ===",
        f"Found {len(results)} match(es):\n"
    ]

    for result in results:
        lines_output.append(f"--- Line {result['line']} ---")

        # Show context before
        if result['context_before']:
            lines_output.append(f"  {result['context_before']}")

        # Highlight matching line
        highlighted = _highlight_text(result['content'], query)
        lines_output.append(f"> {highlighted}")  # > indicates matching line

        # Show context after
        if result['context_after']:
            lines_output.append(f"  {result['context_after']}")

        lines_output.append("")  # Empty line separator

    LOGGER.info(f"Text search in {file_path.name}: {len(results)} matches")

    return "\n".join(lines_output)


def _search_document_file(file_path: Path, query: str, max_results: int) -> str:
    """Search in document file (index-based search)"""

    # Check if index exists
    if not index_exists(file_path):
        # First-time search: create index
        try:
            LOGGER.info(f"First search on {file_path.name}, creating index...")
            create_index(file_path)
        except Exception as e:
            LOGGER.error(f"Failed to create index for {file_path.name}: {e}")
            return (
                f"Error: Failed to index document - {str(e)}\n\n"
                f"💡 Try using read_file(\"{file_path.name}\") to view content directly"
            )

    # Execute search
    try:
        results = search_in_index(file_path, query, max_results)
    except Exception as e:
        LOGGER.error(f"Failed to search index for {file_path.name}: {e}")
        return f"Error: Search failed - {str(e)}"

    if not results:
        return (
            f"=== {file_path.name} (Search: \"{query}\") ===\n"
            f"No matches found.\n\n"
            f"💡 Tips:\n"
            f"  - Try different keywords\n"
            f"  - Use more general terms\n"
            f"  - Check spelling"
        )

    # Format output
    lines_output = [
        f"=== {file_path.name} (Search: \"{query}\") ===",
        f"Found {len(results)} relevant section(s):\n"
    ]

    for i, result in enumerate(results, 1):
        lines_output.append(f"--- Page {result['page']} (Relevance: {result['score']:.1f}) ---")

        # Highlight query in text
        highlighted_text = _highlight_text(result['text'], query)

        # Limit text length for display
        if len(highlighted_text) > 500:
            highlighted_text = highlighted_text[:500] + "..."

        lines_output.append(highlighted_text)

        # Show matched keywords (max 5)
        matched_kw = ", ".join(result['matched_keywords'][:5])
        lines_output.append(f"[Matched: {matched_kw}]")
        lines_output.append("")  # Empty line separator

    LOGGER.info(f"Document search in {file_path.name}: {len(results)} matches")

    return "\n".join(lines_output)


def _highlight_text(text: str, query: str) -> str:
    """Highlight query text in content (using ** for bold)"""
    try:
        # Case-insensitive highlighting
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return pattern.sub(lambda m: f"**{m.group()}**", text)
    except:
        # If regex fails, return original text
        return text
