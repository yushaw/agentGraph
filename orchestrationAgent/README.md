# OrchestrationAgent - Task Decomposition & Delegation Manager

## Overview

OrchestrationAgent (Host Agent) is the "manager" or "supervisor" in the AI framework. It does **NOT** execute concrete work (I/O, network requests, file operations). Its sole responsibility is to orchestrate complex workflows.

## Responsibilities

1. **Understand**: Receive complex, multi-step, or ambiguous goals from users
2. **Deconstruct**: Break down goals into specific, executable sub-tasks
3. **Delegate**: Assign sub-tasks to Worker Agents via `delegate_task`
4. **Supervise**: Receive structured work reports from Workers
5. **Feedback**: Evaluate results and decide next steps (continue/retry/report)

## Architecture

### Strict Tool Restrictions

Host is **STRICTLY RESTRICTED** to orchestration tools only:

**Allowed Tools** (5):
- ✅ `delegate_task` - Delegate sub-tasks to Worker Agent
- ✅ `done_and_report` - Report final results (signal tool)
- ✅ `ask_human` - Ask user for clarification
- ✅ `todo_write` - Track high-level project plan
- ✅ `now` - Get current UTC time

**Forbidden Tools**:
- ❌ File operations (`read_file`, `write_file`, `run_bash_command`)
- ❌ Network operations (`http_fetch`, `search_web`)
- ❌ All other "labor" tools

This design **forces** the Host to delegate all concrete work.

### Graph Structure

```
START → planner → [summarization] → tools (HITL) → planner → finalize → END
          ↑___________|                          |_________|
          (feedback loop)                    (forced return)
```

**Key Features**:
- **Forced Feedback Loop**: Tools always return to planner (no direct END)
- **HITL Protection**: Approval required for risky delegations
- **Auto-Compression**: Supports long orchestration sessions
- **Simplified State**: No images, skills, or dynamic tool loading

### State (Simplified)

`OrchestrationState` is a **subset** of `generalAgent.graph.state.AppState`:

**Included**:
- `messages` - Conversation history
- `todos` - High-level project plan
- `loops`, `max_loops` - Loop control
- `workspace_path`, `uploaded_files` - Worker context
- `context_id`, `thread_id` - Session management

**Excluded** (not needed by Host):
- `images` - Host doesn't process images
- `active_skill` - Host doesn't use skills
- `mentioned_agents`, `allowed_tools` - Host has fixed toolset

## Usage

### Basic Workflow

1. **Start Host CLI**:
   ```bash
   python orchestration_main.py
   ```

2. **User provides complex task**:
   ```
   User> 分析 doc1.pdf 和 doc2.pdf 的异同
   ```

3. **Host decomposes and delegates**:
   ```
   Host> [思考] 需要三个子任务：
         1. 分析 doc1.pdf
         2. 分析 doc2.pdf
         3. 对比结果

   Host> [调用 todo_write(...)]
   Host> [调用 delegate_task("分析 'uploads/doc1.pdf' 的内容...")]
   Worker> (执行分析) 返回结果

   Host> [接收结果]
   Host> [调用 delegate_task("分析 'uploads/doc2.pdf' 的内容...")]
   Worker> (执行分析) 返回结果

   Host> [汇总结果]
   Host> [调用 done_and_report("以下是对比分析...")]
   ```

### Example Prompts

**Simple Delegation**:
```
User> 分析 uploads/report.pdf 的内容
Host> [delegate_task("分析文件 'uploads/report.pdf'，提取关键信息...")]
Worker> (执行)
Host> [done_and_report("报告内容摘要：...")]
```

**Multi-Step Research**:
```
User> 研究 Python 3.13 的新特性
Host> [todo_write([...])]
Host> [delegate_task("搜索 Python 3.13 官方文档...")]
Worker> (搜索并整理)
Host> [delegate_task("总结新特性的实际应用场景...")]
Worker> (分析)
Host> [done_and_report("Python 3.13 新特性总结：...")]
```

**Clarification Required**:
```
User> 分析那个报告
Host> [ask_human("您指的是哪个报告？请提供文件名。")]
User> uploads/q3_report.pdf
Host> [delegate_task("分析文件 'uploads/q3_report.pdf'...")]
```

## Configuration

### Tool Configuration

Edit `orchestrationAgent/config/tools.yaml` to modify tool availability.

**DO NOT** enable labor tools (file ops, network) for Host!

### HITL Rules

Edit `orchestrationAgent/config/hitl_rules.yaml` to configure approval rules.

**Critical Patterns** (require approval):
- Destructive operations: `rm -rf`, `删除.*目录`
- System modifications: `sudo`, `chmod 777`
- Sensitive file access: `.env`, `credentials`

### Settings

Host reuses `generalAgent.config.settings.Settings`:
- Model configuration (`.env`)
- Loop limits (`max_loops`)
- Context management (auto-compression)
- Persistence (SQLite checkpointer)

## Development

### Adding New Orchestration Tools

1. Create tool in `orchestrationAgent/tools/`:
   ```python
   @tool
   def my_orchestration_tool(...) -> str:
       ...
   ```

2. Register in `orchestrationAgent/runtime/app.py`:
   ```python
   orchestration_tools = {
       ...
       "my_tool": my_orchestration_tool,
   }
   ```

3. Add to `orchestrationAgent/config/tools.yaml` (documentation only)

### Testing

Run orchestration-specific tests:
```bash
# Basic workflow test
python orchestration_main.py

# Test delegation
User> 帮我读取 uploads/test.txt 的内容

# Test multi-step
User> 分析 uploads/doc1.pdf 和 doc2.pdf 的差异

# Test HITL
User> 删除 outputs/ 目录
# Should trigger approval prompt
```

## Comparison with GeneralAgent

| Feature | GeneralAgent (Worker) | OrchestrationAgent (Host) |
|---------|---------------------|------------------------|
| **Purpose** | Execute concrete work | Decompose & delegate |
| **Tool Count** | 50+ tools | 5 tools |
| **Tools** | File ops, network, bash, etc. | delegate_task, done_and_report, etc. |
| **Skills** | Supports @mention loading | Not supported |
| **State** | Full AppState | Simplified (no images, skills) |
| **@Mentions** | Supported | Not supported |
| **HITL** | Tool approval | Delegation approval |
| **Use Case** | Direct task execution | Complex workflow orchestration |

## Future Enhancements

### Planned Features

1. **Multi-Worker Support** (from Ch 9 / agents.yaml):
   - Select different Worker types (simple, general, qa, code)
   - Dynamic Worker selection based on task type

2. **Structured Reporting** (from FR-3.6):
   - Force Workers to return `{status, result, error, log_file}` format
   - Better failure handling and retry logic

3. **Fine-Grained Events** (from 3.2):
   - `STEP_START`, `ACTION_START`, `SUBAGENT_STREAM_START`
   - Better observability for V3/V4 UI

4. **Agent Discovery** (from Ch 9):
   - Dynamic Worker catalog in SystemMessage
   - Runtime Worker registration

### Not Planned (Out of Scope)

- ❌ Direct file operations (violates design principle)
- ❌ Skill loading (Host doesn't use skills)
- ❌ Image processing (Host is text-only)

## Troubleshooting

### Host tries to read files directly

**Symptom**: Error "Tool 'read_file' not found"

**Cause**: Host's SystemMessage might not be clear enough

**Solution**: Check `orchestrationAgent/graph/nodes/planner.py` SystemMessage emphasizes delegation

### Worker fails but Host doesn't retry

**Symptom**: Host reports failure immediately

**Cause**: Current implementation doesn't have retry logic

**Solution**: Add retry logic in future iterations (see FR-4 feedback loop enhancement)

### HITL doesn't trigger for dangerous delegations

**Symptom**: Risky tasks execute without approval

**Cause**: HITL rules might not cover the pattern

**Solution**: Add pattern to `orchestrationAgent/config/hitl_rules.yaml`

## References

- [CLAUDE.md](../CLAUDE.md) - Project overview
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) - System architecture
- [docs/FEATURES.md](../docs/FEATURES.md) - Feature documentation
- [generalAgent/](../generalAgent/) - Worker Agent implementation
- [User Requirements](需求文档.md) - Original requirements (Chinese)
