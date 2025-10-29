# Architecture Documentation

> **Note**: This document consolidates technical architecture details from REQUIREMENTS_PART1 (Core Architecture & Tool/Skill Systems), selected best practices from REQUIREMENTS_PART4, and SKILLS_CONFIGURATION.

**Last Updated**: 2025-10-27

---

## Table of Contents

- [Part 1: Core Architecture](#part-1-core-architecture)
  - [1.1 Agent Loop Architecture](#11-agent-loop-architecture)
  - [1.2 State Management](#12-state-management)
  - [1.3 Node System](#13-node-system)
  - [1.4 Routing System](#14-routing-system)
- [Part 2: Tool System](#part-2-tool-system)
  - [2.1 Three-Tier Architecture](#21-three-tier-architecture)
  - [2.2 Tool Discovery and Scanning](#22-tool-discovery-and-scanning)
  - [2.3 Tool Configuration](#23-tool-configuration)
  - [2.4 Tool Metadata](#24-tool-metadata)
  - [2.5 Persistent Tools](#25-persistent-tools)
  - [2.6 Tool Visibility](#26-tool-visibility)
  - [2.7 TODO Tool System](#27-todo-tool-system)
- [Part 3: Skill System](#part-3-skill-system)
  - [3.1 Skills as Knowledge Packages](#31-skills-as-knowledge-packages)
  - [3.2 Skill Registry](#32-skill-registry)
  - [3.3 Skill Configuration](#33-skill-configuration)
  - [3.4 Skill Loading](#34-skill-loading)
  - [3.5 Skill Dependencies](#35-skill-dependencies)
  - [3.6 Skills Catalog](#36-skills-catalog)
  - [3.7 Skill Script Execution](#37-skill-script-execution)
- [Part 4: Best Practices & Design Patterns](#part-4-best-practices--design-patterns)
  - [4.1 Path Handling](#41-path-handling)
  - [4.2 Prompt Engineering](#42-prompt-engineering)
  - [4.3 Error Handling](#43-error-handling)
  - [4.4 Logging and Debugging](#44-logging-and-debugging)
  - [4.5 Configuration Management](#45-configuration-management)

---

## Part 1: Core Architecture

### 1.1 Agent Loop Architecture

**Design Philosophy**: The system adopts an Agent Loop architecture (Claude Code style), NOT a traditional Plan-and-Execute pattern.

**Core Concept**:
- Agent operates in a single loop autonomously deciding execution flow
- Uses `tool_calls` to determine whether to continue calling tools or finish task
- No pre-planning required - responds dynamically to results

**Technical Implementation**:

```python
# generalAgent/graph/builder.py:79-100
graph.add_conditional_edges(
    "agent",
    agent_route,
    {
        "tools": "tools",      # LLM wants to call tools
        "finalize": "finalize",  # LLM decided to finish
    }
)

graph.add_conditional_edges(
    "tools",
    tools_route,
    {
        "agent": "agent",  # Continue loop
    }
)
```

**Flow Diagram**:
```
START → agent ⇄ tools → agent → finalize → END
         ↑_______↓
```

**Design Considerations**:
- Simplified architecture reduces node count
- Empowers LLM with greater autonomy
- TodoWrite tool for task tracking (observer pattern, not commander)
- Loop limit protection prevents infinite loops

---

### 1.2 State Management

**Design**: Uses TypedDict-defined AppState to manage all conversation state.

**State Fields**:

```python
# generalAgent/graph/state.py
class AppState(TypedDict):
    messages: Annotated[List, add_messages]  # Message history
    images: List                              # Image list
    active_skill: Optional[str]              # Currently activated skill
    allowed_tools: List[str]                 # Allowed tool list
    mentioned_agents: List[str]              # @mentioned agents
    persistent_tools: List                   # Persistent tools
    model_pref: Optional[str]                # Model preference
    todos: List[dict]                        # Task list
    context_id: str                          # Context ID
    parent_context: Optional[str]            # Parent context
    loops: int                               # Loop counter
    max_loops: int                           # Maximum loops
    thread_id: Optional[str]                 # Thread ID
    user_id: Optional[str]                   # User ID
    workspace_path: Optional[str]            # Workspace path
```

**Key Fields Explained**:
- `messages`: Uses LangChain's `add_messages` reducer for message history management
- `todos`: Supports dynamic task tracking (pending/in_progress/completed)
- `context_id` + `parent_context`: Enables delegated agent context isolation
- `loops` + `max_loops`: Prevents infinite loops

**Design Considerations**:
- TypedDict provides type hints while maintaining dictionary flexibility
- State fields cover all runtime requirements
- Supports nested delegated agent calls

---

### 1.3 Node System

**Design**: Three core nodes constitute the complete execution flow.

**Node Definitions**:

**1. agent node** (planner.py)
   - **Responsibility**: Analyze tasks, decide to call tools or finish
   - **Input**: User messages + tool results
   - **Output**: tool_calls or finish signal

**2. tools node** (LangGraph ToolNode)
   - **Responsibility**: Execute tool calls
   - **Input**: tool_calls
   - **Output**: ToolMessage

**3. finalize node**
   - **Responsibility**: Generate final response
   - **Input**: Complete conversation history
   - **Output**: Final AIMessage

**Implementation Location**:

```python
# generalAgent/graph/builder.py:56-69
agent_node = build_planner_node(...)
finalize_node = build_finalize_node(...)

graph.add_node("agent", agent_node)
graph.add_node("tools", ToolNode(tool_registry.list_tools()))
graph.add_node("finalize", finalize_node)
```

---

### 1.4 Routing System

**Design**: Conditional edges control transitions between nodes.

**Routing Functions**:

**1. agent_route** (generalAgent/graph/routing.py:6-20)

```python
def agent_route(state: AppState) -> Literal["tools", "finalize"]:
    messages = state["messages"]
    last = messages[-1]

    # Check loop limit
    if state["loops"] >= state["max_loops"]:
        return "finalize"

    # LLM wants to call tools
    if last.tool_calls:
        return "tools"

    # LLM finished
    return "finalize"
```

**2. tools_route** (generalAgent/graph/routing.py:23-26)

```python
def tools_route(state: AppState) -> Literal["agent"]:
    return "agent"  # Always return to agent
```

**Design Considerations**:
- Simple conditional logic, avoiding complexity
- Forced loop limit prevents infinite loops
- Tools node always returns to agent (closed loop)

---

## Part 2: Tool System

### 2.1 Three-Tier Architecture

**Design Philosophy**: Tools are organized into three layers: discovered (all), registered (enabled), and visible (context-specific).

**Layer Definitions**:

**Layer 1: discovered (Discovery Pool)**
- All scanned tools (including disabled ones)
- Stored in `ToolRegistry._discovered: Dict[str, Any]`
- Supports on-demand loading

**Layer 2: registered (Enabled Tools)**
- Enabled tools (enabled: true)
- Stored in `ToolRegistry._tools: Dict[str, Any]`
- Auto-registered at startup

**Layer 3: visible (Context-Visible Tools)**
- Tools available in current context
- Dynamically built via `build_visible_tools()`
- Includes: persistent_tools + allowed_tools + dynamically loaded @mention tools

**Implementation**:

```python
# generalAgent/tools/registry.py
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Any] = {}           # Layer 2
        self._meta: Dict[str, ToolMeta] = {}
        self._discovered: Dict[str, Any] = {}      # Layer 1

    def register_discovered(self, tool: Any):
        """Register tool in discovered pool (Layer 1)"""
        self._discovered[tool.name] = tool

    def register_tool(self, tool: Any):
        """Register tool as enabled (Layer 2)"""
        self._tools[tool.name] = tool

    def load_on_demand(self, tool_name: str) -> Optional[Any]:
        """Load tool from discovered pool when @mentioned"""
        if tool_name in self._discovered:
            tool = self._discovered[tool_name]
            self.register_tool(tool)
            return tool
        return None
```

**Design Considerations**:
- Layer 1 supports plugin discovery without memory overhead
- Layer 2 is core toolset loaded at startup
- Layer 3 is runtime dynamic visibility (most important)

---

### 2.2 Tool Discovery and Scanning

**Design**: Automatically scan specified directories to discover all tools.

**Scan Directories**:
- `generalAgent/tools/builtin/`: Built-in tools
- `generalAgent/tools/custom/`: User-defined tools
- Other configured directories (tools.yaml)

**Scanning Logic**:

```python
# generalAgent/tools/scanner.py:89-135
def scan_multiple_directories(directories: List[Path]) -> Dict[str, Any]:
    all_tools = {}

    for dir_path in directories:
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            tools = _extract_tools_from_module(py_file)
            all_tools.update(tools)

    return all_tools
```

**Multi-Tool File Support**:

```python
# generalAgent/tools/scanner.py:52-86
def _extract_tools_from_module(file_path: Path) -> Dict[str, Any]:
    """Extract ALL tools from a module via __all__ or introspection"""

    # Method 1: Use __all__ if defined
    if hasattr(module, "__all__"):
        tool_names = module.__all__
        for name in tool_names:
            obj = getattr(module, name)
            if isinstance(obj, BaseTool):
                tools[obj.name] = obj

    # Method 2: Introspect all attributes
    else:
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool) and not name.startswith("_"):
                tools[obj.name] = obj

    return tools
```

**Design Considerations**:
- Use `__all__` for explicit exports (recommended)
- Fallback to auto-detection (convenience)
- Supports multiple tools per file

---

### 2.3 Tool Configuration

**Design**: Centrally manage tool configuration through tools.yaml.

**Configuration File Structure**:

```yaml
# generalAgent/config/tools.yaml
core:
  now:
    category: "meta"
    tags: ["meta", "time"]
    description: "Get current UTC time"

optional:
  http_fetch:
    enabled: true
    available_to_subagent: false
    category: "network"
    tags: ["network", "read"]

  extract_links:
    enabled: false
    category: "read"
    tags: ["read", "parse"]
```

**Configuration Loading**:

```python
# generalAgent/tools/config_loader.py:105-126
class ToolConfig:
    def get_all_enabled_tools(self) -> Set[str]:
        """Return all tools with enabled=true"""
        enabled = set()

        # Core tools always enabled
        enabled.update(self.config.get("core", {}).keys())

        # Optional tools if enabled
        for name, cfg in self.config.get("optional", {}).items():
            if cfg.get("enabled", False):
                enabled.add(name)

        return enabled

    def is_available_to_subagent(self, tool_name: str) -> bool:
        """Check if tool should be in all contexts"""
        meta = self._find_tool_config(tool_name)
        return meta.get("available_to_subagent", False)
```

**Design Considerations**:
- Configuration-driven, no code changes needed
- `core` vs `optional` distinguishes system tools from optional tools
- `available_to_subagent` controls global visibility

---

### 2.4 Tool Metadata

**Design**: Provide rich metadata for each tool to support categorization, search, and documentation generation.

**Metadata Definition**:

```python
# generalAgent/tools/__init__.py:13-22
@dataclass
class ToolMeta:
    name: str
    category: str
    tags: List[str]
    description: str
    available_to_subagent: bool = False
    dependencies: List[str] = field(default_factory=list)
```

**Metadata Registration**:

```python
# generalAgent/runtime/app.py:78-88
all_metadata = tool_config.get_all_tool_metadata()
for meta in all_metadata:
    try:
        registry.register_meta(meta)
        LOGGER.debug(f"✓ Registered metadata for: {meta.name}")
    except KeyError:
        LOGGER.warning(f"✗ Metadata found but tool not registered: {meta.name}")
```

**Use Cases**:
- Tool search and discovery
- Auto-generate tool documentation
- Dependency management
- Category browsing

---

### 2.5 Persistent Tools

**Design**: Certain tools need to be always available across all contexts.

**Configuration**:

```yaml
# tools.yaml
optional:
  todo_write:
    enabled: true
    available_to_subagent: true  # Visible in all contexts
```

**Implementation**:

```python
# generalAgent/runtime/app.py:89-99
persistent = []
for tool_name in enabled_tools:
    if tool_config.is_available_to_subagent(tool_name):
        try:
            persistent.append(registry.get_tool(tool_name))
        except KeyError:
            LOGGER.warning(f"Tool '{tool_name}' configured but not found")
```

**Passed to Nodes**:

```python
# generalAgent/graph/nodes/planner.py:224-226
visible_tools = build_visible_tools(
    state=state,
    tool_registry=tool_registry,
    persistent_global_tools=persistent_global_tools,  # Always included
)
```

**Typical Persistent Tools**:
- `todo_write` / `todo_read`: Task tracking
- `now`: Get current time
- `delegate_task`: Subtask delegation (on-demand loading)

---

### 2.6 Tool Visibility

**Design**: Dynamically build tool visibility list based on current state.

**Implementation**:

```python
# generalAgent/graph/nodes/planner.py:180-226
def build_visible_tools(
    *,
    state: AppState,
    tool_registry: ToolRegistry,
    persistent_global_tools: List,
) -> List:
    """Build list of tools visible to agent in current context"""

    visible = []
    seen_names = set()

    # Step 1: Add persistent global tools
    for tool in persistent_global_tools:
        if tool.name not in seen_names:
            visible.append(tool)
            seen_names.add(tool.name)

    # Step 2: Add skill-specific tools (from active_skill)
    for tool_name in state.get("allowed_tools", []):
        if tool_name not in seen_names:
            tool = tool_registry.get_tool(tool_name)
            if tool:
                visible.append(tool)
                seen_names.add(tool_name)

    # Step 3: Add @mentioned tools (on-demand loading)
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "tool" and mention not in seen_names:
            tool = tool_registry.load_on_demand(mention)
            if tool:
                visible.append(tool)
                seen_names.add(mention)

    return visible
```

**Three-Step Build Process**:
1. **Persistent tools**: Always available (e.g., todo_write)
2. **Skill tools**: Current active skill's tools (allowed_tools)
3. **@mentioned tools**: User dynamically requested tools (on-demand loading)

**Design Considerations**:
- Deduplication (seen_names set)
- Priority order (persistent > allowed > mentioned)
- Dynamic loading (load_on_demand)

---

### 2.7 TODO Tool System

**Design**: A specialized tool system for task tracking using LangGraph Command objects for state synchronization.

**Core Components**:

**1. todo_write Tool** (`generalAgent/tools/builtin/todo_write.py`)

```python
@tool
def todo_write(
    todos: List[dict],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Track multi-step tasks (3+ steps). Helps user see progress.

    Task states: pending | in_progress | completed
    Required fields: content, status
    Optional fields: id (auto-generated), priority (default: medium)

    Rules:
    - Mark in_progress BEFORE starting work
    - Mark completed IMMEDIATELY after finishing (don't batch)
    - Only ONE in_progress at a time
    - Don't mark completed if tests fail, errors occur, or incomplete
    """
    # Validate todos
    for todo in todos:
        if "content" not in todo or "status" not in todo:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="❌ 错误: 每个任务必须包含 'content' 和 'status' 字段",
                            tool_call_id=tool_call_id
                        )
                    ]
                }
            )

    # Check only one in_progress
    in_progress = [t for t in todos if t["status"] == "in_progress"]
    if len(in_progress) > 1:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"❌ 错误: 只能有一个任务处于 'in_progress' 状态",
                        tool_call_id=tool_call_id
                    )
                ]
            }
        )

    # Success: update both todos and messages
    return Command(
        update={
            "todos": todos,  # ← Update state["todos"]
            "messages": [
                ToolMessage(
                    content=f"✅ TODO 列表已更新: {incomplete_count} 个待完成",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )
```

**2. todo_read Tool** (`generalAgent/tools/builtin/todo_read.py`)

```python
@tool
def todo_read(state: Annotated[dict, InjectedState]) -> dict:
    """Read the current todo list to check task status.

    Use this tool proactively and frequently to stay aware of:
    - What tasks are still pending or in progress
    - What you should work on next
    - Whether all tasks are completed

    Returns:
        dict with todos, summary (pending/in_progress/completed counts)
    """
    todos = state.get("todos", [])

    summary = {
        "pending": len([t for t in todos if t.get("status") == "pending"]),
        "in_progress": len([t for t in todos if t.get("status") == "in_progress"]),
        "completed": len([t for t in todos if t.get("status") == "completed"]),
        "total": len(todos)
    }

    return {
        "ok": True,
        "todos": todos,
        "summary": summary
    }
```

**3. TODO Reminder Display** (`generalAgent/graph/nodes/planner.py:190-230`)

```python
# Add todo reminder if there are todos
todos = state.get("todos", [])
if todos:
    in_progress = [t for t in todos if t.get("status") == "in_progress"]
    pending = [t for t in todos if t.get("status") == "pending"]
    completed = [t for t in todos if t.get("status") == "completed"]

    incomplete = in_progress + pending

    if incomplete:
        # Build detailed reminder
        todo_lines = []

        # Show in_progress task(s)
        if in_progress:
            for task in in_progress:
                priority = task.get('priority', 'medium')
                priority_tag = f"[{priority}]" if priority != "medium" else ""
                todo_lines.append(f"  [进行中] {task.get('content')} {priority_tag}".strip())

        # Show all pending tasks
        if pending:
            for task in pending:
                priority = task.get('priority', 'medium')
                priority_tag = f"[{priority}]" if priority != "medium" else ""
                todo_lines.append(f"  [待完成] {task.get('content')} {priority_tag}".strip())

        # Strong reminder to prevent early stopping
        todo_reminder = f"""<system_reminder>
⚠️ 任务追踪 ({len(incomplete)} 个未完成):
{chr(10).join(todo_lines)}
{completed_summary}

请继续完成所有待完成任务。使用 todo_write 更新任务状态。
</system_reminder>"""
```

**Key Features**:

**State Synchronization via Command**:
- `todo_write` returns `Command(update={"todos": ..., "messages": ...})`
- LangGraph automatically merges updates into state
- Both state and conversation history are updated atomically

**Validation Rules**:
- Required fields: `content`, `status`
- Valid statuses: `pending`, `in_progress`, `completed`
- Only ONE task can be `in_progress` at a time
- Auto-generates `id` if missing
- Default `priority` is `medium`

**Integration with ToolNode**:
- Works seamlessly with standard LangGraph ToolNode
- No special handling needed
- Command object triggers state update before returning to agent

**Design Considerations**:
- **Command pattern**: Clean separation between tool logic and state updates
- **Validation-first**: Catches errors before state modification
- **Atomic updates**: State and messages updated together
- **Reminder system**: Prevents agent from forgetting incomplete tasks
- **Priority support**: Tasks can have high/medium/low priority

---

## Part 3: Skill System

### 3.1 Skills as Knowledge Packages

**Core Concept**: Skills are knowledge packages (documentation + scripts), NOT tool containers.

**Key Principles**:
- Skills do NOT contain `allowed_tools` field
- Agent reads SKILL.md and autonomously chooses which tools to use
- Avoids hard-coding tool lists (more flexible)
- Scripts are optional execution resources

**Directory Structure**:

```
skills/pdf/
├── SKILL.md           # Main documentation (required)
├── requirements.txt   # Python dependencies (optional)
├── reference.md       # Reference documentation (optional)
├── forms.md           # Specific guides (optional)
└── scripts/           # Python scripts (optional)
    ├── fill_fillable_fields.py
    └── extract_text.py
```

**SKILL.md Example**:

```markdown
# PDF Processing Skill

## Overview
This skill provides PDF file processing capabilities, including form filling, text extraction, page operations, etc.

## Usage Steps
1. Use `read_file` to read PDF file
2. Choose appropriate script based on task
3. Use `run_skill_script` to execute script
4. Check output results

## Available Scripts
- `fill_fillable_fields.py`: Fill fillable PDF forms
- `extract_text.py`: Extract PDF text content

## Example
Fill PDF form:
\`\`\`python
run_skill_script(
    skill_id="pdf",
    script_name="fill_fillable_fields.py",
    args='{"input_pdf": "uploads/form.pdf", ...}'
)
\`\`\`
```

**Design Considerations**:
- **Flexibility**: Agent can choose most appropriate tools based on task
- **Extensibility**: Adding new tools doesn't require skill definition changes
- **Simplicity**: Skills only contain metadata and documentation
- **Intelligence**: Trust LLM's reasoning capabilities

---

### 3.2 Skill Registry

**Design**: Automatically scan and register skill packages.

**Implementation**:

```python
# generalAgent/skills/registry.py:30-60
class SkillRegistry:
    def __init__(self, skills_root: Path):
        self._skills_root = skills_root
        self._skills: Dict[str, Skill] = {}
        self._scan_skills()

    def _scan_skills(self):
        """Scan skills directory and register all skills"""
        if not self._skills_root.exists():
            return

        for skill_dir in self._skills_root.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # Parse skill metadata from SKILL.md
            meta = self._parse_skill_metadata(skill_md)

            skill = Skill(
                id=skill_dir.name,
                name=meta.get("name", skill_dir.name),
                description=meta.get("description", ""),
                path=skill_dir,
            )

            self._skills[skill.id] = skill
```

**Metadata Parsing**:

```python
def _parse_skill_metadata(self, skill_md: Path) -> dict:
    with open(skill_md, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # First # heading is name
    # First paragraph is description
    name = None
    description = ""

    for line in lines[:10]:
        if line.startswith("# "):
            name = line[2:].strip()
        elif line.strip() and not line.startswith("#"):
            description = line.strip()
            break

    return {"name": name, "description": description}
```

---

### 3.3 Skill Configuration

**Design**: Control skill behavior through skills.yaml configuration.

**Configuration File**: `generalAgent/config/skills.yaml`

```yaml
# Global settings
global:
  enabled: true                    # Enable/disable entire skills system
  auto_load_on_file_upload: true  # Auto-load skills when matching files uploaded

# Core skills - Always loaded at startup
core: []  # Empty by default

# Optional skills - Load on demand
optional:
  pdf:
    enabled: false                           # Show in catalog and load at startup
    available_to_subagent: false                  # Keep loaded across all sessions
    description: "PDF processing and form filling"
    auto_load_on_file_types: ["pdf"]        # Auto-load when .pdf files uploaded

  docx:
    enabled: true
    available_to_subagent: false
    description: "DOCX file processing"
    auto_load_on_file_types: ["docx"]

  xlsx:
    enabled: true
    available_to_subagent: false
    description: "Excel file processing"
    auto_load_on_file_types: ["xlsx", "xls"]
```

**Configuration Options**:

- **`enabled: true/false`**
  - `true`: Skill appears in SystemMessage catalog, available from startup
  - `false`: Skill hidden from catalog, only loads via @mention or file upload
  - **Use case**: Hide experimental or rarely-used skills to reduce prompt noise

- **`available_to_subagent`**: Keep skill loaded across all sessions (not recommended)
  - Default: `false` (skills load per-session)

- **`description`**: Human-readable description shown in catalog

- **`auto_load_on_file_types`**: File extensions that trigger auto-loading
  - Example: `["pdf"]`, `["docx", "doc"]`, `["xlsx", "xls", "csv"]`
  - Uses actual file extensions (not generic types like "office")

**How It Works**:

**1. Skills Catalog Filtering** (`generalAgent/graph/prompts.py`)

```python
def build_skills_catalog(skill_registry, skill_config=None):
    all_skills = skill_registry.list_meta()

    if skill_config:
        enabled_skill_ids = set(skill_config.get_enabled_skills())
        skills = [s for s in all_skills if s.id in enabled_skill_ids]
    else:
        skills = all_skills  # Fallback: show all

    # Build catalog...
```

**Benefits**:
- Reduces SystemMessage size
- Prevents information leakage about disabled skills
- Agent won't try to use skills it doesn't know about

**2. Dynamic File Upload Hints** (`generalAgent/utils/file_processor.py`)

```python
def build_file_upload_reminder(processed_files, skill_config=None):
    for file in documents:
        # Extract file extension (e.g., "docx", "pdf")
        file_ext = Path(filename).suffix.lstrip('.').lower()

        # Find skills that handle this extension
        skills_for_type = skill_config.get_skills_for_file_type(file_ext)

        if skills_for_type:
            skill_mentions = ", ".join([f"@{s}" for s in skills_for_type])
            skill_hint = f" [可用 {skill_mentions} 处理]"
```

**Example Output**:
```
用户上传了 3 个文件：
1. report.pdf (PDF, 1.5 MB) → uploads/report.pdf [可用 @pdf 处理]
2. data.xlsx (OFFICE, 500 KB) → uploads/data.xlsx [可用 @xlsx 处理]
3. summary.docx (OFFICE, 300 KB) → uploads/summary.docx [可用 @docx 处理]
```

---

### 3.4 Skill Loading

**Skill Loading Behavior**:

1. **Default**: Skills are NOT loaded unless explicitly requested
2. **@mention**: `@pdf` loads the skill to workspace
3. **File upload**: Uploading a `.pdf` file auto-loads pdf skill (if `auto_load_on_file_upload: true`)
4. **Core skills**: Skills in `core: []` are loaded at startup (currently empty by default)

**Configuration Pipeline**:

```
build_application()
  ↓ loads skills.yaml
  ↓ returns skill_config
  ↓
build_state_graph(skill_config)
  ↓ passes to planner
  ↓
build_planner_node(skill_config)
  ↓ uses for filtering and hints
  ↓
planner_node() execution
  ├─ build_skills_catalog(skill_config)  → Filter catalog
  └─ build_file_upload_reminder(skill_config)  → Generate hints
```

---

### 3.5 Skill Dependencies

**Design**: Skill scripts may require external Python libraries, which need to be automatically installed.

**requirements.txt Format**:

```
# skills/pdf/requirements.txt
pypdf2>=3.0.0
reportlab>=4.0.0
pillow>=10.0.0
```

**Auto-Installation Flow**:

```python
# shared/workspace/manager.py:156-192
def _link_skill(self, skill_id: str, skill_path: Path):
    """Link skill to workspace and install dependencies"""

    target_dir = self.workspace_path / "skills" / skill_id
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # Create symlink
    if not target_dir.exists():
        target_dir.symlink_to(skill_path, target_is_directory=True)

    # Check for requirements.txt
    requirements = skill_path / "requirements.txt"
    if requirements.exists():
        self._install_skill_dependencies(skill_id, requirements)

def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    """Install skill dependencies using pip"""

    # Check cache
    if self._skill_registry.is_dependencies_installed(skill_id):
        return

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True,
            timeout=120,
        )

        # Mark as installed
        self._skill_registry.mark_dependencies_installed(skill_id)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"Failed to install dependencies for skill '{skill_id}': {error_msg}")
```

**Error Handling**:

```python
# generalAgent/tools/builtin/run_skill_script.py:85-95
except ImportError as e:
    missing_module = str(e).split("'")[1] if "'" in str(e) else "unknown"
    return f"""Script execution failed: Missing dependency

错误: 缺少 Python 模块 '{missing_module}'

建议操作:
1. 检查 skills/{skill_id}/requirements.txt 是否包含此依赖
2. 手动安装: pip install {missing_module}
3. 或联系技能维护者添加依赖声明
"""
```

**When**: Dependencies are installed automatically when:
- User @mentions a skill for the first time in a session
- The skill has a `requirements.txt` file

**How It Works**:
1. **Automatic detection**: WorkspaceManager checks for `requirements.txt` when linking skill
2. **One-time install**: Dependencies installed once, marked as cached in SkillRegistry
3. **Graceful degradation**: If installation fails, agent receives friendly error message

---

### 3.6 Skills Catalog

**Design**: Generate available skills list in system prompt for Agent awareness.

**Implementation**:

```python
# generalAgent/graph/prompts.py:143-174
def build_skills_catalog(skill_registry, skill_config=None) -> str:
    """Build skills catalog for model-invoked pattern"""

    skills = skill_registry.list_meta()

    if skill_config:
        enabled_skill_ids = set(skill_config.get_enabled_skills())
        skills = [s for s in all_skills if s.id in enabled_skill_ids]

    if not skills:
        return ""

    lines = ["# 可用技能（Skills）"]
    lines.append("以下是可用的专业技能。当你需要使用某个技能时：")
    lines.append("1. 使用 read_file 工具读取该技能的 SKILL.md 文件获取详细指导")
    lines.append("2. 根据指导执行相关操作")
    lines.append("3. Skills 不是 tools，而是知识包（文档）")
    lines.append("")

    for skill in skills:
        lines.append(f"## {skill.name} (#{skill.id})")
        lines.append(f"{skill.description}")
        # Use workspace-relative path
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")
        lines.append("")

    return "\n".join(lines)
```

**Injected into System Prompt**:

```python
# generalAgent/graph/nodes/planner.py:265-270
skills_catalog = build_skills_catalog(skill_registry, skill_config)
if skills_catalog:
    system_parts.append(skills_catalog)

system_prompt = "\n\n---\n\n".join(system_parts)
```

**Output Example**:

```
# 可用技能（Skills）

## PDF 处理 (#pdf)
提供 PDF 文件处理能力，包括表单填写、文本提取、页面操作等。
📁 路径: `skills/pdf/SKILL.md`
```

**Design Considerations**:
- Uses workspace-relative paths (doesn't expose project paths)
- Provides clear usage instructions
- Emphasizes skills are documentation, not tools
- Includes path information (easy reference)

---

### 3.7 Skill Script Execution

**Design**: Execute skill scripts through `run_skill_script` tool.

**Tool Definition**:

```python
# generalAgent/tools/builtin/run_skill_script.py:15-35
@tool
def run_skill_script(skill_id: str, script_name: str, args: str) -> str:
    """Execute a Python script from a skill package.

    Args:
        skill_id: The skill identifier (e.g., "pdf")
        script_name: Script filename (e.g., "fill_form.py")
        args: JSON string of script arguments

    Returns:
        Script output or error message
    """
```

**Execution Flow**:

```python
# generalAgent/tools/builtin/run_skill_script.py:50-110
def _execute_script(script_path: Path, args: dict) -> str:
    """Execute script in isolated process"""

    # Set environment variables
    env = os.environ.copy()
    env["AGENT_WORKSPACE_PATH"] = str(workspace_path)

    # Prepare script arguments
    script_input = json.dumps(args)

    # Execute
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=script_input,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=workspace_path,
    )

    if result.returncode != 0:
        return f"Script failed: {result.stderr}"

    return result.stdout
```

**Script Interface Specification**:

```python
# skills/pdf/scripts/example.py
import json
import sys
import os

def main():
    # Read workspace path from environment
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")

    # Read arguments from stdin
    args = json.loads(sys.stdin.read())

    # Execute logic
    input_file = os.path.join(workspace, args["input_pdf"])
    output_file = os.path.join(workspace, args["output_pdf"])

    # ... processing ...

    # Print result to stdout
    print(json.dumps({"status": "success", "output": output_file}))

if __name__ == "__main__":
    main()
```

**Design Considerations**:
- Scripts run in isolated processes (isolation)
- Pass JSON data via stdin/stdout (standardization)
- Pass workspace path via environment variable (security)
- Timeout protection (default 30s)

---

## Part 4: Best Practices & Design Patterns

### 4.1 Path Handling

#### 4.1.1 Workspace Relative Paths vs Absolute Paths

**Problem**: How to hide project absolute paths in system prompts and use workspace-relative paths?

**Implementation**: `generalAgent/graph/prompts.py:144-174`

```python
def build_skills_catalog(skill_registry) -> str:
    for skill in skills:
        lines.append(f"## {skill.name} (#{skill.id})")
        lines.append(f"{skill.description}")
        # Use workspace-relative path (skills are symlinked to workspace/skills/)
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")  # NOT absolute path
        lines.append("")
```

**Design Considerations**:
- Avoid exposing user's project path (e.g., `/Users/yushaw/dev/agentGraph/...`)
- Workspace isolation: All paths relative to `workspace/` root
- Symbolic links: Skills actually in project directory but appear as symlinks in workspace

**Comparison**:
```python
# ❌ Wrong: Exposes absolute path
lines.append(f"📁 路径: `/Users/yushaw/dev/agentGraph/generalAgent/skills/pdf/SKILL.md`")

# ✅ Correct: Workspace relative path
lines.append(f"📁 路径: `skills/pdf/SKILL.md`")
```

---

#### 4.1.2 Two-Step Path Validation (Prevent Path Traversal)

**Problem**: How to prevent users from accessing files outside workspace via `../../etc/passwd` paths?

**Implementation**: `generalAgent/utils/file_processor.py:15-50`

```python
def resolve_workspace_path(
    file_path: str,
    workspace_root: Path,
    *,
    must_exist: bool = False,
    allow_write: bool = False,
) -> Path:
    # Step 1: Resolve logical path (handles .., symlinks)
    logical_path = (workspace_root / file_path).resolve()

    # Step 2: Check if resolved path is within workspace
    try:
        logical_path.relative_to(workspace_root.resolve())
    except ValueError:
        raise ValueError(f"Path outside workspace: {file_path}")

    # Step 3: Existence check
    if must_exist and not logical_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Step 4: Write permission check
    if allow_write:
        allowed_dirs = ["outputs", "temp", "uploads"]
        rel_path = logical_path.relative_to(workspace_root)
        if rel_path.parts[0] not in allowed_dirs:
            raise PermissionError(f"Cannot write to {rel_path.parts[0]}/")

    return logical_path
```

**Design Considerations**:
- `.resolve()` handles symbolic links and `..` paths (normalization)
- `.relative_to()` checks if within workspace (security check)
- Separate read/write permissions (read-only vs writable directories)
- Clear error messages (helps debugging)

**Attack Example**:
```python
# Attack attempt
resolve_workspace_path("../../../etc/passwd", workspace_root)
# → Raises ValueError: Path outside workspace: ../../../etc/passwd

# Legitimate path
resolve_workspace_path("skills/pdf/SKILL.md", workspace_root)
# → /data/workspace/session_123/skills/pdf/SKILL.md
```

---

#### 4.1.3 Symbolic Link Path Handling (Don't Resolve)

**Problem**: How should `list_workspace_files` correctly handle symbolic links to avoid paths jumping out of workspace?

**Implementation**: `generalAgent/tools/builtin/file_ops.py:214-241`

```python
@tool
def list_workspace_files(directory: str = ".") -> str:
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # Use logical path (DON'T resolve symlinks)
    logical_path = workspace_root / directory

    # Check within workspace (using logical path)
    try:
        logical_path.relative_to(workspace_root)
    except ValueError:
        return f"Error: Path outside workspace: {directory}"

    # List files
    items = []
    for item in sorted(logical_path.iterdir()):
        rel_path = item.relative_to(workspace_root)  # Logical relative path

        if item.is_symlink():
            items.append(f"[SKILL] {rel_path}/")  # Mark as skill
        elif item.is_dir():
            items.append(f"[DIR]  {rel_path}/")
        else:
            size = item.stat().st_size
            items.append(f"[FILE] {rel_path} ({size} bytes)")

    return "\n".join(items)
```

**Design Considerations**:
- **Don't use `.resolve()`**: Avoid symlink paths jumping out of workspace
- Use logical paths for listing and checking
- Explicitly mark symlinks (`[SKILL]`)
- Relative paths based on workspace root

**Comparison**:
```python
# ❌ Wrong: resolve() causes paths to jump out of workspace
logical_path = (workspace_root / directory).resolve()
# skills/pdf → /Users/yushaw/dev/agentGraph/generalAgent/skills/pdf
# relative_to(workspace_root) will fail!

# ✅ Correct: Don't resolve, keep logical path
logical_path = workspace_root / directory
# skills/pdf → /data/workspace/session_123/skills/pdf (symlink)
```

---

#### 4.1.4 Project Root Auto-Discovery

**Problem**: How to let program find project root when running from any directory?

**Implementation**: `generalAgent/config/project_root.py:10-45`

```python
def find_project_root(marker_files=None) -> Path:
    """Find project root by looking for marker files"""

    if marker_files is None:
        marker_files = ["pyproject.toml", ".git", "README.md"]

    current = Path.cwd().resolve()

    # Traverse up until marker found or root reached
    while current != current.parent:
        for marker in marker_files:
            if (current / marker).exists():
                return current
        current = current.parent

    # Fallback: current directory
    return Path.cwd()

# Cache project root
PROJECT_ROOT = find_project_root()

def resolve_project_path(relative_path: str) -> Path:
    """Resolve path relative to project root"""
    return PROJECT_ROOT / relative_path
```

**Usage**:
```python
# generalAgent/runtime/app.py:118
skills_root = skills_root or resolve_project_path("generalAgent/skills")

# generalAgent/config/settings.py:120
config_path = resolve_project_path("generalAgent/config/tools.yaml")
```

**Design Considerations**:
- Traverse upward looking for marker files (`pyproject.toml`, `.git`)
- Cache result (`PROJECT_ROOT`) to avoid repeated lookups
- Unified path resolution interface (`resolve_project_path`)
- Supports running program from any directory

---

### 4.2 Prompt Engineering

#### 4.2.1 Context-Aware Dynamic System Reminders

**Problem**: How to dynamically generate system prompts based on user input?

**Implementation**: `generalAgent/graph/prompts.py:177-229`

```python
def build_dynamic_reminder(
    *,
    active_skill: str = None,
    mentioned_tools: list = None,
    mentioned_skills: list = None,
    mentioned_agents: list = None,
    has_images: bool = False,
) -> str:
    """Build context-aware system reminder"""

    reminders = []

    # Skill activation
    if active_skill:
        reminders.append(
            f"<system_reminder>当前激活的技能：{active_skill}。"
            f"优先使用该技能的工具完成任务。</system_reminder>"
        )

    # Tool mentions
    if mentioned_tools:
        tools_str = "、".join(mentioned_tools)
        reminders.append(
            f"<system_reminder>用户提到了工具：{tools_str}。"
            f"请优先使用这些工具完成任务。</system_reminder>"
        )

    # Skill mentions
    if mentioned_skills:
        skills_str = "、".join(mentioned_skills)
        reminders.append(
            f"<system_reminder>用户提到了技能：{skills_str}。"
            f"请先使用 Read 工具读取对应的 SKILL.md 文件"
            f"（位于 skills/{'{skill_id}'}/SKILL.md），"
            f"然后根据文档指导执行操作。</system_reminder>"
        )

    return "\n\n".join(reminders) if reminders else ""
```

**Applied to System Prompt**:
```python
# generalAgent/graph/nodes/planner.py:265-280
def planner_node(state: AppState):
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # Add skills catalog
    skills_catalog = build_skills_catalog(skill_registry, skill_config)
    if skills_catalog:
        system_parts.append(skills_catalog)

    # Add dynamic reminders
    dynamic_reminder = build_dynamic_reminder(
        active_skill=state.get("active_skill"),
        mentioned_tools=...,
        mentioned_skills=...,
        mentioned_agents=...,
    )
    if dynamic_reminder:
        system_parts.append(dynamic_reminder)

    system_prompt = "\n\n---\n\n".join(system_parts)
```

**Design Considerations**:
- Prompt content based on context (not static)
- Uses XML tags (`<system_reminder>`) for clear marking
- Chinese expression, natural and friendly
- Provides clear operation instructions

---

#### 4.2.2 Current Time Injection

**Problem**: How to let Agent know current time?

**Implementation**: `generalAgent/graph/prompts.py:6-14` + `planner.py:265`

**Time Tag Generation**:
```python
# generalAgent/graph/prompts.py:6-14
def get_current_datetime_tag() -> str:
    """Get current date and time in XML tag format"""
    now = datetime.now(timezone.utc)
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"<current_datetime>{datetime_str}</current_datetime>"
```

**Injected into System Prompt**:
```python
# generalAgent/graph/nodes/planner.py:265-275
def planner_node(state: AppState):
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # Add current time
    datetime_tag = get_current_datetime_tag()
    system_parts.append(datetime_tag)

    # ... other parts ...

    system_prompt = "\n\n---\n\n".join(system_parts)
```

**Output Example**:
```
你是 Charlie，一个高效、友好的 AI 助手。
...

---

<current_datetime>2025-01-24 15:30:45 UTC</current_datetime>

---

# 可用技能（Skills）
...
```

**Design Considerations**:
- Use UTC time (avoid timezone confusion)
- XML tag format (structured)
- Dynamically generated (always latest time on each call)
- Placed in system prompt (Agent always knows current time)

---

### 4.3 Error Handling

#### 4.3.1 Tool Error Boundary Decorator

**Problem**: How to uniformly handle exceptions during tool execution?

**Implementation**: `generalAgent/tools/decorators.py:10-40`

```python
from functools import wraps
import logging

LOGGER = logging.getLogger(__name__)

def with_error_boundary(func):
    """Decorator to catch and format tool errors"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except FileNotFoundError as e:
            error_msg = f"File not found: {e.filename}"
            LOGGER.error(f"Tool '{func.__name__}' failed: {error_msg}")
            return f"Error: {error_msg}"

        except PermissionError as e:
            error_msg = f"Permission denied: {e}"
            LOGGER.error(f"Tool '{func.__name__}' failed: {error_msg}")
            return f"Error: {error_msg}"

        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {e}"
            LOGGER.error(f"Tool '{func.__name__}' failed: {error_msg}", exc_info=True)
            return f"Error: {error_msg}"

    return wrapper
```

**Usage Example**:
```python
# generalAgent/tools/builtin/file_ops.py:45-65
@tool
@with_error_boundary
def read_file(file_path: str) -> str:
    """Read file from workspace"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # This may raise FileNotFoundError, PermissionError, etc.
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**Error Return Examples**:
```
Error: File not found: uploads/missing.txt
Error: Permission denied: Cannot write to skills/
Error: Unexpected error: UnicodeDecodeError: 'utf-8' codec can't decode byte...
```

**Design Considerations**:
- Catches common exceptions (file, permission, encoding)
- Returns friendly error messages (not stack traces)
- Logs detailed information (including stack)
- Agent can adjust strategy based on error messages

---

#### 4.3.2 Loop Limit & Deadlock Detection

**Problem**: How to prevent Agent from falling into infinite loops?

**Implementation**: `generalAgent/graph/routing.py:6-20`

```python
def agent_route(state: AppState) -> Literal["tools", "finalize"]:
    """Route agent to tools or finalize"""

    messages = state["messages"]
    last = messages[-1]

    # Check loop limit (CRITICAL)
    if state["loops"] >= state["max_loops"]:
        LOGGER.warning(
            f"Loop limit reached ({state['max_loops']}), forcing finalize"
        )
        return "finalize"

    # LLM wants to call tools
    if last.tool_calls:
        return "tools"

    # LLM finished
    return "finalize"
```

**Loop Counting**:
```python
# generalAgent/graph/nodes/planner.py:340
def planner_node(state: AppState):
    # ... invoke model ...

    return {
        "messages": [result],
        "loops": state["loops"] + 1,  # Increment loop counter
    }
```

**Deadlock Detection (Advanced)**:
```python
def detect_repeated_tool_calls(state: AppState) -> bool:
    """Detect if agent is calling same tool repeatedly"""

    messages = state["messages"][-10:]  # Last 10 messages

    tool_calls = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append((tc["name"], frozenset(tc["args"].items())))

    # Check for repeated calls (same tool + same args)
    if len(tool_calls) >= 3:
        if tool_calls[-1] == tool_calls[-2] == tool_calls[-3]:
            LOGGER.warning(f"Detected repeated tool call: {tool_calls[-1][0]}")
            return True

    return False
```

**Design Considerations**:
- Hard loop limit (`max_loops`)
- Log warning messages
- Detect repeated tool calls (deadlock)
- Force entry to finalize (avoid infinite loops)

---

### 4.4 Logging and Debugging

#### 4.4.1 Structured Logging

**Problem**: How to record clear, searchable logs?

**Implementation**: All modules

**Logging Configuration**:
```python
# generalAgent/__init__.py:10-30
import logging

def setup_logging(level=logging.INFO):
    """Setup structured logging"""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("logs/app.log"),
            logging.StreamHandler(),  # Also print to console
        ],
    )

# Call at startup
setup_logging()
```

**Usage Example**:
```python
# generalAgent/tools/registry.py
import logging

LOGGER = logging.getLogger(__name__)

def load_on_demand(self, tool_name: str):
    LOGGER.info(f"Loading tool on-demand: {tool_name}")

    tool = self._discovered.get(tool_name)
    if tool:
        self.register_tool(tool)
        LOGGER.info(f"✓ Tool loaded: {tool_name}")
    else:
        LOGGER.warning(f"✗ Tool not found: {tool_name}")
```

**Log Output**:
```
2025-01-24 15:30:45 [INFO] generalAgent.tools.registry:95 - Loading tool on-demand: http_fetch
2025-01-24 15:30:45 [INFO] generalAgent.tools.registry:99 - ✓ Tool loaded: http_fetch
```

**Design Considerations**:
- Includes timestamp, level, module, line number
- Outputs to both file and console
- Uses `__name__` as logger name (automatic categorization)
- Friendly symbols (✓ ✗ →)

---

#### 4.4.2 Tool Call Logging

**Problem**: How to record parameters and results of each tool call?

**Implementation**: `generalAgent/graph/nodes/planner.py:320-340`

```python
def planner_node(state: AppState):
    # ... invoke model ...

    result = model.invoke(messages, tools=visible_tools)

    # Log tool calls
    if result.tool_calls:
        for tool_call in result.tool_calls:
            LOGGER.info(
                f"Tool call: {tool_call['name']}({_format_args(tool_call['args'])})"
            )

    return {"messages": [result], "loops": state["loops"] + 1}

def _format_args(args: dict) -> str:
    """Format tool arguments for logging"""
    # Truncate long values
    formatted = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 100:
            formatted[k] = v[:100] + "..."
        else:
            formatted[k] = v

    return ", ".join(f"{k}={v!r}" for k, v in formatted.items())
```

**Log Output**:
```
2025-01-24 15:30:45 [INFO] generalAgent.graph.nodes.planner:325 - Tool call: read_file(file_path='uploads/data.txt')
2025-01-24 15:30:45 [INFO] generalAgent.graph.nodes.planner:325 - Tool call: write_file(file_path='outputs/result.txt', content='Analysis results...（truncated）...')
```

**Design Considerations**:
- Record tool name and parameters
- Truncate long parameters (e.g., file content)
- Can be used for auditing and debugging
- Don't record sensitive information (e.g., API keys)

---

### 4.5 Configuration Management

#### 4.5.1 Pydantic Settings for .env Loading

**Problem**: How to elegantly manage environment variable configuration?

**Implementation**: `generalAgent/config/settings.py:15-125`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class ModelConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    id: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

class GovernanceConfig(BaseModel):
    max_message_history: int = Field(default=40, ge=10, le=100)
    max_loops: int = Field(default=100, ge=1, le=500)

class ObservabilityConfig(BaseModel):
    langsmith_enabled: bool = Field(default=False)
    langsmith_api_key: Optional[str] = None
    session_db_path: str = Field(default="data/sessions.db")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model slots
    model_basic: Optional[ModelConfig] = None
    model_reasoning: Optional[ModelConfig] = None

    # Governance
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)

    # Observability
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

**Usage Example**:
```python
# generalAgent/runtime/app.py:110
settings = get_settings()
max_loops = settings.governance.max_loops
db_path = settings.observability.session_db_path
```

**Design Considerations**:
- Pydantic provides type validation (automatic checking)
- `Field` provides default values and range limits (`ge`, `le`)
- `env_file` automatically loads `.env` file
- Singleton pattern (`get_settings()`) avoids repeated loading
- Grouped configuration (model/governance/observability)

---

## Summary

This architecture document consolidates:

**Part 1: Core Architecture**
- Agent Loop architecture (not Plan-and-Execute)
- State management via TypedDict
- Three-node system (agent/tools/finalize)
- Conditional edge routing

**Part 2: Tool System**
- Three-tier architecture (discovered/registered/visible)
- Auto-discovery and scanning
- Configuration-driven metadata
- Persistent tools and dynamic visibility
- TODO tool system with Command-based state sync

**Part 3: Skill System**
- Skills as knowledge packages (not tool containers)
- Configuration-driven catalog filtering
- Dynamic file upload hints
- Automatic dependency installation
- Script execution interface

**Part 4: Best Practices**
- Path handling (workspace isolation, security)
- Prompt engineering (context-aware, dynamic)
- Error handling (boundaries, loop limits)
- Logging (structured, tool calls)
- Configuration management (Pydantic, .env)

---

**Related Documentation**:
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing strategies
- [CONTEXT_MANAGEMENT.md](CONTEXT_MANAGEMENT.md) - KV cache optimization
- [DOCUMENT_SEARCH_OPTIMIZATION.md](DOCUMENT_SEARCH_OPTIMIZATION.md) - Search system
- [HITL_GUIDE.md](HITL_GUIDE.md) - Human-in-the-loop patterns

**Configuration Files**:
- `generalAgent/config/tools.yaml` - Tool configuration
- `generalAgent/config/skills.yaml` - Skill configuration
- `generalAgent/config/hitl_rules.yaml` - HITL approval rules
- `.env` - Environment variables
