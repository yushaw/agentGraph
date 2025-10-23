"""Parse #filename mentions for file uploads from uploads/ directory."""

from __future__ import annotations

import re
from typing import Tuple, List


def parse_file_mentions(text: str) -> Tuple[List[str], str]:
    """Parse #filename mentions from user input.

    Extracts file references like #image.png and returns them along with
    the cleaned text (with #filename removed).

    Args:
        text: User input text

    Returns:
        Tuple of (file_mentions, cleaned_text)

    Examples:
        >>> parse_file_mentions("分析这个图 #screenshot.png")
        (['screenshot.png'], '分析这个图')

        >>> parse_file_mentions("处理 #file1.pdf #file2.txt")
        (['file1.pdf', 'file2.txt'], '处理')

        >>> parse_file_mentions("## 标题")  # markdown heading, not file
        ([], '## 标题')
    """
    # Pattern: #filename.ext
    # Must have extension (at least one dot followed by 1-5 chars)
    # Avoids matching markdown headings like "## Heading"
    pattern = r'#([a-zA-Z0-9_\-\u4e00-\u9fa5]+\.[a-zA-Z0-9]{1,5})'

    matches = re.findall(pattern, text)

    # Remove duplicates while preserving order
    seen = set()
    file_mentions = []
    for match in matches:
        if match not in seen:
            file_mentions.append(match)
            seen.add(match)

    # Clean text: remove #filename patterns
    cleaned_text = re.sub(pattern, '', text)

    # Clean up extra whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return file_mentions, cleaned_text


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
    # Test cases
    test_cases = [
        "分析这个图 #screenshot.png",
        "处理 #file1.pdf #file2.txt 这两个文件",
        "## 这是标题",  # Should not match
        "#image.jpg #data.csv #report.pdf",
        "没有文件",
        "#中文文件名.pdf",
        "#file-with-dash.txt #file_with_underscore.py",
    ]

    print("File Upload Parser Tests:\n")
    for test in test_cases:
        mentions, cleaned = parse_file_mentions(test)
        print(f"Input:   {test}")
        print(f"Files:   {mentions}")
        print(f"Cleaned: {cleaned}")
        print()
