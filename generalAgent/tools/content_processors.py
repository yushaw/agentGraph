"""Content processors for post-processing tool results.

This module provides a lightweight, extensible framework for processing content
returned by tools (e.g., web scraping results). Inspired by Crawl4AI's filter
architecture and LangChain's runnable patterns.

Architecture:
- ContentProcessor: Protocol defining processor interface
- LLMContentCleaner: Clean content using LLM to remove noise
- run_content_pipeline: Execute processors in sequence
"""

import os
from typing import Protocol, Dict, Any, Optional
from abc import abstractmethod


class ContentProcessor(Protocol):
    """Protocol for content processors.

    Processors transform content with contextual information.
    Each processor should:
    - Implement process() to transform content
    - Implement should_process() to determine if processing is needed
    """

    @abstractmethod
    async def process(
        self,
        content: str,
        context: Dict[str, Any]
    ) -> str:
        """Process content with context.

        Args:
            content: Raw content to process
            context: Contextual information (query, url, etc.)

        Returns:
            Processed content
        """
        ...

    def should_process(self, context: Dict[str, Any]) -> bool:
        """Check if processor should run based on context.

        Args:
            context: Contextual information

        Returns:
            True if processor should run, False otherwise
        """
        return True


class LLMContentCleaner:
    """Clean content using LLM to remove noise and irrelevant information.

    Uses the base model to intelligently filter content while preserving:
    - Document structure (headings, lists, paragraphs)
    - Query-relevant information
    - Readability

    Removes:
    - Navigation elements
    - Advertisements
    - Irrelevant links and boilerplate
    - Redundant content
    """

    def __init__(self, model_resolver, min_length: int = 2000):
        """Initialize LLM content cleaner.

        Args:
            model_resolver: Model resolver function to get models
            min_length: Minimum content length to trigger cleaning
        """
        self.model_resolver = model_resolver
        self.min_length = min_length
        self.enabled = os.getenv("JINA_CONTENT_CLEANING", "true").lower() == "true"

    def should_process(self, context: Dict[str, Any]) -> bool:
        """Only process if enabled and content is long enough.

        Args:
            context: Must contain 'content' key with string value

        Returns:
            True if should clean content
        """
        if not self.enabled:
            return False

        content = context.get("content", "")
        return len(content) > self.min_length

    async def process(self, content: str, context: Dict[str, Any]) -> str:
        """Clean content using base model.

        Args:
            content: Raw content to clean
            context: Should contain 'query' or 'url' for context

        Returns:
            Cleaned content
        """
        if not self.should_process(context):
            return content

        # Get query or URL for context
        query = context.get("query") or context.get("url", "")

        # Get base model ID from configs
        from generalAgent.config import Settings
        from generalAgent.runtime.model_resolver import resolve_model_configs

        settings = Settings()
        model_configs = resolve_model_configs(settings)
        base_model_id = model_configs["base"]["id"]

        # Use base model for cleaning
        model = self.model_resolver(base_model_id)

        # Build cleaning prompt
        prompt = self._build_cleaning_prompt(content, query)

        # Clean content
        response = await model.ainvoke(prompt)
        cleaned = response.content if hasattr(response, 'content') else str(response)

        return cleaned

    def _build_cleaning_prompt(self, content: str, query: str) -> str:
        """Build cleaning prompt for LLM.

        Args:
            content: Content to clean
            query: Query or URL for context

        Returns:
            Prompt string
        """
        return f"""请清理以下网页内容，保留与查询相关的核心信息，去除无关和无意义的内容。

查询上下文：{query}

清理要求：
1. 保留文档结构（标题、列表、段落层级）
2. 删除导航菜单、广告、页脚等噪音
3. 去除无关的链接和样板文字
4. 压缩冗余重复的内容
5. 保持内容的可读性和连贯性

原始内容：
{content}

请直接输出清理后的内容，不要添加任何说明或前缀："""


async def run_content_pipeline(
    content: str,
    processors: list[ContentProcessor],
    context: Dict[str, Any]
) -> str:
    """Run content through processor pipeline.

    Executes processors in sequence, passing output of each processor
    as input to the next. Updates context['content'] after each step.

    Args:
        content: Initial content
        processors: List of processors to run
        context: Contextual information (updated with content after each step)

    Returns:
        Final processed content

    Example:
        >>> context = {"query": "Python tutorial", "url": "https://example.com"}
        >>> processors = [cleaner, summarizer]
        >>> result = await run_content_pipeline(content, processors, context)
    """
    result = content
    context["content"] = content  # Add content to context for should_process checks

    for processor in processors:
        if processor.should_process(context):
            result = await processor.process(result, context)
            context["content"] = result  # Update for next processor

    return result


# Global cleaner instance (lazy initialized)
_cleaner: Optional[LLMContentCleaner] = None


def get_content_cleaner() -> LLMContentCleaner:
    """Get or create global LLM content cleaner instance.

    Returns:
        LLMContentCleaner instance
    """
    global _cleaner
    if _cleaner is None:
        from generalAgent.config import Settings
        from generalAgent.runtime.model_resolver import (
            resolve_model_configs,
            build_model_resolver
        )

        settings = Settings()
        model_configs = resolve_model_configs(settings)
        model_resolver = build_model_resolver(model_configs)

        min_length = int(os.getenv("JINA_CLEANING_MIN_LENGTH", "2000"))
        _cleaner = LLMContentCleaner(
            model_resolver=model_resolver,
            min_length=min_length
        )

    return _cleaner


__all__ = [
    "ContentProcessor",
    "LLMContentCleaner",
    "run_content_pipeline",
    "get_content_cleaner",
]
