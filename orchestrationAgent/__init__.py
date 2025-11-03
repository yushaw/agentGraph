"""OrchestrationAgent - Task decomposition and delegation manager.

The Orchestration Agent acts as a "manager" or "supervisor" in the AI framework.
It does NOT execute concrete work (I/O, network requests, file operations).

Its sole responsibility is:
1. Understand: Receive complex, multi-step, or ambiguous goals from users
2. Deconstruct: Break down goals into specific, executable sub-tasks
3. Delegate: Assign sub-tasks to Worker Agents via delegate_task
4. Supervise: Receive structured work reports from Workers
5. Feedback: Evaluate results and decide next steps (continue/retry/report)

Key Design Principles:
- Strict tool restrictions: Only orchestration tools (delegate_task, done_and_report, etc.)
- No "labor" tools: Cannot read files, fetch URLs, run bash commands
- Forced feedback loop: Always returns to planner after tool execution
- HITL protection: Approval required for risky delegations
- Context compression: Supports long-running orchestration sessions
"""

__version__ = "1.0.0"
