"""Edit file tool for precise string replacements."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

LOGGER = logging.getLogger(__name__)

__all__ = ["edit_file"]


@tool
def edit_file(
    path: Annotated[str, "File path relative to workspace root"],
    old_string: Annotated[str, "The exact text to replace"],
    new_string: Annotated[str, "The text to replace it with"],
    replace_all: Annotated[bool, "Replace all occurrences (default: False)"] = False
) -> str:
    """Exact string replacement in files. Safer than write_file for targeted edits.

    MUST use read_file first to see contents
    old_string must match EXACTLY (whitespace, indentation)
    Can only edit: outputs/, temp/, uploads/ (NOT skills/)

    NEVER:
    - Include line numbers from read_file in old_string/new_string
    - Use ".." or "/" prefix in path

    Fails if old_string not found or not unique (unless replace_all=True)

    Examples:
        read_file("outputs/config.txt")
        edit_file("outputs/config.txt", "port = 8080", "port = 3000")

        edit_file("outputs/data.txt", "foo", "bar", replace_all=True)
    """
    try:
        # Validation
        if old_string == new_string:
            return "Error: old_string and new_string must be different"

        # Security: reject paths with traversal attempts
        if ".." in path or path.startswith("/"):
            return f"Error: Access denied. Invalid path: {path}"

        # Get workspace root
        import os
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured. Cannot edit files."

        workspace_root = Path(workspace_root).resolve()

        # Construct logical path
        logical_path = workspace_root / path

        # Security: ensure within workspace
        try:
            relative_path = logical_path.relative_to(workspace_root)
        except ValueError:
            return f"Error: Access denied. Can only edit files within workspace: {path}"

        # Security: only allow editing writable directories
        allowed_dirs = ["uploads", "outputs", "temp"]
        if not any(relative_path.parts[0] == allowed_dir for allowed_dir in allowed_dirs):
            return f"Error: Can only edit files in {', '.join(allowed_dirs)}/ directories. Got: {path}"

        # Resolve path
        target_path = logical_path.resolve()

        # Check file exists
        if not target_path.exists():
            return f"Error: File not found: {path}"

        if not target_path.is_file():
            return f"Error: Not a file: {path}"

        # Read current content
        content = target_path.read_text(encoding="utf-8")

        # Check if old_string exists
        if old_string not in content:
            return f"Error: String not found in file: {old_string[:100]}..."

        # Count occurrences
        occurrences = content.count(old_string)

        if not replace_all and occurrences > 1:
            return (
                f"Error: Found {occurrences} occurrences of old_string, but replace_all=False. "
                f"Either provide a more unique string or set replace_all=True."
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacements = occurrences
        else:
            new_content = content.replace(old_string, new_string, 1)
            replacements = 1

        # Write back
        target_path.write_text(new_content, encoding="utf-8")

        LOGGER.info(f"Edited file: {path} ({replacements} replacement(s))")

        return f"Success: Replaced {replacements} occurrence(s) in {path}"

    except UnicodeDecodeError:
        return f"Error: File is not a text file (binary content detected): {path}"
    except Exception as e:
        LOGGER.error(f"Failed to edit file {path}: {e}")
        return f"Error: {str(e)}"
