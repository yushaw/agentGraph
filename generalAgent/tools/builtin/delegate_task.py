"""Delegate complex tasks to an isolated agent - Claude Code style."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Optional, Annotated

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool, InjectedToolArg
from langgraph.types import Command

# Module-level variables to store app graph and parent state (set by runtime/planner)
# Changed from ContextVar to simple module variable to avoid async context issues
_app_graph: Optional[Any] = None
_parent_state_store: dict[str, dict] = {}  # {thread_id: parent_state}


def set_app_graph(app_graph):
    """Set the application graph for delegated task execution.

    Called by runtime after graph is built.
    """
    global _app_graph
    _app_graph = app_graph


def set_parent_state(thread_id: str, state: dict):
    """Store parent state for subagent inheritance.

    Called by planner before tool execution.
    """
    global _parent_state_store
    _parent_state_store[thread_id] = state


@tool
async def delegate_task(
    task: str,
    max_loops: int = 50,
    config: Annotated[dict, InjectedToolArg] = None,
) -> str:
    """将独立子任务委派给专用子 agent 执行（适合需要多轮迭代的任务）

    ⚠️ **重要：子 agent 继承主 agent 的工具和技能**
    - 子 agent 看不到主对话历史（独立上下文）

    **何时使用：**
    - 需要多轮工具调用的复杂子任务（深度研究、反复尝试、大文档分析）
    - 可能产生大量中间结果的任务（网页搜索、多次搜索、批量文件处理），避免污染主对话

    **任务描述要求：**
    必须包含：
    1. 目标是什么
    2. 需要哪些上下文信息
    3. 期望的返回格式（Markdown 表格、JSON、文本摘要等）

    Args:
        task: 详细的任务描述（必须自包含！）

    Examples:
        # 深度搜索
        delegate_task("搜索 src/ 目录下所有使用 old_api() 的代码。"
                      "要求：记录文件路径、行号、调用上下文。"
                      "返回：Markdown 表格 [文件 | 行号 | 代码片段]")

        # 反复调试
        delegate_task("运行脚本 scripts/migrate.py，如果出错则分析并修复，重复直到成功。"
                      "返回：1) 最终可运行的代码，2) 遇到的问题和解决方案")

        # 大文档分析
        delegate_task("分析 uploads/report.pdf（80页）："
                      "1) 提取所有表格数据"
                      "2) 计算关键指标（收入、支出、利润）"
                      "返回：结构化 JSON")
    """
    try:
        # Get app graph from module variable
        app_graph = _app_graph
        if app_graph is None:
            return json.dumps({
                "ok": False,
                "error": "Application graph not initialized",
            }, ensure_ascii=False)

        # Get parent state from config (injected by LangGraph)
        parent_state = {}
        parent_thread_id = None
        if config:
            configurable = config.get("configurable", {})
            parent_thread_id = configurable.get("thread_id")
            if parent_thread_id and parent_thread_id in _parent_state_store:
                parent_state = _parent_state_store[parent_thread_id]

        # Generate unique context ID
        context_id = f"subagent-{uuid.uuid4().hex[:8]}"

        # Inherit from parent state
        parent_mentioned_agents = parent_state.get("mentioned_agents", [])
        parent_active_skill = parent_state.get("active_skill")
        parent_workspace = parent_state.get("workspace_path")
        parent_uploaded_files = parent_state.get("uploaded_files", [])

        # Create independent state for delegated agent
        delegated_state = {
            "messages": [HumanMessage(content=task)],
            "images": [],
            "active_skill": parent_active_skill,  # Inherit active skill
            "allowed_tools": [],
            "mentioned_agents": list(parent_mentioned_agents),  # Inherit @mentions
            "new_mentioned_agents": [],  # No new mentions initially
            "persistent_tools": [],
            "model_pref": None,
            "todos": [],
            "context_id": context_id,
            "parent_context": parent_state.get("context_id", "main"),
            "loops": 0,
            "max_loops": max_loops,
            "thread_id": context_id,  # Use context_id as thread_id for isolation
            "user_id": parent_state.get("user_id"),
            "workspace_path": parent_workspace,  # Inherit workspace
            "uploaded_files": list(parent_uploaded_files),  # Inherit uploaded files
            "new_uploaded_files": [],  # No new uploads initially
        }

        # Run delegated agent in isolated context with streaming
        config = {"configurable": {"thread_id": context_id}}

        print(f"\n[subagent-{context_id[:8]}] Starting execution...")

        final_state = None
        message_count = 1  # Start at 1 (user message already there)

        # Use astream for real-time output with interrupt handling
        async for state_snapshot in app_graph.astream(
            delegated_state,
            config=config,
            stream_mode="values"
        ):
            final_state = state_snapshot

            # Print new messages
            current_messages = state_snapshot.get("messages", [])
            for idx in range(message_count, len(current_messages)):
                msg = current_messages[idx]

                # Determine message type and content
                if hasattr(msg, "content"):
                    content = str(msg.content)
                    if hasattr(msg, "type"):
                        msg_type = msg.type
                    else:
                        msg_type = msg.__class__.__name__

                    # Print based on type
                    if msg_type in {"ai", "AIMessage"}:
                        if content:
                            print(f"[subagent-{context_id[:8]}] {content}")
                    elif msg_type in {"tool", "ToolMessage"}:
                        # Print tool calls concisely
                        tool_name = getattr(msg, "name", "tool")
                        if content:
                            print(f"[subagent-{context_id[:8]}] [tool: {tool_name}] {content[:100]}...")

            message_count = len(current_messages)

        # Handle interrupts (e.g., ask_human)
        while True:
            graph_state = await app_graph.aget_state(config)

            # Check if there are any interrupts
            if (graph_state.next and graph_state.tasks and
                hasattr(graph_state.tasks[0], 'interrupts') and
                graph_state.tasks[0].interrupts):

                # Get interrupt data
                interrupt_value = graph_state.tasks[0].interrupts[0].value
                interrupt_type = interrupt_value.get("type", "generic")

                if interrupt_type == "user_input_request":
                    # Handle ask_human request
                    question = interrupt_value.get("question", "")
                    context_info = interrupt_value.get("context", "")
                    default = interrupt_value.get("default")

                    # Print question with subagent prefix
                    print()
                    if context_info:
                        print(f"[subagent-{context_id[:8]}] 💡 {context_info}")
                    print(f"[subagent-{context_id[:8]}] 💬 {question}")
                    if default:
                        print(f"[subagent-{context_id[:8]}]    (默认: {default})")

                    # Get user input (synchronous in async context)
                    loop = asyncio.get_event_loop()
                    answer = await loop.run_in_executor(None, lambda: input("> ").strip())

                    # Handle empty answer
                    if not answer and default:
                        answer = default
                        print(f"[subagent-{context_id[:8]}] ✓ 使用默认值: {default}")

                    # Resume execution with answer
                    async for state_snapshot in app_graph.astream(
                        Command(resume=answer),
                        config=config,
                        stream_mode="values"
                    ):
                        final_state = state_snapshot

                        # Print new messages
                        current_messages = state_snapshot.get("messages", [])
                        for idx in range(message_count, len(current_messages)):
                            msg = current_messages[idx]
                            if hasattr(msg, "content"):
                                content = str(msg.content)
                                msg_type = getattr(msg, "type", msg.__class__.__name__)
                                if msg_type in {"ai", "AIMessage"} and content:
                                    print(f"[subagent-{context_id[:8]}] {content}")

                        message_count = len(current_messages)
                else:
                    # Unknown interrupt type, skip
                    print(f"[subagent-{context_id[:8]}] ⚠️ Unknown interrupt type: {interrupt_type}")
                    break
            else:
                # No more interrupts, execution complete
                break

        print(f"[subagent-{context_id[:8]}] Completed\n")

        # Extract result from final message
        if final_state:
            messages = final_state.get("messages", [])
            if messages:
                last_message = messages[-1]
                result_text = getattr(last_message, "content", "No response")
            else:
                result_text = "No response from delegated agent"

            # Check if result is too brief (< 200 chars), request more detailed summary (max 1 retry)
            if len(result_text) < 200:
                print(f"[subagent-{context_id[:8]}] ⚠️ 结果太简短（{len(result_text)} chars），请求更详细的摘要...\n")

                # Create continuation prompt
                continuation_prompt = HumanMessage(content="""你的上一次回复太简短了（< 200 字符）。

请提供更详细的摘要，包括：
1. 你做了什么（使用了哪些工具，读取了哪些文件）
2. 发现了什么（关键信息、错误、解决方案）
3. 结果是什么（文件路径、函数名、配置等）

**重要**：主 Agent 无法看到你的工具调用历史，只能看到你的最终回复！""")

                # Continue execution with the continuation prompt
                message_count = len(messages)  # Reset counter for continuation
                async for state_snapshot in app_graph.astream(
                    {**final_state, "messages": messages + [continuation_prompt]},
                    config=config,
                    stream_mode="values"
                ):
                    final_state = state_snapshot

                    # Print new messages
                    current_messages = state_snapshot.get("messages", [])
                    for idx in range(message_count, len(current_messages)):
                        msg = current_messages[idx]
                        if hasattr(msg, "content"):
                            content = str(msg.content)
                            msg_type = getattr(msg, "type", msg.__class__.__name__)
                            if msg_type in {"ai", "AIMessage"} and content:
                                print(f"[subagent-{context_id[:8]}] {content}")

                    message_count = len(current_messages)

                print(f"[subagent-{context_id[:8]}] Continuation completed\n")

                # Re-extract the final result
                messages = final_state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    result_text = getattr(last_message, "content", "No response")

            return json.dumps({
                "ok": True,
                "result": result_text,
                "context_id": context_id,
                "loops": final_state.get("loops", 0),
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "ok": False,
                "error": "Delegated agent execution produced no final state",
            }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": f"Delegated agent execution failed: {str(e)}",
        }, ensure_ascii=False)


__all__ = ["delegate_task", "set_parent_state"]
