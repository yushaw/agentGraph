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

COMPACT_PROMPT = """你的任务是为一个通用 AI 助手的对话历史创建详细摘要。

**摘要要求：**
请按时间顺序分析对话，提取以下关键信息：

1. **用户请求和意图**
   - 明确记录用户的所有请求和意图

2. **关键信息**
   - 提到的重要概念、专业术语
   - 数据、事实、时间点

3. **文件操作**
   - 提到的文件路径（如 `uploads/report.pdf`, `outputs/result.txt`）
   - 文件内容摘要、操作原因

4. **工具调用记录**
   - 记录工具调用及结果
   - 格式：`工具名(参数) → 结果`

5. **技能使用**
   - 使用的技能（如 @pdf, @docx）及用途

6. **错误和修复**
   - 遇到的错误、问题
   - 解决方法和用户反馈

7. **当前工作**
   - 最新的工作进展
   - 待完成的事项（用户明确提到的）

**输出格式：**
请使用以下结构提供摘要：

## 用户请求和意图
[详细描述]

## 关键信息
- [信息 1]
- [信息 2]
...

## 文件操作
- **文件路径 1**
  - 操作原因: ...
  - 更改摘要: ...
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

## 当前工作
[详细描述当前正在进行的工作]

---

**重要提示：**
- 保持简洁（控制在 2000 字以内）
- 不要输出 TODO 列表（系统会动态追踪）
- 仅输出摘要内容，不要包含额外说明或元数据

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
        model_invoker: Callable,  # 用于调用 LLM 的函数
        context_window: int = 128000  # 模型的 context window
    ) -> CompressionResult:
        """
        执行消息压缩

        Args:
            messages: 待压缩的消息列表
            model_invoker: LLM 调用函数
            context_window: 模型的 context window 大小

        Returns:
            CompressionResult 包含压缩后的消息和详细报告
        """
        logger.info("Starting context compression")

        # 2. 记录压缩前状态
        before_count = len(messages)
        before_tokens = self._estimate_tokens(messages)

        # 3. 分层消息
        partitioned = self._partition_messages(messages, context_window)

        # 4. 执行压缩
        try:
            compressed = await self._compress_partitioned(
                partitioned,
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
        else:
            strategy = "compact"

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
        context_window: int
    ) -> Dict[str, List[BaseMessage]]:
        """
        划分消息（混合策略：Token 比例 + 消息数）

        策略：
        - System: 保留所有 SystemMessage
        - Recent: 保留最近 N% context window 或 M 条消息（取先到者）
        - Old: 剩余所有消息（将被压缩）
        """
        # 1. 分离 SystemMessage
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        # 2. 配置（根据 context window 计算实际 token 数）
        keep_recent_tokens = int(context_window * self.context_settings.keep_recent_ratio)
        keep_recent_messages = self.context_settings.keep_recent_messages

        logger.debug(
            f"Partition config: keep_recent={keep_recent_tokens} tokens or {keep_recent_messages} msgs "
            f"(context_window={context_window})"
        )

        # 3. 估算每条消息的 token（粗略）
        message_tokens = [self._estimate_single_message_tokens(m) for m in non_system_messages]

        # 4. 从后往前扫描，划分 Recent
        recent_tokens = 0
        recent_count = 0
        for i in range(len(non_system_messages) - 1, -1, -1):
            recent_tokens += message_tokens[i]
            recent_count += 1

            # 达到任一条件就停止
            if recent_tokens >= keep_recent_tokens or recent_count >= keep_recent_messages:
                break

        recent = non_system_messages[-recent_count:] if recent_count > 0 else []
        old = non_system_messages[:-recent_count] if recent_count > 0 else non_system_messages

        old_tokens = sum(message_tokens[:len(old)]) if old else 0

        logger.debug(
            f"Partitioned messages: system={len(system_messages)}, "
            f"old={len(old)} (~{old_tokens} tokens), "
            f"recent={len(recent)} (~{recent_tokens} tokens)"
        )

        return {
            "system": system_messages,
            "old": old,
            "middle": [],  # 保持兼容性，但为空
            "recent": recent
        }

    def _estimate_single_message_tokens(self, msg: BaseMessage) -> int:
        """估算单条消息的 token（粗略）

        使用简单的字符数估算：
        - 中文平均 1 token ≈ 2 chars
        - 英文平均 1 token ≈ 4 chars
        - 取平均值: 1 token ≈ 2 chars
        """
        content_len = len(str(msg.content))
        return content_len // 2

    async def _compress_partitioned(
        self,
        partitioned: Dict[str, List[BaseMessage]],
        model_invoker: Callable
    ) -> List[BaseMessage]:
        """
        压缩分层后的消息

        策略：一次性压缩 Old + Middle，只保留 Recent
        """
        compressed = []

        # 1. 保留 SystemMessage
        compressed.extend(partitioned["system"])

        # 2. 合并 Old + Middle，一次性压缩
        messages_to_compress = partitioned["old"] + partitioned["middle"]

        if messages_to_compress:
            logger.info(f"Compressing {len(messages_to_compress)} messages (Old + Middle) in single LLM call")
            summary = await self._summarize_messages(
                messages_to_compress,
                model_invoker
            )
            compressed.append(SystemMessage(content=f"""# 对话历史摘要（系统自动生成）

以下是早期对话的摘要（原始 {len(messages_to_compress)} 条消息）：

{summary}

---
📝 本消息由系统自动生成，用于节省 token。
"""))

        # 3. 保留 Recent（完整），但需要清理孤儿 ToolMessage
        recent_messages = partitioned["recent"]
        cleaned_recent = self._clean_orphan_tool_messages(recent_messages)
        compressed.extend(cleaned_recent)

        return compressed

    def _clean_orphan_tool_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        清理孤儿 ToolMessage（没有对应 tool_call 的 ToolMessage）

        在压缩后，如果 AIMessage (包含 tool_calls) 被压缩掉了，
        但对应的 ToolMessage 被保留在 Recent 中，会导致 API 错误。

        Args:
            messages: 消息列表

        Returns:
            清理后的消息列表
        """
        if not messages:
            return messages

        # 收集所有 tool_call_id
        valid_tool_call_ids = set()
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    if 'id' in tc:
                        valid_tool_call_ids.add(tc['id'])

        # 过滤掉孤儿 ToolMessage
        cleaned = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                # 检查是否有对应的 tool_call_id
                tool_call_id = getattr(msg, 'tool_call_id', None)
                if tool_call_id and tool_call_id in valid_tool_call_ids:
                    cleaned.append(msg)
                else:
                    logger.debug(f"Removing orphan ToolMessage: tool_call_id={tool_call_id}")
            else:
                cleaned.append(msg)

        return cleaned

    async def _summarize_messages(
        self,
        messages: List[BaseMessage],
        model_invoker: Callable
    ) -> str:
        """
        使用 LLM 生成摘要

        Args:
            messages: 待摘要的消息
            model_invoker: LLM 调用函数（接受 prompt 和 max_tokens）

        Returns:
            摘要文本
        """
        # 构造输入
        messages_text = self._format_messages_for_summary(messages)
        full_prompt = f"{COMPACT_PROMPT}\n\n{messages_text}"

        # 调用 LLM（限制输出长度为 2000 字）
        # 中文: 1 token ≈ 1.5-2 字符，2000 字 ≈ 1200 tokens
        # 加 20% buffer: 1200 * 1.2 = 1440 tokens
        summary = await model_invoker(full_prompt, max_tokens=1440)

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
