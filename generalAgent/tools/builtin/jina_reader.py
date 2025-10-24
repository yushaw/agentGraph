"""Jina Reader API - Convert web pages to LLM-friendly markdown."""

import os
import json
from typing import Optional
import httpx
from langchain_core.tools import tool


JINA_READER_API = "https://r.jina.ai/"
JINA_API_TIMEOUT = 30.0


@tool
async def fetch_web(url: str, target_selector: Optional[str] = None) -> str:
    """获取网页并转换为干净的 Markdown 格式。自动去除广告、导航栏等噪音内容。

    使用场景：需要读取网页内容、分析文章、提取信息时使用。支持中英文等多语言网页。

    参数：
        url: 要抓取的网址（如 "https://example.com"）
        target_selector: 可选的 CSS 选择器，只提取页面特定部分（如 "article.main"）

    返回：JSON 格式，包含 url、title、content(markdown)、description

    示例：
        fetch_web("https://docs.python.org/3/tutorial/")  # 抓取 Python 教程
        fetch_web("https://baike.baidu.com/item/Python")  # 中文百科
    """
    api_key = os.getenv("JINA_API_KEY")
    if not api_key:
        return json.dumps(
            {"error": "JINA_API_KEY environment variable not set"},
            ensure_ascii=False
        )

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

    # Add optional target selector
    if target_selector:
        headers["X-Target-Selector"] = target_selector

    # Prepare request body
    body = {"url": url}

    try:
        with httpx.Client(timeout=JINA_API_TIMEOUT) as client:
            response = client.post(
                JINA_READER_API,
                headers=headers,
                json=body
            )
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract relevant fields from Jina's response format
            if "data" in data:
                result = {
                    "url": data["data"].get("url", url),
                    "title": data["data"].get("title", ""),
                    "content": data["data"].get("content", ""),
                    "description": data["data"].get("description", ""),
                    "usage": data["data"].get("usage", {})
                }
            else:
                # Fallback if response format is different
                result = data

            # Post-process content with LLM cleaning
            if result.get("content"):
                from generalAgent.tools.content_processors import (
                    get_content_cleaner,
                    run_content_pipeline
                )

                cleaner = get_content_cleaner()
                context = {
                    "url": url,
                    "query": "",  # fetch_web doesn't have query context
                }

                result["content"] = await run_content_pipeline(
                    result["content"],
                    [cleaner],
                    context
                )

            return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}"
        try:
            error_body = e.response.json()
            error_detail += f": {error_body}"
        except:
            error_detail += f": {e.response.text}"

        return json.dumps(
            {"error": f"Failed to fetch web page: {error_detail}"},
            ensure_ascii=False
        )

    except httpx.TimeoutException:
        return json.dumps(
            {"error": f"Request timeout after {JINA_API_TIMEOUT}s"},
            ensure_ascii=False
        )

    except Exception as e:
        return json.dumps(
            {"error": f"Unexpected error: {str(e)}"},
            ensure_ascii=False
        )


__all__ = ["fetch_web"]
