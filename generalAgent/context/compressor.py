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

COMPACT_PROMPT = """你的任务是为一个通用 AI 助手的对话历史创建详细摘要，以便恢复完整上下文。

请**按时间顺序逐段分析**对话历史，对每个重要片段识别：
- 用户的明确请求（原话是什么）
- 助手的处理方法和决策
- 关键操作和结果
- 用户的反馈（特别是纠正、偏好、新要求）

**摘要要求：**

1. **用户请求和意图**（按时间顺序）
   - 记录用户的**所有明确请求**（保留原始表述）
   - 区分明确请求 vs 推断意图
   - 标注请求之间的依赖关系（如"基于前面的结果..."）
   - **重要**：捕获用户的纠正和偏好（如"不要这样做"、"我更喜欢..."）

2. **决策和推理过程**
   - 助手为什么采取某个方法（技术决策）
   - 遇到的选择点和最终决策
   - 用户对方法的反馈（接受/拒绝/修改）

3. **关键信息和上下文**
   - 重要概念、专业术语、领域知识
   - 具体数据、事实、时间点、配置参数
   - 用户提供的背景信息（需求场景、约束条件）

4. **文件操作**
   - 文件路径：`uploads/report.pdf`, `outputs/result.txt`
   - 操作类型：读取/写入/修改/搜索
   - 文件内容摘要（关键信息）
   - 操作原因和影响

5. **工具和技能使用**
   - 工具调用：`tool_name(参数)` → 结果
   - 技能加载：@skill_name 及使用场景
   - 调用原因和效果

6. **错误、问题和解决**
   - 错误描述（包含错误信息片段）
   - 根本原因分析
   - 解决方法（具体步骤）
   - **重要**：用户对解决方案的反馈

7. **当前状态**
   - 最新完成的工作
   - 待完成任务（仅用户明确提到的，不要推测）
   - 可能影响后续工作的重要上下文

---

**输出格式：**

## 1. 用户请求时间线

**第一阶段**（对话开始 - XX轮）：
- 用户请求："[原话]"
- 助手方法：[简要说明]
- 用户反馈：[接受/修改/拒绝]

**第二阶段**（XX - XX轮）：
- ...

## 2. 关键决策和推理

- **决策点1**：[问题描述]
  - 选择：[最终方案]
  - 理由：[为什么]
  - 结果：[效果如何]

## 3. 重要信息

**领域知识/概念**：
- [概念1]：[说明]

**数据和事实**：
- [关键数据]

**配置和参数**：
- [参数名]=<value>

## 4. 文件操作记录

- `uploads/file.pdf`
  - 操作：读取（第X轮）
  - 内容：[关键内容摘要]
  - 用途：[为什么操作]

## 5. 工具和技能

**工具调用**：
- `tool_name(args)` → 结果（第X轮）
  - 目的：[为什么调用]

**技能使用**：
- @skill：[使用场景]

## 6. 错误和解决

- **错误**：[描述 + 错误信息片段]
  - 原因：[根因]
  - 解决：[具体步骤]
  - 反馈：[用户是否满意]

## 7. 当前状态

**已完成**：
- [最新完成的工作]

**待完成**（用户明确要求）：
- [任务1]
- [任务2]

**重要上下文**：
- [可能影响后续的信息]

---

**输出要求：**
- 保持简洁（≤2000字）
- 不要输出TODO列表（系统会动态追踪）
- 不要添加元数据或说明性文字
- 保留用户原话中的关键措辞
- 优先记录用户反馈和纠正

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
