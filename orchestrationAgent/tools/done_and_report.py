"""done_and_report - Signal tool for task completion.

This is a "signal tool" that serves a CONTROL FLOW purpose:
- It does NOT perform any operation
- It is a MARKER that tells the Graph router: "Work is complete, this is the final result"

Why use a tool instead of just AI Message?
- Without tool: Graph cannot programmatically know when Host decided work is done
- With tool: Our routing logic becomes simple and robust:

  if tool_calls contains done_and_report:
      route to finalize -> END
  else:
      route to tools node (execute delegate_task)
"""

from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool, InjectedToolArg


@tool
def done_and_report(
    final_result: str,
    summary: str = "",
    config: Annotated[dict, InjectedToolArg] = None,
) -> str:
    """向用户汇报最终结果并结束任务（信号工具）

    这是一个"信号工具"，用于告诉系统："工作已完成，这是最终结果，请结束任务。"

    **何时使用：**
    - 所有子任务都已完成
    - 你已经汇总了所有 Worker 的结果
    - 准备向用户报告最终成果

    **使用要求：**
    调用此工具后，任务将立即结束，不会再执行任何操作。
    因此，请确保 `final_result` 包含完整的、用户友好的总结。

    Args:
        final_result: 最终结果（必须详细且用户友好）
        summary: （可选）简短摘要（1-2 句话）

    Examples:
        # 示例 1：简单任务完成
        done_and_report(
            final_result="已完成分析。文件 'report.pdf' 包含 50 页内容，主要讨论..."
        )

        # 示例 2：多步骤任务完成
        done_and_report(
            final_result="已完成对比分析：\\n\\n"
                        "**doc1.pdf**: 主要结论是...\\n"
                        "**doc2.pdf**: 主要结论是...\\n\\n"
                        "**主要差异**: ...",
            summary="两份文档的主要差异在于研究方法和结论"
        )
    """
    # This is a signal tool - it doesn't need to do anything
    # The Graph router will detect this tool call and route to finalize -> END

    return json.dumps({
        "signal": "task_complete",
        "final_result": final_result,
        "summary": summary or final_result[:100],
    }, ensure_ascii=False)


__all__ = ["done_and_report"]
