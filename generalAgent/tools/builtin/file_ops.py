"""File operation tools with workspace isolation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

LOGGER = logging.getLogger(__name__)

__all__ = ["read_file", "write_file", "list_workspace_files"]


@tool
def read_file(
    path: Annotated[str, "File path relative to workspace root (e.g., 'skills/pdf/SKILL.md' or 'uploads/document.txt')"]
) -> str:
    """Read file from workspace. Path relative to workspace root, NOT absolute.

    Can read: skills/, uploads/, outputs/, temp/
    Returns: UTF-8 text content or error

    NEVER use ".." or "/" prefix (security violation)

    Examples:
        read_file("skills/pdf/SKILL.md")
        read_file("uploads/document.txt")
        read_file("outputs/result.csv")
    """
    try:
        # Security: reject paths with traversal attempts
        if ".." in path or path.startswith("/"):
            return f"Error: Access denied. Invalid path: {path}"

        # Get workspace root from environment or use default
        # In actual execution, this will be injected via RunnableConfig
        import os
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            # Fallback: try to read from project generalAgent/skills/ (for backward compatibility)
            from generalAgent.config.project_root import get_project_root
            project_root = get_project_root()
            target_path = (project_root / path).resolve()

            # Check if trying to read from generalAgent/skills/
            skills_dir = project_root / "generalAgent" / "skills"
            if target_path.is_relative_to(skills_dir):
                if not target_path.exists():
                    return f"Error: File not found: {path}"

                content = target_path.read_text(encoding="utf-8")
                LOGGER.info(f"Read file (project skills): {path} ({len(content)} chars)")
                return content

            return "Error: No workspace configured. Please ensure workspace is initialized."

        workspace_root = Path(workspace_root).resolve()

        # Construct logical path (before resolution)
        logical_path = workspace_root / path

        # Security: ensure the logical path is within workspace (before following symlinks)
        # This allows reading symlinked skills while preventing path traversal
        try:
            logical_path.relative_to(workspace_root)
        except ValueError:
            return f"Error: Access denied. Can only read files within workspace: {path}"

        # Now resolve to get the actual file location (follows symlinks)
        target_path = logical_path.resolve()

        # Check existence
        if not target_path.exists():
            return f"Error: File not found: {path}"

        if not target_path.is_file():
            return f"Error: Not a file: {path}"

        # Read file
        content = target_path.read_text(encoding="utf-8")
        LOGGER.info(f"Read file: {path} ({len(content)} chars)")

        return content

    except UnicodeDecodeError:
        return f"Error: File is not a text file (binary content detected): {path}"
    except Exception as e:
        LOGGER.error(f"Failed to read file {path}: {e}")
        return f"Error: {str(e)}"


@tool
def write_file(
    path: Annotated[str, "File path relative to workspace (e.g., 'outputs/result.txt', 'temp/data.json')"],
    content: Annotated[str, "File content to write"]
) -> str:
    """Write/overwrite file in workspace. Creates parent dirs automatically.

    Can ONLY write to: uploads/, outputs/, temp/ (NOT skills/)
    NEVER use ".." or "/" prefix

    Use outputs/ for permanent results, temp/ for temporary files

    Examples:
        write_file("outputs/analysis.txt", "Analysis: 42 issues")
        write_file("temp/data.json", '{"users": 100}')
    """
    try:
        # Security: reject paths with traversal attempts
        if ".." in path or path.startswith("/"):
            return f"Error: Access denied. Invalid path: {path}"

        # Get workspace root
        import os
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured. Cannot write files."

        workspace_root = Path(workspace_root).resolve()

        # Construct logical path (before resolution)
        logical_path = workspace_root / path

        # Security: ensure the logical path is within workspace (before following symlinks)
        try:
            relative_path = logical_path.relative_to(workspace_root)
        except ValueError:
            return f"Error: Access denied. Can only write files within workspace: {path}"

        # Additional security: only allow writing to specific subdirectories
        allowed_dirs = ["uploads", "outputs", "temp"]

        # Check if path starts with an allowed directory
        if not any(relative_path.parts[0] == allowed_dir for allowed_dir in allowed_dirs):
            return f"Error: Can only write to {', '.join(allowed_dirs)}/ directories. Got: {path}"

        # Resolve to actual path (now that we've validated the logical path)
        target_path = logical_path.resolve()

        # Create parent directories
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        target_path.write_text(content, encoding="utf-8")

        file_size = len(content)
        LOGGER.info(f"Wrote file: {path} ({file_size} chars)")

        return f"Success: File written to {path} ({file_size} bytes)"

    except Exception as e:
        LOGGER.error(f"Failed to write file {path}: {e}")
        return f"Error: {str(e)}"


@tool
def list_workspace_files(
    directory: Annotated[str, "Directory to list (e.g., 'uploads', 'outputs', 'skills/pdf')"] = "."
) -> str:
    """List files/directories in workspace. Returns [DIR]/[FILE] indicators.

    Use "." for workspace root. NEVER use ".." or "/" prefix

    Examples:
        list_workspace_files(".")
        list_workspace_files("uploads")
        list_workspace_files("skills/pdf")
    """
    try:
        # Security: reject paths with traversal attempts
        if ".." in directory or directory.startswith("/"):
            return f"Error: Access denied. Invalid path: {directory}"

        import os
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured."

        workspace_root = Path(workspace_root).resolve()

        # Construct logical path (before resolution)
        if directory == ".":
            logical_dir = workspace_root
        else:
            logical_dir = workspace_root / directory

        # Security check: ensure logical path is within workspace (before following symlinks)
        if directory != ".":
            try:
                logical_dir.relative_to(workspace_root)
            except ValueError:
                return f"Error: Access denied: {directory}"

        # Check if directory exists (use logical path, not resolved)
        if not logical_dir.exists():
            return f"Error: Directory not found: {directory}"

        if not logical_dir.is_dir():
            return f"Error: Not a directory: {directory}"

        # List contents - use logical_dir (not resolved) to preserve symlinks
        items = []
        for item in sorted(logical_dir.iterdir()):
            # Skip hidden files like .metadata.json
            if item.name.startswith('.'):
                continue
            # Calculate relative path from logical path (before resolution)
            try:
                relative = item.relative_to(workspace_root)
            except ValueError:
                # If relative_to fails, construct path manually
                if directory == ".":
                    relative = Path(item.name)
                else:
                    relative = Path(directory) / item.name

            if item.is_dir():
                items.append(f"📁 {relative}/")
            else:
                size = item.stat().st_size
                items.append(f"📄 {relative} ({size} bytes)")

        if not items:
            return f"Directory is empty: {directory}"

        result = f"Contents of {directory}:\n" + "\n".join(items)
        LOGGER.info(f"Listed directory: {directory} ({len(items)} items)")

        return result

    except Exception as e:
        LOGGER.error(f"Failed to list directory {directory}: {e}")
        return f"Error: {str(e)}"
