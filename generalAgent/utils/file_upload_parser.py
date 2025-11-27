"""Parse #filename mentions for file uploads from uploads/ directory.

Supports:
- Single file: #filename.ext
- Path with file: #dir/subdir/filename.ext
- Directory (all files): #dir/subdir/
- Glob pattern: #dir/*.pdf, #**/*.md
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple, List


def parse_file_mentions(text: str) -> Tuple[List[str], str]:
    """Parse #filename mentions from user input.

    Extracts file references and returns them along with the cleaned text.

    Supported patterns:
        - #filename.ext          -> Single file in uploads/
        - #dir/file.ext          -> File in subdirectory
        - #dir/                   -> All files in directory (non-recursive)
        - #dir/**                 -> All files in directory (recursive)
        - #dir/*.pdf              -> Glob pattern
        - #**/*.md                -> Recursive glob from uploads/

    Args:
        text: User input text

    Returns:
        Tuple of (file_mentions, cleaned_text)
        file_mentions may contain paths, directories (ending with /), or glob patterns

    Examples:
        >>> parse_file_mentions("分析这个图 #screenshot.png")
        (['screenshot.png'], '分析这个图')

        >>> parse_file_mentions("处理 #demo/file1.pdf #file2.txt")
        (['demo/file1.pdf', 'file2.txt'], '处理')

        >>> parse_file_mentions("分析 #demo_requirement/ 目录")
        (['demo_requirement/'], '分析 目录')

        >>> parse_file_mentions("找所有PDF #docs/*.pdf")
        (['docs/*.pdf'], '找所有PDF')

        >>> parse_file_mentions("## 标题")  # markdown heading, not file
        ([], '## 标题')
    """
    # Pattern explanation:
    # - Start with # (not ##)
    # - Match path components: alphanumeric, chinese, underscore, dash, dot, slash, asterisk
    # - Must either:
    #   1. End with .ext (file with extension)
    #   2. End with / (directory)
    #   3. Contain * (glob pattern)
    # - Negative lookbehind (?<!#) avoids markdown headings
    pattern = r'(?<!#)#((?:[a-zA-Z0-9_\-\u4e00-\u9fa5.*]+/)*(?:[a-zA-Z0-9_\-\u4e00-\u9fa5.*]+\.[a-zA-Z0-9]{1,5}|[a-zA-Z0-9_\-\u4e00-\u9fa5]+/|\*\*/?|[a-zA-Z0-9_\-\u4e00-\u9fa5]*\*[a-zA-Z0-9_\-\u4e00-\u9fa5.*]*))'

    matches = re.findall(pattern, text)

    # Remove duplicates while preserving order
    seen = set()
    file_mentions = []
    for match in matches:
        if match not in seen:
            file_mentions.append(match)
            seen.add(match)

    # Clean text: replace #pattern with the pattern itself (remove #)
    cleaned_text = re.sub(pattern, r'\1', text)

    # Clean up extra whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return file_mentions, cleaned_text


def expand_file_patterns(patterns: List[str], base_dir: Path) -> List[str]:
    """Expand directory and glob patterns to actual file paths.

    Args:
        patterns: List of file patterns (files, directories, globs)
        base_dir: Base directory (uploads/)

    Returns:
        List of actual file paths relative to base_dir

    Examples:
        expand_file_patterns(['demo/'], base_dir)
        -> ['demo/file1.md', 'demo/file2.csv']

        expand_file_patterns(['*.pdf'], base_dir)
        -> ['doc1.pdf', 'doc2.pdf']

        expand_file_patterns(['demo/**'], base_dir)
        -> ['demo/a.md', 'demo/sub/b.md']
    """
    expanded = []
    seen = set()

    for pattern in patterns:
        # Case 1: Directory (ends with /)
        if pattern.endswith('/'):
            dir_path = base_dir / pattern.rstrip('/')
            if dir_path.is_dir():
                # Non-recursive: only direct children
                for f in dir_path.iterdir():
                    if f.is_file() and not f.name.startswith('.'):
                        rel_path = str(f.relative_to(base_dir))
                        if rel_path not in seen:
                            expanded.append(rel_path)
                            seen.add(rel_path)

        # Case 2: Recursive glob (**)
        elif '**' in pattern:
            for f in base_dir.glob(pattern):
                if f.is_file() and not f.name.startswith('.'):
                    rel_path = str(f.relative_to(base_dir))
                    if rel_path not in seen:
                        expanded.append(rel_path)
                        seen.add(rel_path)

        # Case 3: Simple glob (*)
        elif '*' in pattern:
            for f in base_dir.glob(pattern):
                if f.is_file() and not f.name.startswith('.'):
                    rel_path = str(f.relative_to(base_dir))
                    if rel_path not in seen:
                        expanded.append(rel_path)
                        seen.add(rel_path)

        # Case 4: Regular file path
        else:
            file_path = base_dir / pattern
            if file_path.is_file():
                if pattern not in seen:
                    expanded.append(pattern)
                    seen.add(pattern)

    return sorted(expanded)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted string like "245 KB" or "1.2 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


if __name__ == "__main__":
    # Test cases for parse_file_mentions
    test_cases = [
        "分析这个图 #screenshot.png",
        "处理 #file1.pdf #file2.txt 这两个文件",
        "## 这是标题",  # Should not match
        "#image.jpg #data.csv #report.pdf",
        "没有文件",
        "#中文文件名.pdf",
        "#file-with-dash.txt #file_with_underscore.py",
        # New patterns
        "分析 #demo_requirement/ 目录下的所有文件",
        "处理 #docs/*.md 所有markdown",
        "找 #**/*.pdf 所有PDF",
        "#dir/subdir/file.txt 子目录文件",
    ]

    print("=== parse_file_mentions Tests ===\n")
    for test in test_cases:
        mentions, cleaned = parse_file_mentions(test)
        print(f"Input:   {test}")
        print(f"Files:   {mentions}")
        print(f"Cleaned: {cleaned}")
        print()

    # Test expand_file_patterns if uploads directory exists
    print("=== expand_file_patterns Tests ===\n")
    base_dir = Path("uploads")
    if base_dir.exists():
        test_patterns = [
            ["demo_requirement/"],
            ["*.pdf"],
            ["demo_requirement/*.md"],
        ]
        for patterns in test_patterns:
            expanded = expand_file_patterns(patterns, base_dir)
            print(f"Pattern:  {patterns}")
            print(f"Expanded: {expanded}")
            print()
    else:
        print(f"Skipping: {base_dir} does not exist")
