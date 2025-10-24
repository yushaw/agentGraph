# GeneralAgent 详细需求文档 - Part 1: 核心架构与工具系统

## 1. 核心架构需求

### 1.1 Agent Loop 架构

**需求描述**：系统采用 Agent Loop 架构（Claude Code 风格），而非传统的 Plan-and-Execute 模式。

**详细说明**：
- Agent 在单一循环中自主决定执行流程
- 通过 tool_calls 决定是继续调用工具还是结束任务
- 不需要预先制定计划，而是动态响应

**技术实现**：
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

**设计考量**：
- 简化架构，减少节点数量
- 赋予 LLM 更大的自主权
- 通过 TodoWrite 工具进行任务追踪（观察者模式，非指挥者）

### 1.2 状态管理

**需求描述**：使用 TypedDict 定义的 AppState 管理所有对话状态。

**状态字段**：
```python
# generalAgent/graph/state.py
class AppState(TypedDict):
    messages: Annotated[List, add_messages]  # 消息历史
    images: List                              # 图片列表
    active_skill: Optional[str]              # 当前激活的技能
    allowed_tools: List[str]                 # 允许使用的工具列表
    mentioned_agents: List[str]              # @提及的代理
    persistent_tools: List                   # 持久化工具
    model_pref: Optional[str]                # 模型偏好
    todos: List[dict]                        # 任务列表
    context_id: str                          # 上下文 ID
    parent_context: Optional[str]            # 父上下文
    loops: int                               # 循环计数
    max_loops: int                           # 最大循环次数
    thread_id: Optional[str]                 # 线程 ID
    user_id: Optional[str]                   # 用户 ID
    workspace_path: Optional[str]            # 工作区路径
```

**详细说明**：
- `messages`: 使用 LangChain 的 `add_messages` reducer 管理消息历史
- `todos`: 支持动态任务追踪（pending/in_progress/completed）
- `context_id` + `parent_context`: 实现 subagent 上下文隔离
- `loops` + `max_loops`: 防止无限循环

**设计考量**：
- TypedDict 提供类型提示但保持字典灵活性
- 状态字段覆盖所有运行时需求
- 支持嵌套 subagent 调用

### 1.3 节点系统

**需求描述**：三个核心节点构成完整的执行流程。

**节点定义**：

1. **agent 节点** (planner.py)
   - 职责：分析任务，决定调用工具或结束
   - 输入：用户消息 + 工具结果
   - 输出：tool_calls 或 finish 信号

2. **tools 节点** (LangGraph ToolNode)
   - 职责：执行工具调用
   - 输入：tool_calls
   - 输出：ToolMessage

3. **finalize 节点**
   - 职责：生成最终回复
   - 输入：完整对话历史
   - 输出：最终 AIMessage

**实现位置**：
```python
# generalAgent/graph/builder.py:56-69
agent_node = build_planner_node(...)
finalize_node = build_finalize_node(...)

graph.add_node("agent", agent_node)
graph.add_node("tools", ToolNode(tool_registry.list_tools()))
graph.add_node("finalize", finalize_node)
```

### 1.4 路由系统

**需求描述**：条件边路由控制节点间转换。

**路由函数**：

1. **agent_route** (generalAgent/graph/routing.py:6-20)
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

2. **tools_route** (generalAgent/graph/routing.py:23-26)
```python
def tools_route(state: AppState) -> Literal["agent"]:
    return "agent"  # Always return to agent
```

**设计考量**：
- 简单的条件判断，避免复杂逻辑
- 强制循环限制防止无限循环
- tools 节点总是返回 agent（闭环）

---

## 2. 工具系统需求

### 2.1 三层工具加载架构

**需求描述**：工具分为三个层次：discovered（已发现）、registered（已注册）、visible（可见）。

**详细说明**：

**第一层：discovered（已发现工具池）**
- 所有扫描到的工具（包括禁用的）
- 存储在 `ToolRegistry._discovered: Dict[str, Any]`
- 支持按需加载

**第二层：registered（已注册工具）**
- 启用的工具（enabled: true）
- 存储在 `ToolRegistry._tools: Dict[str, Any]`
- 启动时自动注册

**第三层：visible（可见工具）**
- 当前上下文可用的工具
- 通过 `build_visible_tools()` 动态构建
- 包括：persistent_tools + allowed_tools + 动态加载的 @mention 工具

**实现代码**：
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

**设计考量**：
- Layer 1 支持插件发现但不占用内存
- Layer 2 是启动时加载的核心工具集
- Layer 3 是运行时动态可见性（最重要）

### 2.2 工具扫描与发现

**需求描述**：自动扫描指定目录，发现所有工具。

**扫描目录**：
- `generalAgent/tools/builtin/`: 内置工具
- `generalAgent/tools/custom/`: 用户自定义工具
- 其他配置的目录（tools.yaml）

**扫描逻辑**：
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

**多工具文件支持**：
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

**设计考量**：
- 使用 `__all__` 明确导出（推荐）
- 回退到自动检测（便利）
- 支持一个文件多个工具

### 2.3 工具配置系统

**需求描述**：通过 tools.yaml 集中管理工具配置。

**配置文件结构**：
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
    always_available: false
    category: "network"
    tags: ["network", "read"]

  extract_links:
    enabled: false
    category: "read"
    tags: ["read", "parse"]
```

**配置加载**：
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

    def is_always_available(self, tool_name: str) -> bool:
        """Check if tool should be in all contexts"""
        meta = self._find_tool_config(tool_name)
        return meta.get("always_available", False)
```

**设计考量**：
- 配置驱动，无需修改代码
- `core` vs `optional` 区分系统工具和可选工具
- `always_available` 控制全局可见性

### 2.4 工具元数据系统

**需求描述**：为每个工具提供丰富的元数据，支持分类、搜索、文档生成。

**元数据定义**：
```python
# generalAgent/tools/__init__.py:13-22
@dataclass
class ToolMeta:
    name: str
    category: str
    tags: List[str]
    description: str
    always_available: bool = False
    dependencies: List[str] = field(default_factory=list)
```

**元数据注册**：
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

**使用场景**：
- 工具搜索与发现
- 自动生成工具文档
- 依赖管理
- 分类浏览

### 2.5 持久化工具（Persistent Tools）

**需求描述**：某些工具需要在所有上下文中始终可用。

**配置方式**：
```yaml
# tools.yaml
optional:
  todo_write:
    enabled: true
    always_available: true  # 所有上下文可见
```

**实现**：
```python
# generalAgent/runtime/app.py:89-99
persistent = []
for tool_name in enabled_tools:
    if tool_config.is_always_available(tool_name):
        try:
            persistent.append(registry.get_tool(tool_name))
        except KeyError:
            LOGGER.warning(f"Tool '{tool_name}' configured but not found")
```

**传递到节点**：
```python
# generalAgent/graph/nodes/planner.py:224-226
visible_tools = build_visible_tools(
    state=state,
    tool_registry=tool_registry,
    persistent_global_tools=persistent_global_tools,  # 始终包含
)
```

**典型持久化工具**：
- `todo_write` / `todo_read`: 任务追踪
- `now`: 获取当前时间
- `call_subagent`: 子任务委派（按需加载）

### 2.6 工具可见性构建（核心机制）

**需求描述**：根据当前状态动态构建工具可见性列表。

**实现代码**：
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

**三步构建流程**：
1. **持久化工具**：始终可用（如 todo_write）
2. **技能工具**：当前激活技能的工具（allowed_tools）
3. **@提及工具**：用户动态请求的工具（按需加载）

**设计考量**：
- 去重（seen_names set）
- 优先级顺序（persistent > allowed > mentioned）
- 动态加载（load_on_demand）

---

## 3. 技能系统需求

### 3.1 技能定义（Knowledge Package）

**需求描述**：技能是知识包（文档 + 脚本），NOT 工具容器。

**核心概念**：
- 技能不包含 `allowed_tools` 字段
- 技能通过 SKILL.md 提供指导
- Agent 读取 SKILL.md 后自主选择工具
- 脚本是可选的执行资源

**目录结构**：
```
skills/pdf/
├── SKILL.md           # 主文档（必需）
├── requirements.txt   # Python 依赖（可选）
├── reference.md       # 参考文档（可选）
├── forms.md           # 特定指南（可选）
└── scripts/           # Python 脚本（可选）
    ├── fill_fillable_fields.py
    └── extract_text.py
```

**SKILL.md 示例**：
```markdown
# PDF 处理技能

## 概述
本技能提供 PDF 文件处理能力，包括表单填写、文本提取、页面操作等。

## 使用步骤
1. 使用 `read_file` 读取 PDF 文件
2. 根据任务选择合适的脚本
3. 使用 `run_skill_script` 执行脚本
4. 检查输出结果

## 可用脚本
- `fill_fillable_fields.py`: 填写可填写 PDF 表单
- `extract_text.py`: 提取 PDF 文本内容

## 示例
填写 PDF 表单：
\`\`\`python
run_skill_script(
    skill_id="pdf",
    script_name="fill_fillable_fields.py",
    args='{"input_pdf": "uploads/form.pdf", ...}'
)
\`\`\`
```

### 3.2 技能注册系统

**需求描述**：自动扫描和注册技能包。

**实现代码**：
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

**元数据解析**：
从 SKILL.md 的前几行提取标题和描述：
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

### 3.3 技能依赖管理

**需求描述**：技能脚本可能需要外部 Python 库，需要自动安装。

**requirements.txt 格式**：
```
# skills/pdf/requirements.txt
pypdf2>=3.0.0
reportlab>=4.0.0
pillow>=10.0.0
```

**自动安装流程**：
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

### 3.4 技能目录（Skills Catalog）

**需求描述**：在系统提示中生成可用技能列表，供 Agent 了解和使用。

**实现代码**：
```python
# generalAgent/graph/prompts.py:143-174
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

**注入到系统提示**：
```python
# generalAgent/graph/nodes/planner.py:265-270
skills_catalog = build_skills_catalog(skill_registry)
if skills_catalog:
    system_parts.append(skills_catalog)

system_prompt = "\n\n---\n\n".join(system_parts)
```

**输出示例**：
```
# 可用技能（Skills）

## PDF 处理 (#pdf)
提供 PDF 文件处理能力，包括表单填写、文本提取、页面操作等。
📁 路径: `skills/pdf/SKILL.md`
```

**设计考量**：
- 使用 workspace-relative 路径（不暴露项目路径）
- 提供明确的使用指导
- 强调 skills 是文档，不是工具

### 3.5 技能脚本执行

**需求描述**：通过 `run_skill_script` 工具执行技能脚本。

**工具定义**：
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

**执行流程**：
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

**脚本接口规范**：
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

**设计考量**：
- 脚本在独立进程中运行（隔离）
- 通过 stdin/stdout 传递 JSON 数据（标准化）
- 环境变量传递 workspace 路径（安全）
- 超时保护（默认 30s）
