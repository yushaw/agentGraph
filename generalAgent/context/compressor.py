"""Context compression and summarization.

This module provides utilities for compressing conversation history
when approaching token limits.
"""

from __future__ import annotations

from typing import List, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from generalAgent.config.settings import ContextManagementSettings
from generalAgent.graph.message_utils import clean_message_history, truncate_messages_safely


# Prompt templates for compression - Optimized for AgentGraph Agent Loop
COMPACT_PROMPT = """你正在压缩一段 Agent 对话历史，以便在不丢失关键信息的前提下节省 token。

这是一个 **LangGraph Agent Loop 系统**，Agent 通过调用工具完成任务。请详细总结以下内容：

## 总结要求

### 1. 用户请求和意图
- 用户明确提出的需求
- 任务目标和期望结果

### 2. 工具调用记录（核心重点）
按时间顺序列出所有工具调用：
- **工具名称**：如 read_file, write_file, search_file, run_bash_command 等
- **关键参数**：文件路径、搜索关键词、命令等
- **调用结果**：成功/失败，重要输出
- **调用原因**：为什么调用这个工具

示例格式：
```
read_file("uploads/report.pdf") → 成功读取 PDF（15 页）
  原因：用户要求分析报告内容
  结果：发现 Q3 财务数据

search_file("uploads/data.xlsx", "revenue") → 找到 3 处匹配
  原因：查找营收相关数据
  结果：Sheet1 A15:A17
```

### 3. 技能（Skill）使用
- 加载了哪些 Skill（如 @pdf, @docx）
- Skill 的使用场景和效果

### 4. 文件操作记录
- **读取的文件**：路径、文件类型、内容摘要
- **写入的文件**：路径、内容用途
- **工作空间结构**：uploads/, outputs/, skills/ 中的文件

### 5. 错误和修复
- 遇到的错误（工具调用失败、API 错误等）
- 如何修复的
- 用户反馈和调整

### 6. TODO 任务状态
- 已完成的任务
- 进行中的任务
- 待完成的任务

### 7. 关键决策点
- 为什么选择某个方法或工具
- 放弃的方案和原因

### 8. 当前状态
- 最后一次操作
- 下一步计划（如果有明确指示）

## 输出格式

使用清晰的分段结构，**保留文件路径、工具名称、关键参数**等技术细节。

<summary>
[用中文输出详细总结，确保包含所有工具调用、文件操作、错误修复等信息]
</summary>"""


SUMMARIZE_PROMPT = """你正在极简压缩一段 Agent 对话历史（紧急情况下使用）。

请用 **不超过 200 字** 总结：
1. 核心任务是什么
2. 使用了哪些关键工具（如 read_file, search_file 等）
3. 处理了哪些文件（路径）
4. 当前状态和主要成果

输出格式：一段简洁的中文描述，**必须包含文件路径和工具名称**。

示例：
用户要求分析 uploads/report.pdf，调用 read_file 读取内容后使用 search_file 查找关键词"revenue"，在 Sheet1 找到 Q3 数据。已完成数据提取，待生成分析报告到 outputs/analysis.md。"""


class ContextCompressor:
    """Compresses conversation history using LLM-based summarization.

    This class implements a layered compression strategy:
    1. Keep recent N messages uncompressed
    2. Compact middle messages (detailed summary)
    3. Summarize old messages (extreme compression)
    """

    def __init__(self, context_settings: ContextManagementSettings):
        self.context_settings = context_settings

    def partition_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
    ) -> dict[str, List[BaseMessage]]:
        """Partition messages into system, old, middle, and recent layers.

        Args:
            messages: Full conversation history
            strategy: Compression strategy to apply

        Returns:
            Dictionary with keys: 'system', 'old', 'middle', 'recent'
        """
        # Separate system messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]

        # Clean message history
        cleaned = clean_message_history(non_system)

        # Keep recent N messages (safely preserving AI-Tool pairs)
        keep_recent = self.context_settings.keep_recent_messages
        recent_messages = truncate_messages_safely(cleaned, keep_recent=keep_recent)

        # Calculate indices
        recent_start_idx = len(cleaned) - len(recent_messages)

        if strategy == "compact":
            # For compact: keep middle messages for detailed summary
            middle_count = self.context_settings.compact_middle_messages
            middle_start_idx = max(0, recent_start_idx - middle_count)
            middle_messages = cleaned[middle_start_idx:recent_start_idx]
            old_messages = cleaned[:middle_start_idx]
        else:
            # For summarize: all non-recent messages are "old"
            middle_messages = []
            old_messages = cleaned[:recent_start_idx]

        return {
            "system": system_msgs,
            "old": old_messages,
            "middle": middle_messages,
            "recent": recent_messages,
        }

    async def compress_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
        model_invoker,  # Callable that invokes LLM
    ) -> List[BaseMessage]:
        """Compress message history using specified strategy.

        Args:
            messages: Full conversation history
            strategy: "compact" (detailed) or "summarize" (extreme)
            model_invoker: Async function to invoke LLM (e.g., invoke_planner)

        Returns:
            Compressed message list
        """
        # Partition messages
        partitions = self.partition_messages(messages, strategy)

        system_msgs = partitions["system"]
        old_msgs = partitions["old"]
        middle_msgs = partitions["middle"]
        recent_msgs = partitions["recent"]

        # Build compressed history
        compressed_history: List[BaseMessage] = []

        # 1. Always keep system messages
        compressed_history.extend(system_msgs)

        # 2. Compress old messages if any
        if old_msgs:
            if strategy == "summarize":
                # Extreme compression
                summary_prompt = SystemMessage(content=SUMMARIZE_PROMPT)
                summary_response = await model_invoker(
                    messages=[summary_prompt] + old_msgs,
                    tools=[],
                )
                compressed_history.append(
                    HumanMessage(
                        content=f"[上下文摘要 - Summarize]\n{summary_response.content}"
                    )
                )
            else:
                # Detailed compression (same as compact for old messages)
                compact_prompt = SystemMessage(content=COMPACT_PROMPT)
                compact_response = await model_invoker(
                    messages=[compact_prompt] + old_msgs,
                    tools=[],
                )
                compressed_history.append(
                    HumanMessage(
                        content=f"[上下文压缩 - Compact Old]\n{compact_response.content}"
                    )
                )

        # 3. Compact middle messages if any (only in compact strategy)
        if middle_msgs and strategy == "compact":
            compact_prompt = SystemMessage(content=COMPACT_PROMPT)
            compact_response = await model_invoker(
                messages=[compact_prompt] + middle_msgs,
                tools=[],
            )
            compressed_history.append(
                HumanMessage(
                    content=f"[上下文压缩 - Compact Middle]\n{compact_response.content}"
                )
            )

        # 4. Keep recent messages uncompressed
        compressed_history.extend(recent_msgs)

        return compressed_history

    def estimate_compression_ratio(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
    ) -> dict:
        """Estimate compression effectiveness before actually compressing.

        Args:
            messages: Full conversation history
            strategy: Compression strategy

        Returns:
            Dictionary with compression statistics
        """
        partitions = self.partition_messages(messages, strategy)

        # Estimate character counts (rough proxy for tokens)
        def char_count(msgs: List[BaseMessage]) -> int:
            return sum(len(m.content) for m in msgs if hasattr(m, "content"))

        total_chars = char_count(messages)
        system_chars = char_count(partitions["system"])
        old_chars = char_count(partitions["old"])
        middle_chars = char_count(partitions["middle"])
        recent_chars = char_count(partitions["recent"])

        # Estimate compressed size
        # Compact: ~10-20% of original, Summarize: ~2-5%
        old_compressed = old_chars * (0.05 if strategy == "summarize" else 0.15)
        middle_compressed = middle_chars * 0.15 if strategy == "compact" else 0

        estimated_final = system_chars + old_compressed + middle_compressed + recent_chars

        return {
            "original_chars": total_chars,
            "estimated_final_chars": int(estimated_final),
            "compression_ratio": estimated_final / total_chars if total_chars > 0 else 1.0,
            "messages_before": len(messages),
            "messages_after_estimate": (
                len(partitions["system"])
                + (1 if old_chars > 0 else 0)  # Old summary message
                + (1 if middle_chars > 0 and strategy == "compact" else 0)  # Middle compact
                + len(partitions["recent"])
            ),
        }
