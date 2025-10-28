"""Jina Search API - Web search optimized for LLMs."""

import os
import json
from typing import Optional
import httpx
from langchain_core.tools import tool


JINA_SEARCH_API = "https://s.jina.ai/"
JINA_API_TIMEOUT = 30.0


@tool
async def web_search(
    query: str,
    num_results: int = 5,
    allowed_domains: Optional[list[str]] = None,
    blocked_domains: Optional[list[str]] = None,
    location: Optional[str] = None,
    language: Optional[str] = None  # Keep parameter for compatibility but ignore it
) -> str:
    """搜索网页并返回结果的完整内容（Markdown 格式）。用于获取最新信息、查找资料。

    使用场景：需要最新信息、超出知识截止日期的内容、查找特定领域资料时使用。
    重要：上下文占用会很多，建议使用 delegate_task 工具使用子代理进行搜索

    参数：
        query: 搜索关键词（如 "Python 最佳实践 2025"）
        num_results: 返回结果数量（1-10，默认 5）
        allowed_domains: 只搜索这些域名（如 ["github.com", "stackoverflow.com"]）
        blocked_domains: 排除这些域名（如 ["example.com"]）
        location: 地理位置，用于本地化搜索（如 "Beijing", "New York"）

    返回：JSON 格式，包含 query、results 数组（每个结果有 title、url、content、description）

    示例：
        web_search("Python 异步编程教程 2025")  # 在查询中指定年份或日期范围
        web_search("AI news 2025", allowed_domains=["techcrunch.com"])  # 仅搜索特定网站
        web_search("restaurants", location="San Francisco")  # 本地化搜索
    """
    api_key = os.getenv("JINA_API_KEY")
    if not api_key:
        return json.dumps(
            {"error": "JINA_API_KEY environment variable not set"},
            ensure_ascii=False
        )

    # Validate num_results
    num_results = max(1, min(10, num_results))

    # Check if image stripping is enabled
    strip_images = os.getenv("JINA_STRIP_IMAGES", "true").lower() == "true"

    # Get remove selectors for noise filtering
    remove_selectors = os.getenv("JINA_REMOVE_SELECTORS", "")

    # Prepare headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Return-Format": "markdown",  # Ensure markdown output
    }

    # Apply image retention policy
    if strip_images:
        headers["X-Retain-Images"] = "none"  # Remove all images from response

    # Apply noise removal (nav, footer, sidebar, etc.)
    if remove_selectors:
        headers["X-Remove-Selector"] = remove_selectors

    # Prepare request body
    body = {
        "q": query,
        "num": num_results
    }

    # Add optional parameters
    if location:
        body["location"] = location

    # Note: language parameter is not reliably supported by Jina Search API
    # Most language codes (except "en") are rejected by the validator
    # Query language is auto-detected, so we skip this parameter
    # if language:
    #     body["hl"] = language

    try:
        with httpx.Client(timeout=JINA_API_TIMEOUT) as client:
            response = client.post(
                JINA_SEARCH_API,
                headers=headers,
                json=body
            )
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract and format results
            results = []
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    url = item.get("url", "")

                    # Apply domain filtering
                    if allowed_domains or blocked_domains:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc.lower()
                        # Remove 'www.' prefix for comparison
                        domain = domain.removeprefix("www.")

                        # Check allowed domains
                        if allowed_domains:
                            allowed = any(
                                domain == d.lower().removeprefix("www.") or
                                domain.endswith("." + d.lower().removeprefix("www."))
                                for d in allowed_domains
                            )
                            if not allowed:
                                continue

                        # Check blocked domains
                        if blocked_domains:
                            blocked = any(
                                domain == d.lower().removeprefix("www.") or
                                domain.endswith("." + d.lower().removeprefix("www."))
                                for d in blocked_domains
                            )
                            if blocked:
                                continue

                    result = {
                        "title": item.get("title", ""),
                        "url": url,
                        "content": item.get("content", ""),
                        "description": item.get("description", ""),
                        "usage": item.get("usage", {})
                    }
                    results.append(result)

            # Post-process content with LLM cleaning (parallel execution with concurrency limit)
            from generalAgent.tools.content_processors import (
                get_content_cleaner,
                run_content_pipeline
            )
            import asyncio

            cleaner = get_content_cleaner()

            # Collect cleaning tasks for parallel execution
            cleaning_tasks = []
            for result in results:
                if result.get("content"):
                    context = {
                        "query": query,
                        "url": result.get("url", ""),
                    }
                    task = run_content_pipeline(
                        result["content"],
                        [cleaner],
                        context
                    )
                    cleaning_tasks.append((result, task))

            # Execute cleaning tasks in parallel with concurrency limit (max 10 concurrent)
            if cleaning_tasks:
                # Use semaphore to limit concurrent LLM calls
                max_concurrent = 10
                semaphore = asyncio.Semaphore(max_concurrent)

                async def clean_with_semaphore(result, task):
                    async with semaphore:
                        return result, await task

                # Run all tasks with semaphore control
                results_with_cleaned = await asyncio.gather(
                    *[clean_with_semaphore(result, task) for result, task in cleaning_tasks],
                    return_exceptions=True
                )

                # Update results with cleaned content (handle exceptions gracefully)
                for item in results_with_cleaned:
                    if isinstance(item, Exception):
                        # Log error but don't fail entire search
                        print(f"Content cleaning failed: {str(item)}")
                        continue
                    result, cleaned = item
                    result["content"] = cleaned

            output = {
                "query": query,
                "results": results,
                "total_results": len(results)
            }

            return json.dumps(output, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}"
        try:
            error_body = e.response.json()
            error_detail += f": {error_body}"
        except:
            error_detail += f": {e.response.text}"

        return json.dumps(
            {"error": f"Search request failed: {error_detail}"},
            ensure_ascii=False
        )

    except httpx.TimeoutException:
        return json.dumps(
            {"error": f"Search timeout after {JINA_API_TIMEOUT}s"},
            ensure_ascii=False
        )

    except Exception as e:
        return json.dumps(
            {"error": f"Unexpected error: {str(e)}"},
            ensure_ascii=False
        )


__all__ = ["web_search"]
