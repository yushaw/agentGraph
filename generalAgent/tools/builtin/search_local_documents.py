"""Search documents in local Windows document database (360 FastFind)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, List, Optional

from langchain_core.tools import tool

LOGGER = logging.getLogger(__name__)

__all__ = ["search_local_documents"]

# Default database path on Windows
DEFAULT_DB_PATH = r"C:\ProgramData\360safe\FastFind\documents.db"


@tool
def search_local_documents(
    query: Annotated[str, "Search keywords (supports FTS5 syntax: AND, OR, NOT, phrases)"],
    file_types: Annotated[Optional[List[str]], "Filter by file extensions, e.g. ['pdf', 'docx', 'txt']"] = None,
    days: Annotated[Optional[int], "Only search files modified within last N days"] = None,
    limit: Annotated[int, "Maximum number of results to return"] = 8,
) -> str:
    """Search local documents using Windows document database.

    This tool searches the local document index database (360 FastFind) using FTS5 full-text search.

    Query Syntax (FTS5):
    - Simple: "报告" (matches documents containing 报告)
    - Phrase: '"年度报告"' (exact phrase match)
    - Boolean: "预算 AND 2024", "销售 OR 营销", "报告 NOT 草稿"
    - Prefix: "财务*" (matches 财务报表, 财务分析, etc.)

    Examples:
        search_local_documents("项目方案")
        search_local_documents("合同", file_types=["pdf", "docx"])
        search_local_documents("会议纪要", days=30)
        search_local_documents("预算 AND 2024", file_types=["xlsx"], limit=5)
    """
    try:
        db_path = Path(DEFAULT_DB_PATH)

        if not db_path.exists():
            return f"Error: Document database not found at {DEFAULT_DB_PATH}"

        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query using FTS5 search
        # documents_search is the FTS5 virtual table
        params = []

        # Base FTS5 query with snippet
        # snippet(table, column_index, before, after, ellipsis, max_tokens)
        # filecontent is column index 8 in the FTS table
        base_sql = """
            SELECT
                d.filename,
                d.filename as filepath,
                snippet(documents_search, 8, '<b>', '</b>', '...', 32) as snippet,
                d.modifytime,
                d.filesize,
                d.filetype
            FROM documents_search
            JOIN documents d ON documents_search.rowid = d.rowid
            WHERE documents_search MATCH ?
        """
        params.append(query)

        # Add file type filter
        if file_types:
            placeholders = ",".join("?" * len(file_types))
            # Normalize extensions (remove leading dot if present)
            normalized_types = [ft.lstrip('.').lower() for ft in file_types]
            base_sql += f" AND LOWER(d.filetype) IN ({placeholders})"
            params.extend(normalized_types)

        # Add date filter
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_timestamp = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
            base_sql += " AND d.modifytime >= ?"
            params.append(cutoff_timestamp)

        # Add limit
        base_sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        cursor.execute(base_sql, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return _format_no_results(query, file_types, days)

        return _format_results(query, rows, file_types, days)

    except sqlite3.OperationalError as e:
        error_msg = str(e)
        if "no such table" in error_msg:
            return "Error: FTS5 search table not found. Database may not be properly indexed."
        elif "malformed MATCH" in error_msg:
            return f"Error: Invalid search query syntax. Check FTS5 query format.\nDetails: {error_msg}"
        else:
            LOGGER.error(f"Database error: {e}")
            return f"Error: Database query failed - {error_msg}"
    except Exception as e:
        LOGGER.error(f"Failed to search local documents: {e}")
        return f"Error: {str(e)}"


def _format_no_results(query: str, file_types: Optional[List[str]], days: Optional[int]) -> str:
    """Format response when no results found."""
    lines = [
        f"=== Local Document Search: \"{query}\" ===",
        "No matching documents found.",
        "",
        "💡 Tips:",
        "  - Try different or broader keywords",
        "  - Use fewer filters",
    ]

    if file_types:
        lines.append(f"  - Current filter: {', '.join(file_types)} files only")
    if days:
        lines.append(f"  - Current filter: last {days} days only")

    return "\n".join(lines)


def _format_results(query: str, rows: list, file_types: Optional[List[str]], days: Optional[int]) -> str:
    """Format search results."""
    filter_desc = []
    if file_types:
        filter_desc.append(f"types: {', '.join(file_types)}")
    if days:
        filter_desc.append(f"last {days} days")

    filter_str = f" ({', '.join(filter_desc)})" if filter_desc else ""

    lines = [
        f"=== Local Document Search: \"{query}\"{filter_str} ===",
        f"Found {len(rows)} document(s):",
        ""
    ]

    for i, row in enumerate(rows, 1):
        filename = row["filename"] or "Unknown"
        filepath = row["filepath"] or ""
        snippet = row["snippet"] or ""
        modifytime = row["modifytime"] or ""
        filesize = row["filesize"] or 0
        filetype = row["filetype"] or ""

        # Format file size
        size_str = _format_size(filesize) if filesize else ""

        # Format modification time (show date only)
        date_str = ""
        if modifytime:
            try:
                if isinstance(modifytime, str):
                    date_str = modifytime[:10]  # YYYY-MM-DD
                else:
                    date_str = str(modifytime)[:10]
            except:
                date_str = str(modifytime)

        lines.append(f"{i}. 📄 {filename}")
        lines.append(f"   路径: {filepath}")
        if snippet:
            # Clean up snippet (remove extra whitespace)
            clean_snippet = " ".join(snippet.split())
            lines.append(f"   片段: {clean_snippet}")
        if date_str or size_str:
            meta_parts = []
            if date_str:
                meta_parts.append(f"修改: {date_str}")
            if size_str:
                meta_parts.append(f"大小: {size_str}")
            lines.append(f"   {' | '.join(meta_parts)}")
        lines.append("")

    return "\n".join(lines)


def _format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
