# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentGraph is a LangGraph-based agent framework with an **Agent Loop architecture** (Claude Code style). The system uses:
- Single agent loop where the LLM decides execution flow via tool calls
- **HITL (Human-in-the-Loop)** support for interactive workflows and safety
- Flexible skill packages with SKILL.md documentation
- On-demand tool loading with `@mention` support
- Multi-model routing (base, reasoning, vision, code, chat)
- Session persistence with SQLite checkpointer

## Project Structure (Post-Refactoring)

The codebase is organized into shared infrastructure and agent-specific implementations:

```
project/
├── shared/                     # Shared infrastructure (reusable across agents)
│   ├── cli/
│   │   └── base_cli.py        # Base CLI framework with command routing
│   ├── session/
│   │   ├── store.py           # Session persistence (SQLite)
│   │   └── manager.py         # Session lifecycle management
│   └── workspace/
│       └── manager.py         # Workspace isolation & file management
│
├── generalAgent/              # General-purpose conversational agent
│   ├── cli.py                # GeneralAgent CLI implementation
│   ├── runtime/
│   │   └── app.py            # Application assembly
│   ├── graph/                # LangGraph nodes & routing
│   ├── hitl/                 # HITL (Human-in-the-Loop) components
│   │   ├── approval_checker.py  # Tool approval rule engine
│   │   └── approval_node.py     # Approval-aware ToolNode wrapper
│   ├── tools/                # Tool system
│   │   └── builtin/
│   │       └── ask_human.py  # User input request tool
│   ├── skills/               # Skill packages
│   ├── config/
│   │   ├── hitl_rules.yaml   # Approval rules configuration
│   │   ├── skills.yaml       # Skills loading configuration
│   │   ├── tools.yaml        # Tools loading configuration
│   │   └── skill_config_loader.py  # Skills config parser
│   └── utils/                # Utilities
│
├── main.py                    # Entrypoint for GeneralAgent CLI
└── main_old.py               # Backup of pre-refactor main.py
```

### Shared Infrastructure

**Purpose**: Provide reusable components for building different agents (generalAgent, qaAgent, codeAgent, etc.)

**Key Components**:

1. **BaseCLI** (`shared/cli/base_cli.py`)
   - Abstract base class for command-line interfaces
   - Handles command routing (`/quit`, `/help`, `/sessions`, `/load`, `/reset`, `/current`)
   - Main input/output loop
   - Subclasses implement agent-specific logic

2. **SessionManager** (`shared/session/manager.py`)
   - Session lifecycle management
   - Integrates SessionStore (persistence) + WorkspaceManager (file isolation)
   - Methods: `create_session()`, `load_session()`, `reset_session()`, `save_current_session()`

3. **SessionStore** (`shared/session/store.py`)
   - SQLite-based session persistence
   - Stores conversation history and state

4. **WorkspaceManager** (`shared/workspace/manager.py`)
   - Per-session isolated file workspaces
   - Automatic skill loading with dependency installation
   - Directory structure: `skills/`, `uploads/`, `outputs/`, `temp/`

### Agent-Specific Implementation

**GeneralAgent** is implemented by:

1. **GeneralAgentCLI** (`generalAgent/cli.py`)
   - Extends `BaseCLI` with GeneralAgent-specific logic
   - Handles @mention parsing and skill loading
   - Processes file uploads
   - Streams LangGraph execution
   - Auto-saves sessions after each turn

2. **main.py**
   - Entrypoint (~60 lines, down from 477!)
   - Assembles application and shared infrastructure
   - Launches CLI

### Adding New Agents

To add a new agent (e.g., `qaAgent`):

1. Create agent directory: `qaAgent/`
2. Implement CLI: `qaAgent/cli.py` (extends `BaseCLI`)
3. Implement agent logic: `qaAgent/workflow.py` or `qaAgent/graph/`
4. Create entrypoint: `qa_main.py`

Example:

```python
# qa_main.py
from shared.cli.base_cli import BaseCLI
from shared.session.manager import SessionManager
from qaAgent.workflow import build_qa_workflow

class QAAgentCLI(BaseCLI):
    async def handle_user_message(self, user_input: str):
        # QA-specific logic here
        result = await self.workflow.process_question(user_input)
        print(f"A> {result}")

async def main():
    app, initial_state_factory = build_qa_workflow()

    # Reuse shared infrastructure!
    session_manager = SessionManager(...)
    cli = QAAgentCLI(...)
    await cli.run()
```

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
# Method 1: Run from project root (recommended)
python main.py
# Or: uv run python main.py

# Method 2: Run GeneralAgent directly (works from any directory)
python generalAgent/main.py
# Or from generalAgent directory:
cd generalAgent && python main.py

# CLI commands within the session:
#   /quit, /exit     - Exit the program
#   /reset           - Reset current session
#   /sessions        - List saved sessions
#   /load <id>       - Load a session by ID prefix
#   /current         - Show current session info
#   /clean           - Clean up old workspace files (>7 days)
```

**Note**: The codebase now uses **project-root-aware path resolution**, so you can run from any directory. All paths (tools, skills, config, logs, data) are automatically resolved relative to the project root.

### Testing

The project has a comprehensive test suite organized into four tiers:

```bash
# Quick validation before commits (< 30s)
python tests/run_tests.py smoke

# Run unit tests
python tests/run_tests.py unit

# Run integration tests
python tests/run_tests.py integration

# Run end-to-end business workflow tests
python tests/run_tests.py e2e

# Run all test types
python tests/run_tests.py all

# Generate coverage report
python tests/run_tests.py coverage
```

**Test organization:**
- `tests/smoke/` - Fast critical-path tests for quick validation
- `tests/unit/` - Module-level tests (HITL, MCP, Tools, Skills, etc.)
- `tests/integration/` - Module interaction tests (@mention system, registries, etc.)
- `tests/e2e/` - Complete business workflow tests
- `tests/fixtures/` - Test infrastructure (test MCP servers, etc.)

**For detailed testing guidelines**, see [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)

## Architecture

### Agent Loop Flow
```
START → agent ⇄ tools → agent → finalize → END
```

- **agent** node: LLM decides whether to call tools or finish (generalAgent/graph/nodes/planner.py)
- **tools** node: Executes tool calls and returns to agent
- **finalize** node: Final response processing before END

### Key Components

**State Management** (generalAgent/graph/state.py)
- `AppState` TypedDict defines all conversation state
- `messages`: LangChain message history
- `todos`: Task tracking list (via TodoWrite tool)
- `mentioned_agents`: @mention tracking for tools/skills/agents
- `active_skill`, `allowed_tools`: Skill context
- `context_id`, `parent_context`: Subagent isolation
- `loops`, `max_loops`: Loop control

**Model Registry** (generalAgent/models/registry.py)
- Five model slots: base, reasoning, vision, code, chat
- Models configured via `.env` (MODEL_BASIC_*, MODEL_REASONING_*, etc.)
- Supports OpenAI-compatible APIs (DeepSeek, Moonshot, GLM, etc.)

**Tool System** (generalAgent/tools/)
- Three-tier architecture:
  - `_discovered`: All scanned tools (including disabled)
  - `_tools`: Enabled tools (immediately available)
  - `load_on_demand()`: Load tools when @mentioned
- Configuration driven by `generalAgent/config/tools.yaml`
- Builtin tools in `generalAgent/tools/builtin/`
- Custom tools in `generalAgent/tools/custom/` (user-defined)

**Skill System** (generalAgent/skills/)
- Skills are **knowledge packages** (documentation + scripts), NOT tool containers
- Structure: `skills/{skill_id}/SKILL.md` + `scripts/` + reference docs
- Configuration driven by `generalAgent/config/skills.yaml`
  - `enabled: true/false` - Controls visibility in skills catalog
  - `auto_load_on_file_types: [...]` - Auto-load when matching files uploaded
  - Only enabled skills appear in SystemMessage catalog
- When user mentions `@skill` or uploads matching file, skills are symlinked to session workspace
- Agent uses `read_file` tool to read SKILL.md and follow guidance
- Agent can use `run_bash_command` tool to execute skill scripts
- Skills do NOT have `allowed_tools` field

**@Mention System** (generalAgent/utils/mention_classifier.py)
- Three types:
  - `@tool` - Load specific tool on demand
  - `@skill` - Generate reminder to read SKILL.md
  - `@agent` - Load call_subagent tool
- Mentions parsed in main.py and classified in planner.py

**KV Cache Optimization** ⭐ NEW (generalAgent/graph/nodes/planner.py, finalize.py)
- **Fixed SystemMessage**: Generated once at initialization, never changes
- **Minute-level timestamp**: `<current_datetime>YYYY-MM-DD HH:MM UTC</current_datetime>` placed at bottom of SystemMessage
- **Reminders moved to last message**: Dynamic reminders (TODOs, @mentions, file uploads) appended to last HumanMessage instead of SystemMessage
- **Result**: 70-90% KV Cache reuse, 60-80% cost reduction in multi-turn conversations
- See `docs/CONTEXT_MANAGEMENT.md` for detailed explanation

### Important Files

- `generalAgent/runtime/app.py` - Application assembly, tool/skill registry initialization
- `generalAgent/graph/builder.py` - LangGraph construction, node wiring
- `generalAgent/graph/nodes/planner.py` - Agent node logic, @mention handling, tool visibility
- `generalAgent/graph/routing.py` - Conditional edge routing (agent_route, tools_route)
- `generalAgent/config/settings.py` - Pydantic settings from .env
- `generalAgent/persistence/session_store.py` - SQLite session persistence
- `generalAgent/persistence/workspace.py` - Workspace manager for session isolation
- `generalAgent/tools/builtin/file_ops.py` - File operation tools (read_file, write_file, list_workspace_files)
- `generalAgent/tools/builtin/run_bash_command.py` - Execute bash commands and skill scripts
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
4. **Script Execution** - Agent uses `run_bash_command` to execute Python scripts
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

**run_bash_command** (disabled by default, requires @mention)
```bash
# Execute Python scripts from skills
run_bash_command("python skills/pdf/scripts/fill_fillable_fields.py uploads/form.pdf outputs/filled.pdf")

# Or with complex commands
run_bash_command("python skills/pdf/scripts/extract_form_field_info.py uploads/form.pdf outputs/fields.json")
```

## HITL (Human-in-the-Loop)

GeneralAgent supports two core HITL patterns for interactive agent workflows:

### 1. ask_human Tool - Agent Requests User Input

The `ask_human` tool allows the Agent to actively request information from the user when needed.

**Tool interface:**
```python
ask_human(
    question="Your question here",
    context="Why this information is needed",  # Optional
    input_type="text",  # Currently only "text" supported
    default=None,  # Optional default value
    required=True  # Whether answer is required
)
```

**Example usage:**
```
User> 帮我订个酒店
Agent> [calls ask_human tool]

💡 需要知道城市才能搜索酒店
💬 您想预订哪个城市的酒店？
> 北京

Agent> 好的，正在搜索北京的酒店...
```

**How it works:**
- Agent decides to call `ask_human` via LLM decision (just like any other tool)
- Graph execution pauses (LangGraph `interrupt()`)
- User provides input via CLI
- Answer is returned as ToolMessage and added to LLM context
- Agent continues with the answer

### 2. Tool Approval - System Intercepts Dangerous Operations

Dangerous tool operations automatically trigger user approval before execution.

**Configuration:** `generalAgent/config/hitl_rules.yaml`

```yaml
global:
  enabled: true
  default_action: allow

tools:
  run_bash_command:
    enabled: true
    patterns:
      high_risk:
        - "rm\\s+-rf"           # Force delete
        - "sudo"                # Privilege escalation
      medium_risk:
        - "curl"                # Network requests
        - "pip\\s+install"      # Package installation
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

**Example approval flow:**
```
User> @run_bash_command 帮我执行 rm -rf /tmp/test
Agent> [attempts to call run_bash_command]

🛡️  工具审批: run_bash_command
   原因: 匹配high_risk风险模式: rm\s+-rf
   参数: command="rm -rf /tmp/test"
   批准? [y/n] > n

✗ 已拒绝
Agent> 出于安全考虑，系统阻止了执行 rm -rf 命令...
```

**How it works:**
- Agent calls a tool normally (LLM decision)
- `ApprovalToolNode` intercepts the call before execution
- `ApprovalChecker` analyzes tool arguments against rules
- If risky, triggers `interrupt()` for user approval
- Approval/rejection is transparent to LLM (not in conversation history)
- If approved, tool executes normally
- If rejected, returns error ToolMessage to LLM

**Three-layer approval rules:**
1. **Config file** (`hitl_rules.yaml`) - Regex pattern matching
2. **Tool custom checkers** - Programmatic rules registered via `ApprovalChecker.register_checker()`
3. **Built-in defaults** - Hardcoded safety rules in `approval_checker.py`

### HITL Architecture

**Key Components:**

1. **ApprovalChecker** (`generalAgent/hitl/approval_checker.py`)
   - Examines tool arguments for risk patterns
   - Returns `ApprovalDecision` with risk level and reason
   - Supports regex pattern matching and custom checkers

2. **ApprovalToolNode** (`generalAgent/hitl/approval_node.py`)
   - Wraps LangGraph `ToolNode`
   - Intercepts tool calls before execution
   - Triggers `interrupt()` if approval needed
   - Returns rejection ToolMessage if user declines

3. **CLI Interrupt Handling** (`generalAgent/cli.py`)
   - After each `astream()`, checks for interrupts via `aget_state()`
   - Handles two interrupt types: `user_input_request` and `tool_approval`
   - Resumes execution with `Command(resume=value)`
   - Minimal UI prompts (极简版)

4. **LangGraph Checkpointer**
   - Required for interrupt/resume functionality
   - Currently uses `MemorySaver` (in-memory, session-scoped)
   - Can be upgraded to `AsyncSqliteSaver` for persistent checkpointing

**Note:** Approval decisions are NOT added to LLM conversation history - they're purely system-level behavior. Only tool results (approved execution or rejection message) are visible to the LLM.

## Skill Configuration

Skills can be controlled via `generalAgent/config/skills.yaml`:

```yaml
global:
  enabled: true
  auto_load_on_file_upload: true  # Auto-load skill when uploading matching files

core: []  # Skills always loaded at startup

optional:
  pdf:
    enabled: false  # Default: not loaded
    always_available: false
    description: "PDF processing and form filling"
    auto_load_on_file_types: ["pdf"]  # Auto-load when .pdf uploaded
```

**Skill loading behavior:**
1. **Default**: Skills are NOT loaded unless explicitly requested
2. **@mention**: `@pdf` loads the skill to workspace
3. **File upload**: Uploading a `.pdf` file auto-loads pdf skill (if `auto_load_on_file_upload: true`)
4. **Core skills**: Skills in `core: []` are loaded at startup (currently empty by default)

**Configuration options:**
- `enabled: true` - Show skill in catalog and load at startup
- `enabled: false` - Hide from catalog, only load via @mention or file upload
- `auto_load_on_file_types` - List of file extensions that trigger auto-load
- `always_available: true` - Keep skill loaded across all sessions (not recommended)

**Important behaviors:**
- **Skills catalog filtering**: Only `enabled: true` skills appear in the SystemMessage catalog
  - Reduces prompt noise and prevents information leakage
  - Agent won't know about disabled skills unless user @mentions them
- **Dynamic file upload hints**: When user uploads a file, hints are generated based on `auto_load_on_file_types`
  - Example: Uploading `report.docx` shows `[可用 @docx 处理]` if docx skill is configured
  - Hints are generated dynamically from `skills.yaml`, no hardcoded mappings

## Tool Configuration

Edit `generalAgent/config/tools.yaml` to control tool availability:

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

1. Create tool file in `generalAgent/tools/builtin/` or `generalAgent/tools/custom/`
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
   ├── requirements.txt   # Python dependencies (optional)
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

3. **(Optional) Dependency Management:**
   - If scripts require external libraries, create `requirements.txt`
   - Example `skills/pdf/requirements.txt`:
     ```
     pypdf2>=3.0.0
     reportlab>=4.0.0
     pillow>=10.0.0
     ```
   - Dependencies are **automatically installed** when user first @mentions the skill
   - Installation happens once per session, cached for future use

4. Skills are automatically available when user @mentions them

Example workflow:
```
User> @pdf 帮我填写这个PDF表单
System> [检测到 @pdf]
        [检查依赖: skills/pdf/requirements.txt]
        [自动安装: pip install -r requirements.txt]  # 首次使用时
        [已加载技能: pdf]
Agent> [Uses read_file to read skills/pdf/SKILL.md]
       [Follows instructions from SKILL.md]
       [Uses run_bash_command to execute: python skills/pdf/scripts/fill_fillable_fields.py ...]
```

### Dependency Installation Details

**When:** Dependencies are installed automatically when:
- User @mentions a skill for the first time in a session
- The skill has a `requirements.txt` file

**How it works:**
1. **Automatic detection**: WorkspaceManager checks for `requirements.txt` when linking skill
2. **One-time install**: Dependencies installed once, marked as cached in SkillRegistry
3. **Graceful degradation**: If installation fails, agent receives friendly error message

**Error handling:**
- Script import errors show clear message: "缺少 Python 模块 'module_name'"
- Suggests manual installation: `pip install module_name`
- Agent can inform user and request manual intervention if needed

**Example error message:**
```
Script execution failed: Missing dependency

错误: 缺少 Python 模块 'pypdf2'

建议操作:
1. 检查 skills/pdf/requirements.txt 是否包含此依赖
2. 手动安装: pip install pypdf2
3. 或联系技能维护者添加依赖声明
```

## HITL (Human-in-the-Loop) Mechanism

AgentGraph integrates two HITL patterns for human oversight and interaction:

### 1. ask_human Tool - Agent-Initiated Interaction

**Purpose**: Allow the agent to actively request information from users when needed.

**When to use:**
- Agent lacks necessary information to proceed
- Need user confirmation for critical decisions
- Require user choice between multiple options

**Tool Interface:**
```python
ask_human(
    question: str,              # The question to ask
    context: str = "",          # Additional context for the user
    input_type: "text",         # Currently only "text" supported
    default: Optional[str] = None,
    required: bool = True
)
```

**Example Usage:**
```
Agent> 我需要了解您的偏好才能继续。
       [Calls ask_human(question="您希望报告以什么格式输出？", ...)]

User receives:
💬 您希望报告以什么格式输出？
   (默认: markdown)
> PDF

Agent> 好的，我将生成 PDF 格式的报告。
```

**Implementation Details:**
- Uses `interrupt()` to pause graph execution
- User response stored in conversation history as ToolMessage
- Future extensibility: choice/multi_choice input types planned

### 2. Tool Approval Framework - System-Level Safety

**Purpose**: Detect and prevent potentially dangerous operations automatically.

**How it works:**
1. **Intercept**: ApprovalToolNode wraps ToolNode and examines all tool calls
2. **Evaluate**: ApprovalChecker uses three-layer rule system to determine risk
3. **Pause**: If approval needed, graph execution pauses via `interrupt()`
4. **Resume**: User approves/rejects, graph continues with result

**Four-Layer Approval Rules:**

**Priority 1 - Tool Custom Checkers** (highest priority)
```python
# Custom logic for specific tools
def check_bash_command(args: dict) -> ApprovalDecision:
    command = args.get("command", "")
    if re.search(r"rm\s+-rf", command):
        return ApprovalDecision(
            needs_approval=True,
            reason="删除命令可能影响系统文件",
            risk_level="high"
        )
```

**Priority 2 - Global Risk Patterns** (cross-tool detection)
```yaml
# generalAgent/config/hitl_rules.yaml
global:
  risk_patterns:
    critical:
      patterns:
        - "password\\s*[=:]\\s*['\"]?\\w+"      # Password leak
        - "api[_-]?key\\s*[=:]\\s*"             # API key leak
        - "secret\\s*[=:]\\s*"                  # Secret leak
      action: require_approval
      reason: "检测到敏感信息（密码/密钥/令牌）"
    high:
      patterns:
        - "/etc/passwd"                          # System files
        - "DROP\\s+(TABLE|DATABASE)"             # SQL deletion
```

**Priority 3 - Tool-Specific Config Rules**
```yaml
# generalAgent/config/hitl_rules.yaml
tools:
  run_bash_command:
    enabled: true
    patterns:
      high_risk:
        - "rm\\s+-rf"
        - "sudo"
      medium_risk:
        - "curl"
        - "wget"
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

**Priority 4 - Built-in Default Rules** (fallback)
```python
# Safe operations allowed by default
SAFE_COMMANDS = ["ls", "pwd", "cat", "grep", ...]
```

**User Experience (极简版):**
```
Agent decides to run: curl https://example.com

User sees:
🛡️  工具审批: run_bash_command
   原因: 网络请求需要确认
   参数: curl https://example.com
   批准? [y/n] > y

Agent continues with approved command
```

**Key Design Principles:**
- **Transparent to LLM**: Approval decisions NOT added to conversation context
- **Capability-level granularity**: Approval based on arguments, not entire tool
- **Four-layer architecture**: Custom checkers → Global patterns → Tool rules → Default
- **Cross-tool detection**: Global patterns detect risks across all tools (e.g., password leaks)
- **Extensible**: Easy to add new patterns and custom checkers
- **MVP-ready**: Production-quality error handling and user prompts

**Configuration:**
Edit `generalAgent/config/hitl_rules.yaml` to customize approval behavior:
```yaml
global:
  # Global risk patterns (apply to all tools)
  risk_patterns:
    critical:
      patterns:
        - "password\\s*[=:]\\s*['\"]?\\w+"
        - "api[_-]?key\\s*[=:]\\s*"
      action: require_approval
      reason: "检测到敏感信息"

tools:
  # Tool-specific rules
  http_fetch:
    enabled: true
    patterns:
      high_risk:
        - "internal\\.company\\.com"  # Block internal domains
    actions:
      high_risk: require_approval

  run_bash_command:
    enabled: true
    patterns:
      high_risk:
        - "rm\\s+-rf"
        - "sudo"
        - "chmod\\s+777"
      medium_risk:
        - "curl"
        - "wget"
        - "pip\\s+install"
```

**Implementation Files:**
- `generalAgent/hitl/approval_checker.py` - Four-layer rule system (lines 20-150)
- `generalAgent/hitl/approval_node.py` - ApprovalToolNode wrapper (lines 22-80)
- `generalAgent/tools/builtin/ask_human.py` - ask_human tool implementation
- `generalAgent/graph/builder.py:79-91` - Conditional ApprovalToolNode integration
- `generalAgent/cli.py:252-288` - Interrupt handling loop
- `generalAgent/cli.py:370-443` - User interaction handlers (极简版 UI)

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

### Settings Architecture

The configuration system uses **Pydantic BaseSettings** for automatic environment variable loading:

**Structure** (generalAgent/config/settings.py):
```python
Settings
├── ModelRoutingSettings     # Model IDs and credentials
├── GovernanceSettings       # Runtime controls (auto_approve, max_loops)
└── ObservabilitySettings    # Tracing, logging, persistence
```

**Key Features**:
- **Automatic .env loading** - All settings classes inherit from `BaseSettings`
- **Multiple aliases** - `AliasChoices` support provider-specific names (MODEL_BASIC_*, MODEL_REASONING_*, etc.)
- **No fallbacks needed** - Settings are loaded directly from environment, no manual `os.getenv()` calls
- **Type validation** - Pydantic validates types, ranges (e.g., `max_loops: int = Field(ge=1, le=500)`)

**Example**:
```python
from generalAgent.config.settings import get_settings

settings = get_settings()  # Cached singleton
api_key = settings.models.reason_api_key  # Automatically loaded from .env
max_loops = settings.governance.max_loops  # Default: 100
```

**Recent Optimization** (2025-10-27):
- Changed nested settings from `BaseModel` to `BaseSettings`
- Added `SettingsConfigDict(env_file=".env", ...)` to enable environment loading
- Removed manual fallback patterns (`or _env()`) from business logic
- All 5 reflective HITL tests now pass with proper model initialization

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

## Refactoring History (2025-10-24)

### Main.py Refactoring: Shared Infrastructure Extraction

**Motivation**: The original `main.py` (477 lines) contained too much business logic, making it difficult to:
- Add new agents (e.g., qaAgent, codeAgent)
- Maintain consistent session/workspace management
- Reuse CLI infrastructure across different agent types

**Changes**:

1. **Created `shared/` directory** for reusable infrastructure:
   - `shared/cli/base_cli.py` - Abstract CLI framework (command routing, main loop)
   - `shared/session/manager.py` - Session lifecycle management
   - `shared/session/store.py` - Moved from `generalAgent/persistence/`
   - `shared/workspace/manager.py` - Moved from `generalAgent/persistence/`

2. **Created `generalAgent/cli.py`**:
   - Extends `BaseCLI` with GeneralAgent-specific logic
   - Handles @mention parsing, file uploads, LangGraph streaming
   - ~300 lines of focused agent logic

3. **New `main.py`** (~60 lines):
   - Simple entrypoint that assembles components
   - Initializes shared infrastructure
   - Launches GeneralAgentCLI

4. **Updated `build_application()`**:
   - Now returns `(app, initial_state_factory, skill_registry, tool_registry)`
   - Provides registries for mention classification

**Benefits**:
- ✅ Easy to add new agents (just extend `BaseCLI` and create entrypoint)
- ✅ Shared session/workspace logic across all agents
- ✅ Clear separation: infrastructure (shared) vs business logic (agent-specific)
- ✅ 87% reduction in main.py complexity (477 → 60 lines)

**Migration Notes**:
- Old `main.py` backed up as `main_old.py`
- All functionality preserved (tested with `/help`, `/sessions`, `/load`, etc.)
- No changes to LangGraph, tools, skills, or core agent logic

## Recent Fixes

### Skills Configuration Management (2025-10-27)

**Issue**: Skills catalog showed all scanned skills regardless of `skills.yaml` configuration, and file upload hints were hardcoded.

**Fixed**:
1. **Skills Catalog Filtering** - `generalAgent/graph/prompts.py`
   - `build_skills_catalog()` now accepts `skill_config` parameter
   - Only shows skills with `enabled: true` in SystemMessage
   - Prevents information leakage about disabled skills

2. **Dynamic File Upload Hints** - `generalAgent/utils/file_processor.py`
   - `build_file_upload_reminder()` generates hints based on `auto_load_on_file_types`
   - Fixed office file type matching (uses file extension instead of generic "office" type)
   - Removed hardcoded `FILE_TYPE_TO_SKILL` constant

3. **Configuration Pipeline**
   - `build_application()` → loads and returns `skill_config`
   - `build_state_graph()` → passes `skill_config` to planner
   - `build_planner_node()` → uses `skill_config` for filtering and hints
   - Log message shows correct enabled skills count

**Files Modified**:
- `generalAgent/graph/prompts.py:160-169` - Catalog filtering
- `generalAgent/graph/nodes/planner.py:235-236` - Config usage and logging
- `generalAgent/graph/builder.py` - Config passing
- `generalAgent/runtime/app.py` - Config loading
- `generalAgent/utils/file_processor.py:265-276` - Dynamic hints
- `generalAgent/main.py` - Config reception

**Test**: `tests/unit/test_skills_filtering.py` and `tests/integration/test_skills_integration.py`

### Earlier Fixes (2025-10-24)

### 1. Skills Path Correction
- **Issue**: Code referenced `Path("skills")` instead of `Path("generalAgent/skills")`
- **Fixed**: Updated `main.py:268` and `generalAgent/runtime/app.py:117`

### 2. Symlink Path Resolution in list_workspace_files
- **Issue**: `list_workspace_files` used `resolve()` causing paths outside workspace
- **Fixed**: `generalAgent/tools/builtin/file_ops.py:214-241` - use logical paths

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
