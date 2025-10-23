"""Parser for @mention syntax in user input."""

from __future__ import annotations

import re
from typing import List, Tuple


def parse_mentions(text: str) -> Tuple[List[str], str]:
    """Parse @mentions from user input and return cleaned text.

    Supports:
    - @agent_name
    - @skill_name
    - @tool_name

    Examples:
        "@weather 北京今天怎么样" -> (["weather"], "北京今天怎么样")
        "@weather @pptx 生成天气报告" -> (["weather", "pptx"], "生成天气报告")
        "普通文本" -> ([], "普通文本")

    Args:
        text: User input text

    Returns:
        Tuple of (mentioned_names, cleaned_text)
    """
    # Pattern: @word (word can be alphanumeric, underscore, hyphen)
    pattern = r'@([\w\-]+)'

    # Find all mentions
    mentions = re.findall(pattern, text)

    # Remove mentions from text
    cleaned_text = re.sub(pattern, '', text).strip()

    # Remove extra whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

    return mentions, cleaned_text


def format_mention_reminder(mentions: List[str]) -> str:
    """Format a system reminder for mentioned agents/skills/tools.

    Args:
        mentions: List of mentioned names

    Returns:
        Formatted reminder string
    """
    if not mentions:
        return ""

    mentions_str = "、".join(mentions)
    return f"<system_reminder>用户明确提到了：{mentions_str}。请优先使用这些工具或技能。</system_reminder>"


# Examples for testing
if __name__ == "__main__":
    test_cases = [
        "@weather 北京今天怎么样",
        "@weather @pptx 生成一个关于天气的PPT",
        "普通查询，没有mention",
        "@http_fetch https://example.com",
        "   @weather    北京     ",  # extra whitespace
    ]

    for case in test_cases:
        mentions, cleaned = parse_mentions(case)
        print(f"Input: {case!r}")
        print(f"  Mentions: {mentions}")
        print(f"  Cleaned: {cleaned!r}")
        print(f"  Reminder: {format_mention_reminder(mentions)}")
        print()
