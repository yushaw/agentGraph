"""Agent nodes for handoff pattern.

Each agent (simple, general, etc.) gets its own node in the graph.
These nodes handle the execution of specialized agents and return control
when tasks are complete.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage
from langgraph.types import Command

from generalAgent.utils.error_handler import with_error_boundary
from generalAgent.utils.logging_utils import log_node_entry

if TYPE_CHECKING:
    from generalAgent.graph.state import AppState

LOGGER = logging.getLogger(__name__)


def build_simple_agent_node():
    """Build SimpleAgent node for handoff pattern.

    SimpleAgent characteristics:
    - Stateless, single-turn execution
    - Uses reasoning model for complex tasks
    - Returns result and hands back control to main agent

    Returns:
        Callable: simple_agent node function
    """

    @with_error_boundary("simple_agent")
    async def simple_agent_node(state: AppState) -> Command:
        """Execute SimpleAgent and return result to main agent.

        Args:
            state: Current graph state

        Returns:
            Command: Command object to return to main agent
        """
        log_node_entry(LOGGER, "simple_agent", state)

        # Import SimpleAgent
        try:
            from simpleAgent.simple_agent import SimpleAgent
        except ImportError as e:
            error_msg = f"Failed to import SimpleAgent: {e}\n\nPlease ensure simpleAgent is available."
            LOGGER.error(error_msg)

            return Command(
                goto="agent",  # Return to main agent
                update={
                    "messages": [AIMessage(content=f"Error: {error_msg}")],
                    "current_agent": "agent",
                },
            )

        # Get the task (last message)
        messages = state.get("messages", [])
        if not messages:
            error_msg = "No messages in state for SimpleAgent"
            LOGGER.error(error_msg)
            return Command(
                goto="agent",
                update={
                    "messages": [AIMessage(content=f"Error: {error_msg}")],
                    "current_agent": "agent",
                },
            )

        last_message = messages[-1]
        task = last_message.content if hasattr(last_message, "content") else str(last_message)

        LOGGER.info(f"SimpleAgent executing task: {task[:100]}...")

        # Execute SimpleAgent
        try:
            # Create SimpleAgent instance
            # Note: SimpleAgent.run() is a synchronous method
            agent = SimpleAgent()

            # Get workspace path (for file access)
            workspace_path = state.get("workspace_path")
            if workspace_path:
                import os
                os.environ["AGENT_WORKSPACE_PATH"] = workspace_path
                LOGGER.debug(f"Set AGENT_WORKSPACE_PATH={workspace_path}")

            # Run SimpleAgent (synchronous call)
            # SimpleAgent returns a string result
            result = agent.run(task)

            LOGGER.info(f"SimpleAgent completed successfully")
            LOGGER.debug(f"Result: {result[:200]}...")

            # 弹出调用栈（返回时从栈中移除自己）
            agent_call_stack = state.get("agent_call_stack", [])
            if agent_call_stack and agent_call_stack[-1] == "simple":
                agent_call_stack = agent_call_stack[:-1]
                LOGGER.debug(f"Popped 'simple' from call stack: {agent_call_stack}")

            # Return to main agent with result
            return Command(
                goto="agent",  # Return to main agent
                update={
                    "messages": [AIMessage(content=result)],
                    "agent_call_stack": agent_call_stack,  # 更新调用栈
                    "current_agent": "agent",  # Reset to main agent
                },
            )

        except Exception as e:
            error_msg = f"SimpleAgent execution failed: {e}"
            LOGGER.error(error_msg, exc_info=True)

            # 错误时也要弹出调用栈
            agent_call_stack = state.get("agent_call_stack", [])
            if agent_call_stack and agent_call_stack[-1] == "simple":
                agent_call_stack = agent_call_stack[:-1]

            return Command(
                goto="agent",
                update={
                    "messages": [AIMessage(content=f"Error during SimpleAgent execution: {e}")],
                    "agent_call_stack": agent_call_stack,
                    "current_agent": "agent",
                },
            )

    return simple_agent_node


def build_agent_node_from_card(agent_card):
    """Build agent node dynamically from AgentCard.

    This is a factory function that creates agent nodes based on AgentCard metadata.

    Args:
        agent_card: AgentCard instance

    Returns:
        Callable: agent node function

    Raises:
        NotImplementedError: If agent type is not supported yet
    """
    agent_id = agent_card.id

    # Route to specific agent builder
    if agent_id == "simple":
        return build_simple_agent_node()
    elif agent_id == "general":
        # Future: implement general agent node
        raise NotImplementedError(f"GeneralAgent node not implemented yet")
    else:
        raise ValueError(f"Unknown agent type: {agent_id}")
