"""Process uploaded files for agent consumption."""

from __future__ import annotations

import base64
import shutil
from pathlib import Path
from typing import Dict, List, Literal, Optional
from dataclasses import dataclass

from .file_upload_parser import format_file_size


FileType = Literal["image", "pdf", "text", "code", "office", "unknown"]


# File size limits (in bytes)
MAX_FILE_SIZE: Dict[FileType, int] = {
    "image": 10 * 1024 * 1024,   # 10MB
    "pdf": 50 * 1024 * 1024,     # 50MB
    "text": 5 * 1024 * 1024,     # 5MB
    "code": 5 * 1024 * 1024,     # 5MB
    "office": 20 * 1024 * 1024,  # 20MB
    "unknown": 10 * 1024 * 1024, # 10MB
}


# Text file size threshold for direct injection (10KB)
TEXT_INJECT_THRESHOLD = 10 * 1024


@dataclass
class ProcessedFile:
    """Result of processing a single file."""

    filename: str
    file_type: FileType
    size_bytes: int
    size_formatted: str
    workspace_path: str  # Relative path in workspace, e.g., "uploads/file.png"

    # For images
    base64_data: Optional[str] = None
    mime_type: Optional[str] = None

    # For text files
    text_content: Optional[str] = None

    # Error info
    error: Optional[str] = None


def classify_file_type(filename: str) -> FileType:
    """Classify file type by extension.

    Args:
        filename: File name with extension

    Returns:
        File type classification
    """
    ext = Path(filename).suffix.lower()

    # Image types
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        return "image"

    # PDF
    if ext == ".pdf":
        return "pdf"

    # Text files
    if ext in {".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log"}:
        return "text"

    # Code files
    if ext in {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".sh"}:
        return "code"

    # Office documents
    if ext in {".docx", ".xlsx", ".pptx"}:
        return "office"

    return "unknown"


def get_image_mime_type(filename: str) -> str:
    """Get MIME type for image file.

    Args:
        filename: Image filename

    Returns:
        MIME type string like "image/png"
    """
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


def process_file(
    filename: str,
    tmp_dir: Path,
    workspace_dir: Path,
) -> ProcessedFile:
    """Process a single uploaded file.

    Args:
        filename: Name of file to process
        tmp_dir: Path to uploads/ directory
        workspace_dir: Path to workspace directory

    Returns:
        ProcessedFile with results or error
    """
    source_path = tmp_dir / filename
    file_type = classify_file_type(filename)

    # Check if file exists
    if not source_path.exists():
        return ProcessedFile(
            filename=filename,
            file_type=file_type,
            size_bytes=0,
            size_formatted="0 B",
            workspace_path="",
            error=f"File not found: {filename}",
        )

    # Get file size
    size_bytes = source_path.stat().st_size
    size_formatted = format_file_size(size_bytes)

    # Check size limit
    max_size = MAX_FILE_SIZE.get(file_type, MAX_FILE_SIZE["unknown"])
    if size_bytes > max_size:
        return ProcessedFile(
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            size_formatted=size_formatted,
            workspace_path="",
            error=f"File too large: {size_formatted} (max: {format_file_size(max_size)})",
        )

    # Process based on type
    dest_path = workspace_dir / "uploads" / filename
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_relative = f"uploads/{filename}"

    try:
        if file_type == "image":
            # Copy to workspace
            shutil.copy2(source_path, dest_path)

            # Also encode as base64 for vision
            with open(source_path, "rb") as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode("utf-8")

            return ProcessedFile(
                filename=filename,
                file_type=file_type,
                size_bytes=size_bytes,
                size_formatted=size_formatted,
                workspace_path=workspace_relative,
                base64_data=base64_data,
                mime_type=get_image_mime_type(filename),
            )

        elif file_type in ("text", "code"):
            # Copy to workspace
            shutil.copy2(source_path, dest_path)

            # If small enough, also read content for injection
            text_content = None
            if size_bytes <= TEXT_INJECT_THRESHOLD:
                with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()

            return ProcessedFile(
                filename=filename,
                file_type=file_type,
                size_bytes=size_bytes,
                size_formatted=size_formatted,
                workspace_path=workspace_relative,
                text_content=text_content,
            )

        else:
            # For pdf, office, unknown: just copy to workspace
            shutil.copy2(source_path, dest_path)

            return ProcessedFile(
                filename=filename,
                file_type=file_type,
                size_bytes=size_bytes,
                size_formatted=size_formatted,
                workspace_path=workspace_relative,
            )

    except Exception as e:
        return ProcessedFile(
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            size_formatted=size_formatted,
            workspace_path="",
            error=f"Failed to process file: {str(e)}",
        )


def build_file_upload_reminder(processed_files: List[ProcessedFile | dict], skill_config=None) -> str:
    """Build system_reminder message for uploaded files.

    Args:
        processed_files: List of successfully processed files (ProcessedFile objects or dicts)
        skill_config: SkillConfig instance for dynamic skill hints (optional)

    Returns:
        Formatted system_reminder XML string
    """
    if not processed_files:
        return ""

    # Helper to get attribute from ProcessedFile or dict
    def get_attr(f, key):
        return f.get(key) if isinstance(f, dict) else getattr(f, key)

    # Separate by type
    images = [f for f in processed_files if get_attr(f, "file_type") == "image" and not get_attr(f, "error")]
    documents = [f for f in processed_files if get_attr(f, "file_type") in ("pdf", "office") and not get_attr(f, "error")]
    texts = [f for f in processed_files if get_attr(f, "file_type") in ("text", "code") and not get_attr(f, "error")]
    others = [f for f in processed_files if get_attr(f, "file_type") == "unknown" and not get_attr(f, "error")]

    lines = []

    # Count
    total = len(images) + len(documents) + len(texts) + len(others)
    if total == 1:
        lines.append(f"用户上传了 1 个文件：")
    else:
        lines.append(f"用户上传了 {total} 个文件：")

    # List files
    file_num = 1
    for file in images:
        lines.append(
            f"{file_num}. {get_attr(file, 'filename')} (图片, {get_attr(file, 'size_formatted')}) → {get_attr(file, 'workspace_path')} [已加载到 vision]"
        )
        file_num += 1

    for file in documents:
        # Dynamic skill hint based on config
        skill_hint = ""
        file_type = get_attr(file, "file_type")

        if skill_config:
            # Extract actual file extension for skill matching
            # (skills.yaml uses specific extensions like "docx", "pptx", not generic "office")
            from pathlib import Path
            filename = get_attr(file, "filename")
            file_ext = Path(filename).suffix.lstrip('.').lower()  # e.g., "docx", "pptx", "pdf"

            # Get skills that can handle this file extension
            skills_for_type = skill_config.get_skills_for_file_type(file_ext)
            if skills_for_type:
                skill_mentions = ", ".join([f"@{s}" for s in skills_for_type])
                skill_hint = f" [可用 {skill_mentions} 处理]"
        else:
            # Fallback: hardcoded hint for pdf only
            if file_type == "pdf":
                skill_hint = " [可用 @pdf 处理]"

        lines.append(
            f"{file_num}. {get_attr(file, 'filename')} ({file_type.upper()}, {get_attr(file, 'size_formatted')}) → {get_attr(file, 'workspace_path')}{skill_hint}"
        )
        file_num += 1

    for file in texts:
        lines.append(
            f"{file_num}. {get_attr(file, 'filename')} (文本, {get_attr(file, 'size_formatted')}) → {get_attr(file, 'workspace_path')} [可用 read_file 读取]"
        )
        file_num += 1

    for file in others:
        lines.append(
            f"{file_num}. {get_attr(file, 'filename')} (文件, {get_attr(file, 'size_formatted')}) → {get_attr(file, 'workspace_path')}"
        )
        file_num += 1

    # Additional hints
    if images:
        lines.append("")
        lines.append("图片内容已通过 vision 能力加载，你可以直接分析图片内容。")

    if documents or texts:
        lines.append("其他文件可使用相应工具处理。")

    return "<system_reminder>\n" + "\n".join(lines) + "\n</system_reminder>"


if __name__ == "__main__":
    # Test file classification
    print("File Type Classification Tests:\n")
    test_files = [
        "image.png",
        "photo.jpg",
        "document.pdf",
        "data.txt",
        "config.json",
        "script.py",
        "report.docx",
        "unknown.xyz",
    ]

    for filename in test_files:
        file_type = classify_file_type(filename)
        max_size = MAX_FILE_SIZE.get(file_type, MAX_FILE_SIZE["unknown"])
        print(f"{filename:20s} → {file_type:8s} (max: {format_file_size(max_size)})")
