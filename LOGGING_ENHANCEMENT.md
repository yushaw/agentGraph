# Logging Enhancement Summary

## Overview
Enhanced the logging system for AgentGraph to provide comprehensive debugging and monitoring capabilities. All logs are written to timestamped files in the `logs/` directory.

## What Was Added

### 1. Enhanced Logging Utilities (`agentgraph/utils/logging_utils.py`)

**New logging functions:**
- `log_node_entry()` - Logs node entry with complete state snapshot
- `log_node_exit()` - Logs node exit with state updates
- `log_prompt()` - Logs system prompts sent to LLM
- `log_visible_tools()` - Logs available tools for each phase
- `log_routing_decision()` - Logs routing decisions with reasons
- `log_plan_created()` - Logs plan creation details
- `log_step_execution()` - Logs step execution progress
- `log_model_selection()` - Logs model selection decisions
- `log_tool_call()` - Logs tool invocations
- `log_tool_result()` - Logs tool execution results

**Updated functions:**
- `log_state_transition()` - Enhanced with more state details

### 2. Node-Level Logging

#### Planner Node (`agentgraph/graph/nodes/planner.py`)
- Node entry/exit with state snapshots
- Visible tools assembly process
- Tool loading from:
  - Persistent global tools
  - Activated skills (via select_skill)
  - @mentioned agents/skills/tools
- Capability detection (code, vision)
- Multimodal input detection
- System prompt construction
- Message history truncation details
- Model selection parameters

#### Step Executor Node (`agentgraph/graph/nodes/step_executor.py`)
- Step-by-step execution tracking
- Budget checking (current_calls vs max_calls)
- Visible tools assembly for each step
- Subagent-specific tools
- Dynamic prompt building
- Subagent invocation details

#### Analyze Node (`agentgraph/graph/nodes/analyze.py`)
- Task complexity analysis
- Pending tool calls detection
- Recent tool execution summary
- Plan extraction from create_plan results

#### Finalize Node (`agentgraph/graph/nodes/finalize.py`)
- Skip conditions (no messages, non-tool messages, meta operations)
- Message history processing
- Final response generation

#### Post Node (`agentgraph/graph/nodes/post.py`)
- Tool result extraction
- create_plan handling
- select_skill handling
- State updates from tool results

### 3. Routing Decision Logging (`agentgraph/graph/routing.py`)

All routing functions now log:
- `post_route()` - Plan vs analyze decision
- `analyze_route()` - Continue vs simple vs end decision
- `tools_route()` - Initial vs loop phase routing
- `step_route()` - Step progress vs finalize decision

Each routing decision includes:
- Source node
- Destination node
- Reason for the decision

## Log File Structure

### Log Format
```
YYYY-MM-DD HH:MM:SS | LEVEL    | logger.name | message
```

### Example Log Output

```
2025-10-23 15:46:48 | INFO     | agentgraph.planner | ################################################################################
2025-10-23 15:46:48 | INFO     | agentgraph.planner | # ENTERING NODE: planner
2025-10-23 15:46:48 | INFO     | agentgraph.planner | ################################################################################
2025-10-23 15:46:48 | INFO     | agentgraph.planner | State snapshot:
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - execution_phase: initial
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - task_complexity: unknown
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - loops: 0/10
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - step_idx: 0
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - step_calls: 0/3
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - messages: 1
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - active_skill: None
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - mentioned_agents: []
2025-10-23 15:46:48 | INFO     | agentgraph.planner | Building visible tools...
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - Starting with 6 persistent global tools
2025-10-23 15:46:48 | INFO     | agentgraph.planner |   - Final tool count after deduplication: 6
```

## Log Hierarchy

```
agentgraph (root logger)
├── agentgraph.planner
├── agentgraph.step_executor
├── agentgraph.analyze
├── agentgraph.finalize
├── agentgraph.post
└── agentgraph.routing
```

All child loggers inherit the file handler from the root logger, so all logs go to the same file.

## Configuration

### Log Levels
- **File Handler**: DEBUG (captures everything)
- **Console Handler**: WARNING (only shows warnings/errors to user)
- **Root Logger**: DEBUG (allows all child loggers to emit logs)

### Log File Location
- Directory: `logs/`
- Filename pattern: `agentgraph_YYYYMMDD_HHMMSS.log`
- Created automatically at session start

## Benefits

1. **Complete Execution Trace**: Every node transition is logged with full state
2. **Tool Visibility Tracking**: Know exactly which tools are available at each phase
3. **Prompt Debugging**: See the exact prompts sent to LLM
4. **Routing Logic**: Understand why the graph took specific paths
5. **@mention Debugging**: Track how @mentions load tools
6. **Message History**: See how history is cleaned and truncated
7. **Budget Tracking**: Monitor loop counts and step call budgets

## Usage

### In CLI (main.py)
Logging is automatically initialized when the application starts:
```python
logger = get_logger()
```

### In Tests
Import and use logger:
```python
from agentgraph.utils.logging_utils import get_logger
logger = get_logger()
```

### Viewing Logs
```bash
# View latest log
tail -f logs/$(ls -t logs/ | head -1)

# Search for specific node
grep "ENTERING NODE: planner" logs/*.log

# Search for routing decisions
grep "Routing decision" logs/*.log
```

## Files Modified

1. `agentgraph/utils/logging_utils.py` - Enhanced with new functions
2. `agentgraph/graph/nodes/planner.py` - Added comprehensive logging
3. `agentgraph/graph/nodes/step_executor.py` - Added comprehensive logging
4. `agentgraph/graph/nodes/analyze.py` - Added comprehensive logging
5. `agentgraph/graph/nodes/finalize.py` - Added comprehensive logging
6. `agentgraph/graph/nodes/post.py` - Added comprehensive logging
7. `agentgraph/graph/routing.py` - Added routing decision logging

## Testing

All logging enhancements have been tested with:
- Simple queries (e.g., "你好")
- @mention queries (e.g., "@weather 北京今天怎么样")
- Complex multi-step tasks

The logging system successfully captures all node transitions, state changes, tool loading, and routing decisions.
