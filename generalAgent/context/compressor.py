"""
上下文压缩器

负责：
1. 分层消息（Recent/Middle/Old）
2. 调用 LLM 执行 Compact/Summarize
3. 生成压缩报告
4. 降级策略（压缩失败时使用简单截断）
"""

from typing import List, Dict, Literal, Optional, Callable
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """压缩结果"""
    messages: List[BaseMessage]
    before_count: int
    after_count: int
    before_tokens: int  # 粗略估算
    after_tokens: int   # 粗略估算
    strategy: Literal["compact", "summarize", "emergency_truncate"]
    compression_ratio: float


# ===== Prompt 模板 =====

COMPACT_PROMPT = """你的任务是创建一个详细的对话摘要，特别关注用户的明确请求和你之前的操作。这个摘要应该全面捕捉技术细节、代码模式和架构决策，这些对于在不丢失上下文的情况下继续开发工作至关重要。

**摘要要求：**

按时间顺序分析每条消息和对话部分，识别：

1. **用户请求和意图**
   - 明确记录所有用户的请求和意图

2. **关键技术概念**
   - 列出所有重要的技术概念、技术和框架

3. **文件和代码操作**
   - 列举具体的文件和代码部分（检查、修改或创建）
   - 特别关注最近的消息，包括：
     * 完整的文件路径（如 `uploads/report.pdf`, `outputs/analysis.md`）
     * 关键代码片段（函数签名、重要逻辑）
     * 操作原因和结果的摘要

4. **工具调用记录**
   - 记录所有工具调用及其结果
   - 格式：`工具名(参数) → 结果`
   - 说明调用原因和影响

5. **技能使用**
   - 记录使用的技能（如 @pdf, @docx）
   - 说明技能的用途和效果

6. **错误和修复**
   - 列出所有遇到的错误
   - 详细说明修复方法
   - 记录用户反馈（特别是用户要求不同做法时）

7. **TODO 任务状态**
   - 列出所有待办任务的状态
   - 标记已完成、进行中和待完成的任务

8. **当前工作**
   - 详细描述在此摘要请求之前正在进行的工作
   - 特别关注最近的消息
   - 包括文件名和代码片段

**输出格式：**

请使用以下结构提供摘要：

## 用户请求和意图
[详细描述]

## 关键技术概念
- [概念 1]
- [概念 2]
...

## 文件和代码操作
- **文件路径 1**
  - 操作原因: ...
  - 更改摘要: ...
  - 重要代码片段: ...
- **文件路径 2**
  ...

## 工具调用记录
- `tool_name(args)` → 结果
  - 原因: ...
  - 影响: ...

## 技能使用
- @skill_name: 用途说明

## 错误和修复
- **错误描述**: ...
  - 修复方法: ...
  - 用户反馈: ...

## TODO 任务状态
- ✅ [已完成任务]
- ⏳ [进行中任务]
- ⏸ [待完成任务]

## 当前工作
[详细描述当前正在进行的工作，包括文件名和代码片段]

---

请仅输出摘要内容，不要包含额外的说明或元数据。
"""

SUMMARIZE_PROMPT = """请将以下对话总结为一个简洁的摘要（不超过 200 字）。

**必须包含：**
1. 主要任务
2. 关键文件路径（如 `uploads/file.pdf`, `outputs/result.md`）
3. 主要工具调用（如 `read_file`, `write_file`）
4. 解决的问题
5. 当前状态

**格式要求：**
- 使用简洁的中文
- 直接输出摘要内容
- 不要包含"摘要："等前缀

**示例：**
用户要求分析 uploads/report.pdf 并生成报告。使用 read_file 读取PDF（15页，Q3财报），search_file 查找营收数据，write_file 生成 outputs/analysis.md。修复了索引未创建的错误。已完成报告生成，等待用户确认。

---

请开始总结：
"""


class ContextCompressor:
    """上下文压缩器"""

    def __init__(self, settings):
        self.settings = settings
        self.context_settings = settings.context

    async def compress_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["auto", "compact", "summarize"],
        model_invoker: Callable,  # 用于调用 LLM 的函数
        compact_count: int = 0,
        last_compression_ratio: Optional[float] = None
    ) -> CompressionResult:
        """
        执行消息压缩

        Args:
            messages: 待压缩的消息列表
            strategy: 压缩策略 (auto/compact/summarize)
            model_invoker: LLM 调用函数
            compact_count: 当前压缩次数
            last_compression_ratio: 上次压缩率

        Returns:
            CompressionResult 包含压缩后的消息和详细报告
        """
        # 1. 决定策略
        if strategy == "auto":
            from .token_tracker import TokenTracker
            tracker = TokenTracker(self.settings)
            strategy = tracker._decide_strategy(compact_count, last_compression_ratio)

        logger.info(f"Starting compression with strategy: {strategy}")

        # 2. 记录压缩前状态
        before_count = len(messages)
        before_tokens = self._estimate_tokens(messages)

        # 3. 分层消息
        partitioned = self._partition_messages(messages, strategy)

        # 4. 执行压缩
        try:
            compressed = await self._compress_partitioned(
                partitioned,
                strategy,
                model_invoker
            )
        except Exception as e:
            logger.error(f"LLM compression failed: {e}")
            # 降级：使用简单截断
            logger.warning("Falling back to simple truncation")
            from .truncator import MessageTruncator
            truncator = MessageTruncator(self.settings)
            compressed = truncator.truncate(messages)
            strategy = "emergency_truncate"

        # 5. 记录压缩后状态
        after_count = len(compressed)
        after_tokens = self._estimate_tokens(compressed)
        compression_ratio = after_tokens / before_tokens if before_tokens > 0 else 1.0

        logger.info(
            f"Compression complete: {before_count} → {after_count} messages, "
            f"~{before_tokens} → ~{after_tokens} tokens ({compression_ratio:.1%})"
        )

        return CompressionResult(
            messages=compressed,
            before_count=before_count,
            after_count=after_count,
            before_tokens=before_tokens,
            after_tokens=after_tokens,
            strategy=strategy,
            compression_ratio=compression_ratio
        )

    def _partition_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"]
    ) -> Dict[str, List[BaseMessage]]:
        """
        分层消息

        分层策略：
        - System: 保留所有 SystemMessage
        - Recent: 保留最近 N 条（完整）
        - Middle: 中间 M 条（需要压缩）
        - Old: 剩余消息（需要压缩）
        """
        # 分离 SystemMessage
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        # 配置
        keep_recent = self.context_settings.keep_recent_messages
        compact_middle = self.context_settings.compact_middle_messages

        # 分层
        total = len(non_system_messages)

        if total <= keep_recent:
            # 消息太少，不需要分层
            return {
                "system": system_messages,
                "old": [],
                "middle": [],
                "recent": non_system_messages
            }

        # Recent: 最后 N 条
        recent = non_system_messages[-keep_recent:]
        remaining = non_system_messages[:-keep_recent]

        if len(remaining) <= compact_middle:
            # 剩余消息不多，全部作为 middle
            return {
                "system": system_messages,
                "old": [],
                "middle": remaining,
                "recent": recent
            }

        # Old + Middle
        old = remaining[:-compact_middle]
        middle = remaining[-compact_middle:]

        logger.debug(
            f"Partitioned messages: system={len(system_messages)}, "
            f"old={len(old)}, middle={len(middle)}, recent={len(recent)}"
        )

        return {
            "system": system_messages,
            "old": old,
            "middle": middle,
            "recent": recent
        }

    async def _compress_partitioned(
        self,
        partitioned: Dict[str, List[BaseMessage]],
        strategy: Literal["compact", "summarize"],
        model_invoker: Callable
    ) -> List[BaseMessage]:
        """
        压缩分层后的消息

        策略：
        - compact: Old + Middle 都使用详细摘要
        - summarize: Old 使用极简摘要，Middle 使用详细摘要
        """
        compressed = []

        # 1. 保留 SystemMessage
        compressed.extend(partitioned["system"])

        # 2. 压缩 Old
        if partitioned["old"]:
            old_strategy = "summarize" if strategy == "summarize" else "compact"
            old_summary = await self._summarize_messages(
                partitioned["old"],
                old_strategy,
                model_invoker
            )
            compressed.append(SystemMessage(content=f"""# 对话历史摘要（系统自动生成）

以下是早期对话的 {old_strategy} 摘要（原始 {len(partitioned["old"])} 条消息）：

{old_summary}

---
📝 本消息由系统自动生成，用于节省 token。
"""))

        # 3. 压缩 Middle
        if partitioned["middle"]:
            middle_summary = await self._summarize_messages(
                partitioned["middle"],
                "compact",  # Middle 总是使用详细摘要
                model_invoker
            )
            compressed.append(SystemMessage(content=f"""# 近期对话摘要（系统自动生成）

以下是近期对话的 compact 摘要（原始 {len(partitioned["middle"])} 条消息）：

{middle_summary}

---
📝 本消息由系统自动生成，用于节省 token。
"""))

        # 4. 保留 Recent（完整）
        compressed.extend(partitioned["recent"])

        return compressed

    async def _summarize_messages(
        self,
        messages: List[BaseMessage],
        strategy: Literal["compact", "summarize"],
        model_invoker: Callable
    ) -> str:
        """
        使用 LLM 生成摘要

        Args:
            messages: 待摘要的消息
            strategy: compact (详细) or summarize (简洁)
            model_invoker: LLM 调用函数

        Returns:
            摘要文本
        """
        # 选择 Prompt
        prompt = COMPACT_PROMPT if strategy == "compact" else SUMMARIZE_PROMPT

        # 构造输入
        messages_text = self._format_messages_for_summary(messages)
        full_prompt = f"{prompt}\n\n{messages_text}"

        # 调用 LLM
        summary = await model_invoker(full_prompt)

        return summary.strip()

    def _format_messages_for_summary(self, messages: List[BaseMessage]) -> str:
        """将消息格式化为文本（供 LLM 摘要）"""
        formatted = []

        for msg in messages:
            role = msg.__class__.__name__.replace("Message", "")
            content = str(msg.content)[:2000]  # 限制长度

            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                tools = ", ".join(tc.get("name", "unknown") for tc in msg.tool_calls)
                formatted.append(f"[{role}] 调用工具: {tools}")
            elif isinstance(msg, ToolMessage):
                tool_name = getattr(msg, 'name', 'unknown')
                formatted.append(f"[{role}:{tool_name}] {content[:500]}...")
            else:
                formatted.append(f"[{role}] {content}")

        return "\n\n".join(formatted)

    def _estimate_tokens(self, messages: List[BaseMessage]) -> int:
        """
        粗略估算 token 数

        使用简单的字符数估算：
        - 中文: ~1.5 chars/token
        - 英文: ~4 chars/token
        - 平均: ~2 chars/token
        """
        total_chars = sum(len(str(m.content)) for m in messages)
        return total_chars // 2  # 粗略估算
