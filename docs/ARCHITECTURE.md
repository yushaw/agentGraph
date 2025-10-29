# 架构文档

> **说明**: 本文档整合了 REQUIREMENTS_PART1（核心架构与工具/技能系统）、REQUIREMENTS_PART4 的精选最佳实践以及 SKILLS_CONFIGURATION 的技术架构细节。

**最后更新**: 2025-10-27

---

## 目录

- [第一部分：核心架构](#第一部分核心架构)
  - [1.1 Agent Loop 架构](#11-agent-loop-架构)
  - [1.2 状态管理](#12-状态管理)
  - [1.3 节点系统](#13-节点系统)
  - [1.4 路由系统](#14-路由系统)
- [第二部分：工具系统](#第二部分工具系统)
  - [2.1 三层架构](#21-三层架构)
  - [2.2 工具发现与扫描](#22-工具发现与扫描)
  - [2.3 工具配置](#23-工具配置)
  - [2.4 工具元数据](#24-工具元数据)
  - [2.5 持久化工具](#25-持久化工具)
  - [2.6 工具可见性](#26-工具可见性)
  - [2.7 TODO 工具系统](#27-todo-工具系统)
- [第三部分：技能系统](#第三部分技能系统)
  - [3.1 技能作为知识包](#31-技能作为知识包)
  - [3.2 技能注册表](#32-技能注册表)
  - [3.3 技能配置](#33-技能配置)
  - [3.4 技能加载](#34-技能加载)
  - [3.5 技能依赖](#35-技能依赖)
  - [3.6 技能目录](#36-技能目录)
  - [3.7 技能脚本执行](#37-技能脚本执行)
- [第四部分：最佳实践与设计模式](#第四部分最佳实践与设计模式)
  - [4.1 路径处理](#41-路径处理)
  - [4.2 Prompt 工程](#42-prompt-工程)
  - [4.3 错误处理](#43-错误处理)
  - [4.4 日志与调试](#44-日志与调试)
  - [4.5 配置管理](#45-配置管理)

---

## 第一部分：核心架构

### 1.1 Agent Loop 架构

**设计理念**: 系统采用 Agent Loop 架构（Claude Code 风格），而非传统的 Plan-and-Execute 模式。

**核心概念**:
- Agent 在单一循环中自主决定执行流程
- 使用 `tool_calls` 判断是继续调用工具还是结束任务
- 无需预先规划 - 根据结果动态响应

**技术实现**:

```python
# generalAgent/graph/builder.py:79-100
graph.add_conditional_edges(
    "agent",
    agent_route,
    {
        "tools": "tools",      # LLM 想要调用工具
        "finalize": "finalize",  # LLM 决定结束
    }
)

graph.add_conditional_edges(
    "tools",
    tools_route,
    {
        "agent": "agent",  # 继续循环
    }
)
```

**流程图**:
```
START → agent ⇄ tools → agent → finalize → END
         ↑_______↓
```

**设计考量**:
- 简化架构，减少节点数量
- 赋予 LLM 更大自主权
- TodoWrite 工具用于任务跟踪（观察者模式，非指挥者）
- 循环限制保护防止无限循环

---

### 1.2 状态管理

**设计**: 使用 TypedDict 定义的 AppState 管理所有会话状态。

**状态字段**:

```python
# generalAgent/graph/state.py
class AppState(TypedDict):
    messages: Annotated[List, add_messages]  # 消息历史
    images: List                              # 图片列表
    active_skill: Optional[str]              # 当前激活的技能
    allowed_tools: List[str]                 # 允许的工具列表

    # @Mention 跟踪 (双字段设计)
    mentioned_agents: List[str]              # 所有 @mention 历史 (累加)
    new_mentioned_agents: List[str]          # 当前轮新 @mention (用完即清)

    persistent_tools: List                   # 持久化工具
    model_pref: Optional[str]                # 模型偏好
    todos: List[dict]                        # 任务列表
    context_id: str                          # 上下文 ID
    parent_context: Optional[str]            # 父上下文
    loops: int                               # 循环计数器
    max_loops: int                           # 最大循环次数
    thread_id: Optional[str]                 # 线程 ID
    user_id: Optional[str]                   # 用户 ID
    workspace_path: Optional[str]            # 工作空间路径

    # 文件上传跟踪 (双字段设计)
    uploaded_files: List[Any]                # 所有上传文件历史 (累加)
    new_uploaded_files: List[Any]            # 当前轮新上传文件 (用完即清)
```

**关键字段说明**:
- `messages`: 使用 LangChain 的 `add_messages` reducer 管理消息历史
- `todos`: 支持动态任务跟踪（pending/in_progress/completed）
- `context_id` + `parent_context`: 实现子 agent 的上下文隔离
- `loops` + `max_loops`: 防止无限循环

**双字段设计 (Reminder 去重机制)**:

为了防止 system_reminder 重复生成，采用"历史字段 + 新增字段"的双字段设计：

| 字段类型 | 历史字段 | 新增字段 | 用途 |
|---------|---------|---------|------|
| **@Mention** | `mentioned_agents` | `new_mentioned_agents` | 工具/技能/代理提及 |
| **文件上传** | `uploaded_files` | `new_uploaded_files` | 文件上传记录 |

**工作原理**:
1. **CLI 层** (用户输入时):
   - 累加到历史字段 (`mentioned_agents`, `uploaded_files`)
   - 设置新增字段 (`new_mentioned_agents`, `new_uploaded_files`)

2. **Planner 层** (生成 Reminder):
   - 历史字段用于**加载工具/技能** (确保功能可用)
   - 新增字段用于**生成 Reminder** (只提醒一次)

3. **Planner 返回** (清理):
   - 显式清空新增字段 (`new_*` → `[]`)
   - 历史字段保持不变 (持久记录)

**设计考量**:
- TypedDict 提供类型提示，同时保持字典的灵活性
- 状态字段覆盖所有运行时需求
- 支持嵌套子 agent 调用
- **Reminder 只在相关事件发生时显示一次** (避免重复干扰)

---

### 1.3 节点系统

**设计**: 四个核心节点构成完整执行流程（含自动上下文压缩）。

**节点定义**:

**1. agent 节点** (planner.py)
   - **职责**: 分析任务，决定调用工具或结束；检测 token 使用率
   - **输入**: 用户消息 + 工具结果
   - **输出**: tool_calls、结束信号、或压缩标志 (`needs_compression`)
   - **Token 检测**: 调用 LLM 前检查 token 使用率，>95% 时设置 `needs_compression=True` 并立即返回

**2. summarization 节点** ⭐ NEW (summarization.py)
   - **职责**: 自动压缩对话历史（当 token 使用 >95%）
   - **输入**: 完整会话历史
   - **输出**: 压缩后的消息 + 重置 token 计数器
   - **策略**: LLM 智能压缩（保留关键信息）→ 降级为紧急截断
   - **触发方式**: 通过 routing 自动触发，压缩后返回 agent 继续执行

**3. tools 节点** (LangGraph ToolNode)
   - **职责**: 执行工具调用
   - **输入**: tool_calls
   - **输出**: ToolMessage

**4. finalize 节点**
   - **职责**: 生成最终响应
   - **输入**: 完整会话历史
   - **输出**: 最终 AIMessage

**实现位置**:

```python
# generalAgent/graph/builder.py:60-86
agent_node = build_planner_node(...)
summarization_node = build_summarization_node(settings=settings)
finalize_node = build_finalize_node(...)

graph.add_node("agent", agent_node)
graph.add_node("summarization", summarization_node)  # 自动压缩节点
graph.add_node("tools", ToolNode(tool_registry.list_tools()))
graph.add_node("finalize", finalize_node)
```

---

### 1.4 路由系统

**设计**: 条件边控制节点间的转换，支持自动压缩流程。

**路由函数**:

**1. agent_route** (generalAgent/graph/routing.py:14-62)

```python
def agent_route(state: AppState) -> Literal["tools", "summarization", "finalize"]:
    loops = state.get("loops", 0)
    max_loops = state.get("max_loops", 42)

    # 检查循环限制
    if loops >= max_loops:
        return "finalize"

    # 检查是否需要压缩（planner 设置的标志）
    needs_compression = state.get("needs_compression", False)
    auto_compressed = state.get("auto_compressed_this_request", False)

    if needs_compression and not auto_compressed:
        return "summarization"  # Token 使用 >95%，触发压缩

    # 检查工具调用
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

    return "finalize"
```

**2. tools_route** (generalAgent/graph/routing.py:65-76)

```python
def tools_route(state: AppState) -> Literal["agent"]:
    return "agent"  # 总是返回到 agent
```

**3. summarization_route** ⭐ NEW (generalAgent/graph/routing.py:79-90)

```python
def summarization_route(state: AppState) -> Literal["agent"]:
    return "agent"  # 压缩完成后返回 agent 继续处理原始请求
```

**执行流程**:

```
用户消息 → agent (检测 96% token 使用)
             ↓
          设置 needs_compression=True
             ↓
          routing 检查标志
             ↓
        summarization (压缩 302 → 13 条消息)
             ↓
          routing 返回 agent
             ↓
          agent (用压缩后的上下文继续执行)
             ↓
          tools / finalize
```

**设计考量**:
- 优先检查压缩需求，避免 token 溢出
- 压缩后自动返回 agent，用户无感知
- 循环限制防止无限循环
- Tools 节点总是返回到 agent（闭环）

---

### 1.5 上下文管理与自动压缩 ⭐ NEW

**设计目标**: 自动管理对话历史长度，防止 token 溢出，同时保持对话连贯性。

#### 1.5.1 核心机制

**Token 监控** (generalAgent/context/token_tracker.py)
- 在每次调用 LLM 前检查累积 token 使用
- 根据使用率分为 4 个级别：
  - **normal** (< 75%): 正常状态
  - **info** (75-85%): 显示提示，加载 `compact_context` 工具
  - **warning** (85-95%): 显示警告，建议压缩
  - **critical** (≥ 95%): 触发自动压缩

**自动压缩流程**:

```
1. Planner 检测 token 使用 > 95%
   ↓
2. 设置 needs_compression=True，跳过 LLM 调用
   ↓
3. Routing 检查标志，路由到 summarization 节点
   ↓
4. Summarization 执行压缩
   - 保留最近 10 条消息（可配置）
   - 压缩旧消息为摘要（LLM生成）
   - 重置 token 计数器
   ↓
5. 返回 agent 节点，用压缩后的上下文继续执行
```

#### 1.5.2 压缩策略

**分层保留**:
- **System**: 保留所有 SystemMessage
- **Recent**: 保留最近 N 条消息（完整）
- **Old**: 剩余消息压缩为摘要

**配置参数** (generalAgent/config/settings.py:240-271):

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enabled` | `True` | 是否启用上下文管理 |
| `info_threshold` | `0.75` | 75% 显示提示 |
| `warning_threshold` | `0.85` | 85% 显示警告 |
| `critical_threshold` | `0.95` | 95% 触发自动压缩 |
| `keep_recent_messages` | `10` | 保留最近 N 条消息 |
| `keep_recent_ratio` | `0.15` | 保留最近 15% context window |
| `min_messages_to_compress` | `15` | 最少 15 条才触发压缩 |
| `max_history_messages` | `100` | 紧急截断保留 100 条 |

**环境变量配置**:
```bash
# .env 文件
CONTEXT_CRITICAL_THRESHOLD=0.95  # 调整触发阈值
CONTEXT_KEEP_RECENT_MESSAGES=10  # 保留最近消息数
CONTEXT_MIN_MESSAGES_TO_COMPRESS=15  # 最小消息数
```

#### 1.5.3 实现细节

**关键文件**:
- `generalAgent/graph/nodes/summarization.py` - 压缩节点
- `generalAgent/context/manager.py` - 上下文管理器
- `generalAgent/context/compressor.py` - 压缩引擎
- `generalAgent/context/token_tracker.py` - Token 监控
- `generalAgent/config/settings.py` - 配置定义

**孤儿 ToolMessage 处理**:

压缩时会自动清理孤儿 ToolMessage（没有对应 tool_call 的 ToolMessage）：

```python
# compressor.py:290-327
def _clean_orphan_tool_messages(messages):
    # 收集有效的 tool_call_id
    valid_ids = {tc['id'] for msg in messages
                 if isinstance(msg, AIMessage) and msg.tool_calls
                 for tc in msg.tool_calls}

    # 过滤孤儿 ToolMessage
    return [msg for msg in messages
            if not isinstance(msg, ToolMessage)
            or msg.tool_call_id in valid_ids]
```

**降级策略**:
1. LLM 智能压缩（默认）
2. 失败 → 紧急截断（保留最近 100 条）

#### 1.5.4 用户体验

**静默压缩**: 压缩过程对用户完全透明，无通知消息

**示例日志**:
```
INFO - Token usage: 96.1% (123,000 / 128,000)
INFO - Routing to summarization node
INFO - Compressing 291 messages in single LLM call
INFO - Compression successful: 302 → 13 messages (5.1%)
INFO - Returning to agent with compressed context
```

**效果**:
- 压缩前: 302 条消息, 123K tokens
- 压缩后: 13 条消息, 6.5K tokens
- 压缩率: 95% token 减少

---

## 第二部分：工具系统

### 2.1 三层架构

**设计理念**: 工具分为三层组织：已发现（全部）、已注册（已启用）和可见（特定上下文）。

**层次定义**:

**第 1 层: discovered（发现池）**
- 所有扫描到的工具（包括禁用的）
- 存储在 `ToolRegistry._discovered: Dict[str, Any]`
- 支持按需加载

**第 2 层: registered（已启用工具）**
- 启用的工具（enabled: true）
- 存储在 `ToolRegistry._tools: Dict[str, Any]`
- 启动时自动注册

**第 3 层: visible（上下文可见工具）**
- 当前上下文中可用的工具
- 通过 `build_visible_tools()` 动态构建
- 包括: persistent_tools + allowed_tools + 动态加载的 @mention 工具

**实现**:

```python
# generalAgent/tools/registry.py
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Any] = {}           # 第 2 层
        self._meta: Dict[str, ToolMeta] = {}
        self._discovered: Dict[str, Any] = {}      # 第 1 层

    def register_discovered(self, tool: Any):
        """在发现池中注册工具（第 1 层）"""
        self._discovered[tool.name] = tool

    def register_tool(self, tool: Any):
        """注册工具为已启用（第 2 层）"""
        self._tools[tool.name] = tool

    def load_on_demand(self, tool_name: str) -> Optional[Any]:
        """当被 @mention 时从发现池加载工具"""
        if tool_name in self._discovered:
            tool = self._discovered[tool_name]
            self.register_tool(tool)
            return tool
        return None
```

**设计考量**:
- 第 1 层支持插件发现，无内存开销
- 第 2 层是启动时加载的核心工具集
- 第 3 层是运行时动态可见性（最重要）

---

### 2.2 工具发现与扫描

**设计**: 自动扫描指定目录发现所有工具。

**扫描目录**:
- `generalAgent/tools/builtin/`: 内置工具
- `generalAgent/tools/custom/`: 用户自定义工具
- 其他配置的目录（tools.yaml）

**扫描逻辑**:

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

**多工具文件支持**:

```python
# generalAgent/tools/scanner.py:52-86
def _extract_tools_from_module(file_path: Path) -> Dict[str, Any]:
    """通过 __all__ 或内省从模块中提取所有工具"""

    # 方法 1: 如果定义了 __all__，使用它
    if hasattr(module, "__all__"):
        tool_names = module.__all__
        for name in tool_names:
            obj = getattr(module, name)
            if isinstance(obj, BaseTool):
                tools[obj.name] = obj

    # 方法 2: 内省所有属性
    else:
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool) and not name.startswith("_"):
                tools[obj.name] = obj

    return tools
```

**设计考量**:
- 使用 `__all__` 进行显式导出（推荐）
- 回退到自动检测（便利性）
- 支持单文件多工具

---

### 2.3 工具配置

**设计**: 通过 tools.yaml 集中管理工具配置。

**配置文件结构**:

```yaml
# generalAgent/config/tools.yaml
core:
  now:
    category: "meta"
    tags: ["meta", "time"]
    description: "获取当前 UTC 时间"

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

**配置加载**:

```python
# generalAgent/tools/config_loader.py:105-126
class ToolConfig:
    def get_all_enabled_tools(self) -> Set[str]:
        """返回所有 enabled=true 的工具"""
        enabled = set()

        # 核心工具总是启用
        enabled.update(self.config.get("core", {}).keys())

        # 可选工具如果启用
        for name, cfg in self.config.get("optional", {}).items():
            if cfg.get("enabled", False):
                enabled.add(name)

        return enabled

    def is_available_to_subagent(self, tool_name: str) -> bool:
        """检查工具是否应该在所有上下文中可用"""
        meta = self._find_tool_config(tool_name)
        return meta.get("available_to_subagent", False)
```

**设计考量**:
- 配置驱动，无需修改代码
- `core` vs `optional` 区分系统工具和可选工具
- `available_to_subagent` 控制全局可见性

---

### 2.4 工具元数据

**设计**: 为每个工具提供丰富的元数据，支持分类、搜索和文档生成。

**元数据定义**:

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

**元数据注册**:

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

**使用场景**:
- 工具搜索和发现
- 自动生成工具文档
- 依赖管理
- 分类浏览

---

### 2.5 持久化工具

**设计**: 某些工具需要在所有上下文中始终可用。

**配置**:

```yaml
# tools.yaml
optional:
  todo_write:
    enabled: true
    available_to_subagent: true  # 在所有上下文中可见
```

**实现**:

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

**传递给节点**:

```python
# generalAgent/graph/nodes/planner.py:224-226
visible_tools = build_visible_tools(
    state=state,
    tool_registry=tool_registry,
    persistent_global_tools=persistent_global_tools,  # 总是包含
)
```

**典型持久化工具**:
- `todo_write` / `todo_read`: 任务跟踪
- `now`: 获取当前时间
- `delegate_task`: 子任务委托（按需加载）

---

### 2.6 工具可见性

**设计**: 根据当前状态动态构建工具可见性列表。

**实现**:

```python
# generalAgent/graph/nodes/planner.py:180-226
def build_visible_tools(
    *,
    state: AppState,
    tool_registry: ToolRegistry,
    persistent_global_tools: List,
) -> List:
    """构建当前上下文中 agent 可见的工具列表"""

    visible = []
    seen_names = set()

    # 步骤 1: 添加持久化全局工具
    for tool in persistent_global_tools:
        if tool.name not in seen_names:
            visible.append(tool)
            seen_names.add(tool.name)

    # 步骤 2: 添加技能特定工具（来自 active_skill）
    for tool_name in state.get("allowed_tools", []):
        if tool_name not in seen_names:
            tool = tool_registry.get_tool(tool_name)
            if tool:
                visible.append(tool)
                seen_names.add(tool_name)

    # 步骤 3: 添加 @mentioned 工具（按需加载）
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "tool" and mention not in seen_names:
            tool = tool_registry.load_on_demand(mention)
            if tool:
                visible.append(tool)
                seen_names.add(mention)

    return visible
```

**三步构建流程**:
1. **持久化工具**: 总是可用（例如 todo_write）
2. **技能工具**: 当前激活技能的工具（allowed_tools）
3. **@mentioned 工具**: 用户动态请求的工具（按需加载）

**设计考量**:
- 去重（seen_names 集合）
- 优先级顺序（persistent > allowed > mentioned）
- 动态加载（load_on_demand）

---

### 2.7 TODO 工具系统

**设计**: 使用 LangGraph Command 对象实现状态同步的专用任务跟踪工具系统。

**核心组件**:

**1. todo_write 工具** (`generalAgent/tools/builtin/todo_write.py`)

```python
@tool
def todo_write(
    todos: List[dict],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """跟踪多步骤任务（3+ 步骤）。帮助用户查看进度。

    任务状态: pending | in_progress | completed
    必需字段: content, status
    可选字段: id（自动生成）, priority（默认: medium）

    规则:
    - 开始工作前标记为 in_progress
    - 完成后立即标记为 completed（不要批量）
    - 一次只能有一个 in_progress
    - 如果测试失败、出错或不完整，不要标记为 completed
    """
    # 验证 todos
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

    # 检查只有一个 in_progress
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

    # 成功: 同时更新 todos 和 messages
    return Command(
        update={
            "todos": todos,  # ← 更新 state["todos"]
            "messages": [
                ToolMessage(
                    content=f"✅ TODO 列表已更新: {incomplete_count} 个待完成",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )
```

**2. todo_read 工具** (`generalAgent/tools/builtin/todo_read.py`)

```python
@tool
def todo_read(state: Annotated[dict, InjectedState]) -> dict:
    """读取当前待办事项列表以检查任务状态。

    主动并频繁使用此工具来了解：
    - 哪些任务仍处于待处理或进行中状态
    - 接下来应该处理什么
    - 是否所有任务都已完成

    Returns:
        包含 todos、summary（pending/in_progress/completed 计数）的字典
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

**3. TODO 提醒显示** (`generalAgent/graph/nodes/planner.py:190-230`)

```python
# 如果有待办事项，添加 todo 提醒
todos = state.get("todos", [])
if todos:
    in_progress = [t for t in todos if t.get("status") == "in_progress"]
    pending = [t for t in todos if t.get("status") == "pending"]
    completed = [t for t in todos if t.get("status") == "completed"]

    incomplete = in_progress + pending

    if incomplete:
        # 构建详细提醒
        todo_lines = []

        # 显示 in_progress 任务
        if in_progress:
            for task in in_progress:
                priority = task.get('priority', 'medium')
                priority_tag = f"[{priority}]" if priority != "medium" else ""
                todo_lines.append(f"  [进行中] {task.get('content')} {priority_tag}".strip())

        # 显示所有 pending 任务
        if pending:
            for task in pending:
                priority = task.get('priority', 'medium')
                priority_tag = f"[{priority}]" if priority != "medium" else ""
                todo_lines.append(f"  [待完成] {task.get('content')} {priority_tag}".strip())

        # 强提醒以防止提前停止
        todo_reminder = f"""<system_reminder>
⚠️ 任务追踪 ({len(incomplete)} 个未完成):
{chr(10).join(todo_lines)}
{completed_summary}

请继续完成所有待完成任务。使用 todo_write 更新任务状态。
</system_reminder>"""
```

**关键特性**:

**通过 Command 实现状态同步**:
- `todo_write` 返回 `Command(update={"todos": ..., "messages": ...})`
- LangGraph 自动将更新合并到状态中
- 状态和会话历史原子性更新

**验证规则**:
- 必需字段: `content`, `status`
- 有效状态: `pending`, `in_progress`, `completed`
- 一次只能有一个任务处于 `in_progress` 状态
- 如果缺少 `id` 则自动生成
- 默认 `priority` 为 `medium`

**与 ToolNode 集成**:
- 与标准 LangGraph ToolNode 无缝协作
- 不需要特殊处理
- Command 对象在返回给 agent 之前触发状态更新

**设计考量**:
- **Command 模式**: 工具逻辑和状态更新之间的清晰分离
- **验证优先**: 在状态修改之前捕获错误
- **原子更新**: 状态和消息一起更新
- **提醒系统**: 防止 agent 忘记未完成的任务
- **优先级支持**: 任务可以有高/中/低优先级

---

## 第三部分：技能系统

### 3.1 技能作为知识包

**核心概念**: 技能是知识包（文档 + 脚本），而非工具容器。

**关键原则**:
- 技能不包含 `allowed_tools` 字段
- Agent 读取 SKILL.md 并自主选择使用哪些工具
- 避免硬编码工具列表（更灵活）
- 脚本是可选的执行资源

**目录结构**:

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

**SKILL.md 示例**:

```markdown
# PDF 处理技能

## 概述
此技能提供 PDF 文件处理能力，包括表单填写、文本提取、页面操作等。

## 使用步骤
1. 使用 `read_file` 读取 PDF 文件
2. 根据任务选择合适的脚本
3. 使用 `run_skill_script` 执行脚本
4. 检查输出结果

## 可用脚本
- `fill_fillable_fields.py`: 填写可填充 PDF 表单
- `extract_text.py`: 提取 PDF 文本内容

## 示例
填写 PDF 表单:
\`\`\`python
run_skill_script(
    skill_id="pdf",
    script_name="fill_fillable_fields.py",
    args='{"input_pdf": "uploads/form.pdf", ...}'
)
\`\`\`
```

**设计考量**:
- **灵活性**: Agent 可以根据任务选择最合适的工具
- **可扩展性**: 添加新工具不需要修改技能定义
- **简单性**: 技能只包含元数据和文档
- **智能性**: 信任 LLM 的推理能力

---

### 3.2 技能注册表

**设计**: 自动扫描并注册技能包。

**实现**:

```python
# generalAgent/skills/registry.py:30-60
class SkillRegistry:
    def __init__(self, skills_root: Path):
        self._skills_root = skills_root
        self._skills: Dict[str, Skill] = {}
        self._scan_skills()

    def _scan_skills(self):
        """扫描技能目录并注册所有技能"""
        if not self._skills_root.exists():
            return

        for skill_dir in self._skills_root.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # 从 SKILL.md 解析技能元数据
            meta = self._parse_skill_metadata(skill_md)

            skill = Skill(
                id=skill_dir.name,
                name=meta.get("name", skill_dir.name),
                description=meta.get("description", ""),
                path=skill_dir,
            )

            self._skills[skill.id] = skill
```

**元数据解析**:

```python
def _parse_skill_metadata(self, skill_md: Path) -> dict:
    with open(skill_md, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 第一个 # 标题是名称
    # 第一个段落是描述
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

### 3.3 技能配置

**设计**: 通过 skills.yaml 配置控制技能行为。

**配置文件**: `generalAgent/config/skills.yaml`

```yaml
# 全局设置
global:
  enabled: true                    # 启用/禁用整个技能系统
  auto_load_on_file_upload: true  # 上传匹配文件时自动加载技能

# 核心技能 - 启动时总是加载
core: []  # 默认为空

# 可选技能 - 按需加载
optional:
  pdf:
    enabled: false                           # 显示在目录中并在启动时加载
    available_to_subagent: false                  # 在所有会话中保持加载状态
    description: "PDF 处理和表单填写"
    auto_load_on_file_types: ["pdf"]        # 上传 .pdf 文件时自动加载

  docx:
    enabled: true
    available_to_subagent: false
    description: "DOCX 文件处理"
    auto_load_on_file_types: ["docx"]

  xlsx:
    enabled: true
    available_to_subagent: false
    description: "Excel 文件处理"
    auto_load_on_file_types: ["xlsx", "xls"]
```

**配置选项**:

- **`enabled: true/false`**
  - `true`: 技能出现在 SystemMessage 目录中，启动时可用
  - `false`: 技能在目录中隐藏，只能通过 @mention 或文件上传加载
  - **使用场景**: 隐藏实验性或很少使用的技能以减少 prompt 噪音

- **`available_to_subagent`**: 在所有会话中保持技能加载状态（不推荐）
  - 默认: `false`（技能按会话加载）

- **`description`**: 目录中显示的人类可读描述

- **`auto_load_on_file_types`**: 触发自动加载的文件扩展名
  - 示例: `["pdf"]`, `["docx", "doc"]`, `["xlsx", "xls", "csv"]`
  - 使用实际文件扩展名（而不是通用类型如 "office"）

**工作原理**:

**1. 技能目录过滤** (`generalAgent/graph/prompts.py`)

```python
def build_skills_catalog(skill_registry, skill_config=None):
    all_skills = skill_registry.list_meta()

    if skill_config:
        enabled_skill_ids = set(skill_config.get_enabled_skills())
        skills = [s for s in all_skills if s.id in enabled_skill_ids]
    else:
        skills = all_skills  # 回退: 显示所有

    # 构建目录...
```

**优势**:
- 减少 SystemMessage 大小
- 防止禁用技能的信息泄露
- Agent 不会尝试使用它不知道的技能

**2. 动态文件上传提示** (`generalAgent/utils/file_processor.py`)

```python
def build_file_upload_reminder(processed_files, skill_config=None):
    for file in documents:
        # 提取文件扩展名（例如 "docx", "pdf"）
        file_ext = Path(filename).suffix.lstrip('.').lower()

        # 查找处理此扩展名的技能
        skills_for_type = skill_config.get_skills_for_file_type(file_ext)

        if skills_for_type:
            skill_mentions = ", ".join([f"@{s}" for s in skills_for_type])
            skill_hint = f" [可用 {skill_mentions} 处理]"
```

**示例输出**:
```
用户上传了 3 个文件：
1. report.pdf (PDF, 1.5 MB) → uploads/report.pdf [可用 @pdf 处理]
2. data.xlsx (OFFICE, 500 KB) → uploads/data.xlsx [可用 @xlsx 处理]
3. summary.docx (OFFICE, 300 KB) → uploads/summary.docx [可用 @docx 处理]
```

---

### 3.4 技能加载

**技能加载行为**:

1. **默认**: 除非明确请求，否则不加载技能
2. **@mention**: `@pdf` 将技能加载到工作空间
3. **文件上传**: 上传 `.pdf` 文件会自动加载 pdf 技能（如果 `auto_load_on_file_upload: true`）
4. **核心技能**: `core: []` 中的技能在启动时加载（当前默认为空）

**配置流水线**:

```
build_application()
  ↓ 加载 skills.yaml
  ↓ 返回 skill_config
  ↓
build_state_graph(skill_config)
  ↓ 传递给 planner
  ↓
build_planner_node(skill_config)
  ↓ 用于过滤和提示
  ↓
planner_node() 执行
  ├─ build_skills_catalog(skill_config)  → 过滤目录
  └─ build_file_upload_reminder(skill_config)  → 生成提示
```

---

### 3.5 技能依赖

**设计**: 技能脚本可能需要外部 Python 库，需要自动安装。

**requirements.txt 格式**:

```
# skills/pdf/requirements.txt
pypdf2>=3.0.0
reportlab>=4.0.0
pillow>=10.0.0
```

**自动安装流程**:

```python
# shared/workspace/manager.py:156-192
def _link_skill(self, skill_id: str, skill_path: Path):
    """将技能链接到工作空间并安装依赖"""

    target_dir = self.workspace_path / "skills" / skill_id
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # 创建符号链接
    if not target_dir.exists():
        target_dir.symlink_to(skill_path, target_is_directory=True)

    # 检查 requirements.txt
    requirements = skill_path / "requirements.txt"
    if requirements.exists():
        self._install_skill_dependencies(skill_id, requirements)

def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    """使用 pip 安装技能依赖"""

    # 检查缓存
    if self._skill_registry.is_dependencies_installed(skill_id):
        return

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True,
            timeout=120,
        )

        # 标记为已安装
        self._skill_registry.mark_dependencies_installed(skill_id)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"Failed to install dependencies for skill '{skill_id}': {error_msg}")
```

**错误处理**:

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

**何时**: 在以下情况下自动安装依赖:
- 用户首次在会话中 @mentions 技能
- 技能有 `requirements.txt` 文件

**工作原理**:
1. **自动检测**: WorkspaceManager 在链接技能时检查 `requirements.txt`
2. **一次性安装**: 依赖安装一次，在 SkillRegistry 中标记为已缓存
3. **优雅降级**: 如果安装失败，agent 收到友好的错误消息

---

### 3.6 技能目录

**设计**: 在系统提示中生成可用技能列表，让 Agent 知晓。

**实现**:

```python
# generalAgent/graph/prompts.py:143-174
def build_skills_catalog(skill_registry, skill_config=None) -> str:
    """为模型调用模式构建技能目录"""

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
        # 使用工作空间相对路径
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")
        lines.append("")

    return "\n".join(lines)
```

**注入到系统提示中**:

```python
# generalAgent/graph/nodes/planner.py:265-270
skills_catalog = build_skills_catalog(skill_registry, skill_config)
if skills_catalog:
    system_parts.append(skills_catalog)

system_prompt = "\n\n---\n\n".join(system_parts)
```

**输出示例**:

```
# 可用技能（Skills）

## PDF 处理 (#pdf)
提供 PDF 文件处理能力，包括表单填写、文本提取、页面操作等。
📁 路径: `skills/pdf/SKILL.md`
```

**设计考量**:
- 使用工作空间相对路径（不暴露项目路径）
- 提供清晰的使用说明
- 强调技能是文档，而非工具
- 包含路径信息（便于引用）

---

### 3.7 技能脚本执行

**设计**: 通过 `run_skill_script` 工具执行技能脚本。

**工具定义**:

```python
# generalAgent/tools/builtin/run_skill_script.py:15-35
@tool
def run_skill_script(skill_id: str, script_name: str, args: str) -> str:
    """从技能包执行 Python 脚本。

    Args:
        skill_id: 技能标识符（例如 "pdf"）
        script_name: 脚本文件名（例如 "fill_form.py"）
        args: 脚本参数的 JSON 字符串

    Returns:
        脚本输出或错误消息
    """
```

**执行流程**:

```python
# generalAgent/tools/builtin/run_skill_script.py:50-110
def _execute_script(script_path: Path, args: dict) -> str:
    """在隔离进程中执行脚本"""

    # 设置环境变量
    env = os.environ.copy()
    env["AGENT_WORKSPACE_PATH"] = str(workspace_path)

    # 准备脚本参数
    script_input = json.dumps(args)

    # 执行
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

**脚本接口规范**:

```python
# skills/pdf/scripts/example.py
import json
import sys
import os

def main():
    # 从环境变量读取工作空间路径
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")

    # 从 stdin 读取参数
    args = json.loads(sys.stdin.read())

    # 执行逻辑
    input_file = os.path.join(workspace, args["input_pdf"])
    output_file = os.path.join(workspace, args["output_pdf"])

    # ... 处理 ...

    # 将结果打印到 stdout
    print(json.dumps({"status": "success", "output": output_file}))

if __name__ == "__main__":
    main()
```

**设计考量**:
- 脚本在隔离进程中运行（隔离性）
- 通过 stdin/stdout 传递 JSON 数据（标准化）
- 通过环境变量传递工作空间路径（安全性）
- 超时保护（默认 30 秒）

---

## 第四部分：最佳实践与设计模式

### 4.1 路径处理

#### 4.1.1 工作空间相对路径 vs 绝对路径

**问题**: 如何在系统提示中隐藏项目绝对路径并使用工作空间相对路径？

**实现**: `generalAgent/graph/prompts.py:144-174`

```python
def build_skills_catalog(skill_registry) -> str:
    for skill in skills:
        lines.append(f"## {skill.name} (#{skill.id})")
        lines.append(f"{skill.description}")
        # 使用工作空间相对路径（技能被符号链接到 workspace/skills/）
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")  # 而不是绝对路径
        lines.append("")
```

**设计考量**:
- 避免暴露用户的项目路径（例如 `/Users/yushaw/dev/agentGraph/...`）
- 工作空间隔离: 所有路径相对于 `workspace/` 根目录
- 符号链接: 技能实际在项目目录中，但在工作空间中显示为符号链接

**对比**:
```python
# ❌ 错误: 暴露绝对路径
lines.append(f"📁 路径: `/Users/yushaw/dev/agentGraph/generalAgent/skills/pdf/SKILL.md`")

# ✅ 正确: 工作空间相对路径
lines.append(f"📁 路径: `skills/pdf/SKILL.md`")
```

---

#### 4.1.2 两步路径验证（防止路径遍历）

**问题**: 如何防止用户通过 `../../etc/passwd` 路径访问工作空间外的文件？

**实现**: `generalAgent/utils/file_processor.py:15-50`

```python
def resolve_workspace_path(
    file_path: str,
    workspace_root: Path,
    *,
    must_exist: bool = False,
    allow_write: bool = False,
) -> Path:
    # 步骤 1: 解析逻辑路径（处理 .., 符号链接）
    logical_path = (workspace_root / file_path).resolve()

    # 步骤 2: 检查解析后的路径是否在工作空间内
    try:
        logical_path.relative_to(workspace_root.resolve())
    except ValueError:
        raise ValueError(f"Path outside workspace: {file_path}")

    # 步骤 3: 存在性检查
    if must_exist and not logical_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # 步骤 4: 写权限检查
    if allow_write:
        allowed_dirs = ["outputs", "temp", "uploads"]
        rel_path = logical_path.relative_to(workspace_root)
        if rel_path.parts[0] not in allowed_dirs:
            raise PermissionError(f"Cannot write to {rel_path.parts[0]}/")

    return logical_path
```

**设计考量**:
- `.resolve()` 处理符号链接和 `..` 路径（规范化）
- `.relative_to()` 检查是否在工作空间内（安全检查）
- 分离读/写权限（只读目录 vs 可写目录）
- 清晰的错误消息（有助于调试）

**攻击示例**:
```python
# 攻击尝试
resolve_workspace_path("../../../etc/passwd", workspace_root)
# → 抛出 ValueError: Path outside workspace: ../../../etc/passwd

# 合法路径
resolve_workspace_path("skills/pdf/SKILL.md", workspace_root)
# → /data/workspace/session_123/skills/pdf/SKILL.md
```

---

#### 4.1.3 符号链接路径处理（不要解析）

**问题**: `list_workspace_files` 应该如何正确处理符号链接以避免路径跳出工作空间？

**实现**: `generalAgent/tools/builtin/file_ops.py:214-241`

```python
@tool
def list_workspace_files(directory: str = ".") -> str:
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 使用逻辑路径（不要解析符号链接）
    logical_path = workspace_root / directory

    # 检查是否在工作空间内（使用逻辑路径）
    try:
        logical_path.relative_to(workspace_root)
    except ValueError:
        return f"Error: Path outside workspace: {directory}"

    # 列出文件
    items = []
    for item in sorted(logical_path.iterdir()):
        rel_path = item.relative_to(workspace_root)  # 逻辑相对路径

        if item.is_symlink():
            items.append(f"[SKILL] {rel_path}/")  # 标记为技能
        elif item.is_dir():
            items.append(f"[DIR]  {rel_path}/")
        else:
            size = item.stat().st_size
            items.append(f"[FILE] {rel_path} ({size} bytes)")

    return "\n".join(items)
```

**设计考量**:
- **不要使用 `.resolve()`**: 避免符号链接路径跳出工作空间
- 使用逻辑路径进行列表和检查
- 明确标记符号链接（`[SKILL]`）
- 相对路径基于工作空间根目录

**对比**:
```python
# ❌ 错误: resolve() 导致路径跳出工作空间
logical_path = (workspace_root / directory).resolve()
# skills/pdf → /Users/yushaw/dev/agentGraph/generalAgent/skills/pdf
# relative_to(workspace_root) 将失败！

# ✅ 正确: 不解析，保持逻辑路径
logical_path = workspace_root / directory
# skills/pdf → /data/workspace/session_123/skills/pdf（符号链接）
```

---

#### 4.1.4 项目根目录自动发现

**问题**: 如何让程序从任何目录运行时都能找到项目根目录？

**实现**: `generalAgent/config/project_root.py:10-45`

```python
def find_project_root(marker_files=None) -> Path:
    """通过查找标记文件来找到项目根目录"""

    if marker_files is None:
        marker_files = ["pyproject.toml", ".git", "README.md"]

    current = Path.cwd().resolve()

    # 向上遍历直到找到标记或到达根目录
    while current != current.parent:
        for marker in marker_files:
            if (current / marker).exists():
                return current
        current = current.parent

    # 回退: 当前目录
    return Path.cwd()

# 缓存项目根目录
PROJECT_ROOT = find_project_root()

def resolve_project_path(relative_path: str) -> Path:
    """解析相对于项目根目录的路径"""
    return PROJECT_ROOT / relative_path
```

**使用**:
```python
# generalAgent/runtime/app.py:118
skills_root = skills_root or resolve_project_path("generalAgent/skills")

# generalAgent/config/settings.py:120
config_path = resolve_project_path("generalAgent/config/tools.yaml")
```

**设计考量**:
- 向上遍历查找标记文件（`pyproject.toml`, `.git`）
- 缓存结果（`PROJECT_ROOT`）避免重复查找
- 统一的路径解析接口（`resolve_project_path`）
- 支持从任何目录运行程序

---

### 4.2 Prompt 工程

#### 4.2.1 上下文感知的动态系统提醒

**问题**: 如何根据用户输入动态生成系统提示？

**实现**: `generalAgent/graph/prompts.py:177-229`

```python
def build_dynamic_reminder(
    *,
    active_skill: str = None,
    mentioned_tools: list = None,
    mentioned_skills: list = None,
    mentioned_agents: list = None,
    has_images: bool = False,
) -> str:
    """构建上下文感知的系统提醒"""

    reminders = []

    # 技能激活
    if active_skill:
        reminders.append(
            f"<system_reminder>当前激活的技能：{active_skill}。"
            f"优先使用该技能的工具完成任务。</system_reminder>"
        )

    # 工具提及
    if mentioned_tools:
        tools_str = "、".join(mentioned_tools)
        reminders.append(
            f"<system_reminder>用户提到了工具：{tools_str}。"
            f"请优先使用这些工具完成任务。</system_reminder>"
        )

    # 技能提及
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

**应用到系统提示中**:
```python
# generalAgent/graph/nodes/planner.py:265-280
def planner_node(state: AppState):
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # 添加技能目录
    skills_catalog = build_skills_catalog(skill_registry, skill_config)
    if skills_catalog:
        system_parts.append(skills_catalog)

    # 添加动态提醒
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

**设计考量**:
- 提示内容基于上下文（非静态）
- 使用 XML 标签（`<system_reminder>`）清晰标记
- 中文表达，自然友好
- 提供清晰的操作说明

---

#### 4.2.2 当前时间注入

**问题**: 如何让 Agent 知道当前时间？

**实现**: `generalAgent/graph/prompts.py:6-14` + `planner.py:265`

**时间标签生成**:
```python
# generalAgent/graph/prompts.py:6-14
def get_current_datetime_tag() -> str:
    """获取 XML 标签格式的当前日期和时间"""
    now = datetime.now(timezone.utc)
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"<current_datetime>{datetime_str}</current_datetime>"
```

**注入到系统提示中**:
```python
# generalAgent/graph/nodes/planner.py:265-275
def planner_node(state: AppState):
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # 添加当前时间
    datetime_tag = get_current_datetime_tag()
    system_parts.append(datetime_tag)

    # ... 其他部分 ...

    system_prompt = "\n\n---\n\n".join(system_parts)
```

**输出示例**:
```
你是 Charlie，一个高效、友好的 AI 助手。
...

---

<current_datetime>2025-01-24 15:30:45 UTC</current_datetime>

---

# 可用技能（Skills）
...
```

**设计考量**:
- 使用 UTC 时间（避免时区混淆）
- XML 标签格式（结构化）
- 动态生成（每次调用都是最新时间）
- 放在系统提示中（Agent 总是知道当前时间）

---

### 4.3 错误处理

#### 4.3.1 工具错误边界装饰器

**问题**: 如何统一处理工具执行期间的异常？

**实现**: `generalAgent/tools/decorators.py:10-40`

```python
from functools import wraps
import logging

LOGGER = logging.getLogger(__name__)

def with_error_boundary(func):
    """捕获并格式化工具错误的装饰器"""

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

**使用示例**:
```python
# generalAgent/tools/builtin/file_ops.py:45-65
@tool
@with_error_boundary
def read_file(file_path: str) -> str:
    """从工作空间读取文件"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 这可能会抛出 FileNotFoundError, PermissionError 等
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**错误返回示例**:
```
Error: File not found: uploads/missing.txt
Error: Permission denied: Cannot write to skills/
Error: Unexpected error: UnicodeDecodeError: 'utf-8' codec can't decode byte...
```

**设计考量**:
- 捕获常见异常（文件、权限、编码）
- 返回友好的错误消息（而不是堆栈跟踪）
- 记录详细信息（包括堆栈）
- Agent 可以根据错误消息调整策略

---

#### 4.3.2 循环限制与死锁检测

**问题**: 如何防止 Agent 陷入无限循环？

**实现**: `generalAgent/graph/routing.py:6-20`

```python
def agent_route(state: AppState) -> Literal["tools", "finalize"]:
    """将 agent 路由到 tools 或 finalize"""

    messages = state["messages"]
    last = messages[-1]

    # 检查循环限制（关键）
    if state["loops"] >= state["max_loops"]:
        LOGGER.warning(
            f"Loop limit reached ({state['max_loops']}), forcing finalize"
        )
        return "finalize"

    # LLM 想要调用工具
    if last.tool_calls:
        return "tools"

    # LLM 完成
    return "finalize"
```

**循环计数**:
```python
# generalAgent/graph/nodes/planner.py:340
def planner_node(state: AppState):
    # ... 调用模型 ...

    return {
        "messages": [result],
        "loops": state["loops"] + 1,  # 增加循环计数器
    }
```

**死锁检测（高级）**:
```python
def detect_repeated_tool_calls(state: AppState) -> bool:
    """检测 agent 是否重复调用相同工具"""

    messages = state["messages"][-10:]  # 最后 10 条消息

    tool_calls = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append((tc["name"], frozenset(tc["args"].items())))

    # 检查重复调用（相同工具 + 相同参数）
    if len(tool_calls) >= 3:
        if tool_calls[-1] == tool_calls[-2] == tool_calls[-3]:
            LOGGER.warning(f"Detected repeated tool call: {tool_calls[-1][0]}")
            return True

    return False
```

**设计考量**:
- 硬循环限制（`max_loops`）
- 记录警告消息
- 检测重复工具调用（死锁）
- 强制进入 finalize（避免无限循环）

---

### 4.4 日志与调试

#### 4.4.1 结构化日志

**问题**: 如何记录清晰、可搜索的日志？

**实现**: 所有模块

**日志配置**:
```python
# generalAgent/__init__.py:10-30
import logging

def setup_logging(level=logging.INFO):
    """设置结构化日志"""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("logs/app.log"),
            logging.StreamHandler(),  # 也打印到控制台
        ],
    )

# 启动时调用
setup_logging()
```

**使用示例**:
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

**日志输出**:
```
2025-01-24 15:30:45 [INFO] generalAgent.tools.registry:95 - Loading tool on-demand: http_fetch
2025-01-24 15:30:45 [INFO] generalAgent.tools.registry:99 - ✓ Tool loaded: http_fetch
```

**设计考量**:
- 包含时间戳、级别、模块、行号
- 输出到文件和控制台
- 使用 `__name__` 作为 logger 名称（自动分类）
- 友好的符号（✓ ✗ →）

---

#### 4.4.2 工具调用日志

**问题**: 如何记录每次工具调用的参数和结果？

**实现**: `generalAgent/graph/nodes/planner.py:320-340`

```python
def planner_node(state: AppState):
    # ... 调用模型 ...

    result = model.invoke(messages, tools=visible_tools)

    # 记录工具调用
    if result.tool_calls:
        for tool_call in result.tool_calls:
            LOGGER.info(
                f"Tool call: {tool_call['name']}({_format_args(tool_call['args'])})"
            )

    return {"messages": [result], "loops": state["loops"] + 1}

def _format_args(args: dict) -> str:
    """格式化工具参数以供日志记录"""
    # 截断长值
    formatted = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 100:
            formatted[k] = v[:100] + "..."
        else:
            formatted[k] = v

    return ", ".join(f"{k}={v!r}" for k, v in formatted.items())
```

**日志输出**:
```
2025-01-24 15:30:45 [INFO] generalAgent.graph.nodes.planner:325 - Tool call: read_file(file_path='uploads/data.txt')
2025-01-24 15:30:45 [INFO] generalAgent.graph.nodes.planner:325 - Tool call: write_file(file_path='outputs/result.txt', content='Analysis results...（truncated）...')
```

**设计考量**:
- 记录工具名称和参数
- 截断长参数（例如文件内容）
- 可用于审计和调试
- 不记录敏感信息（例如 API keys）

---

### 4.5 配置管理

#### 4.5.1 Pydantic Settings 加载 .env

**问题**: 如何优雅地管理环境变量配置？

**实现**: `generalAgent/config/settings.py:15-125`

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

    # 模型槽位
    model_basic: Optional[ModelConfig] = None
    model_reasoning: Optional[ModelConfig] = None

    # 治理
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)

    # 可观测性
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

# 全局设置实例
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """获取或创建设置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

**使用示例**:
```python
# generalAgent/runtime/app.py:110
settings = get_settings()
max_loops = settings.governance.max_loops
db_path = settings.observability.session_db_path
```

**设计考量**:
- Pydantic 提供类型验证（自动检查）
- `Field` 提供默认值和范围限制（`ge`, `le`）
- `env_file` 自动加载 `.env` 文件
- 单例模式（`get_settings()`）避免重复加载
- 分组配置（model/governance/observability）

---

## 总结

本架构文档整合了：

**第一部分：核心架构**
- Agent Loop 架构（而非 Plan-and-Execute）
- 通过 TypedDict 管理状态
- 三节点系统（agent/tools/finalize）
- 条件边路由

**第二部分：工具系统**
- 三层架构（discovered/registered/visible）
- 自动发现和扫描
- 配置驱动的元数据
- 持久化工具和动态可见性
- 基于 Command 的状态同步的 TODO 工具系统

**第三部分：技能系统**
- 技能作为知识包（而非工具容器）
- 配置驱动的目录过滤
- 动态文件上传提示
- 自动依赖安装
- 脚本执行接口

**第四部分：最佳实践**
- 路径处理（工作空间隔离、安全性）
- Prompt 工程（上下文感知、动态）
- 错误处理（边界、循环限制）
- 日志（结构化、工具调用）
- 配置管理（Pydantic、.env）

---

**相关文档**:
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - 测试策略
- [CONTEXT_MANAGEMENT.md](CONTEXT_MANAGEMENT.md) - KV 缓存优化
- [DOCUMENT_SEARCH_OPTIMIZATION.md](DOCUMENT_SEARCH_OPTIMIZATION.md) - 搜索系统
- [HITL_GUIDE.md](HITL_GUIDE.md) - Human-in-the-loop 模式

**配置文件**:
- `generalAgent/config/tools.yaml` - 工具配置
- `generalAgent/config/skills.yaml` - 技能配置
- `generalAgent/config/hitl_rules.yaml` - HITL 审批规则
- `.env` - 环境变量
