"""Find files by name pattern (glob-based file search)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

LOGGER = logging.getLogger(__name__)

__all__ = ["find_files"]


@tool
def find_files(
    pattern: Annotated[str, "Glob pattern (e.g., '*.pdf', '**/*.py', '*report*')"],
    path: Annotated[str, "Directory to search (default: workspace root)"] = "."
) -> str:
    """Find files by name pattern (fast, doesn't read file content).

    Uses glob patterns to match filenames. Much faster than search_file()
    because it only checks filenames, not file contents.

    Pattern syntax:
    - "*" matches anything
    - "?" matches any single character
    - "**" matches directories recursively
    - "[abc]" matches any character in brackets
    - "{pdf,docx}" matches either extension

    Args:
        pattern: Glob pattern
                 "*.pdf"       : All PDFs in directory
                 "**/*.py"     : All Python files recursively
                 "*report*"    : Files with "report" in name
                 "*.{pdf,docx}": PDFs and DOCXs
        path: Directory to search (default: "." for workspace root)
              Use "." for root, "uploads" for uploads/ folder

    Returns:
        List of matching files with sizes and modification times

    Examples:
        find_files("*.pdf")                      # All PDFs
        find_files("**/*test*.py")               # All test files recursively
        find_files("*report*", path="uploads")   # Reports in uploads/
        find_files("*.{pdf,docx}")               # PDFs and DOCXs

    Note: This tool does NOT read file contents. To search within files,
          use search_file() instead.
    """
    try:
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured."

        workspace_root = Path(workspace_root).resolve()

        # Resolve search path
        if path == ".":
            search_path = workspace_root
        else:
            # Security check
            if ".." in path or path.startswith("/"):
                return f"Error: Access denied. Invalid path: {path}"

            search_path = workspace_root / path

            # Ensure search path is within workspace
            try:
                search_path.relative_to(workspace_root)
            except ValueError:
                return f"Error: Access denied: {path}"

        if not search_path.exists():
            return f"Error: Directory not found: {path}"

        if not search_path.is_dir():
            return f"Error: Not a directory: {path}"

        # Execute glob search
        matches = list(search_path.glob(pattern))

        # Filter results:
        # 1. Only files (not directories)
        # 2. Exclude hidden files/directories
        # 3. Exclude index directory
        filtered_matches = []
        for m in matches:
            # Must be a file
            if not m.is_file():
                continue

            # No hidden files/directories in path
            if any(p.startswith('.') for p in m.parts):
                continue

            # No index directory
            if '.indexes' in m.parts:
                continue

            filtered_matches.append(m)

        if not filtered_matches:
            return (
                f"No files found matching pattern: {pattern}\n\n"
                f"💡 Tips:\n"
                f"  - Use * for wildcards: *.pdf\n"
                f"  - Use ** for recursive search: **/*.py\n"
                f"  - Use {{}} for multiple extensions: *.{{pdf,docx}}\n"
                f"  - Check if directory exists: {path}"
            )

        # Sort by modification time (newest first)
        filtered_matches.sort(key=lambda m: m.stat().st_mtime, reverse=True)

        # Format output
        lines = [f"Found {len(filtered_matches)} file(s) matching '{pattern}':\n"]

        for m in filtered_matches:
            # Get relative path from workspace
            rel_path = m.relative_to(workspace_root)

            # Get file size (human-readable)
            size = m.stat().st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f}KB"
            else:
                size_str = f"{size/1024/1024:.1f}MB"

            lines.append(f"  📄 {rel_path} ({size_str})")

        LOGGER.info(f"Found {len(filtered_matches)} files matching '{pattern}' in {path}")

        return "\n".join(lines)

    except Exception as e:
        LOGGER.error(f"Failed to find files with pattern '{pattern}': {e}")
        return f"Error: {str(e)}"
