# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentGraph is a LangGraph-based agent framework with an **Agent Loop architecture** (Claude Code style). The system uses:
- Single agent loop where the LLM decides execution flow via tool calls
- Flexible skill packages with SKILL.md documentation
- On-demand tool loading with `@mention` support
- Multi-model routing (base, reasoning, vision, code, chat)
- Session persistence with SQLite checkpointer

## Development Commands

### Environment Setup
```bash
# Install dependencies (Python 3.12 required)
uv sync
# Or: pip install -e .

# Copy environment template and configure API keys
cp .env.example .env
# Edit .env with your model API keys
```

### Running the Application
```bash
# Start the interactive CLI
python main.py

# CLI commands within the session:
#   /quit, /exit     - Exit the program
#   /reset           - Reset current session
#   /sessions        - List saved sessions
#   /load <id>       - Load a session by ID prefix
#   /current         - Show current session info
#   /clean           - Clean up old workspace files (>7 days)
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_mention_types.py

# Run with verbose output
pytest -v
```

## Architecture

### Agent Loop Flow
```
START → agent ⇄ tools → agent → finalize → END
```

- **agent** node: LLM decides whether to call tools or finish (agentgraph/graph/nodes/planner.py)
- **tools** node: Executes tool calls and returns to agent
- **finalize** node: Final response processing before END

### Key Components

**State Management** (agentgraph/graph/state.py)
- `AppState` TypedDict defines all conversation state
- `messages`: LangChain message history
- `todos`: Task tracking list (via TodoWrite tool)
- `mentioned_agents`: @mention tracking for tools/skills/agents
- `active_skill`, `allowed_tools`: Skill context
- `context_id`, `parent_context`: Subagent isolation
- `loops`, `max_loops`: Loop control

**Model Registry** (agentgraph/models/registry.py)
- Five model slots: base, reasoning, vision, code, chat
- Models configured via `.env` (MODEL_BASIC_*, MODEL_REASONING_*, etc.)
- Supports OpenAI-compatible APIs (DeepSeek, Moonshot, GLM, etc.)

**Tool System** (agentgraph/tools/)
- Three-tier architecture:
  - `_discovered`: All scanned tools (including disabled)
  - `_tools`: Enabled tools (immediately available)
  - `load_on_demand()`: Load tools when @mentioned
- Configuration driven by `agentgraph/config/tools.yaml`
- Builtin tools in `agentgraph/tools/builtin/`
- Custom tools in `agentgraph/tools/custom/` (user-defined)

**Skill System** (agentgraph/skills/)
- Skills are **knowledge packages** (documentation + scripts), NOT tool containers
- Structure: `skills/{skill_id}/SKILL.md` + `scripts/` + reference docs
- When user mentions `@pdf`, skills are symlinked to session workspace
- Agent uses `read_file` tool to read SKILL.md and follow guidance
- Agent can use `run_skill_script` tool to execute skill scripts
- Skills do NOT have `allowed_tools` field

**@Mention System** (agentgraph/utils/mention_classifier.py)
- Three types:
  - `@tool` - Load specific tool on demand
  - `@skill` - Generate reminder to read SKILL.md
  - `@agent` - Load call_subagent tool
- Mentions parsed in main.py and classified in planner.py

### Important Files

- `agentgraph/runtime/app.py` - Application assembly, tool/skill registry initialization
- `agentgraph/graph/builder.py` - LangGraph construction, node wiring
- `agentgraph/graph/nodes/planner.py` - Agent node logic, @mention handling, tool visibility
- `agentgraph/graph/routing.py` - Conditional edge routing (agent_route, tools_route)
- `agentgraph/config/settings.py` - Pydantic settings from .env
- `agentgraph/persistence/session_store.py` - SQLite session persistence
- `agentgraph/persistence/workspace.py` - Workspace manager for session isolation
- `agentgraph/tools/builtin/file_ops.py` - File operation tools (read_file, write_file, list_workspace_files)
- `agentgraph/tools/builtin/run_skill_script.py` - Execute skill scripts
- `agentgraph/tools/builtin/run_bash_command.py` - Execute bash commands
- `main.py` - CLI entrypoint with streaming, @mention parsing, session/workspace management

## Workspace Isolation

Each session has an isolated workspace directory inspired by OpenAI Code Interpreter and E2B:

### Directory Structure
```
data/workspace/{session_id}/
├── skills/           # Symlinked skills when @mentioned (read-only)
│   └── pdf/
│       ├── SKILL.md
│       ├── forms.md
│       ├── reference.md
│       └── scripts/
├── uploads/          # User-uploaded files
├── outputs/          # Agent-generated outputs
├── temp/             # Temporary files
└── .metadata.json    # Session metadata
```

### Workflow

1. **Session Start** - Workspace created at `data/workspace/{thread_id}/`
2. **@skill Mention** - Skills symlinked to `workspace/skills/`
3. **File Operations** - Agent uses `read_file`, `write_file` tools
4. **Script Execution** - Agent uses `run_skill_script` to execute Python scripts
5. **Cleanup** - Old workspaces (7+ days) automatically deleted

### Security

- **Path isolation** - Tools cannot access files outside workspace
- **Write restrictions** - Can only write to outputs/, temp/, uploads/
- **Skills read-only** - Symlinked from project skills/ directory
- **Timeout protection** - Script execution limited to 30s default
- **Environment variable** - `AGENT_WORKSPACE_PATH` set before tool execution

### File Operation Tools

**read_file**
```python
read_file("skills/pdf/SKILL.md")  # Read skill documentation
read_file("uploads/document.pdf")  # Read user upload
```

**write_file**
```python
write_file("outputs/result.txt", "Analysis results...")
write_file("temp/data.json", '{"key": "value"}')
```

**list_workspace_files**
```python
list_workspace_files(".")         # List all
list_workspace_files("uploads")   # List specific directory
```

**run_skill_script** (disabled by default, requires @mention)
```python
run_skill_script(
    skill_id="pdf",
    script_name="fill_fillable_fields.py",
    args='{"input_pdf": "uploads/form.pdf", "output_pdf": "outputs/filled.pdf"}'
)
```

## Tool Configuration

Edit `agentgraph/config/tools.yaml` to control tool availability:

```yaml
core:
  now:
    category: "meta"
    tags: ["meta", "time"]
    description: "Get current UTC time"

optional:
  http_fetch:
    enabled: true          # Load at startup
    always_available: false
    category: "network"
    tags: ["network", "read"]

  extract_links:
    enabled: false         # Not loaded at startup, but available via @mention
    category: "read"
    tags: ["read", "parse"]
```

**Tool behavior:**
- `enabled: true` - Loaded at application startup
- `enabled: false` - Available via on-demand loading when user @mentions it
- `always_available: true` - Added to all agent contexts (use sparingly)

## Adding New Tools

1. Create tool file in `agentgraph/tools/builtin/` or `agentgraph/tools/custom/`
2. Tool function must be decorated with `@tool` from langchain_core.tools
3. Add configuration to `tools.yaml`:
   ```yaml
   optional:
     my_new_tool:
       enabled: true
       always_available: false
       category: "compute"
       tags: ["custom", "utility"]
       description: "Brief description"
   ```
4. Tool will be auto-discovered by scanner on next startup

## Adding New Skills

1. Create directory structure:
   ```
   skills/<skill_id>/
   ├── SKILL.md           # Main documentation (required)
   ├── reference.md       # Additional reference (optional)
   ├── forms.md           # Specific guides (optional)
   └── scripts/           # Python scripts (optional)
       ├── script1.py
       └── script2.py
   ```

2. Write `SKILL.md` with:
   - Overview of what the skill does
   - Step-by-step usage instructions
   - Examples
   - References to scripts (if any)

3. Add metadata to skill registry (if needed)

4. Skills are automatically available when user @mentions them

Example workflow:
```
User> @pdf 帮我填写这个PDF表单
System> [检测到 @pdf]
        [已加载技能: pdf]
Agent> [Uses read_file to read skills/pdf/SKILL.md]
       [Follows instructions from SKILL.md]
       [Uses run_skill_script to execute fill_fillable_fields.py]
```

## Model Configuration

Models configured via `.env` with provider-specific aliases:

```bash
# DeepSeek models
MODEL_BASIC_API_KEY=sk-xxx
MODEL_BASIC_BASE_URL=https://api.deepseek.com
MODEL_BASIC_ID=deepseek-chat

MODEL_REASONING_API_KEY=sk-xxx
MODEL_REASONING_BASE_URL=https://api.deepseek.com
MODEL_REASONING_ID=deepseek-reasoner

# GLM models (OpenAI-compatible)
MODEL_MULTIMODAL_API_KEY=xxx
MODEL_MULTIMODAL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_MULTIMODAL_ID=glm-4.5v

# Moonshot Kimi
MODEL_CHAT_API_KEY=xxx
MODEL_CHAT_BASE_URL=https://api.moonshot.cn/v1
MODEL_CHAT_ID=kimi-k2-0905-preview
```

The system also supports canonical names (MODEL_BASE_*, MODEL_REASON_*, MODEL_VISION_*, MODEL_CODE_*, MODEL_CHAT_*) which are aliased to the provider-specific names above.

## Refactoring Notes

See `REFACTORING_NOTES.md` for detailed information about the recent tools and skills refactoring, including:
- Three-tier tool loading architecture
- @Mention classification system (tools/skills/agents)
- Configuration-driven metadata
- Correct skills architecture (documentation, not tool containers)

## Observability

**LangSmith Tracing** - Set in `.env`:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-key
```

**Session Persistence** - Enabled by default via SQLite:
- Sessions stored in `data/sessions.db`
- Use `/sessions` to list, `/load <id>` to restore

**Logging** - Logs written to `logs/` directory with timestamps

## Recent Fixes (2025-10-24)

### 1. Skills Path Correction
- **Issue**: Code referenced `Path("skills")` instead of `Path("agentgraph/skills")`
- **Fixed**: Updated `main.py:268` and `agentgraph/runtime/app.py:117`

### 2. Symlink Path Resolution in list_workspace_files
- **Issue**: `list_workspace_files` used `resolve()` causing paths outside workspace
- **Fixed**: `agentgraph/tools/builtin/file_ops.py:214-241` - use logical paths

### 3. Multi-Tool File Support
- **Issue**: Tool scanner only loaded first tool from files with multiple tools
- **Impact**: `read_file` and `write_file` were not loaded (only `list_workspace_files`)
- **Fixed**:
  - Added `__all__` export to `file_ops.py`
  - Rewrote `_extract_tools_from_module()` to return list instead of single tool
  - Now supports multiple tools per file via `__all__` declaration
- **Result**: All 13 tools now load correctly

### 4. Workspace Cleanup on Exit
- **Added**: Automatic cleanup of workspaces >7 days old on program exit
- **Added**: `/clean` command for manual cleanup
- **Files**: `main.py:241-249` (command), `main.py:459-468` (auto-cleanup)
