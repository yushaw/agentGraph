# GeneralAgent 详细需求文档 - Part 4: 实现技巧与设计模式

## 11. 实现技巧集锦

本章节收录了 GeneralAgent 项目中的 50+ 实现技巧，每个技巧包含：问题、实现位置、代码示例、设计考量。

---

### 分类 A: 路径处理技巧

#### A1. 工作区相对路径 vs 绝对路径

**问题**：如何在系统提示中隐藏项目绝对路径，使用工作区相对路径？

**实现位置**：`generalAgent/graph/prompts.py:144-174`

**代码示例**：
```python
def build_skills_catalog(skill_registry) -> str:
    for skill in skills:
        lines.append(f"## {skill.name} (#{skill.id})")
        lines.append(f"{skill.description}")
        # Use workspace-relative path (skills are symlinked to workspace/skills/)
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")  # NOT absolute path
        lines.append("")
```

**设计考量**：
- 避免暴露用户的项目路径（如 `/Users/yushaw/dev/agentGraph/...`）
- 工作区隔离：所有路径都相对于 `workspace/` 根目录
- 符号链接：skills 实际在项目目录，但在工作区中以符号链接形式出现

**对比**：
```python
# ❌ 错误：暴露绝对路径
lines.append(f"📁 路径: `/Users/yushaw/dev/agentGraph/generalAgent/skills/pdf/SKILL.md`")

# ✅ 正确：工作区相对路径
lines.append(f"📁 路径: `skills/pdf/SKILL.md`")
```

---

#### A2. 两步路径验证（防止路径遍历）

**问题**：如何防止用户通过 `../../etc/passwd` 等路径访问工作区外的文件？

**实现位置**：`generalAgent/utils/file_processor.py:15-50`

**代码示例**：
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

**设计考量**：
- `.resolve()` 处理符号链接和 `..` 路径（规范化）
- `.relative_to()` 检查是否在工作区内（安全检查）
- 分离读写权限（只读 vs 可写目录）
- 明确的错误消息（帮助调试）

**攻击示例**：
```python
# 攻击尝试
resolve_workspace_path("../../../etc/passwd", workspace_root)
# → 抛出 ValueError: Path outside workspace: ../../../etc/passwd

# 合法路径
resolve_workspace_path("skills/pdf/SKILL.md", workspace_root)
# → /data/workspace/session_123/skills/pdf/SKILL.md
```

---

#### A3. 符号链接路径处理（不 resolve）

**问题**：`list_workspace_files` 如何正确处理符号链接，避免路径跳出工作区？

**实现位置**：`generalAgent/tools/builtin/file_ops.py:214-241`

**代码示例**：
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

**设计考量**：
- **不使用 `.resolve()`**：避免符号链接路径跳出工作区
- 使用逻辑路径（logical path）进行列表和检查
- 明确标记符号链接（`[SKILL]`）
- 相对路径基于工作区根目录

**对比**：
```python
# ❌ 错误：resolve() 导致路径跳出工作区
logical_path = (workspace_root / directory).resolve()
# skills/pdf → /Users/yushaw/dev/agentGraph/generalAgent/skills/pdf
# relative_to(workspace_root) 会失败！

# ✅ 正确：不 resolve，保持逻辑路径
logical_path = workspace_root / directory
# skills/pdf → /data/workspace/session_123/skills/pdf（符号链接）
```

---

#### A4. 项目根目录自动识别

**问题**：如何让程序在任何目录运行时都能找到项目根目录？

**实现位置**：`generalAgent/config/project_root.py:10-45`

**代码示例**：
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

**应用**：
```python
# generalAgent/runtime/app.py:118
skills_root = skills_root or resolve_project_path("generalAgent/skills")

# generalAgent/config/settings.py:120
config_path = resolve_project_path("generalAgent/config/tools.yaml")
```

**设计考量**：
- 向上遍历查找标记文件（`pyproject.toml`, `.git`）
- 缓存结果（`PROJECT_ROOT`）避免重复查找
- 统一路径解析接口（`resolve_project_path`）
- 支持从任意目录运行程序

---

### 分类 B: 工具系统技巧

#### B1. 三层工具架构（discovered/registered/visible）

**问题**：如何实现既支持启动加载又支持按需加载的工具系统？

**实现位置**：`generalAgent/tools/registry.py:20-100`

**代码示例**：
```python
class ToolRegistry:
    def __init__(self):
        self._discovered: Dict[str, Any] = {}  # Layer 1: All found tools
        self._tools: Dict[str, Any] = {}       # Layer 2: Enabled tools
        self._meta: Dict[str, ToolMeta] = {}

    def register_discovered(self, tool: Any):
        """Add tool to discovery pool (not loaded yet)"""
        self._discovered[tool.name] = tool

    def register_tool(self, tool: Any):
        """Load tool as enabled"""
        self._tools[tool.name] = tool

    def load_on_demand(self, tool_name: str) -> Optional[Any]:
        """Load from discovered pool when @mentioned"""
        if tool_name in self._tools:
            return self._tools[tool_name]  # Already loaded

        if tool_name in self._discovered:
            tool = self._discovered[tool_name]
            self.register_tool(tool)  # Move to Layer 2
            return tool

        return None
```

**三层说明**：
- **Layer 1 (discovered)**: 所有扫描到的工具（包括禁用的）
- **Layer 2 (registered)**: 启用的工具（`enabled: true`）
- **Layer 3 (visible)**: 当前上下文可见的工具（动态构建）

**设计考量**：
- Layer 1 支持插件发现但不占用内存
- Layer 2 是启动时加载的核心工具集
- Layer 3 是运行时动态可见性（最重要）
- 按需加载（load_on_demand）连接 Layer 1 和 Layer 2

---

#### B2. 多工具文件支持（\_\_all\_\_ 导出）

**问题**：一个 Python 文件如何导出多个工具？

**实现位置**：`generalAgent/tools/builtin/file_ops.py:1-15`

**代码示例**：
```python
# file_ops.py
from langchain_core.tools import tool

@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""
    pass

@tool
def write_file(file_path: str, content: str) -> str:
    """Write file to workspace"""
    pass

@tool
def list_workspace_files(directory: str = ".") -> str:
    """List files in directory"""
    pass

# Export all tools explicitly
__all__ = ["read_file", "write_file", "list_workspace_files"]
```

**扫描器处理**：
```python
# generalAgent/tools/scanner.py:52-86
def _extract_tools_from_module(file_path: Path) -> Dict[str, Any]:
    """Extract ALL tools from a module"""

    tools = {}

    # Method 1: Use __all__ if defined (recommended)
    if hasattr(module, "__all__"):
        tool_names = module.__all__
        for name in tool_names:
            obj = getattr(module, name)
            if isinstance(obj, BaseTool):
                tools[obj.name] = obj

    # Method 2: Introspect all attributes (fallback)
    else:
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool) and not name.startswith("_"):
                tools[obj.name] = obj

    return tools
```

**设计考量**：
- 使用 `__all__` 明确声明导出（推荐）
- 回退到自动检测（便利）
- 避免导出私有工具（`_internal_tool`）
- 支持一个文件多个相关工具

---

#### B3. 工具元数据与配置分离

**问题**：如何在不修改工具代码的情况下管理工具的分类、标签、可用性？

**实现位置**：`generalAgent/config/tools.yaml` + `generalAgent/tools/config_loader.py`

**配置文件**：
```yaml
# tools.yaml
core:
  now:
    category: "meta"
    tags: ["meta", "time"]
    description: "Get current UTC time"

optional:
  http_fetch:
    enabled: true
    always_available: false
    category: "network"
    tags: ["network", "read"]
    description: "Fetch web page content"

  extract_links:
    enabled: false  # Disabled but available via @mention
    category: "read"
    tags: ["read", "parse"]
    description: "Extract links from HTML"
```

**加载逻辑**：
```python
# generalAgent/tools/config_loader.py:105-140
class ToolConfig:
    def __init__(self, config_path: Path = None):
        self.config = self._load_yaml(config_path)

    def get_all_enabled_tools(self) -> Set[str]:
        """Return tool names with enabled=true"""
        enabled = set()

        # Core tools always enabled
        enabled.update(self.config.get("core", {}).keys())

        # Optional tools if enabled
        for name, cfg in self.config.get("optional", {}).items():
            if cfg.get("enabled", False):
                enabled.add(name)

        return enabled

    def is_always_available(self, tool_name: str) -> bool:
        """Check if tool is globally visible"""
        meta = self._find_tool_config(tool_name)
        return meta.get("always_available", False)

    def get_all_tool_metadata(self) -> List[ToolMeta]:
        """Build metadata list from config"""
        metadata = []

        for category in ["core", "optional"]:
            for name, cfg in self.config.get(category, {}).items():
                meta = ToolMeta(
                    name=name,
                    category=cfg.get("category", "general"),
                    tags=cfg.get("tags", []),
                    description=cfg.get("description", ""),
                    always_available=cfg.get("always_available", False),
                )
                metadata.append(meta)

        return metadata
```

**设计考量**：
- 配置驱动，无需修改代码
- `core` vs `optional` 区分系统工具和可选工具
- `enabled` 控制启动加载
- `always_available` 控制全局可见性
- 支持分类、标签、描述（便于搜索和文档生成）

---

#### B4. 动态工具可见性构建

**问题**：如何根据当前上下文（persistent + allowed + @mentioned）动态构建工具列表？

**实现位置**：`generalAgent/graph/nodes/planner.py:180-226`

**代码示例**：
```python
def build_visible_tools(
    *,
    state: AppState,
    tool_registry: ToolRegistry,
    persistent_global_tools: List,
    skill_registry: SkillRegistry,
) -> List:
    """Build list of tools visible to agent in current context"""

    visible = []
    seen_names = set()

    # Step 1: Add persistent global tools (always available)
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

    # Step 3: Add @mentioned tools/agents (on-demand loading)
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "tool" and mention not in seen_names:
            tool = tool_registry.load_on_demand(mention)
            if tool:
                visible.append(tool)
                seen_names.add(mention)

        elif mention_type == "agent":
            # Load call_subagent tool
            tool = tool_registry.get_tool("call_subagent")
            if tool and "call_subagent" not in seen_names:
                visible.append(tool)
                seen_names.add("call_subagent")

    return visible
```

**三步构建流程**：
1. **持久化工具**：始终可用（如 `todo_write`, `now`）
2. **技能工具**：当前激活技能的工具（`allowed_tools`）
3. **@提及工具**：用户动态请求的工具（按需加载）

**设计考量**：
- 去重（`seen_names` set）
- 优先级顺序（persistent > allowed > mentioned）
- 动态加载（`load_on_demand`）
- 支持三类 @mention（tool/skill/agent）

---

#### B5. 环境变量传递工作区路径

**问题**：工具如何知道当前会话的工作区路径？

**实现位置**：`generalAgent/cli.py:250-260` + 所有文件工具

**设置环境变量**：
```python
# generalAgent/cli.py:250-260
async def handle_user_message(self, user_input: str):
    """Handle user message"""

    # Set workspace path in environment
    os.environ["AGENT_WORKSPACE_PATH"] = str(self.workspace_path)
    os.environ["AGENT_CONTEXT_ID"] = self.session_manager.current_session_id

    # Execute graph
    result = await self.app.ainvoke(...)
```

**工具读取环境变量**：
```python
# generalAgent/tools/builtin/file_ops.py:45-60
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""

    # Get workspace path from environment
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    if not workspace_root:
        return "Error: Workspace path not set"

    # Validate and read
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**设计考量**：
- 避免全局变量（支持多会话）
- 环境变量作为上下文传递机制
- 所有工具统一接口（`os.environ.get`）
- 支持子进程继承（脚本执行）

---

### 分类 C: Prompt 工程技巧

#### C1. 动态系统提醒（Context-Aware）

**问题**：如何根据用户输入动态生成系统提示？

**实现位置**：`generalAgent/graph/prompts.py:177-229`

**代码示例**：
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

    # Agent mentions
    if mentioned_agents:
        agents_str = "、".join(mentioned_agents)
        reminders.append(
            f"<system_reminder>用户提到了代理：{agents_str}。"
            f"你可以使用 call_subagent 工具将任务委派给子代理执行。</system_reminder>"
        )

    return "\n\n".join(reminders) if reminders else ""
```

**应用到系统提示**：
```python
# generalAgent/graph/nodes/planner.py:265-280
def planner_node(state: AppState):
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # Add skills catalog
    skills_catalog = build_skills_catalog(skill_registry)
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

**设计考量**：
- 提示内容基于上下文（不是静态的）
- 使用 XML 标签（`<system_reminder>`）明确标记
- 中文表达，自然友好
- 提供明确的操作指导

---

#### C2. 技能目录动态生成

**问题**：如何让 Agent 知道有哪些技能可用？

**实现位置**：`generalAgent/graph/prompts.py:143-174`

**代码示例**：
```python
def build_skills_catalog(skill_registry) -> str:
    """Build skills catalog for model-invoked pattern"""

    skills = skill_registry.list_meta()

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

**输出示例**：
```
# 可用技能（Skills）
以下是可用的专业技能。当你需要使用某个技能时：
1. 使用 read_file 工具读取该技能的 SKILL.md 文件获取详细指导
2. 根据指导执行相关操作
3. Skills 不是 tools，而是知识包（文档）

## PDF 处理 (#pdf)
提供 PDF 文件处理能力，包括表单填写、文本提取、页面操作等。
📁 路径: `skills/pdf/SKILL.md`
```

**设计考量**：
- 自动生成，无需手写
- 提供使用指导（避免误用）
- 强调 skills 是文档，不是工具
- 包含路径信息（方便查阅）

---

#### C3. 主 Agent vs 子 Agent 提示差异

**问题**：主代理和子代理的系统提示有何区别？

**实现位置**：`generalAgent/graph/prompts.py:34-120`

**主 Agent 提示（PLANNER_SYSTEM_PROMPT）**：
```python
PLANNER_SYSTEM_PROMPT = f"""{CHARLIE_BASE_IDENTITY}

# 工作方式
你以自主循环方式工作：分析请求 → 调用工具 → 检查完成度 → 继续或停止

## 工具使用场景
### 文件操作
- read_file, write_file, edit_file, list_workspace_files

### 技能系统（Skills）
Skills 是知识包（文档），**不是工具**。
**推荐使用方式**（避免长文档污染上下文）：
1. 用户提到 @skill 或上传特定类型文件时
2. **优先用 call_subagent 委派任务**，让 subagent 读取 SKILL.md 并执行

### 任务委派（推荐优先使用）
- call_subagent: 将独立子任务委派给专用 agent 执行
  - **优先使用场景**（避免主 agent 上下文堆积）：
    - 需要多轮尝试的复杂操作
    - 独立的子目标
"""
```

**子 Agent 提示（SUBAGENT_SYSTEM_PROMPT）**：
```python
SUBAGENT_SYSTEM_PROMPT = """你是任务执行器（Subagent），负责完成主 Agent 委托的具体任务。

核心原则：
- 目标导向：只完成任务描述中的具体目标
- 直接执行：收到任务后立即使用工具完成，无需寒暄、确认、解释
- 返回结果：提供具体数据/分析，不是对话

工作流程：
1. 理解任务目标
2. 使用工具执行（如需外部信息/操作）或直接返回结果（如可直接回答）
3. 返回结果后立即停止

输出要求：
- ✅ \"查询结果：北京今天晴天，15-25°C\"
- ❌ \"好的，我来帮您查询天气\"（不要寒暄）

限制：
- 不要询问用户（无法对话）
"""
```

**对比表**：

| 维度 | 主 Agent | 子 Agent |
|------|----------|----------|
| 风格 | 友好对话 | 任务执行 |
| 输出 | 解释 + 结果 | 仅结果 |
| 循环 | 长循环（100+） | 短循环（15） |
| 用户交互 | 可询问 | 不可询问 |
| 任务委派 | 可委派子任务 | 专注当前任务 |

**设计考量**：
- 主 Agent：强调友好、对话、委派
- 子 Agent：强调高效、直接、执行
- 上下文隔离（子 Agent 看不到主历史）

---

#### C4. 当前时间注入

**问题**：如何让 Agent 知道当前时间？

**实现位置**：`generalAgent/graph/prompts.py:6-14` + `planner.py:265`

**时间标签生成**：
```python
# generalAgent/graph/prompts.py:6-14
def get_current_datetime_tag() -> str:
    """Get current date and time in XML tag format"""
    now = datetime.now(timezone.utc)
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"<current_datetime>{datetime_str}</current_datetime>"
```

**注入到系统提示**：
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

**输出示例**：
```
你是 Charlie，一个高效、友好的 AI 助手。
...

---

<current_datetime>2025-01-24 15:30:45 UTC</current_datetime>

---

# 可用技能（Skills）
...
```

**设计考量**：
- 使用 UTC 时间（避免时区混淆）
- XML 标签格式（结构化）
- 动态生成（每次调用都是最新时间）
- 放在系统提示中（Agent 始终知道当前时间）

---

### 分类 D: 配置管理技巧

#### D1. Pydantic Settings 加载 .env

**问题**：如何优雅地管理环境变量配置？

**实现位置**：`generalAgent/config/settings.py:15-125`

**代码示例**：
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

    @field_validator("model_basic", mode="before")
    @classmethod
    def build_model_config(cls, v):
        """Build ModelConfig from environment variables"""
        if isinstance(v, dict):
            return ModelConfig(**v)
        return v

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

**使用示例**：
```python
# generalAgent/runtime/app.py:110
settings = get_settings()
max_loops = settings.governance.max_loops
db_path = settings.observability.session_db_path
```

**设计考量**：
- Pydantic 提供类型验证（自动检查）
- `Field` 提供默认值和范围限制（`ge`, `le`）
- `env_file` 自动加载 `.env` 文件
- 单例模式（`get_settings()`）避免重复加载
- 分组配置（model/governance/observability）

---

#### D2. 模型别名支持（Provider-Specific）

**问题**：如何支持多个模型提供商的不同命名习惯？

**实现位置**：`generalAgent/runtime/model_resolver.py:15-50`

**代码示例**：
```python
def resolve_model_configs(settings: Settings) -> Dict[str, dict]:
    """Resolve model configs from environment variables with provider aliases"""

    configs = {}

    # Provider-specific aliases
    aliases = {
        "MODEL_BASIC_": "base",        # DeepSeek naming
        "MODEL_REASONING_": "reasoning",
        "MODEL_MULTIMODAL_": "vision",  # GLM naming
        "MODEL_CODE_": "code",
        "MODEL_CHAT_": "chat",          # Moonshot naming
        # Canonical names (fallback)
        "MODEL_BASE_": "base",
        "MODEL_REASON_": "reasoning",
        "MODEL_VISION_": "vision",
    }

    for prefix, slot in aliases.items():
        api_key = os.getenv(f"{prefix}API_KEY")
        if api_key:
            configs[slot] = {
                "api_key": api_key,
                "base_url": os.getenv(f"{prefix}BASE_URL"),
                "id": os.getenv(f"{prefix}ID"),
            }

    return configs
```

**环境变量示例**：
```bash
# DeepSeek naming
MODEL_BASIC_API_KEY=sk-xxx
MODEL_BASIC_BASE_URL=https://api.deepseek.com
MODEL_BASIC_ID=deepseek-chat

# GLM naming (multimodal)
MODEL_MULTIMODAL_API_KEY=xxx
MODEL_MULTIMODAL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_MULTIMODAL_ID=glm-4.5v

# Moonshot naming
MODEL_CHAT_API_KEY=xxx
MODEL_CHAT_BASE_URL=https://api.moonshot.cn/v1
MODEL_CHAT_ID=kimi-k2-0905-preview
```

**设计考量**：
- 支持不同提供商的命名习惯
- 向后兼容（canonical names 作为 fallback）
- 统一到 5 个插槽（base/reasoning/vision/code/chat）
- 灵活配置（用户可选择任意提供商）

---

#### D3. YAML 配置热加载

**问题**：如何让配置文件修改后无需重启生效？

**实现位置**：`generalAgent/tools/config_loader.py:20-60`

**代码示例**：
```python
class ToolConfig:
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or resolve_project_path("generalAgent/config/tools.yaml")
        self._last_modified = None
        self._config = None

    def _load_yaml(self) -> dict:
        """Load YAML with file modification time tracking"""

        # Check if file modified
        current_mtime = self.config_path.stat().st_mtime

        if self._config is not None and self._last_modified == current_mtime:
            return self._config  # Use cached config

        # Reload from file
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        self._last_modified = current_mtime
        LOGGER.info(f"Reloaded tool config from {self.config_path}")

        return self._config

    @property
    def config(self) -> dict:
        """Get config with automatic reload on file change"""
        return self._load_yaml()
```

**使用示例**：
```python
# generalAgent/runtime/app.py:44
tool_config = load_tool_config()

# Every access checks for file modification
enabled_tools = tool_config.get_all_enabled_tools()  # Auto-reloads if file changed
```

**设计考量**：
- 检查文件修改时间（`st_mtime`）
- 缓存配置（避免重复解析）
- 透明重载（用户无需关心）
- 日志记录（便于调试）

**注意**：当前实现支持检测，但不会自动触发工具重新注册。完整热加载需要：
```python
# 监听文件变化 → 重新扫描工具 → 更新注册表
```

---

### 分类 E: 消息管理技巧

#### E1. Clean 策略（保留完整轮次）

**问题**：如何在清理消息时保持对话的完整性？

**实现位置**：`generalAgent/utils/message_utils.py:15-70`

**代码示例**：
```python
def clean_messages(
    messages: List[BaseMessage],
    max_history: int = 40,
) -> List[BaseMessage]:
    """Clean messages by removing intermediate tool calls"""

    if len(messages) <= max_history:
        return messages

    # Keep first message (usually system/initial user message)
    first_msg = messages[0]

    # Process remaining messages
    recent = messages[1:]

    # Identify complete turns
    # A turn = User → Assistant → [Tools] → Assistant (final)
    turns = []
    current_turn = []

    for msg in recent:
        current_turn.append(msg)

        # Turn ends with assistant message WITHOUT tool_calls
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            turns.append(current_turn)
            current_turn = []

    # Handle incomplete turn at end
    if current_turn:
        turns.append(current_turn)

    # Keep last N complete turns
    max_turns = max_history // 4  # Estimate ~4 messages per turn
    kept_turns = turns[-max_turns:]

    # Flatten back to message list
    cleaned = [first_msg]
    for turn in kept_turns:
        cleaned.extend(turn)

    return cleaned
```

**轮次识别逻辑**：
```
Turn 1:
  - HumanMessage: "帮我读取文件"
  - AIMessage(tool_calls=[read_file])  # Not end
  - ToolMessage: "文件内容..."
  - AIMessage: "文件内容是..."  # End (no tool_calls)

Turn 2:
  - HumanMessage: "总结一下"
  - AIMessage: "总结如下..."  # End (no tool_calls)
```

**设计考量**：
- 保持对话完整性（不截断工具调用链）
- 估算轮次数量（`max_history // 4`）
- 处理不完整轮次（末尾可能正在进行）
- 总是保留第一条消息（上下文基础）

---

#### E2. 消息角色管理

**问题**：LangChain 的消息类型如何正确使用？

**实现位置**：所有节点和工具

**消息类型说明**：
```python
from langchain_core.messages import (
    AIMessage,       # LLM 输出
    HumanMessage,    # 用户输入
    SystemMessage,   # 系统提示（通常不存储在历史中）
    ToolMessage,     # 工具执行结果
)
```

**正确使用示例**：
```python
# 1. User input
messages.append(HumanMessage(content="帮我读取 uploads/data.txt"))

# 2. Agent wants to call tool
messages.append(AIMessage(
    content="",  # Can be empty when calling tools
    tool_calls=[{
        "name": "read_file",
        "args": {"file_path": "uploads/data.txt"},
        "id": "call_abc123",  # Unique ID
    }]
))

# 3. Tool returns result
messages.append(ToolMessage(
    content="File contents: Hello World",
    tool_call_id="call_abc123",  # Must match AIMessage.tool_calls[].id
))

# 4. Agent responds to user
messages.append(AIMessage(content="文件内容是：Hello World"))
```

**常见错误**：
```python
# ❌ 错误：tool_call_id 不匹配
ToolMessage(content="...", tool_call_id="wrong_id")

# ❌ 错误：使用 HumanMessage 表示工具结果
HumanMessage(content="Tool result: ...")

# ❌ 错误：SystemMessage 放在历史中
messages.append(SystemMessage(content="你是 AI 助手"))
```

**设计考量**：
- `tool_call_id` 必须匹配（LangChain 要求）
- SystemMessage 不存储在历史中（每次动态生成）
- AIMessage 可以只有 `tool_calls` 没有 `content`
- ToolMessage 必须跟在 AIMessage(tool_calls) 之后

---

#### E3. 消息历史限制配置

**问题**：如何让用户灵活配置消息历史限制？

**实现位置**：`.env` + `generalAgent/config/settings.py` + `planner.py`

**配置定义**：
```python
# .env
MAX_MESSAGE_HISTORY=40  # 默认 40，范围 10-100

# generalAgent/config/settings.py:85-95
class GovernanceConfig(BaseModel):
    max_message_history: int = Field(
        default=40,
        ge=10,   # 最小 10
        le=100,  # 最大 100
        description="Maximum message history to keep",
    )

    @field_validator("max_message_history")
    @classmethod
    def validate_history(cls, v):
        if not (10 <= v <= 100):
            raise ValueError("max_message_history must be between 10 and 100")
        return v
```

**应用到节点**：
```python
# generalAgent/graph/nodes/planner.py:290-305
def planner_node(state: AppState):
    messages = state["messages"]

    # Apply message limit
    max_history = settings.governance.max_message_history
    if len(messages) > max_history:
        messages = clean_messages(messages, max_history)
        LOGGER.info(f"Cleaned messages: {len(state['messages'])} → {len(messages)}")

    # ... invoke model ...
```

**设计考量**：
- 环境变量配置（用户友好）
- Pydantic 验证（防止无效值）
- 合理范围限制（10-100）
- 日志记录（便于调试）

**最佳实践**：
- 简单任务：20-30
- 复杂任务：40-60
- 长对话：60-100
- 配合 call_subagent 使用（避免主历史过长）

---

### 分类 F: 会话持久化技巧

#### F1. LangGraph Checkpointer 集成

**问题**：如何使用 LangGraph 的 Checkpointer 实现会话持久化？

**实现位置**：`generalAgent/persistence/checkpointer.py:15-40`

**代码示例**：
```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

def build_checkpointer(db_path: str) -> Optional[SqliteSaver]:
    """Build SQLite checkpointer for LangGraph"""

    if not db_path:
        return None

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # Create SQLite connection
    conn = sqlite3.connect(
        str(db_file),
        check_same_thread=False,  # Allow multi-threaded access
    )

    # Create LangGraph checkpointer
    checkpointer = SqliteSaver(conn)

    LOGGER.info(f"Session persistence enabled: {db_path}")

    return checkpointer
```

**应用到图**：
```python
# generalAgent/runtime/app.py:125-145
checkpointer = build_checkpointer(settings.observability.session_db_path)

app = graph.build_state_graph(
    ...,
    checkpointer=checkpointer,  # Enable persistence
)
```

**使用 checkpointer**：
```python
# generalAgent/cli.py:280-310
async def handle_user_message(self, user_input: str):
    """Handle user message with persistence"""

    # Create config with thread_id
    config = {
        "configurable": {
            "thread_id": self.session_manager.current_session_id,
        }
    }

    # Execute graph (state automatically saved)
    async for chunk in self.app.astream(initial_state, config=config):
        # ... process chunks ...
        pass

    # State is automatically checkpointed after each step!
```

**加载会话**：
```python
# Load existing session
config = {"configurable": {"thread_id": "session_123"}}
state = await app.aget_state(config)

# Resume execution
result = await app.ainvoke(new_input, config=config)
```

**设计考量**：
- LangGraph 自动管理 checkpoints（无需手动保存）
- `thread_id` 作为会话标识符
- SQLite 提供轻量级持久化
- `check_same_thread=False` 支持异步

---

#### F2. 会话元数据管理

**问题**：除了对话状态，如何存储会话元数据（创建时间、用户 ID 等）？

**实现位置**：`shared/session/store.py:60-125`

**数据库表结构**：
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    thread_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT  -- JSON string
);
```

**SessionStore 实现**：
```python
class SessionStore:
    def create_session(self, thread_id: str, user_id: str = None) -> dict:
        """Create new session record"""

        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions (thread_id, user_id, created_at, updated_at, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (thread_id, user_id, now, now, "{}"),
            )

        return {
            "thread_id": thread_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }

    def update_session(self, thread_id: str, metadata: dict = None):
        """Update session metadata"""

        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            if metadata:
                conn.execute(
                    """UPDATE sessions
                       SET updated_at = ?, metadata = ?
                       WHERE thread_id = ?""",
                    (now, json.dumps(metadata), thread_id),
                )
            else:
                conn.execute(
                    """UPDATE sessions SET updated_at = ? WHERE thread_id = ?""",
                    (now, thread_id),
                )

    def list_sessions(self, user_id: str = None, limit: int = 20) -> List[dict]:
        """List recent sessions"""

        with self._connect() as conn:
            if user_id:
                rows = conn.execute(
                    """SELECT * FROM sessions
                       WHERE user_id = ?
                       ORDER BY updated_at DESC
                       LIMIT ?""",
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM sessions
                       ORDER BY updated_at DESC
                       LIMIT ?""",
                    (limit,),
                ).fetchall()

        return [dict(row) for row in rows]
```

**设计考量**：
- 分离元数据和对话状态（不同表）
- JSON 存储灵活元数据（`metadata` 列）
- 按 `updated_at` 排序（最近使用的在前）
- 支持用户过滤（多用户系统）

---

#### F3. 会话 ID 生成策略

**问题**：如何生成唯一且友好的会话 ID？

**实现位置**：`shared/session/manager.py:125-140`

**代码示例**：
```python
import uuid
from datetime import datetime

def _generate_thread_id(self) -> str:
    """Generate unique thread ID"""

    # Format: date_time_uuid
    # Example: 20250124_153045_a1b2c3d4

    now = datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    uuid_part = uuid.uuid4().hex[:8]  # Short UUID

    thread_id = f"{date_part}_{time_part}_{uuid_part}"

    return thread_id
```

**优点**：
- 可读性（包含日期时间）
- 唯一性（UUID 部分）
- 简短（总共 24 字符）
- 可排序（日期在前）

**使用示例**：
```python
# 生成的 ID
"20250124_153045_a1b2c3d4"

# 命令行加载
/load 20250124  # 可以只输入前缀

# 代码匹配
sessions = [s for s in all_sessions if s["thread_id"].startswith(prefix)]
```

**设计考量**：
- 避免使用纯 UUID（不可读）
- 包含时间戳（便于识别）
- 支持前缀匹配（用户友好）
- 长度适中（24 字符）

---

### 分类 G: 技能系统技巧

#### G1. Skills as Knowledge Packages（非工具容器）

**问题**：为什么 Skills 不包含 `allowed_tools` 字段？

**核心理念**：
- Skills 是**知识包**（SKILL.md + scripts），不是工具容器
- Agent 读取 SKILL.md 后**自主选择**使用哪些工具
- 避免硬编码工具列表（更灵活）

**错误设计（旧版本）**：
```python
# ❌ 错误：Skills 包含 allowed_tools
skill = {
    "id": "pdf",
    "name": "PDF 处理",
    "allowed_tools": ["read_file", "write_file", "run_skill_script"],  # 硬编码
}
```

**正确设计（当前版本）**：
```python
# ✅ 正确：Skills 只是文档
skill = {
    "id": "pdf",
    "name": "PDF 处理",
    "description": "提供 PDF 文件处理能力",
    "path": Path("skills/pdf"),
}

# skills/pdf/SKILL.md 内容
"""
# PDF 处理技能

## 使用步骤
1. 使用 read_file 读取 PDF 文件  # Agent 自己决定用 read_file
2. 使用 run_skill_script 执行脚本  # Agent 自己决定用 run_skill_script
3. ...
"""
```

**设计考量**：
- 灵活性：Agent 可以根据任务选择最合适的工具
- 可扩展性：添加新工具无需修改 skill 定义
- 简洁性：Skill 只包含元数据和文档
- 智能性：信任 LLM 的推理能力

---

#### G2. 技能脚本依赖自动安装

**问题**：如何自动安装技能脚本需要的 Python 库？

**实现位置**：`shared/workspace/manager.py:156-192`

**代码示例**：
```python
def _link_skill(self, skill_id: str, skill_path: Path):
    """Link skill to workspace and install dependencies"""

    target_dir = self.workspace_path / "skills" / skill_id

    # Create symlink
    if not target_dir.exists():
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        target_dir.symlink_to(skill_path, target_is_directory=True)

    # Check for requirements.txt
    requirements = skill_path / "requirements.txt"
    if requirements.exists() and not self._is_dependencies_installed(skill_id):
        self._install_skill_dependencies(skill_id, requirements)

def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    """Install dependencies using pip"""

    try:
        LOGGER.info(f"Installing dependencies for skill '{skill_id}'...")

        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True,
            timeout=120,  # 2 minutes timeout
        )

        # Mark as installed
        self._skill_registry.mark_dependencies_installed(skill_id)

        LOGGER.info(f"✓ Dependencies installed for '{skill_id}'")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(
            f"Failed to install dependencies for skill '{skill_id}': {error_msg}"
        )

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Dependency installation timeout for skill '{skill_id}'")
```

**requirements.txt 示例**：
```
# skills/pdf/requirements.txt
pypdf2>=3.0.0
reportlab>=4.0.0
pillow>=10.0.0
```

**设计考量**：
- **首次使用时安装**（不是启动时）
- **缓存安装状态**（避免重复安装）
- **超时保护**（2 分钟）
- **错误提示友好**（引导用户手动安装）

**错误处理**：
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

---

#### G3. 技能脚本接口规范

**问题**：技能脚本如何与 Agent 通信？

**实现位置**：所有技能脚本（`skills/*/scripts/*.py`）

**接口规范**：
```python
# skills/pdf/scripts/fill_form.py
import json
import sys
import os

def main():
    # 1. Read workspace path from environment
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")
    if not workspace:
        print(json.dumps({"error": "AGENT_WORKSPACE_PATH not set"}))
        sys.exit(1)

    # 2. Read arguments from stdin (JSON)
    try:
        args = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    # 3. Validate required arguments
    required = ["input_pdf", "output_pdf", "fields"]
    missing = [k for k in required if k not in args]
    if missing:
        print(json.dumps({"error": f"Missing arguments: {missing}"}))
        sys.exit(1)

    # 4. Execute logic
    input_path = os.path.join(workspace, args["input_pdf"])
    output_path = os.path.join(workspace, args["output_pdf"])

    try:
        # ... PDF processing logic ...
        result = fill_pdf_form(input_path, output_path, args["fields"])

        # 5. Print result to stdout (JSON)
        print(json.dumps({
            "status": "success",
            "output_file": args["output_pdf"],
            "fields_filled": len(args["fields"]),
        }))

    except Exception as e:
        # 6. Print error (JSON)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**调用方式**：
```python
# generalAgent/tools/builtin/run_skill_script.py:85-110
result = subprocess.run(
    [sys.executable, str(script_path)],
    input=json.dumps(args),  # stdin
    capture_output=True,
    text=True,
    timeout=timeout,
    env=env,  # AGENT_WORKSPACE_PATH
    cwd=workspace_path,
)

if result.returncode != 0:
    return f"Script failed: {result.stderr}"

return result.stdout  # JSON string
```

**设计考量**：
- **stdin/stdout 通信**（标准化）
- **JSON 格式**（结构化）
- **环境变量传递 workspace**（安全）
- **错误处理统一**（JSON 格式）
- **工作目录设置**（cwd=workspace）

---

### 分类 H: 环境变量技巧

#### H1. 环境变量作为上下文传递

**问题**：如何在不改变函数签名的情况下传递上下文信息？

**实现位置**：`generalAgent/cli.py:250-260` + 所有工具

**设置环境变量**：
```python
# generalAgent/cli.py:250-260
async def handle_user_message(self, user_input: str):
    """Handle user message"""

    # Set context in environment
    os.environ["AGENT_WORKSPACE_PATH"] = str(self.workspace_path)
    os.environ["AGENT_CONTEXT_ID"] = self.session_manager.current_session_id
    os.environ["AGENT_USER_ID"] = self.user_id or "anonymous"

    # Execute graph (tools can access environment)
    result = await self.app.ainvoke(...)
```

**工具读取环境变量**：
```python
# generalAgent/tools/builtin/file_ops.py:45-50
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    # ... use workspace_root ...
```

**设计考量**：
- 避免全局变量（支持多会话）
- 工具无需额外参数（接口简洁）
- 子进程自动继承（脚本执行）
- 线程安全（每次执行前设置）

**支持的环境变量**：
- `AGENT_WORKSPACE_PATH`: 工作区路径
- `AGENT_CONTEXT_ID`: 会话 ID
- `AGENT_USER_ID`: 用户 ID
- `AGENT_PARENT_CONTEXT`: 父上下文（subagent）

---

#### H2. 子进程环境变量继承

**问题**：脚本执行时如何访问环境变量？

**实现位置**：`generalAgent/tools/builtin/run_skill_script.py:85-110`

**代码示例**：
```python
def _execute_script(script_path: Path, args: dict) -> str:
    """Execute script in isolated process"""

    # Prepare environment (copy current + add custom)
    env = os.environ.copy()
    env["AGENT_WORKSPACE_PATH"] = str(workspace_path)
    env["AGENT_SCRIPT_TIMEOUT"] = "30"

    # Execute subprocess with environment
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(args),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,  # Pass environment to subprocess
        cwd=workspace_path,
    )

    return result.stdout
```

**脚本访问**：
```python
# skills/pdf/scripts/example.py
import os

workspace = os.environ.get("AGENT_WORKSPACE_PATH")
timeout = int(os.environ.get("AGENT_SCRIPT_TIMEOUT", "30"))
```

**设计考量**：
- `os.environ.copy()` 继承当前环境
- 添加自定义变量（`AGENT_*`）
- 子进程隔离（不影响主进程）
- 统一接口（所有脚本都能访问）

---

### 分类 I: 日志与调试技巧

#### I1. 结构化日志记录

**问题**：如何记录清晰、可搜索的日志？

**实现位置**：所有模块

**日志配置**：
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

**使用示例**：
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

**日志输出**：
```
2025-01-24 15:30:45 [INFO] generalAgent.tools.registry:95 - Loading tool on-demand: http_fetch
2025-01-24 15:30:45 [INFO] generalAgent.tools.registry:99 - ✓ Tool loaded: http_fetch
```

**设计考量**：
- 包含时间戳、级别、模块、行号
- 同时输出到文件和控制台
- 使用 `__name__` 作为 logger 名称（自动分类）
- 友好的符号（✓ ✗ →）

---

#### I2. Prompt 截断日志

**问题**：如何在日志中显示长 Prompt 的摘要？

**实现位置**：`generalAgent/graph/nodes/planner.py:305-315`

**代码示例**：
```python
def planner_node(state: AppState):
    # Build system prompt
    system_prompt = build_system_prompt(state)

    # Log prompt (truncated)
    max_length = settings.logging.prompt_max_length or 500
    if len(system_prompt) > max_length:
        preview = system_prompt[:max_length] + f"... ({len(system_prompt)} chars)"
    else:
        preview = system_prompt

    LOGGER.debug(f"System prompt:\n{preview}")

    # ... invoke model ...
```

**配置**：
```bash
# .env
LOG_PROMPT_MAX_LENGTH=500  # 默认 500，范围 100-5000
```

**日志输出**：
```
2025-01-24 15:30:45 [DEBUG] generalAgent.graph.nodes.planner:308 - System prompt:
你是 Charlie，一个高效、友好的 AI 助手。

核心能力：
- 调用工具完成任务
- 委派子任务给专用 agent
...（省略）... (3456 chars)
```

**设计考量**：
- 避免日志文件过大
- 保留足够信息用于调试
- 可配置截断长度
- 显示总字符数

---

#### I3. 工具调用日志

**问题**：如何记录每次工具调用的参数和结果？

**实现位置**：`generalAgent/graph/nodes/planner.py:320-340`

**代码示例**：
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

**日志输出**：
```
2025-01-24 15:30:45 [INFO] generalAgent.graph.nodes.planner:325 - Tool call: read_file(file_path='uploads/data.txt')
2025-01-24 15:30:45 [INFO] generalAgent.graph.nodes.planner:325 - Tool call: write_file(file_path='outputs/result.txt', content='Analysis results...（截断）...')
```

**设计考量**：
- 记录工具名称和参数
- 截断长参数（如文件内容）
- 可用于审计和调试
- 不记录敏感信息（如 API keys）

---

### 分类 J: 错误处理技巧

#### J1. 工具错误边界装饰器

**问题**：如何统一处理工具执行中的异常？

**实现位置**：`generalAgent/tools/decorators.py:10-40`

**代码示例**：
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

**使用示例**：
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

**错误返回示例**：
```
Error: File not found: uploads/missing.txt
Error: Permission denied: Cannot write to skills/
Error: Unexpected error: UnicodeDecodeError: 'utf-8' codec can't decode byte...
```

**设计考量**：
- 捕获常见异常（文件、权限、编码）
- 返回友好错误消息（不是堆栈）
- 记录详细日志（包括堆栈）
- Agent 可以根据错误消息调整策略

---

#### J2. 优雅降级（Graceful Degradation）

**问题**：某个功能不可用时，如何继续提供服务？

**实现示例 1：模型 fallback**
```python
# generalAgent/runtime/model_resolver.py:85-100
def resolve(self, state: AppState, node_name: str) -> str:
    """Resolve model with fallback"""

    # Prefer vision model for images
    if state.get("images") and "vision" in self.configs:
        return "vision"

    # Fallback to base model
    if "base" in self.configs:
        return "base"

    # Ultimate fallback: first available
    return list(self.configs.keys())[0]
```

**实现示例 2：技能依赖安装失败**
```python
# shared/workspace/manager.py:180-195
def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    try:
        subprocess.run([...], check=True, timeout=120)
        self._skill_registry.mark_dependencies_installed(skill_id)

    except subprocess.CalledProcessError as e:
        # Don't fail the whole session, just warn
        LOGGER.warning(f"Failed to install dependencies for '{skill_id}': {e}")
        LOGGER.warning("Skill scripts may not work. Manual installation required.")

    except subprocess.TimeoutExpired:
        LOGGER.warning(f"Dependency installation timeout for '{skill_id}'")
```

**设计考量**：
- 功能失败不应导致整个系统崩溃
- 提供 fallback 选项
- 明确告知用户降级状态
- 记录警告日志

---

#### J3. 循环限制与死锁检测

**问题**：如何防止 Agent 陷入无限循环？

**实现位置**：`generalAgent/graph/routing.py:6-20`

**代码示例**：
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

**循环计数**：
```python
# generalAgent/graph/nodes/planner.py:340
def planner_node(state: AppState):
    # ... invoke model ...

    return {
        "messages": [result],
        "loops": state["loops"] + 1,  # Increment loop counter
    }
```

**死锁检测（高级）**：
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

**设计考量**：
- 硬性循环限制（`max_loops`）
- 记录警告日志
- 检测重复工具调用（死锁）
- 强制进入 finalize（避免无限循环）

---

## 总结

本文档收录了 GeneralAgent 项目中的 50+ 实现技巧，涵盖：

- **路径处理**（4 个技巧）：工作区隔离、路径验证、符号链接、项目根目录
- **工具系统**（5 个技巧）：三层架构、多工具文件、元数据、可见性、环境变量
- **Prompt 工程**（4 个技巧）：动态提醒、技能目录、差异化提示、时间注入
- **配置管理**（3 个技巧）：Pydantic Settings、模型别名、YAML 热加载
- **消息管理**（3 个技巧）：Clean 策略、角色管理、历史限制
- **会话持久化**（3 个技巧）：Checkpointer、元数据、ID 生成
- **技能系统**（3 个技巧）：知识包理念、依赖安装、脚本接口
- **环境变量**（2 个技巧）：上下文传递、子进程继承
- **日志与调试**（3 个技巧）：结构化日志、Prompt 截断、工具日志
- **错误处理**（3 个技巧）：错误边界、优雅降级、循环限制

每个技巧都包含：
- ❓ 问题描述
- 📍 实现位置
- 💻 代码示例
- 💡 设计考量

这些技巧是项目演进过程中积累的最佳实践，帮助理解代码设计背后的思考。
