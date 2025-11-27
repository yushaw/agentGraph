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

**For detailed testing guidelines**, see [docs/TESTING.md](docs/TESTING.md)

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
- `context_id`, `parent_context`: Delegated agent isolation
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
  - `@agent` - Load delegate_task tool
- Mentions parsed in main.py and classified in planner.py

**File Upload System** (generalAgent/utils/file_upload_parser.py)
- Use `#` prefix to reference files from `uploads/` directory
- Supported patterns:
  - `#filename.ext` - Single file
  - `#dir/file.ext` - File in subdirectory
  - `#dir/` - All files in directory (non-recursive)
  - `#dir/**` - All files recursively
  - `#dir/*.pdf` - Glob pattern
  - `#*.md` - Root directory glob
- Example: `分析 #demo_requirement/ 目录下的所有文档` expands to all files in that directory
- Files are copied to session workspace and injected into message content

**KV Cache Optimization** ⭐ NEW (generalAgent/graph/nodes/planner.py, finalize.py)
- **Fixed SystemMessage**: Generated once at initialization, never changes
- **Minute-level timestamp**: `<current_datetime>YYYY-MM-DD HH:MM UTC</current_datetime>` placed at bottom of SystemMessage
- **Reminders moved to last message**: Dynamic reminders (TODOs, @mentions, file uploads) appended to last HumanMessage instead of SystemMessage
- **Result**: 70-90% KV Cache reuse, 60-80% cost reduction in multi-turn conversations
- See [docs/OPTIMIZATION.md - Part 1](docs/OPTIMIZATION.md#part-1-context-management--kv-cache-optimization) for detailed explanation

### Important Files

- `generalAgent/runtime/app.py` - Application assembly, tool/skill registry initialization
- `generalAgent/graph/builder.py` - LangGraph construction, node wiring
- `generalAgent/graph/nodes/planner.py` - Agent node logic, @mention handling, tool visibility
- `generalAgent/graph/routing.py` - Conditional edge routing (agent_route, tools_route)
- `generalAgent/config/settings.py` - Pydantic settings from .env
- `generalAgent/persistence/session_store.py` - SQLite session persistence
- `generalAgent/persistence/workspace.py` - Workspace manager for session isolation
- `generalAgent/tools/builtin/file_ops.py` - File operation tools (read_file, write_file, list_workspace_files)
- `generalAgent/tools/builtin/find_files.py` - File name search tool (glob-based)
- `generalAgent/tools/builtin/search_file.py` - Content search tool (text and documents)
- `generalAgent/tools/builtin/run_bash_command.py` - Execute bash commands and skill scripts
- `generalAgent/utils/document_extractors.py` - Document content extraction (PDF/DOCX/XLSX/PPTX)
- `generalAgent/utils/text_indexer.py` - Global MD5-based indexing and search
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

The agent has access to a comprehensive set of file operation tools following the Unix philosophy (single responsibility principle).

**read_file** - Read file content with automatic format detection
```python
read_file("skills/pdf/SKILL.md")      # Read skill documentation
read_file("uploads/document.pdf")     # Read PDF preview
read_file("uploads/report.docx")      # Read DOCX preview
read_file("uploads/data.xlsx")        # Read Excel preview
read_file("uploads/slides.pptx")      # Read PowerPoint preview
```

**Supported formats:**
- **Text files** (<100KB): Full content
- **Text files** (>100KB): First 50K chars with truncation notice
- **Documents** (PDF/DOCX/XLSX/PPTX):
  - Small files (≤10 pages/sheets/slides): Full content
  - Large files: Preview with search hint
  - PDF/DOCX: First 10 pages (~30K chars)
  - XLSX: First 3 sheets (~20K chars)
  - PPTX: First 15 slides (~25K chars)

**find_files** - Fast file name pattern matching (like Unix find/glob)
```python
find_files("*.pdf")                      # All PDFs in workspace
find_files("**/*.py")                    # All Python files recursively
find_files("*report*", path="uploads")   # Files with "report" in name
find_files("*.{pdf,docx}")               # Multiple extensions
```

**search_file** - Search for content within files
```python
search_file("uploads/report.pdf", "Q3 revenue")           # Search in PDF
search_file("uploads/error.log", "ERROR", max_results=10) # Search in text
search_file("uploads/data.xlsx", "customer churn")        # Search in Excel
```

**Search strategies:**
- **Text files**: Real-time line-by-line scanning with context
- **Documents**: Index-based search with automatic indexing
  - First search creates index (2-5 seconds)
  - Subsequent searches are instant (<100ms)
  - Multi-strategy scoring: phrase match (10 pts) > trigrams (5 pts) > bigrams (3 pts) > keywords (2 pts)
  - Global MD5-based index cache in `data/indexes/`

**Document indexing details:**
- Indexes stored globally in `data/indexes/` with two-level directory structure
- MD5-based deduplication across sessions
- Automatic staleness detection and reindexing (24-hour threshold)
- **Orphan index cleanup**: When same-name file is replaced (different MD5), old index is automatically deleted
- **Index update strategy**:
  - Same content, different path → Use same index (efficient)
  - Same path, different content → Create new index, delete old (automatic)
  - File deleted → Index cleaned on next `cleanup_old_indexes()` call
- Chunking strategies:
  - PDF: By page (preserves table extraction)
  - DOCX: By paragraph (~1000 chars, maintains readability)
  - XLSX: By sheet (logical units)
  - PPTX: By slide

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

**screenshot** (Windows 10/11) - Capture screen content
```python
screenshot()                        # Capture primary monitor
screenshot(filename="error_state")  # Custom filename
screenshot(monitor=1)               # Capture specific monitor (0-based index)
screenshot(all_monitors=True)       # Capture all monitors combined
screenshot(active_window=True)      # Capture currently active window
screenshot(hwnd=12345)              # Capture specific window by handle
```

**list_monitors** (Windows 10/11) - List available monitors
```python
list_monitors()
# -> Monitor 0 (Primary): 1920x1080 at (0, 0)
#    Monitor 1: 2560x1440 at (1920, 0)
```

**list_windows** (Windows 10/11) - List windows with handles
```python
list_windows()
# -> hwnd=12345 | 1200x800 | Chrome - Google
#    hwnd=67890 | 800x600  | Notepad
```

**get_active_window** (Windows 10/11) - Get active window info
```python
get_active_window()
# -> Active window: hwnd=12345, title=Chrome - Google, size=1200x800
```

**Screenshot tool requirements**: `pip install pywin32 pillow`

**Tool selection guide:**
- Use `find_files` when: Looking for files by name/pattern
- Use `read_file` when: Want to see document content/preview
- Use `search_file` when: Looking for specific keywords or information within a file
- Use `screenshot` when: Need to capture user's current screen state
- For large documents: Always prefer `search_file` over `read_file` for finding specific content

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
- `available_to_subagent: true` - Tool is available to delegated subagents when inherited from main agent

### Subagent Tool Inheritance

When using `delegate_task` to create a subagent, the subagent automatically inherits:

1. **@mentioned tools** - All tools that were @mentioned by the main agent
2. **@mentioned skills** - The active skill from the main agent
3. **Workspace** - Same workspace directory (shared file access)
4. **Uploaded files** - All files uploaded in the session

**Tool availability levels:**
- **Core tools** (in `core:` section) - Always `available_to_subagent: true` by default
- **Optional tools with `available_to_subagent: true`** - Available to subagent when main agent @mentions them
- **Optional tools with `available_to_subagent: false`** - NOT inherited by subagent (even if main agent used them)

**Example configuration:**
```yaml
optional:
  fetch_web:
    enabled: true
    available_to_subagent: true  # Subagent can inherit this
    category: "network"

  search_web:
    enabled: true
    available_to_subagent: true  # Subagent can inherit this
    category: "network"

  compact_context:
    enabled: false
    available_to_subagent: false  # Subagent cannot inherit this
    category: "meta"
```

**User workflow example:**
```
User> @fetch_web 帮我研究一下 Python 3.13 的新特性
Agent> [Loads fetch_web tool, uses it to fetch content]
       [Decides to delegate deep analysis]
       [Calls delegate_task("分析 Python 3.13 新特性...")]

Subagent> [Inherits fetch_web tool automatically]
          [Can continue fetching web pages without re-@mentioning]
          [Produces detailed analysis]
```

**Implementation details:**
- Parent state stored in `delegate_task._parent_state_store` before tool execution (generalAgent/graph/nodes/planner.py:360-376)
- Subagent retrieves parent state via `config` injection (generalAgent/tools/builtin/delegate_task.py:91-116)
- Subagent inherits `mentioned_agents`, `active_skill`, `workspace_path`, `uploaded_files`

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

## Context Management Configuration ⭐ NEW

AgentGraph includes automatic context compression to manage long conversations efficiently. When token usage exceeds the critical threshold (default: 95%), the system automatically compresses older messages while preserving recent context.

### Configuration Parameters

All context management settings are configured via `.env` file:

```bash
# Enable/disable context management
CONTEXT_MANAGEMENT_ENABLED=true

# Token monitoring thresholds (0.01-0.99)
CONTEXT_INFO_THRESHOLD=0.75        # 75% - Log info message
CONTEXT_WARNING_THRESHOLD=0.85     # 85% - Log warning
CONTEXT_CRITICAL_THRESHOLD=0.95    # 95% - Trigger auto-compression

# Recent message preservation
CONTEXT_KEEP_RECENT_RATIO=0.15     # Keep 15% of context window as recent
CONTEXT_KEEP_RECENT_MESSAGES=10    # Or keep at least 10 messages (whichever reached first)

# Compression trigger condition
CONTEXT_MIN_MESSAGES_TO_COMPRESS=15  # Minimum messages before compression

# Emergency fallback (if LLM compression fails)
CONTEXT_MAX_HISTORY=100            # Keep last 100 messages max
```

### How Auto-Compression Works

1. **Token Monitoring** - System tracks `cumulative_prompt_tokens` after each LLM call
2. **Critical Detection** - When usage exceeds `CONTEXT_CRITICAL_THRESHOLD`, planner sets `needs_compression` flag
3. **Routing to Compression** - Conditional routing directs to dedicated summarization node
4. **Silent Compression** - Old messages compressed via LLM, recent messages preserved
5. **Return to Agent** - After compression, flow returns to agent to continue answering user's question

**User Experience**: Compression is completely silent (no notifications). The agent continues the conversation seamlessly.

**Example**: A conversation with 302 messages (~123K tokens, 96% usage) compresses to 13 messages (~6.5K tokens, 95% reduction) while preserving full context through LLM summarization.

**Key Files**:
- `generalAgent/graph/nodes/summarization.py` - Dedicated compression node
- `generalAgent/graph/routing.py` - Routing logic with compression trigger
- `generalAgent/context/compressor.py` - Core compression implementation
- `generalAgent/config/settings.py` - Configuration schema

For architectural details, see [docs/ARCHITECTURE.md - Section 1.5](docs/ARCHITECTURE.md).

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

## Documentation Structure

The project documentation has been reorganized (2025-10-27) for better clarity and maintainability:

### Core Documentation (docs/)

**Six core documents** replacing the previous 14-document structure:

1. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
   - Core architecture (Agent Loop, State, Nodes, Routing)
   - Tool system (Three-tier, Discovery, Configuration, TODO tools)
   - Skill system (Knowledge packages, Registry, Dependencies)
   - Best practices (Path handling, Prompt engineering, Error handling)

2. **[docs/FEATURES.md](docs/FEATURES.md)** - User-facing features
   - Workspace isolation
   - @Mention system
   - File upload
   - Message history
   - Delegated agent system
   - MCP integration
   - HITL (Human-in-the-Loop)

3. **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development guide
   - Environment setup
   - Developing tools
   - Developing skills
   - Extending the system
   - Best practices
   - Debugging

4. **[docs/OPTIMIZATION.md](docs/OPTIMIZATION.md)** - Performance optimization
   - Context management & KV Cache (70-90% reuse)
   - Document search optimization
   - Text indexer (SQLite FTS5)
   - Other optimizations

5. **[docs/TESTING.md](docs/TESTING.md)** - Testing guide
   - Four-tier test architecture
   - Unit, Integration, E2E tests
   - HITL testing
   - Test development guidelines

6. **[docs/README.md](docs/README.md)** - Documentation index & maintenance guide
   - Quick navigation
   - Update procedures
   - Finding information
   - Contributing guidelines

### Language Versions

Documentation is available in both English and Chinese:
- **English**: [docs/en/](docs/en/) - Full English documentation
- **Chinese**: [docs/](docs/) - 中文文档（默认）
- All six core documents are fully translated
- Use language switcher links at bottom of each document

### Quick Links

- **Getting Started**: [README.md](README.md) → [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- **Architecture Overview**: [docs/ARCHITECTURE.md - Part 1](docs/ARCHITECTURE.md)
- **Feature Guide**: [docs/FEATURES.md](docs/FEATURES.md)
- **Tool Development**: [docs/DEVELOPMENT.md - Part 2](docs/DEVELOPMENT.md)
- **Skill Development**: [docs/DEVELOPMENT.md - Part 3](docs/DEVELOPMENT.md)
- **Testing**: [docs/TESTING.md](docs/TESTING.md)
- **Performance**: [docs/OPTIMIZATION.md](docs/OPTIMIZATION.md)

### Documentation Maintenance

When updating documentation:
1. Identify affected documents (see [docs/README.md - Maintenance Guide](docs/README.md#documentation-maintenance-guide))
2. Update relevant sections with code examples and file paths
3. Update cross-references
4. Add entry to CHANGELOG.md
5. Verify all links and examples

For detailed maintenance procedures, see [docs/README.md](docs/README.md).
