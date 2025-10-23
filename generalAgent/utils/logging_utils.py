"""Logging utilities for AgentGraph."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Generate log filename with timestamp
LOG_FILE = LOGS_DIR / f"agentgraph_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Setup logging configuration for AgentGraph.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    # Create root logger for agentgraph
    logger = logging.getLogger("agentgraph")
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all child logs
    logger.propagate = False  # Don't propagate to root logger

    # Clear existing handlers
    logger.handlers = []

    # File handler (detailed logs)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (user-friendly)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=" * 80)
    logger.info(f"AgentGraph session started")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 80)

    return logger


def log_state_transition(logger: logging.Logger, from_node: str, to_node: str, state: Dict[str, Any]) -> None:
    """Log state transition between nodes.

    Args:
        logger: Logger instance
        from_node: Source node name
        to_node: Destination node name
        state: Current state dictionary
    """
    logger.info("=" * 80)
    logger.info(f"Node transition: {from_node} → {to_node}")
    logger.info(f"  Context: {state.get('context_id')}")
    logger.info(f"  Loops: {state.get('loops')}/{state.get('max_loops')}")
    logger.info(f"  Message count: {len(state.get('messages', []))}")
    logger.info(f"  Active skill: {state.get('active_skill')}")
    logger.info(f"  Mentioned agents: {state.get('mentioned_agents', [])}")
    logger.info(f"  Allowed tools: {state.get('allowed_tools', [])}")
    logger.info(f"  Todo count: {len(state.get('todos', []))}")
    logger.info("=" * 80)


def log_tool_call(logger: logging.Logger, tool_name: str, args: Dict[str, Any]) -> None:
    """Log tool invocation.

    Args:
        logger: Logger instance
        tool_name: Name of the tool being called
        args: Tool arguments
    """
    logger.info(f"Tool call: {tool_name}")
    logger.debug(f"  Arguments: {json.dumps(args, ensure_ascii=False, indent=2)}")


def log_tool_result(logger: logging.Logger, tool_name: str, result: Any, success: bool = True) -> None:
    """Log tool execution result.

    Args:
        logger: Logger instance
        tool_name: Name of the tool
        result: Tool execution result
        success: Whether the tool executed successfully
    """
    status = "✓ Success" if success else "✗ Failed"
    logger.info(f"Tool result: {tool_name} - {status}")

    # Log result preview (truncated)
    result_str = str(result)
    if len(result_str) > 500:
        result_str = result_str[:500] + "... (truncated)"
    logger.debug(f"  Result: {result_str}")


def log_model_selection(logger: logging.Logger, phase: str, model_id: str, reason: str = "") -> None:
    """Log model selection decision.

    Args:
        logger: Logger instance
        phase: Execution phase (plan/delegate/finalize)
        model_id: Selected model ID
        reason: Reason for selection
    """
    logger.info(f"Model selected for {phase}: {model_id}")
    if reason:
        logger.debug(f"  Reason: {reason}")


def log_error(logger: logging.Logger, error: Exception, context: str = "") -> None:
    """Log error with context.

    Args:
        logger: Logger instance
        error: Exception instance
        context: Additional context about where the error occurred
    """
    logger.error(f"Error occurred: {type(error).__name__}: {str(error)}")
    if context:
        logger.error(f"  Context: {context}")
    logger.exception("Full traceback:", exc_info=error)


def log_user_message(logger: logging.Logger, content: str) -> None:
    """Log user input.

    Args:
        logger: Logger instance
        content: User message content
    """
    logger.info(f"User input: {content[:100]}{'...' if len(content) > 100 else ''}")


def log_agent_response(logger: logging.Logger, content: str) -> None:
    """Log agent response.

    Args:
        logger: Logger instance
        content: Agent response content
    """
    logger.info(f"Agent response: {content[:100]}{'...' if len(content) > 100 else ''}")


def log_prompt(logger: logging.Logger, phase: str, prompt: str) -> None:
    """Log system prompt being used.

    Args:
        logger: Logger instance
        phase: Phase name (planner/step_executor/finalize)
        prompt: System prompt content
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"System Prompt for {phase}:")
    logger.info(f"{'='*80}")
    logger.info(prompt)
    logger.info(f"{'='*80}\n")


def log_visible_tools(logger: logging.Logger, phase: str, tools: list) -> None:
    """Log visible tools for current phase.

    Args:
        logger: Logger instance
        phase: Phase name
        tools: List of tool names or tool objects
    """
    tool_names = [t.name if hasattr(t, 'name') else str(t) for t in tools]
    logger.info(f"\nVisible tools for {phase}: [{', '.join(tool_names)}]")
    logger.info(f"  Total: {len(tool_names)} tools")


def log_routing_decision(logger: logging.Logger, from_node: str, decision: str, reason: str = "") -> None:
    """Log routing decision.

    Args:
        logger: Logger instance
        from_node: Source node making the decision
        decision: Routing destination
        reason: Reason for the routing decision
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Routing decision from {from_node}:")
    logger.info(f"  → Destination: {decision}")
    if reason:
        logger.info(f"  → Reason: {reason}")
    logger.info(f"{'='*80}\n")


def log_plan_created(logger: logging.Logger, plan: Dict[str, Any]) -> None:
    """Log plan creation details.

    Args:
        logger: Logger instance
        plan: Plan dictionary
    """
    logger.info(f"\n{'='*80}")
    logger.info("Plan created:")
    logger.info(f"  Goal: {plan.get('goal', 'N/A')}")
    logger.info(f"  Total steps: {len(plan.get('steps', []))}")
    for i, step in enumerate(plan.get('steps', []), 1):
        logger.info(f"  Step {i}:")
        logger.info(f"    - ID: {step.get('id')}")
        logger.info(f"    - Agent: {step.get('agent')}")
        logger.info(f"    - Description: {step.get('description')}")
        logger.info(f"    - Max calls: {step.get('max_calls', 3)}")
    logger.info(f"{'='*80}\n")


def log_step_execution(logger: logging.Logger, step_idx: int, step: Dict[str, Any], current_calls: int, max_calls: int) -> None:
    """Log step execution details.

    Args:
        logger: Logger instance
        step_idx: Current step index
        step: Step dictionary
        current_calls: Current call count
        max_calls: Maximum allowed calls
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Executing Step {step_idx + 1}:")
    logger.info(f"  ID: {step.get('id')}")
    logger.info(f"  Agent: {step.get('agent')}")
    logger.info(f"  Description: {step.get('description')}")
    logger.info(f"  Calls: {current_calls}/{max_calls}")
    logger.info(f"  Inputs: {json.dumps(step.get('inputs', {}), ensure_ascii=False)}")
    logger.info(f"  Deliverables: {step.get('deliverables', [])}")
    logger.info(f"  Success criteria: {step.get('success_criteria', 'N/A')}")
    logger.info(f"{'='*80}\n")


def log_node_entry(logger: logging.Logger, node_name: str, state: Dict[str, Any]) -> None:
    """Log node entry with current state.

    Args:
        logger: Logger instance
        node_name: Name of the node being entered
        state: Current state dictionary
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"# ENTERING NODE: {node_name}")
    logger.info(f"{'#'*80}")
    logger.info(f"State snapshot:")
    logger.info(f"  - context_id: {state.get('context_id')}")
    logger.info(f"  - loops: {state.get('loops')}/{state.get('max_loops')}")
    logger.info(f"  - messages: {len(state.get('messages', []))}")
    logger.info(f"  - todos: {len(state.get('todos', []))} tasks")
    logger.info(f"  - active_skill: {state.get('active_skill')}")
    logger.info(f"  - mentioned_agents: {state.get('mentioned_agents', [])}")
    thread_id = state.get('thread_id') or 'N/A'
    logger.info(f"  - thread_id: {thread_id[:8]}...")


def log_node_exit(logger: logging.Logger, node_name: str, updates: Dict[str, Any]) -> None:
    """Log node exit with state updates.

    Args:
        logger: Logger instance
        node_name: Name of the node being exited
        updates: State updates returned by the node
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"# EXITING NODE: {node_name}")
    logger.info(f"{'#'*80}")
    logger.info(f"State updates:")
    for key, value in updates.items():
        if key == "messages":
            logger.info(f"  - messages: +{len(value)} new messages")
        else:
            logger.info(f"  - {key}: {value}")
    logger.info(f"{'#'*80}\n")


# Singleton logger instance
_global_logger = None


def get_logger() -> logging.Logger:
    """Get or create the global logger instance.

    Returns:
        Global logger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = setup_logging()
    return _global_logger
