"""Subagent tool for context isolation - Claude Code style."""

from __future__ import annotations

import json
import uuid
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

# Context variable to store app graph (set by runtime)
_app_graph_ctx: ContextVar[Optional[Any]] = ContextVar("app_graph", default=None)


def set_app_graph(app_graph):
    """Set the application graph for subagent execution.

    Called by runtime after graph is built.
    """
    _app_graph_ctx.set(app_graph)


@tool
async def call_subagent(task: str, max_loops: int = 10) -> str:
    """Launch isolated subagent for complex multi-step tasks. Has access to all tools.

    Use when: Multi-step research, uncertain searches, complex file analysis
    Don't use: Reading known files, simple 1-step tasks, non-tool tasks

    IMPORTANT:
    - Subagent is stateless (cannot send follow-up messages)
    - Provide detailed self-contained task description
    - Specify what info to return in final response
    - Result not visible to user - you must summarize it
    - When ok: true, task complete - don't retry

    Args:
        task: Detailed task (what to do, what to return, research vs code)
        max_loops: Max execution loops (default: 10)

    Returns:
        JSON: {ok: bool, result: str, context_id: str, loops: int}

    Examples:
        call_subagent("Find authentication implementation, explain how login works, return function signatures with file paths")
        call_subagent("Find all API endpoints. List HTTP method, path, handler, file location for each")
        call_subagent("Locate database connection in config/, db/, models/. Return connection function and explain config")
    """
    try:
        # Get app graph from context
        app_graph = _app_graph_ctx.get()
        if app_graph is None:
            return json.dumps({
                "ok": False,
                "error": "Application graph not initialized",
            }, ensure_ascii=False)

        # Generate unique context ID
        context_id = f"subagent-{uuid.uuid4().hex[:8]}"

        # Create independent state for subagent
        subagent_state = {
            "messages": [HumanMessage(content=task)],
            "images": [],
            "active_skill": None,
            "allowed_tools": [],
            "mentioned_agents": [],
            "persistent_tools": [],
            "model_pref": None,
            "todos": [],
            "context_id": context_id,
            "parent_context": "main",  # TODO: Get from current context
            "loops": 0,
            "max_loops": max_loops,
            "thread_id": context_id,  # Use context_id as thread_id for isolation
            "user_id": None,
        }

        # Run subagent in isolated context with streaming
        config = {"configurable": {"thread_id": context_id}}

        print(f"\n[subagent-{context_id[:8]}] Starting execution...")

        final_state = None
        message_count = 1  # Start at 1 (user message already there)

        # Use astream for real-time output
        async for state_snapshot in app_graph.astream(
            subagent_state,
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

        print(f"[subagent-{context_id[:8]}] Completed\n")

        # Extract result from final message
        if final_state:
            messages = final_state.get("messages", [])
            if messages:
                last_message = messages[-1]
                result_text = getattr(last_message, "content", "No response")
            else:
                result_text = "No response from subagent"

            return json.dumps({
                "ok": True,
                "result": result_text,
                "context_id": context_id,
                "loops": final_state.get("loops", 0),
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "ok": False,
                "error": "Subagent execution produced no final state",
            }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": f"Subagent execution failed: {str(e)}",
        }, ensure_ascii=False)
