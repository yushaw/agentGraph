"""Google Custom Search JSON API - High-quality web search with Google."""

import os
import json
from typing import Optional
import httpx
from langchain_core.tools import tool


GOOGLE_SEARCH_API = "https://www.googleapis.com/customsearch/v1"
GOOGLE_API_TIMEOUT = 30.0


@tool
async def search_web(
    query: str,
    num_results: int = 5,
    allowed_domains: Optional[list[str]] = None,
    blocked_domains: Optional[list[str]] = None,
    language: Optional[str] = None,
    safe_search: str = "off"
) -> str:
    """搜索网页并返回结果列表（标题、URL、摘要）。用于获取最新信息、查找资料。

    使用场景：需要最新信息、超出知识截止日期的内容、查找特定领域资料时使用。

    重要：
    - 返回轻量级搜索结果（标题 + 摘要），不含完整页面内容
    - 如需阅读完整内容，请用 fetch_web 工具获取具体 URL
    - 对于需要深度分析的搜索任务，建议使用 delegate_task 工具委派给子代理

    最佳实践：
    1. 在查询中明确指定时间范围（如 "Python 3.13 新特性 2024"）
    2. 使用具体的关键词而非宽泛的概念（如 "FastAPI async best practices" 而非 "Python web"）
    3. 如需特定网站内容，使用 allowed_domains 参数

    参数：
        query: 搜索关键词（具体且明确）
        num_results: 返回结果数量（1-10，默认 5）
        allowed_domains: 只搜索这些域名（如 ["github.com", "stackoverflow.com"]）
        blocked_domains: 排除这些域名（如 ["example.com"]）
        language: 搜索语言（如 "zh-CN", "en"）
        safe_search: 安全搜索级别 ("off", "medium", "high")

    返回：JSON 格式，包含 query、results 数组（每个结果有 title、url、snippet、description）

    示例：
        search_web("Python 3.13 新特性 2024")  # 明确时间范围
        search_web("FastAPI async database connection pool", num_results=10)  # 具体技术问题
        search_web("AI news", allowed_domains=["techcrunch.com", "theverge.com"])  # 特定网站
        search_web("机器学习入门教程", language="zh-CN")  # 指定语言
    """
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key:
        return json.dumps(
            {"error": "GOOGLE_SEARCH_API_KEY environment variable not set"},
            ensure_ascii=False
        )

    if not search_engine_id:
        return json.dumps(
            {"error": "GOOGLE_SEARCH_ENGINE_ID environment variable not set. Get it from: https://programmablesearchengine.google.com/"},
            ensure_ascii=False
        )

    # Validate num_results (Google API max is 10 per request)
    num_results = max(1, min(10, num_results))

    # Prepare query parameters
    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
        "num": num_results,
    }

    # Add optional parameters
    if language:
        params["lr"] = f"lang_{language.split('-')[0]}"  # Convert "zh-CN" to "lang_zh"
        params["hl"] = language  # Interface language

    if safe_search != "off":
        params["safe"] = safe_search

    # Apply domain filtering in query if specified
    if allowed_domains:
        # Google search syntax: site:domain1.com OR site:domain2.com
        site_filter = " OR ".join([f"site:{domain}" for domain in allowed_domains])
        params["q"] = f"{query} ({site_filter})"

    if blocked_domains:
        # Google search syntax: -site:domain1.com -site:domain2.com
        exclude_filter = " ".join([f"-site:{domain}" for domain in blocked_domains])
        params["q"] = f"{query} {exclude_filter}"

    try:
        async with httpx.AsyncClient(timeout=GOOGLE_API_TIMEOUT) as client:
            response = await client.get(GOOGLE_SEARCH_API, params=params)
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract and format results
            results = []
            if "items" in data:
                for item in data["items"]:
                    result = {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "description": item.get("htmlSnippet", "").replace("<b>", "").replace("</b>", ""),
                    }

                    # Add additional metadata if available
                    if "pagemap" in item:
                        pagemap = item["pagemap"]
                        # Extract meta description
                        if "metatags" in pagemap and len(pagemap["metatags"]) > 0:
                            meta = pagemap["metatags"][0]
                            if "og:description" in meta:
                                result["description"] = meta["og:description"]
                            elif "description" in meta:
                                result["description"] = meta["description"]

                    results.append(result)

            # Get search metadata
            search_info = data.get("searchInformation", {})
            total_results = search_info.get("totalResults", "0")
            search_time = search_info.get("searchTime", 0)

            output = {
                "query": query,
                "results": results,
                "total_results": len(results),
                "estimated_total": total_results,
                "search_time": search_time
            }

            return json.dumps(output, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}"
        try:
            error_body = e.response.json()
            # Google API returns structured error messages
            if "error" in error_body:
                error_info = error_body["error"]
                error_detail = f"{error_info.get('code', e.response.status_code)}: {error_info.get('message', 'Unknown error')}"

                # Add helpful hints for common errors
                if e.response.status_code == 403:
                    error_detail += "\n提示：请检查 API Key 是否正确，以及是否超出配额限制"
                elif e.response.status_code == 400:
                    error_detail += "\n提示：请检查 Search Engine ID 是否正确"
        except:
            error_detail += f": {e.response.text}"

        return json.dumps(
            {"error": f"Search request failed: {error_detail}"},
            ensure_ascii=False
        )

    except httpx.TimeoutException:
        return json.dumps(
            {"error": f"Search timeout after {GOOGLE_API_TIMEOUT}s"},
            ensure_ascii=False
        )

    except Exception as e:
        return json.dumps(
            {"error": f"Unexpected error: {str(e)}"},
            ensure_ascii=False
        )


__all__ = ["search_web"]
