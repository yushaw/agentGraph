"""External agent integration tool."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx
from langchain_core.tools import tool


@tool
def call_external_agent(
    agent_url: str,
    task: str,
    context: Optional[str] = None,
    timeout: int = 30,
) -> str:
    """调用外部 Agent 完成任务。

    此工具允许 Charlie 联动其他专业 Agent 协作完成任务。

    Args:
        agent_url: 外部 Agent 的 API 地址
        task: 要完成的任务描述
        context: 可选的上下文信息
        timeout: 超时时间（秒），默认 30 秒

    Returns:
        外部 Agent 的响应结果（JSON 字符串）

    Examples:
        >>> call_external_agent(
        ...     agent_url="https://api.example.com/agent",
        ...     task="分析这段代码的性能瓶颈",
        ...     context="代码: def foo(): ..."
        ... )
    """
    try:
        # Prepare request payload
        payload = {
            "task": task,
            "context": context,
        }

        # Make HTTP POST request
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                agent_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()

            # Parse response
            result = response.json()

            return json.dumps({
                "ok": True,
                "result": result,
                "agent_url": agent_url,
            }, ensure_ascii=False)

    except httpx.TimeoutException:
        return json.dumps({
            "ok": False,
            "error": f"请求超时（{timeout}秒）",
            "agent_url": agent_url,
        }, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({
            "ok": False,
            "error": f"HTTP 错误: {e.response.status_code}",
            "agent_url": agent_url,
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": f"调用失败: {str(e)}",
            "agent_url": agent_url,
        }, ensure_ascii=False)


# For testing
if __name__ == "__main__":
    # Test with a mock endpoint (will fail, but shows the structure)
    result = call_external_agent(
        agent_url="https://httpbin.org/post",
        task="测试任务",
        context="测试上下文"
    )
    print(result)
