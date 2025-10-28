"""File operation tools with workspace isolation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from generalAgent.config.settings import get_settings
from generalAgent.utils.document_extractors import (
    DOCUMENT_EXTENSIONS,
    get_document_info,
    extract_preview,
    extract_full_document
)

LOGGER = logging.getLogger(__name__)

__all__ = ["read_file", "write_file", "list_workspace_files"]

# Text file extensions
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".jsx", ".tsx",
                   ".csv", ".log", ".sh", ".bash", ".xml", ".html", ".css", ".sql", ".ini", ".conf"}


@tool
def read_file(
    path: Annotated[str, "File path relative to workspace root"]
) -> str:
    """Read file from workspace (supports text files and documents).

    Supports:
    - Text files (<100KB): Returns full content
    - Text files (>100KB): Returns first 50K chars with truncation notice
    - Documents (PDF/DOCX/XLSX/PPTX): Extracts preview
      - PDF/DOCX: First 10 pages (~30K chars)
      - XLSX: First 3 sheets (~20K chars)
      - PPTX: First 15 slides (~25K chars)

    For large files or finding specific content, use search_file() tool instead.

    NEVER use ".." or "/" prefix (security violation)

    Examples:
        read_file("uploads/summary.txt")
        read_file("uploads/report.pdf")
        read_file("skills/pdf/SKILL.md")
    """
    try:
        # Security: reject paths with traversal attempts
        if ".." in path or path.startswith("/"):
            return f"Error: Access denied. Invalid path: {path}"

        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            # Fallback: try to read from project generalAgent/skills/
            from generalAgent.config.project_root import get_project_root
            project_root = get_project_root()
            target_path = (project_root / path).resolve()

            skills_dir = project_root / "generalAgent" / "skills"
            if target_path.is_relative_to(skills_dir):
                if not target_path.exists():
                    return f"Error: File not found: {path}"

                content = target_path.read_text(encoding="utf-8")
                LOGGER.info(f"Read file (project skills): {path} ({len(content)} chars)")
                return content

            return "Error: No workspace configured. Please ensure workspace is initialized."

        workspace_root = Path(workspace_root).resolve()
        logical_path = workspace_root / path

        # Security check
        try:
            logical_path.relative_to(workspace_root)
        except ValueError:
            return f"Error: Access denied. Can only read files within workspace: {path}"

        target_path = logical_path.resolve()

        if not target_path.exists():
            return f"Error: File not found: {path}"

        if not target_path.is_file():
            return f"Error: Not a file: {path}"

        # Get file info
        file_ext = target_path.suffix.lower()
        file_size = target_path.stat().st_size
        settings = get_settings()

        # Strategy 1: Text files
        if file_ext in TEXT_EXTENSIONS:
            # Small text file: read full content
            if file_size < settings.documents.text_file_max_size:
                content = target_path.read_text(encoding="utf-8")
                LOGGER.info(f"Read text file: {path} ({len(content)} chars)")
                return f"=== {path} ===\n{content}"

            # Large text file: read preview
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read(settings.documents.text_preview_chars)

            LOGGER.info(f"Read text file preview: {path} ({len(content)} chars)")
            return (
                f"=== {path} (Preview: first {settings.documents.text_preview_chars:,} chars) ===\n"
                f"{content}\n\n"
                f"⚠️ File truncated (total size: {file_size:,} bytes)\n"
                f"💡 Use search_file(\"{path}\", \"keyword\") to find specific content"
            )

        # Strategy 2: Document files
        if file_ext in DOCUMENT_EXTENSIONS:
            doc_info = get_document_info(target_path)

            # Determine preview limits based on file type
            if file_ext == ".pdf":
                max_pages = settings.documents.pdf_preview_pages
                max_chars = settings.documents.pdf_preview_chars
            elif file_ext == ".docx":
                max_pages = settings.documents.docx_preview_pages
                max_chars = settings.documents.docx_preview_chars
            elif file_ext == ".xlsx":
                max_pages = settings.documents.xlsx_preview_sheets
                max_chars = settings.documents.xlsx_preview_chars
            elif file_ext == ".pptx":
                max_pages = settings.documents.pptx_preview_slides
                max_chars = settings.documents.pptx_preview_chars
            else:
                max_pages = 10
                max_chars = 30000

            # Extract preview (respects configured limits)
            preview = extract_preview(target_path, max_pages, max_chars)
            LOGGER.info(f"Extracted document preview: {path} ({len(preview)} chars)")

            # Limit display to 100 characters
            display_preview = preview[:100] + "..." if len(preview) > 100 else preview

            unit = "pages" if file_ext in [".pdf", ".docx"] else "sheets" if file_ext == ".xlsx" else "slides"
            return (
                f"=== {path} ({doc_info['pages']} {unit}) ===\n"
                f"{display_preview}\n\n"
                f"💡 Use search_file(\"{path}\", \"keyword\") to find specific content"
            )

        # Unsupported file type
        return f"Error: Unsupported file type: {file_ext}"

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
    """Writes a file to the local filesystem.

    Usage:
    - This tool will overwrite the existing file if there is one at the provided path
    - If this is an existing file, you MUST use read_file first. Tool will fail if you did not read first
    - ALWAYS prefer edit_file for existing files. NEVER write new files unless explicitly required
    - NEVER proactively create documentation files (*.md, README). Only create if user explicitly requests
    - LONG content (>1000 words): Write outline with [TBD] markers → edit_file to expand sections

    Security:
    - Can ONLY write to: uploads/, outputs/, temp/ (NOT skills/)
    - NEVER use ".." or "/" prefix

    Examples:
        # Create new file with outline
        write_file("outputs/plan.md", "# Plan\n\n## Phase 1\n[TBD]\n\n## Phase 2\n[TBD]")

        # Then expand with edit_file
        edit_file("outputs/plan.md", "[TBD]", "- Task 1\n- Task 2")
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
