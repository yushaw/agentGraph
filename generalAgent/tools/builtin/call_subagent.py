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
    """Execute a task in an isolated subagent context.

    Use this tool for context isolation when:
    - Complex multi-step tasks that need independent execution
    - Uncertain searches requiring multiple rounds
    - Tasks that would benefit from a fresh context

    Do NOT use when:
    - Reading specific files (use Read tool)
    - Searching 2-3 known files (search directly)
    - Simple single-step operations

    Args:
        task: Clear description of what the subagent should accomplish
        max_loops: Maximum loops for subagent execution (default: 10)

    Returns:
        JSON object with:
        - ok (bool): Whether execution succeeded
        - result (str): Subagent's final response
        - context_id (str): Subagent's context identifier
        - loops (int): Number of loops executed

    Example:
        call_subagent("Search the codebase for authentication implementation and summarize how it works")
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
