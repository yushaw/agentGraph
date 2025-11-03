"""Host Planner Node - Orchestration-focused agent node.

The Host Planner is the "manager" node that:
1. Understands user's complex goals
2. Decomposes into sub-tasks
3. Delegates to Workers via delegate_task
4. Monitors progress and decides next steps
5. Reports final results via done_and_report

Key Differences from generalAgent planner:
- Hardcoded SystemMessage emphasizing "manager" role
- No skill loading (@mention not supported)
- No dynamic tool loading (fixed toolset)
- Simplified context (no images, no skills)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from langchain_core.messages import SystemMessage, RemoveMessage
from langgraph.types import interrupt

from orchestrationAgent.graph.state import OrchestrationState
from generalAgent.models import ModelRegistry
from generalAgent.tools import ToolRegistry
from generalAgent.config.settings import Settings

LOGGER = logging.getLogger(__name__)


def build_host_planner_node(
    *,
    model_registry: ModelRegistry,
    model_resolver,
    tool_registry: ToolRegistry,
    settings: Settings,
) -> Callable:
    """Build the Host Planner node.

    Args:
        model_registry: Model registry
        model_resolver: Model resolver (function to get model instances)
        tool_registry: Tool registry (should only contain orchestration tools)
        settings: Application settings

    Returns:
        Async function that processes OrchestrationState
    """

    async def host_planner_node(state: OrchestrationState) -> dict:
        """Host Planner Node - Manager that decomposes and delegates tasks.

        Workflow:
        1. Build SystemMessage (manager role + tool catalog)
        2. Append dynamic reminders (TODOs, uploaded files)
        3. Call LLM with orchestration tools
        4. Check for interrupts (ask_human)
        5. Monitor token usage (trigger compression if needed)
        6. Return updated state
        """
        # ========== Step 1: Build SystemMessage ==========
        system_message = _build_system_message(
            tool_registry=tool_registry,
            settings=settings,
        )

        # ========== Step 2: Build Dynamic Reminders ==========
        reminders = _build_dynamic_reminders(state)

        # ========== Step 3: Prepare Messages ==========
        messages = state.get("messages", [])

        # Remove old SystemMessage if exists
        messages_to_send = [msg for msg in messages if not isinstance(msg, SystemMessage)]

        # Prepend SystemMessage
        messages_to_send = [system_message] + messages_to_send

        # Append reminders to last HumanMessage (KV cache optimization)
        if messages_to_send and reminders:
            last_msg = messages_to_send[-1]
            if hasattr(last_msg, "content") and hasattr(last_msg, "type"):
                if last_msg.type == "human":
                    # Append reminders
                    last_msg.content = f"{last_msg.content}\n\n{reminders}"

        # ========== Step 4: Get Tools ==========
        # Host has fixed toolset (no dynamic loading)
        enabled_tools = list(tool_registry._tools.values())

        # ========== Step 5: Call LLM ==========
        # Use model registry to choose appropriate model
        model_spec = model_registry.prefer(
            phase="plan",
            require_tools=True,
            need_code=False,
            need_vision=False,
        )
        # Resolve actual model instance
        model = model_resolver(model_spec.model_id)
        model_with_tools = model.bind_tools(enabled_tools)

        LOGGER.info(f"[Host Planner] Calling LLM with {len(enabled_tools)} tools")

        response = await model_with_tools.ainvoke(messages_to_send)

        # ========== Step 6: Check for Interrupts ==========
        # If LLM called ask_human, we need to interrupt and wait for user input
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "ask_human":
                    # Extract question from tool call args
                    args = tool_call.get("args", {})
                    question = args.get("question", "")
                    context = args.get("context", "")
                    default = args.get("default")

                    # Interrupt execution (CLI will handle user input)
                    interrupt({
                        "type": "user_input_request",
                        "question": question,
                        "context": context,
                        "default": default,
                    })

        # ========== Step 7: Monitor Token Usage ==========
        needs_compression = False
        cumulative_tokens = state.get("cumulative_prompt_tokens", 0)

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = response.usage_metadata.get("input_tokens", 0)
            cumulative_tokens += prompt_tokens

            # Check if we need compression (>95% of context window)
            if settings.context.enabled:
                context_window = 128000  # Default for most models
                usage_ratio = cumulative_tokens / context_window

                if usage_ratio >= settings.context.critical_threshold:
                    LOGGER.warning(
                        f"[Host Planner] Token usage critical: "
                        f"{cumulative_tokens}/{context_window} ({usage_ratio:.1%})"
                    )
                    needs_compression = True

        # ========== Step 8: Update State ==========
        loops = state.get("loops", 0) + 1

        return {
            "messages": [response],
            "loops": loops,
            "cumulative_prompt_tokens": cumulative_tokens,
            "needs_compression": needs_compression,
        }

    return host_planner_node


def _build_system_message(
    *,
    tool_registry: ToolRegistry,
    settings: Settings,
) -> SystemMessage:
    """Build SystemMessage for Host (Manager role).

    This is a HARDCODED prompt emphasizing:
    - Host is a manager, not a worker
    - Host can only delegate, not execute
    - Workflow: ask_human → todo_write → delegate_task → done_and_report
    """
    # Get current time (minute-level precision for KV cache)
    now_utc = datetime.now(timezone.utc)
    current_datetime = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    # Build tool catalog
    tool_catalog = _build_tool_catalog(tool_registry)

    prompt = f"""你是 **Orchestration Agent**（编排代理），负责**拆解和委派任务**。

## 你的角色定位

你是一个 **AI 经理**，你的职责是：
1. **理解（Understand）**：接收用户的复杂、多步骤或模糊的目标
2. **拆解（Deconstruct）**：将目标拆解为具体的、可执行的子任务
3. **委派（Delegate）**：将子任务分配给你的 Worker Agent 执行
4. **监督（Supervise）**：接收 Worker 的工作汇报
5. **反馈（Feedback）**：评估结果，决定下一步（继续/重试/报告）

**重要限制**：
- ❌ 你不能直接读写文件、访问网络、运行代码
- ❌ 你不能执行具体的"劳动"工作
- ✅ 你只能通过委派工具来完成任务

---

## 你的团队

你手下有一个**通用 Worker Agent**，它具有以下能力：
- 文件操作（读写、搜索、分析文档）
- 网络操作（获取网页、搜索）
- 代码执行（运行脚本、安装依赖）
- 多轮推理（复杂任务需要多次工具调用）

你可以通过 `delegate_task` 工具来调用它。

---

## 你的工作流程

### 1. 接收任务后
- 检查任务是否明确（如果不明确，使用 `ask_human` 澄清）
- 思考需要拆解为几个子任务
- （可选）使用 `todo_write` 记录你的高层计划

### 2. 委派子任务
- 使用 `delegate_task(task="...", max_loops=50)` 工具
- `task` 参数必须**详细且自包含**：
  - 目标是什么
  - 需要哪些上下文信息
  - 期望的返回格式（Markdown 表格、JSON、文本摘要等）

示例：
```
delegate_task(
    task="分析文件 'uploads/report.pdf'（80页）。提取所有表格数据，计算关键指标（收入、支出、利润）。返回结构化 JSON。"
)
```

### 3. 接收结果
- Worker 会返回一个 JSON 对象：
  ```json
  {{
    "ok": true,
    "result": "...",
    "context_id": "subagent-xxx",
    "loops": 15
  }}
  ```
- 如果 `ok: false`，检查 `error` 字段，决定是否重试或修改任务

### 4. 决定下一步
- 如果还有子任务，继续委派
- 如果所有子任务完成，汇总结果
- 使用 `done_and_report(final_result="...")` 向用户报告最终成果

---

## 可用工具

{tool_catalog}

---

## 示例对话

**用户**：分析 doc1.pdf 和 doc2.pdf 的异同

**你的思考**：
1. 需要两个子任务：分析 doc1，分析 doc2
2. 然后对比结果

**你的动作**：
1. `todo_write([{{"content": "分析 doc1.pdf", ...}}, {{"content": "分析 doc2.pdf", ...}}, {{"content": "对比结果", ...}}])`
2. `delegate_task(task="分析文件 'uploads/doc1.pdf' 的内容，提取关键信息...")`
3. （接收结果）
4. `delegate_task(task="分析文件 'uploads/doc2.pdf' 的内容，提取关键信息...")`
5. （接收结果）
6. `done_and_report(final_result="以下是 doc1 和 doc2 的对比：\\n\\n...")`

---

## 注意事项

1. **任务描述要详细**：Worker 看不到你的上下文，必须在 `task` 参数中提供所有必要信息
2. **结果要汇总**：不要直接把 Worker 的原始输出转发给用户，要提炼和组织
3. **失败要处理**：如果 Worker 失败，分析原因，决定是重试、修改任务还是向用户报告
4. **进度要跟踪**：使用 `todo_write` 工具记录项目计划，避免"失忆"

---

<current_datetime>{current_datetime}</current_datetime>
"""

    return SystemMessage(content=prompt)


def _build_tool_catalog(tool_registry: ToolRegistry) -> str:
    """Build tool catalog for SystemMessage.

    Format:
    ### delegate_task
    委派独立子任务给 Worker Agent 执行
    - task: 详细的任务描述（必须自包含）
    - max_loops: 最大迭代次数（默认 50）
    """
    lines = []

    for tool in tool_registry._tools.values():
        # Get tool name
        name = tool.name

        # Get tool description
        description = tool.description or "（无描述）"

        # Get tool args schema
        args_schema = getattr(tool, "args_schema", None)
        if args_schema:
            args_lines = []
            schema_dict = args_schema.schema() if hasattr(args_schema, "schema") else {}
            properties = schema_dict.get("properties", {})
            required = schema_dict.get("required", [])

            for arg_name, arg_info in properties.items():
                arg_desc = arg_info.get("description", "")
                is_required = arg_name in required
                req_marker = "（必填）" if is_required else "（可选）"
                args_lines.append(f"  - `{arg_name}`: {arg_desc} {req_marker}")

            args_text = "\n".join(args_lines) if args_lines else "  （无参数）"
        else:
            args_text = "  （无参数）"

        lines.append(f"### {name}\n{description}\n{args_text}\n")

    return "\n".join(lines)


def _build_dynamic_reminders(state: OrchestrationState) -> str:
    """Build dynamic reminders (appended to last HumanMessage).

    Includes:
    - TODOs (if any)
    - Uploaded files (if any)
    """
    reminders = []

    # === TODO Reminders ===
    todos = state.get("todos", [])
    if todos:
        todo_lines = ["## 当前项目计划（TODOs）\n"]
        for idx, todo in enumerate(todos, 1):
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
            }.get(status, "")
            todo_lines.append(f"{idx}. {status_emoji} [{status}] {content}")

        reminders.append("\n".join(todo_lines))

    # === Uploaded Files ===
    uploaded_files = state.get("uploaded_files", [])
    if uploaded_files:
        file_lines = ["## 用户上传的文件\n"]
        for file_info in uploaded_files:
            path = file_info.get("path", "")
            name = file_info.get("name", "")
            file_type = file_info.get("type", "")
            file_lines.append(f"- `{path}` ({file_type})")

        reminders.append("\n".join(file_lines))

    return "\n\n".join(reminders) if reminders else ""


__all__ = ["build_host_planner_node"]
