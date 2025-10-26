# Context Management in AgentGraph

本文档详细说明 AgentGraph 中的 Context（上下文）管理机制，包括消息历史、状态管理、内存优化和 Subagent 隔离等核心概念。

## 目录

1. [架构概览](#架构概览)
2. [AppState 详解](#appstate-详解)
3. [消息历史管理](#消息历史管理)
4. [System Reminders - 动态提示词注入](#system-reminders---动态提示词注入)
5. [Context 隔离机制](#context-隔离机制)
6. [Session 持久化](#session-持久化)
7. [内存优化策略](#内存优化策略)
8. [最佳实践](#最佳实践)

---

## 架构概览

AgentGraph 采用 **多层次 Context 管理架构**：

```
┌─────────────────────────────────────────────────────────────┐
│             Application Level (Session & Workspace)          │
│  - Session persistence (SQLite checkpointer)                 │
│  - Workspace isolation (per-session directories)             │
│  - File upload tracking                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│          LangGraph State Level (AppState)                    │
│  - messages: Conversation history                            │
│  - todos: Task tracking                                      │
│  - allowed_tools: Dynamic tool access                        │
│  - active_skill: Current skill context                       │
│  - context_id/parent_context: Hierarchical context tracking │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│       Message History Management (Trimming & Cleaning)       │
│  - Configurable history window (MAX_MESSAGE_HISTORY)         │
│  - Safe truncation (preserve tool call chains)               │
│  - Unanswered tool_call cleanup                              │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         Subagent Context Isolation (Independent State)       │
│  - Separate context_id for each subagent                     │
│  - Independent message history                               │
│  - Isolated tool execution                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## AppState 详解

### 核心数据结构

`AppState` 是贯穿整个 LangGraph 执行的状态对象（定义于 `generalAgent/graph/state.py`）：

```python
class AppState(TypedDict, total=False):
    """Conversation state tracked across graph execution."""

    # ========== Messages and media ==========
    messages: Annotated[List[BaseMessage], add_messages]  # 对话历史
    images: List[Any]                                      # 图片附件

    # ========== Skills and tools ==========
    active_skill: Optional[str]      # 当前激活的 skill
    allowed_tools: List[str]         # 当前允许的工具列表
    persistent_tools: List[str]      # 会话级持久工具

    # ========== @Mention tracking ==========
    mentioned_agents: List[str]      # @提及的 agent/skill/tool

    # ========== Task tracking ==========
    todos: List[dict]                # 任务列表（TodoWrite 工具管理）

    # ========== Context isolation ==========
    context_id: str                  # "main" 或 "subagent-{uuid}"
    parent_context: Optional[str]    # 父 context ID（仅 subagent）

    # ========== Execution control ==========
    loops: int                       # 全局循环计数器
    max_loops: int                   # 循环上限（防止死循环）

    # ========== Model preference ==========
    model_pref: Optional[str]        # 用户偏好模型（vision/code/...）

    # ========== Session context ==========
    thread_id: Optional[str]         # Session ID（持久化标识）
    user_id: Optional[str]           # 用户 ID（未来个性化）
    workspace_path: Optional[str]    # 隔离的工作区路径
    uploaded_files: List[Any]        # 上传的文件列表
```

### 关键字段说明

#### 1. **messages** - 对话历史

- **类型**: `Annotated[List[BaseMessage], add_messages]`
- **作用**: 存储完整的对话历史（HumanMessage, AIMessage, ToolMessage, SystemMessage）
- **特殊处理**: 使用 LangGraph 的 `add_messages` 注解，支持增量追加而非覆盖
- **管理**: 通过 `message_utils.py` 的工具函数进行清理和裁剪

#### 2. **context_id** - Context 标识

- **类型**: `str`
- **值**:
  - 主 Agent: `"main"`
  - Subagent: `"subagent-{uuid8}"`（例如 `"subagent-a3f9b2c1"`）
- **作用**: 标识当前执行上下文，支持 Subagent 隔离

#### 3. **parent_context** - 父 Context 引用

- **类型**: `Optional[str]`
- **值**:
  - 主 Agent: `None`
  - Subagent: `"main"`（或父 Subagent 的 context_id）
- **作用**: 支持嵌套 Subagent（目前未使用，预留字段）

#### 4. **thread_id** - Session 标识

- **类型**: `Optional[str]`
- **作用**: LangGraph checkpointer 使用的 session ID
- **行为**:
  - 主 Agent: 用户提供的 session ID
  - Subagent: 使用 `context_id` 作为独立 thread_id（实现隔离）

---

## 消息历史管理

### 1. 配置化的历史窗口

**配置文件**: `generalAgent/config/settings.py`

```python
class GovernanceSettings(BaseSettings):
    max_message_history: int = Field(
        default=40,      # 默认保留 40 条消息
        ge=10,           # 最小 10 条
        le=100,          # 最大 100 条
        alias="MAX_MESSAGE_HISTORY"
    )
```

**环境变量配置** (`.env`):
```bash
MAX_MESSAGE_HISTORY=60  # 根据需求调整（10-100）
```

### 2. 智能裁剪机制

**实现文件**: `generalAgent/graph/message_utils.py`

#### 函数 1: `clean_message_history()`

**目的**: 移除未被响应的 tool_calls，避免 OpenAI API 验证错误

**问题场景**:
```python
# 错误场景：AIMessage 有 tool_calls 但没有对应的 ToolMessage
[
    AIMessage(content="", tool_calls=[{"id": "call_123", "name": "search"}]),
    HumanMessage(content="Actually, nevermind"),  # 用户中断了工具调用
    # 缺少 ToolMessage(tool_call_id="call_123")
]
# ❌ OpenAI API 会拒绝：tool_call_id "call_123" not found
```

**解决方案**:
```python
def clean_message_history(messages: List[BaseMessage]) -> List[BaseMessage]:
    # 第一遍：收集所有被响应的 tool_call_ids
    answered_call_ids = set()
    for msg in messages:
        if isinstance(msg, ToolMessage):
            answered_call_ids.add(msg.tool_call_id)

    # 第二遍：过滤掉有未响应 tool_calls 的 AIMessage
    cleaned = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                unanswered = [tc["id"] for tc in tool_calls
                             if tc["id"] not in answered_call_ids]
                if unanswered:
                    continue  # 跳过此 AIMessage
        cleaned.append(msg)

    return cleaned
```

#### 函数 2: `truncate_messages_safely()`

**目的**: 安全裁剪消息历史，保证 AIMessage-ToolMessage 配对完整性

**核心逻辑**:

1. **识别配对关系**:
   ```python
   # 建立 tool_call_id -> (ai_msg_index, tool_msg_index) 映射
   tool_call_pairs = {}
   for i, msg in enumerate(messages):
       if isinstance(msg, AIMessage):
           for tc in msg.tool_calls:
               tool_call_pairs[tc["id"]] = {"ai_idx": i, "tool_idx": None}
       elif isinstance(msg, ToolMessage):
           if msg.tool_call_id in tool_call_pairs:
               tool_call_pairs[msg.tool_call_id]["tool_idx"] = i
   ```

2. **确定保留范围**:
   ```python
   cutoff_idx = len(messages) - keep_recent  # 例如：50 条消息，保留最近 40 条
   must_keep_indices = set()

   # 保留最近的消息
   for i in range(cutoff_idx, len(messages)):
       must_keep_indices.add(i)

       # 如果是 ToolMessage，也保留对应的 AIMessage（即使在裁剪范围之外）
       if isinstance(messages[i], ToolMessage):
           ai_idx = tool_call_pairs[messages[i].tool_call_id]["ai_idx"]
           must_keep_indices.add(ai_idx)  # 可能 < cutoff_idx
   ```

3. **保留 SystemMessage**:
   ```python
   # SystemMessage 通常包含重要的系统提示，始终保留
   for i, msg in enumerate(messages):
       if isinstance(msg, SystemMessage):
           must_keep_indices.add(i)
   ```

**示例**:
```python
# 原始消息（50 条），keep_recent=10
[
    SystemMessage(...),                          # idx=0, 保留（SystemMessage）
    HumanMessage(...),                           # idx=1, 丢弃
    AIMessage(tool_calls=[call_1]),              # idx=2, 保留（因为 ToolMessage 在保留范围）
    ToolMessage(tool_call_id=call_1),            # idx=3, 丢弃
    ...,
    HumanMessage(...),                           # idx=40, 保留（最近 10 条范围）
    AIMessage(...),                              # idx=41, 保留
    ...,
    HumanMessage(...),                           # idx=49, 保留
]
# 结果：保留 idx=[0, 2, 40, 41, ..., 49]（顺序保持）
```

### 3. 应用位置

**Planner 节点** (`generalAgent/graph/nodes/planner.py:171-173`):
```python
max_message_history = settings.governance.max_message_history

# 执行清理和裁剪
cleaned_history = clean_message_history(history)
recent_history = truncate_messages_safely(cleaned_history, keep_recent=max_message_history)

# 发送给 LLM
prompt_messages = [SystemMessage(content=base_prompt), *recent_history]
result = model.invoke(prompt_messages)
```

**Finalize 节点** (`generalAgent/graph/nodes/finalize.py`):
```python
# 同样的清理流程
cleaned = clean_message_history(state["messages"])
recent = truncate_messages_safely(cleaned, keep_recent=max_message_history)
```

---

## System Reminders - 动态提示词注入

### 1. 什么是 System Reminders

**System Reminders** 是一种动态提示词注入机制，通过 `<system_reminder>` XML 标签向 LLM 提供上下文相关的实时提示。

**核心特点**:
- **动态生成**: 基于当前状态（todos、@mentions、文件上传等）自动生成
- **上下文相关**: 只在需要时出现，避免提示词膨胀
- **XML 标签格式**: 使用 `<system_reminder>` 标签包裹，便于 LLM 识别和解析
- **实时性**: 每次 planner 节点执行时重新生成，确保提示信息最新
- **KV Cache 优化**: Reminders 附加到最后一条消息，而非 SystemMessage，最大化 KV Cache 复用

**设计目的**:
- 引导 LLM 关注重要的上下文信息（如待办任务、用户上传的文件）
- 提示 LLM 使用特定的工具或技能（如 @pdf 技能）
- 防止 LLM 过早停止（如未完成所有 todos 就输出结果）
- 提供实时状态反馈（如"所有任务已完成"）

### 1.1 KV Cache 优化设计 ⭐ NEW

**问题**: 如果 Reminders 放在 SystemMessage 中，每轮内容都会变化，导致 KV Cache 失效。

**解决方案**:
1. ✅ **固定 SystemMessage**: 只包含基础指令 + skills catalog + 固定时间戳
2. ✅ **Reminders 移到末尾**: 附加到最后一条 HumanMessage，或追加轻量上下文消息
3. ✅ **时间戳精度降低**: 使用分钟级（`%Y-%m-%d %H:%M UTC`），初始化后固定不变
4. ✅ **时间戳位置**: 放在 SystemMessage 最底部（所有指令之后）

**效果对比**:

| 方案 | SystemMessage 变化频率 | KV Cache 复用率 | 成本节省 |
|------|------------------------|-----------------|----------|
| **优化前** | 每轮都变 (秒级时间 + reminders) | 0% | 0% |
| **优化后** | 固定不变 | 70-90% | 60-80% |

**实现** (`planner.py:79-89`):
```python
# 在 build_planner_node 初始化时生成一次
now = datetime.now(timezone.utc)
static_datetime_tag = f"<current_datetime>{now.strftime('%Y-%m-%d %H:%M UTC')}</current_datetime>"

# 固定的 SystemMessage (不再变化!)
static_main_prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{build_skills_catalog(skill_registry)}\n\n{static_datetime_tag}"
static_subagent_prompt = f"{SUBAGENT_SYSTEM_PROMPT}\n\n{static_datetime_tag}"
```

### 2. System Reminder 插入位置 ⭐ UPDATED

System Reminders 不再插入到 SystemMessage，而是**附加到最后一条消息**，以优化 KV Cache。

**新架构** (`planner.py:253-270`):
```python
# 1. 固定的 SystemMessage (不包含 reminders)
prompt_messages = [SystemMessage(content=static_main_prompt)]

# 2. 历史消息 (可复用 KV Cache)
message_history = list(recent_history)

# 3. Reminders 附加到最后一条消息
if combined_reminders:
    if message_history and isinstance(message_history[-1], HumanMessage):
        # 情况 A: 最后是 HumanMessage - 附加到它
        last_msg = message_history[-1]
        message_history[-1] = HumanMessage(
            content=f"{last_msg.content}\n\n{combined_reminders}"
        )
    else:
        # 情况 B: 最后不是 HumanMessage - 追加轻量上下文消息
        message_history.append(HumanMessage(content=combined_reminders))

prompt_messages.extend(message_history)
```

**为什么这样设计?**
- ✅ SystemMessage 固定 → KV Cache 可复用
- ✅ 历史消息大部分不变 → KV Cache 可复用
- ✅ 只有最后一条消息变化 → 重新计算量最小
- ✅ Reminders 仍然能被 LLM 看到并理解

### 3. System Reminder 内容类型

System Reminders 共有 **四个主要类型**：

#### 2.1 TODO 追踪提醒 (planner.py:175-206)

**触发条件**: 当 `state["todos"]` 非空且有未完成任务时

**代码实现**:
```python
# generalAgent/graph/nodes/planner.py:175-206
todos = state.get("todos", [])
todo_reminder = ""

if todos:
    in_progress = [t for t in todos if t.get("status") == "in_progress"]
    pending = [t for t in todos if t.get("status") == "pending"]
    completed = [t for t in todos if t.get("status") == "completed"]
    incomplete = in_progress + pending

    if incomplete:
        # 有未完成任务 - 生成提醒
        todo_lines = []
        if in_progress:
            todo_lines.append(f"当前: {in_progress[0].get('content')}")
        if pending:
            todo_lines.append(f"下一个: {pending[0].get('content')}")
            if len(pending) > 1:
                todo_lines.append(f"(还有 {len(pending) - 1} 个待办)")

        todo_reminder = f"""<system_reminder>
⚠️ 任务追踪: {' | '.join(todo_lines)}
使用 todo_read 查看所有任务。完成所有任务后再停止！
</system_reminder>"""

    elif completed:
        # 所有任务已完成
        todo_reminder = f"<system_reminder>✅ 所有 {len(completed)} 个任务已完成！可以输出最终结果。</system_reminder>"
```

**示例输出**:
```xml
<system_reminder>
⚠️ 任务追踪: 当前: 分析用户需求 | 下一个: 设计系统架构 | (还有 3 个待办)
使用 todo_read 查看所有任务。完成所有任务后再停止！
</system_reminder>
```

或

```xml
<system_reminder>✅ 所有 5 个任务已完成！可以输出最终结果。</system_reminder>
```

**重要性**:
- ⚠️ **防止过早停止**: 强烈提醒 LLM 完成所有任务后再停止
- 📊 **进度可见**: 让 LLM 清楚当前进度和剩余任务
- 🎯 **聚焦当前**: 只显示当前和下一个任务，避免提示词过长

#### 2.2 @Mention 提醒 (prompts.py:181-234)

**触发条件**: 当用户使用 `@tool`、`@skill` 或 `@agent` 语法时

**代码实现**:
```python
# generalAgent/graph/nodes/planner.py:162-169
dynamic_reminder = build_dynamic_reminder(
    active_skill=active_skill,
    mentioned_tools=grouped_mentions.get('tools', []),
    mentioned_skills=grouped_mentions.get('skills', []),
    mentioned_agents=grouped_mentions.get('agents', []),
    has_images=has_images,
    has_code=has_code,
)
```

```python
# generalAgent/graph/prompts.py:181-234
def build_dynamic_reminder(
    *,
    active_skill: str = None,
    mentioned_agents: list = None,
    mentioned_tools: list = None,
    mentioned_skills: list = None,
    has_images: bool = False,
    has_code: bool = False,
) -> str:
    reminders = []

    # 1. Active skill reminder
    if active_skill:
        reminders.append(f"<system_reminder>当前激活的技能：{active_skill}。优先使用该技能的工具完成任务。</system_reminder>")

    # 2. Tool mentions
    if mentioned_tools:
        tools_str = "、".join(mentioned_tools)
        reminders.append(f"<system_reminder>用户提到了工具：{tools_str}。请优先使用这些工具完成任务。</system_reminder>")

    # 3. Skill mentions
    if mentioned_skills:
        skills_str = "、".join(mentioned_skills)
        reminders.append(f"<system_reminder>用户提到了技能：{skills_str}。请先使用 Read 工具读取对应的 SKILL.md 文件（位于 skills/{'{skill_id}'}/SKILL.md），然后根据文档指导执行操作。</system_reminder>")

    # 4. Agent mentions (subagent delegation)
    if mentioned_agents:
        agents_str = "、".join(mentioned_agents)
        reminders.append(f"<system_reminder>用户提到了代理：{agents_str}。你可以使用 call_subagent 工具将任务委派给子代理执行。</system_reminder>")

    return "\n\n".join(reminders) if reminders else ""
```

**示例输出**:
```xml
<system_reminder>用户提到了工具：web_search、fetch_web。请优先使用这些工具完成任务。</system_reminder>

<system_reminder>用户提到了技能：pdf。请先使用 Read 工具读取对应的 SKILL.md 文件（位于 skills/pdf/SKILL.md），然后根据文档指导执行操作。</system_reminder>
```

**分类逻辑** (`generalAgent/utils/mention_classifier.py`):
```python
def classify_mentions(mentions: List[str], tool_registry, skill_registry):
    """Classify @mentions into tools, skills, or agents."""
    classifications = []
    for name in mentions:
        if tool_registry.exists(name):
            classifications.append({"name": name, "type": "tool"})
        elif skill_registry.exists(name):
            classifications.append({"name": name, "type": "skill"})
        else:
            # Assume it's an agent mention
            classifications.append({"name": name, "type": "agent"})
    return classifications
```

#### 2.3 文件上传提醒 (file_processor.py:231-299)

**触发条件**: 当用户上传文件（通过 `#filename` 语法）时

**代码实现**:
```python
# generalAgent/graph/nodes/planner.py:229-240
from generalAgent.utils.file_processor import build_file_upload_reminder

uploaded_files = state.get("uploaded_files", [])
file_upload_reminder = ""
if uploaded_files:
    file_upload_reminder = build_file_upload_reminder(uploaded_files)

# Add to reminders
reminders = [r for r in [dynamic_reminder, todo_reminder, file_upload_reminder] if r]
if reminders:
    base_prompt = f"{base_prompt}\n\n{chr(10).join(reminders)}"
```

```python
# generalAgent/utils/file_processor.py:231-299
def build_file_upload_reminder(processed_files: List[ProcessedFile | dict]) -> str:
    """Build system_reminder message for uploaded files."""
    if not processed_files:
        return ""

    # Separate by type
    images = [f for f in processed_files if get_attr(f, "file_type") == "image" and not get_attr(f, "error")]
    documents = [f for f in processed_files if get_attr(f, "file_type") in ("pdf", "office") and not get_attr(f, "error")]
    texts = [f for f in processed_files if get_attr(f, "file_type") in ("text", "code") and not get_attr(f, "error")]
    others = [f for f in processed_files if get_attr(f, "file_type") == "unknown" and not get_attr(f, "error")]

    lines = []

    # Count
    total = len(images) + len(documents) + len(texts) + len(others)
    lines.append(f"用户上传了 {total} 个文件：")

    # List files with processing hints
    file_num = 1
    for file in images:
        lines.append(f"{file_num}. {file.filename} (图片, {file.size_formatted}) → {file.workspace_path} [已加载到 vision]")
        file_num += 1

    for file in documents:
        skill_hint = " [可用 @pdf 处理]" if file.file_type == "pdf" else ""
        lines.append(f"{file_num}. {file.filename} ({file.file_type.upper()}, {file.size_formatted}) → {file.workspace_path}{skill_hint}")
        file_num += 1

    for file in texts:
        lines.append(f"{file_num}. {file.filename} (文本, {file.size_formatted}) → {file.workspace_path} [可用 read_file 读取]")
        file_num += 1

    # Additional hints
    if images:
        lines.append("")
        lines.append("图片内容已通过 vision 能力加载，你可以直接分析图片内容。")
    if documents or texts:
        lines.append("其他文件可使用相应工具处理。")

    return "<system_reminder>\n" + "\n".join(lines) + "\n</system_reminder>"
```

**示例输出**:
```xml
<system_reminder>
用户上传了 3 个文件：
1. screenshot.png (图片, 2.3 MB) → uploads/screenshot.png [已加载到 vision]
2. contract.pdf (PDF, 1.8 MB) → uploads/contract.pdf [可用 @pdf 处理]
3. data.txt (文本, 45 KB) → uploads/data.txt [可用 read_file 读取]

图片内容已通过 vision 能力加载，你可以直接分析图片内容。
其他文件可使用相应工具处理。
</system_reminder>
```

**文件类型分类** (`file_processor.py:64-95`):
```python
def classify_file_type(filename: str) -> FileType:
    ext = Path(filename).suffix.lower()

    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in {".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log"}:
        return "text"
    if ext in {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".sh"}:
        return "code"
    if ext in {".docx", ".xlsx", ".pptx"}:
        return "office"
    return "unknown"
```

#### 2.4 Skills Catalog (prompts.py:147-178)

**触发条件**: 主 Agent 启动时（非 subagent）

**代码实现**:
```python
# generalAgent/graph/nodes/planner.py:223-227
if not is_subagent:
    # Add skills catalog (model-invoked pattern)
    skills_catalog = build_skills_catalog(skill_registry)
    if skills_catalog:
        base_prompt = f"{base_prompt}\n\n{skills_catalog}"
```

```python
# generalAgent/graph/prompts.py:147-178
def build_skills_catalog(skill_registry) -> str:
    """Build skills catalog for model-invoked pattern.

    Returns a formatted list of available skills with descriptions and paths.
    This allows the model to autonomously decide when to use skills.
    """
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
        lines.append(f"📁 路径: `skills/{skill.id}/SKILL.md`")
        lines.append("")

    return "\n".join(lines)
```

**示例输出**:
```markdown
# 可用技能（Skills）
以下是可用的专业技能。当你需要使用某个技能时：
1. 使用 read_file 工具读取该技能的 SKILL.md 文件获取详细指导
2. 根据指导执行相关操作
3. Skills 不是 tools，而是知识包（文档）

## PDF 处理 (#pdf)
处理 PDF 文件的专业技能，包括表单填写、内容提取、转换为图片等功能
📁 路径: `skills/pdf/SKILL.md`

## 演示文稿生成 (#pptx)
使用 Python-PPTX 生成专业演示文稿的技能
📁 路径: `skills/pptx/SKILL.md`
```

**重要性**:
- 🔍 **技能发现**: 让 LLM 知道有哪些可用技能
- 📖 **自主调用**: LLM 可以根据任务需求自主选择使用技能
- 🎓 **知识包模式**: 明确 Skills 是文档，不是工具

### 3. System Reminder 的组装流程

**完整流程** (`generalAgent/graph/nodes/planner.py:158-243`):

```python
# 1. 构建基础系统提示词
datetime_tag = get_current_datetime_tag()
base_prompt = f"{datetime_tag}\n\n{PLANNER_SYSTEM_PROMPT}"

# 2. 添加 Skills Catalog (仅主 Agent)
if not is_subagent:
    skills_catalog = build_skills_catalog(skill_registry)
    if skills_catalog:
        base_prompt = f"{base_prompt}\n\n{skills_catalog}"

# 3. 构建动态提醒
dynamic_reminder = build_dynamic_reminder(
    active_skill=active_skill,
    mentioned_tools=grouped_mentions.get('tools', []),
    mentioned_skills=grouped_mentions.get('skills', []),
    mentioned_agents=grouped_mentions.get('agents', []),
    has_images=has_images,
    has_code=has_code,
)

# 4. 构建 TODO 提醒
todo_reminder = ""
if todos:
    # ... (如前文所示)
    todo_reminder = "<system_reminder>⚠️ 任务追踪: ...</system_reminder>"

# 5. 构建文件上传提醒
file_upload_reminder = ""
if uploaded_files:
    file_upload_reminder = build_file_upload_reminder(uploaded_files)

# 6. 组合所有提醒
reminders = [r for r in [dynamic_reminder, todo_reminder, file_upload_reminder] if r]
if reminders:
    base_prompt = f"{base_prompt}\n\n{chr(10).join(reminders)}"

# 7. 构建最终消息
prompt_messages = [SystemMessage(content=base_prompt), *recent_history]

# 8. 发送给 LLM
output = await invoke_planner(model_registry, model_resolver, tools, prompt_messages, ...)
```

**组装顺序**:
1. 基础系统提示词（PLANNER_SYSTEM_PROMPT 或 SUBAGENT_SYSTEM_PROMPT）
2. Skills Catalog（仅主 Agent）
3. Dynamic Reminder（@mentions）
4. TODO Reminder
5. File Upload Reminder

### 4. System Reminder 与 Context 管理的关系

**层次关系**:
```
┌──────────────────────────────────────────────┐
│  Application Level (main.py)                 │
│  - 解析 @mentions、#files                     │
│  - 更新 state["mentioned_agents"]            │
│  - 更新 state["uploaded_files"]              │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│  Planner Node (planner.py)                   │
│  - 读取 state 中的上下文信息                   │
│  - 生成 System Reminders                      │
│  - 注入到 SystemMessage                       │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│  LLM (Model Invocation)                      │
│  - 接收带有 System Reminders 的提示词         │
│  - 决策工具调用或输出结果                      │
└──────────────────────────────────────────────┘
```

**与其他 Context 管理机制的协同**:

1. **与 Message History 管理**:
   - System Reminders 注入到 SystemMessage（索引 0）
   - Message History 从索引 1 开始
   - 两者独立但互补：Reminders 提供实时提示，History 提供对话上下文

2. **与 AppState**:
   - System Reminders 基于 AppState 动态生成
   - 读取: `state["todos"]`, `state["mentioned_agents"]`, `state["uploaded_files"]`
   - 写入: 无（只读取，不修改）

3. **与 Subagent 隔离**:
   - Subagent 不接收 Skills Catalog（避免提示词过长）
   - Subagent 不接收 TODO/File Reminders（专注于当前任务）
   - Subagent 只接收任务描述（task）作为初始 HumanMessage

### 5. 实际应用示例

#### 示例 1: TODO 追踪场景

**用户输入**:
```
帮我分析这个项目的代码结构，然后写一个详细的设计文档
```

**LLM 行为**:
1. 使用 `todo_write` 创建任务列表：
   ```python
   [
       {"content": "分析项目代码结构", "status": "pending"},
       {"content": "编写设计文档", "status": "pending"}
   ]
   ```

2. **第 1 轮**: Planner 注入提醒
   ```xml
   <system_reminder>
   ⚠️ 任务追踪: 当前: 分析项目代码结构 | 下一个: 编写设计文档
   使用 todo_read 查看所有任务。完成所有任务后再停止！
   </system_reminder>
   ```

3. LLM 完成代码分析，标记第 1 个任务为 `completed`

4. **第 2 轮**: Planner 更新提醒
   ```xml
   <system_reminder>
   ⚠️ 任务追踪: 当前: 编写设计文档
   使用 todo_read 查看所有任务。完成所有任务后再停止！
   </system_reminder>
   ```

5. LLM 编写设计文档，标记第 2 个任务为 `completed`

6. **第 3 轮**: Planner 提示完成
   ```xml
   <system_reminder>✅ 所有 2 个任务已完成！可以输出最终结果。</system_reminder>
   ```

7. LLM 输出最终总结

#### 示例 2: @Mention + 文件上传场景 ⭐ UPDATED

**用户输入**:
```
@pdf 帮我填写这个表单 #contract.pdf
```

**处理流程**:

1. **main.py** 解析:
   ```python
   mentions = ["pdf"]  # 解析 @pdf
   uploaded_files = [
       ProcessedFile(filename="contract.pdf", file_type="pdf", workspace_path="uploads/contract.pdf", ...)
   ]

   state.update({
       "mentioned_agents": ["pdf"],
       "uploaded_files": uploaded_files
   })
   ```

2. **planner.py** 分类:
   ```python
   classifications = classify_mentions(["pdf"], tool_registry, skill_registry)
   # 结果: [{"name": "pdf", "type": "skill"}]

   grouped_mentions = {"skills": ["pdf"], "tools": [], "agents": []}
   ```

3. **planner.py** 生成提醒并附加到最后消息:
   ```python
   # 构建 reminders
   reminders = [
       "<system_reminder>用户提到了技能：pdf。请先使用 read_file 工具读取...</system_reminder>",
       "<system_reminder>用户上传了 1 个文件：\n1. contract.pdf...</system_reminder>"
   ]
   combined_reminders = "\n\n".join(reminders)

   # 附加到最后的 HumanMessage
   message_history[-1] = HumanMessage(content=f"""
   帮我填写这个表单

   <system_reminder>用户提到了技能：pdf。请先使用 read_file 工具读取对应的 SKILL.md 文件...</system_reminder>

   <system_reminder>
   用户上传了 1 个文件：
   1. contract.pdf (PDF, 1.8 MB) → uploads/contract.pdf [可用 @pdf 处理]
   </system_reminder>
   """)

   # 最终发送给 LLM:
   prompt_messages = [
       SystemMessage(content=static_main_prompt),  # ✅ 固定,可复用
       HumanMessage(content="...with reminders...")  # ✅ 只有这条新内容
   ]
   ```

4. **LLM 决策**:
   - 看到 `@pdf` 提醒 → 使用 `read_file("skills/pdf/SKILL.md")`
   - 看到文件上传提醒 → 知道文件位置是 `uploads/contract.pdf`
   - 根据 SKILL.md 指导 → 使用 `run_bash_command` 执行 PDF 填写脚本

#### 示例 3: Subagent 无提醒场景

**主 Agent 调用 Subagent**:
```python
call_subagent(task="分析 uploads/data.csv 中的销售数据")
```

**Subagent 收到的提示词**:
```python
base_prompt = f"{datetime_tag}\n\n{SUBAGENT_SYSTEM_PROMPT}"
# 没有 Skills Catalog
# 没有 TODO Reminder
# 没有 File Upload Reminder
# 只有基础任务指导

prompt_messages = [
    SystemMessage(content=base_prompt),
    HumanMessage(content="分析 uploads/data.csv 中的销售数据")
]
```

**设计理由**:
- Subagent 应专注于单一任务
- 避免 Subagent 提示词过长
- Subagent 不需要 TODO 追踪（任务已明确）
- Subagent 不需要文件上传提醒（文件路径已在任务描述中）

### 6. 其他 Prompt 注入机制

除了 System Reminders,还有以下 prompt 注入点:

#### 6.1 Finalize Node 的时间戳注入 (finalize.py:56-57)

**触发条件**: 每次执行 finalize 节点时（agent loop 结束后）

**代码实现**:
```python
# generalAgent/graph/nodes/finalize.py:56-57
datetime_tag = get_current_datetime_tag()
finalize_prompt = f"{datetime_tag}\n\n{FINALIZE_SYSTEM_PROMPT}"
```

**作用**:
- 为 finalize 阶段提供准确的当前时间
- 让 LLM 在生成最终回复时有时间意识
- 示例: `<current_datetime>2025-01-24 15:30:45 UTC</current_datetime>`

**特点**:
- 与 planner 节点的时间戳注入类似
- 每次 finalize 都会重新生成（保证时间准确性）
- 不包含其他 System Reminders（finalize 是最终总结，不需要提醒）

#### 6.2 文本文件内容直接注入 (cli.py:204-211)

**触发条件**: 用户上传小文本文件（<10KB）时

**代码实现**:
```python
# generalAgent/cli.py:204-211
text_injections = []
for file in processed_files:
    if file.file_type in ("text", "code") and file.text_content:
        text_injections.append(f"\n\n[File: {file.filename}]\n{file.text_content}")

if text_injections:
    message_content[0]["text"] += "".join(text_injections)
```

**示例**:
```
用户输入: 分析这个配置文件 #config.json

实际发送给 LLM 的 HumanMessage:
分析这个配置文件

[File: config.json]
{
  "app_name": "MyApp",
  "version": "1.0.0",
  "database": {
    "host": "localhost",
    "port": 5432
  }
}
```

**特点**:
- **直接注入**: 不通过 System Reminder,而是直接附加到 HumanMessage 内容
- **大小限制**: 只对小文件（<10KB）生效,大文件需要 LLM 主动使用 `read_file` 工具
- **格式化**: 使用 `[File: filename]` 标记清晰标识文件内容
- **性能优化**: 避免小文件也需要工具调用,减少延迟

#### 6.3 图片 Base64 注入 (cli.py:194-202)

**触发条件**: 用户上传图片文件时

**代码实现**:
```python
# generalAgent/cli.py:194-202
for file in processed_files:
    if file.file_type == "image" and file.base64_data:
        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{file.mime_type};base64,{file.base64_data}"
            }
        })

# 构建多模态消息
messages.append(HumanMessage(content=message_content))
```

**示例消息结构**:
```python
HumanMessage(content=[
    {"type": "text", "text": "分析这张图片"},
    {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
        }
    }
])
```

**特点**:
- **多模态消息**: 使用 LangChain 的多模态消息格式
- **Base64 编码**: 图片直接编码为 Base64 附加到消息中
- **自动触发 Vision 模型**: planner 节点检测到图片后自动选择 vision 模型
- **大小限制**: 图片不超过 10MB

### 7. 动态工具和技能加载机制

#### 7.1 工具动态加载 (On-Demand Tool Loading)

**架构设计** - 三层工具系统:

```
┌─────────────────────────────────────────────────┐
│  Tier 1: Core Tools (always available)          │
│  - now, todo_write, todo_read, read_file, ...   │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Tier 2: Enabled Tools (loaded at startup)      │
│  - enabled: true in tools.yaml                   │
│  - fetch_web, web_search, write_file, ...       │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Tier 3: Discovered Tools (load on @mention)    │
│  - enabled: false in tools.yaml                  │
│  - run_bash_command, http_fetch, ...            │
└──────────────────────────────────────────────────┘
```

**实现机制** (`generalAgent/tools/registry.py:83-107`):

```python
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}          # Tier 1 + Tier 2
        self._discovered: Dict[str, BaseTool] = {}     # Tier 1 + Tier 2 + Tier 3

    def load_on_demand(self, tool_name: str) -> BaseTool:
        """Load a tool on-demand from discovered tools.

        This is used when a user @mentions a tool that wasn't enabled at startup.
        """
        if tool_name in self._tools:
            return self._tools[tool_name]  # Already loaded

        if tool_name not in self._discovered:
            raise KeyError(f"Tool not found: {tool_name}")

        # Move from discovered to active
        tool = self._discovered[tool_name]
        self.register_tool(tool)
        return tool
```

**触发流程** (`generalAgent/graph/nodes/planner.py:98-108`):

```python
# 1. 用户输入: "@run_bash_command 执行脚本"
# 2. main.py 解析: mentioned_agents = ["run_bash_command"]
# 3. planner.py 分类: grouped_mentions = {"tools": ["run_bash_command"]}

# 4. planner.py 加载工具:
for tool_name in grouped_mentions['tools']:
    try:
        tool = tool_registry.get_tool(tool_name)  # 尝试从已注册工具获取
        visible_tools.append(tool)
    except KeyError:
        try:
            tool = tool_registry.load_on_demand(tool_name)  # On-demand loading!
            visible_tools.append(tool)
        except KeyError:
            LOGGER.error(f"@{tool_name} load failed")
```

**配置示例** (`generalAgent/config/tools.yaml`):

```yaml
optional:
  run_bash_command:
    enabled: false  # Not loaded at startup
    always_available: false
    category: "execute"
    tags: ["execute", "system"]
    description: "Execute bash commands and Python scripts"

  fetch_web:
    enabled: true  # Loaded at startup
    always_available: false
    category: "network"
    tags: ["network", "read"]
```

**优势**:
- 🚀 **启动快**: 只加载必要工具,减少初始化时间
- 💾 **内存优化**: 未使用的工具不占用内存
- 🔒 **安全性**: 危险工具（如 run_bash_command）默认不加载,需要明确 @mention
- 🎯 **按需加载**: 用户需要时才加载,避免工具列表过长

#### 7.2 技能动态加载 (Skill Linking & Dependency Installation)

**架构设计** - Skills 是文档包,不是工具:

```
┌─────────────────────────────────────────────────┐
│  Project Skills (source)                        │
│  generalAgent/skills/pdf/                      │
│  ├── SKILL.md                                   │
│  ├── requirements.txt                           │
│  └── scripts/                                   │
└────────────────┬────────────────────────────────┘
                 │ symlink when @mentioned
┌────────────────▼────────────────────────────────┐
│  Session Workspace (isolated)                   │
│  data/workspace/{session_id}/skills/pdf/       │
│  ├── SKILL.md → (symlink)                      │
│  ├── requirements.txt → (symlink)              │
│  └── scripts/ → (symlink)                      │
└──────────────────────────────────────────────────┘
```

**触发流程**:

1. **用户 @mention** (`cli.py:127-148`):
   ```python
   # 用户输入: "@pdf 处理这个文件"
   skill_mentions, _ = parse_mentions(user_input)  # ["pdf"]

   # 更新 session workspace
   session_manager.update_workspace_skills(skill_mentions)
   ```

2. **Workspace Manager 加载技能** (`shared/workspace/manager.py`):
   ```python
   def update_workspace_skills(self, skills_to_load: List[str]):
       """Link skills into workspace and install dependencies."""
       for skill_id in skills_to_load:
           # 1. Create symlink
           self._link_skill_to_workspace(skill_id)

           # 2. Check and install dependencies
           success, message = self.skill_registry.ensure_dependencies(skill_id)
           if not success:
               self.logger.warning(f"Skill dependency install failed: {message}")
   ```

3. **依赖安装** (`generalAgent/skills/registry.py:52-104`):
   ```python
   def ensure_dependencies(self, skill_id: str) -> tuple[bool, str]:
       """Check and install skill dependencies if needed."""
       skill = self.get(skill_id)

       # Check if already installed
       if skill.dependencies_installed:
           return True, "Dependencies already installed"

       # Check for requirements.txt
       requirements_file = skill.path / "requirements.txt"
       if not requirements_file.exists():
           skill.dependencies_installed = True
           return True, "No dependencies required"

       # Install dependencies
       result = subprocess.run(
           [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)],
           capture_output=True,
           text=True,
           timeout=120
       )

       if result.returncode != 0:
           return False, f"Failed to install: {result.stderr}"

       skill.dependencies_installed = True
       return True, "Dependencies installed successfully"
   ```

4. **生成 System Reminder** (`prompts.py:218-220`):
   ```python
   if mentioned_skills:
       skills_str = "、".join(mentioned_skills)
       reminders.append(f"<system_reminder>用户提到了技能：{skills_str}。请先使用 Read 工具读取对应的 SKILL.md 文件...</system_reminder>")
   ```

**自动加载机制** (`cli.py:169-183`):

除了 @mention,还支持基于文件类型的自动加载:

```python
# 配置: generalAgent/config/skill_config.yaml
file_type_to_skills:
  pdf: ["pdf"]      # 上传 PDF → 自动加载 @pdf
  pptx: ["pptx"]    # 上传 PPTX → 自动加载 @pptx

# 实现:
if self.skill_config.auto_load_on_file_upload():
    skills_for_type = self.skill_config.get_skills_for_file_type(result.file_type)
    for skill_id in skills_for_type:
        if skill_id not in auto_load_skills:
            auto_load_skills.append(skill_id)

# 加载技能
if auto_load_skills:
    self.session_manager.update_workspace_skills(auto_load_skills)
    print(f"[已自动加载技能: {', '.join(auto_load_skills)}]")
```

**依赖缓存机制**:

- **首次加载**: 安装依赖（可能需要数秒到数分钟）
- **后续使用**: 标记 `dependencies_installed = True`,跳过安装
- **跨会话缓存**: 依赖安装到全局 Python 环境,所有会话共享

**优势**:
- 📦 **隔离性**: 每个 session 有独立的 workspace
- 🔄 **按需加载**: 只 symlink 用户提到的技能
- 📚 **知识包模式**: Skills 是文档,LLM 通过 read_file 获取指导
- 🔧 **自动依赖管理**: 首次使用自动安装依赖
- 🚀 **零配置**: 用户无需手动安装依赖

#### 7.3 动态工具可见性控制

**Planner 节点的工具组装逻辑** (`planner.py:83-127`):

```python
# 1. 初始化: 只有 persistent_global_tools (core tools)
visible_tools: List[BaseTool] = list(persistent_global_tools)

# 2. 添加 @mentioned tools
for tool_name in grouped_mentions['tools']:
    tool = tool_registry.load_on_demand(tool_name)
    visible_tools.append(tool)

# 3. 添加 call_subagent (如果 @mentioned agents)
if grouped_mentions['agents']:
    subagent_tool = tool_registry.get_tool("call_subagent")
    if subagent_tool not in visible_tools:
        visible_tools.append(subagent_tool)

# 4. 去重
deduped: List[BaseTool] = []
seen = set()
for tool in visible_tools:
    if tool.name not in seen:
        seen.add(tool.name)
        deduped.append(tool)
visible_tools = deduped

# 5. Subagent 过滤 (防止嵌套)
if is_subagent:
    visible_tools = [t for t in visible_tools if t.name != "call_subagent"]
```

**可见性原则**:
- ✅ **Core tools**: 始终可见（now, todo_write, read_file, write_file, ...）
- ✅ **Enabled tools**: 启动时加载,始终可见（fetch_web, web_search, ...）
- ⚠️ **@mentioned tools**: 用户提到才加载,临时可见
- ⚠️ **call_subagent**: 用户提到 @agent 时才可见
- ❌ **Subagent 限制**: Subagent 不能看到 call_subagent（防止嵌套）

### 8. 最佳实践

**DO ✅**:
- 使用 System Reminders 提供实时、上下文相关的提示
- 在主 Agent 中使用 TODO Reminder 防止过早停止
- 在文件上传时提供清晰的文件类型和处理建议
- 使用 @mention 语法让 LLM 明确用户意图
- 危险工具（run_bash_command）设为 `enabled: false`,需要 @mention
- 小文本文件（<10KB）直接注入到 HumanMessage,减少工具调用延迟

**DON'T ❌**:
- 不要在 Subagent 中注入过多提醒（保持简洁）
- 不要在 System Reminders 中包含动态数据（如完整文件内容）
- 不要过度依赖 System Reminders（LLM 应有自主决策能力）
- 不要在每轮都注入相同的提醒（动态生成,按需插入）
- 不要将所有工具设为 `enabled: true`（影响启动速度和安全性）
- 不要在 Tier 1 (core tools) 放太多工具（只放必需工具）

**调试技巧**:
```python
# 查看生成的提示词（planner.py:243）
log_prompt(LOGGER, "planner", base_prompt, max_length=500)

# 查看分类结果（planner.py:92-96）
classifications = classify_mentions(mentioned, tool_registry, skill_registry)
grouped_mentions = group_by_type(classifications)
LOGGER.info(f"Grouped mentions: {grouped_mentions}")

# 查看可见工具列表（planner.py:244）
log_visible_tools(LOGGER, "planner", visible_tools)

# 查看技能依赖安装状态
skill = skill_registry.get(skill_id)
LOGGER.info(f"Skill '{skill_id}' dependencies_installed: {skill.dependencies_installed}")
```

---

## Context 隔离机制

### 1. Subagent Context 独立性

**设计目标**: 让 Subagent 拥有独立的上下文，避免污染主 Agent 的消息历史

**实现** (`generalAgent/tools/builtin/call_subagent.py:61-82`):

```python
async def call_subagent(task: str, max_loops: int = 10) -> str:
    # 1. 生成唯一 context_id
    context_id = f"subagent-{uuid.uuid4().hex[:8]}"  # 例如 "subagent-a3f9b2c1"

    # 2. 创建全新的独立 State
    subagent_state = {
        "messages": [HumanMessage(content=task)],  # 全新的消息历史！
        "images": [],
        "active_skill": None,
        "allowed_tools": [],        # Subagent 从零开始获取工具权限
        "mentioned_agents": [],
        "persistent_tools": [],
        "todos": [],
        "context_id": context_id,   # 独立标识
        "parent_context": "main",   # 记录父 context（预留）
        "loops": 0,                 # 独立的循环计数器
        "max_loops": max_loops,
        "thread_id": context_id,    # 使用 context_id 作为 thread_id（隔离）
    }

    # 3. 使用独立的 LangGraph config
    config = {"configurable": {"thread_id": context_id}}

    # 4. 执行 Subagent（完全独立的 State 实例）
    final_state = await app.ainvoke(subagent_state, config)

    # 5. 提取结果返回给主 Agent
    result = {
        "ok": True,
        "result": final_state["messages"][-1].content,
        "context_id": context_id,
        "loops": final_state["loops"]
    }

    return json.dumps(result, ensure_ascii=False)
```

### 2. Context 隔离的好处

#### 场景示例：PDF 转图片任务

**不使用 Subagent**（主 Agent 直接处理）:
```
主 Agent 消息历史（17+ 条）:
1. HumanMessage: "把 PDF 转成图片"
2. AIMessage: tool_call=read_file("skills/pdf/SKILL.md")
3. ToolMessage: [3000 字的 SKILL.md 内容]  ⬅️ 污染主上下文
4. AIMessage: tool_call=read_file("skills/pdf/scripts/convert_to_images.py")
5. ToolMessage: [500 行 Python 代码]         ⬅️ 污染主上下文
6. AIMessage: tool_call=run_bash_command("python skills/pdf/...")
7. ToolMessage: [命令输出...]
8. AIMessage: "转换完成！"
...（后续对话受到 PDF 技能细节的干扰）
```

**使用 Subagent**（推荐）:
```
主 Agent 消息历史（3 条）:
1. HumanMessage: "把 PDF 转成图片"
2. AIMessage: tool_call=call_subagent("读取 PDF skill 并执行转换")
3. ToolMessage: {"ok": true, "result": "转换完成，输出在 outputs/"}

Subagent 消息历史（在独立 context_id="subagent-a3f9b2c1" 中）:
1. HumanMessage: "读取 PDF skill 并执行转换"
2. AIMessage: tool_call=read_file(...)
3. ToolMessage: [3000 字 SKILL.md]  ⬅️ 不污染主 context
4. ...
17. AIMessage: "转换完成！"
```

**对比**:
- 主 Agent 消息数: 17+ → 3（减少 82%）
- 主 Agent 关注点: 保持高层协调，不被技能细节干扰
- Subagent: 独立处理细节，完成后返回简洁结果

### 3. Context 层级关系

```
main (context_id="main", parent_context=None)
├── messages: [主对话历史]
├── thread_id: "user-session-123"
│
├── subagent-a3f9b2c1 (独立 State)
│   ├── context_id: "subagent-a3f9b2c1"
│   ├── parent_context: "main"
│   ├── thread_id: "subagent-a3f9b2c1"  ⬅️ 独立 thread，隔离持久化
│   └── messages: [独立的消息历史]
│
└── subagent-f8d4e2a0 (另一个独立 State)
    ├── context_id: "subagent-f8d4e2a0"
    ├── parent_context: "main"
    └── messages: [独立的消息历史]
```

---

## Session 持久化

### 1. SQLite Checkpointer

**位置**: `generalAgent/persistence/session_store.py`

**作用**: 使用 LangGraph 的 `SqliteSaver` 实现 State 持久化

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver(conn=sqlite_connection)

# 在应用构建时注入
app = graph.build_state_graph(..., checkpointer=checkpointer)

# 使用 thread_id 作为 session 标识
config = {"configurable": {"thread_id": "user-session-123"}}

# 自动持久化每个节点的 State
result = await app.ainvoke(state, config)
```

### 2. 恢复 Session

**CLI 实现** (`generalAgent/cli.py`):

```python
# 加载历史 session
def load_session(session_id: str):
    config = {"configurable": {"thread_id": session_id}}

    # LangGraph 自动从 checkpointer 恢复 State
    snapshot = app.get_state(config)

    if snapshot:
        # 恢复的 State 包含完整的消息历史、todos、workspace_path 等
        print(f"已加载 Session: {session_id}")
        print(f"消息数: {len(snapshot.values['messages'])}")
        print(f"Workspace: {snapshot.values['workspace_path']}")
    else:
        print("Session 不存在")
```

### 3. 持久化的内容

**完整的 AppState** 被持久化到 SQLite:

```sql
-- sessions.db 表结构（简化）
CREATE TABLE checkpoints (
    thread_id TEXT,         -- Session 标识
    checkpoint_id TEXT,     -- Checkpoint 版本
    parent_checkpoint_id TEXT,
    checkpoint BLOB,        -- 序列化的 State（包含 messages, todos, 等）
    metadata BLOB,
    PRIMARY KEY (thread_id, checkpoint_id)
);
```

**存储内容**:
- ✅ `messages`: 完整对话历史
- ✅ `todos`: 任务列表
- ✅ `workspace_path`: 工作区路径
- ✅ `active_skill`: 当前 skill
- ✅ `allowed_tools`: 工具权限
- ✅ 所有其他 AppState 字段

**不存储内容**:
- ❌ 工作区文件（在文件系统，由 WorkspaceManager 管理）
- ❌ Model 实例（运行时重建）

---

## 内存优化策略

### 1. 消息历史裁剪

**触发时机**: 每次 Planner 或 Finalize 节点执行

**裁剪策略**:
- 保留最近 `MAX_MESSAGE_HISTORY` 条消息（默认 40）
- 保留所有 SystemMessage（系统提示）
- 保留 AIMessage-ToolMessage 配对（即使超出范围）

**Token 节省估算**:
```
假设平均每条消息 200 tokens：
- 不裁剪（50 条）: 50 × 200 = 10,000 tokens
- 裁剪到 40 条: 40 × 200 = 8,000 tokens
- 节省: 20% tokens
```

### 2. Subagent 隔离

**内存收益**:
- 主 Agent 不保留 Subagent 的详细执行过程
- Subagent 完成后，仅返回简洁结果（JSON 字符串）
- 典型场景：17 条消息 → 3 条消息（节省 82%）

### 3. 工具结果内容清理

**实现** (`generalAgent/graph/message_utils.py` 可扩展):

```python
def clean_tool_message_content(content: str, max_length: int = 1000) -> str:
    """截断过长的工具返回内容"""
    if len(content) > max_length:
        return content[:max_length] + f"\n... (truncated, {len(content)} chars total)"
    return content
```

**应用场景**:
- 读取长文档（SKILL.md）后截断显示
- 工具返回大量数据时压缩

### 4. Image 内容管理

**策略** (`AppState.images`):
- 图片以 base64 存储在 `images` 字段
- 发送给 vision model 后可清理（避免重复发送）
- 考虑使用外部存储（S3/本地文件）并传递 URL

---

## 最佳实践

### 1. 合理设置 MAX_MESSAGE_HISTORY

**推荐配置**:
```bash
# 简单对话场景（快速响应）
MAX_MESSAGE_HISTORY=20

# 一般场景（平衡性能和上下文）
MAX_MESSAGE_HISTORY=40  # 默认

# 复杂长对话（需要更多上下文）
MAX_MESSAGE_HISTORY=60

# 极限场景（研究/调试）
MAX_MESSAGE_HISTORY=100  # 最大值
```

**权衡**:
- ⬆️ 更大的历史窗口 → 更好的上下文理解，但更慢、更贵
- ⬇️ 更小的历史窗口 → 更快、更便宜，但可能丢失上下文

### 2. 优先使用 Subagent

**适用场景**:
- ✅ 需要读取长文档（SKILL.md, reference docs）
- ✅ 多步骤任务（搜索 → 分析 → 总结）
- ✅ 独立子任务（不影响主对话流程）
- ✅ 调试和实验（失败不污染主 context）

**不适用场景**:
- ❌ 简单单步任务（now, todo_write）
- ❌ 需要主 Agent 上下文的任务
- ❌ 对响应速度要求极高的场景（Subagent 有启动开销）

### 3. 定期清理 Session

**建议**:
```bash
# 清理 7 天以上的 workspace（自动）
python main.py  # 启动时自动清理

# 手动清理
/clean  # CLI 命令
```

**原因**:
- 避免 SQLite 数据库无限增长
- 清理废弃的 workspace 文件

### 4. 监控消息历史长度

**实现** (`generalAgent/cli.py`):
```python
# 显示当前消息数
/current

# 输出示例：
# Session: user-session-123
# Messages: 42 / 40 (max)  ⬅️ 接近上限，可能触发裁剪
# Workspace: /path/to/workspace
```

### 5. 避免重复发送大内容

**反模式**:
```python
# ❌ 每次都重复发送长文档
for i in range(5):
    state["messages"].append(HumanMessage(content=long_document))  # 浪费！
```

**最佳实践**:
```python
# ✅ 发送一次，后续引用
state["messages"].append(HumanMessage(content=long_document))
# ... 后续对话直接引用，不重复发送
state["messages"].append(HumanMessage(content="基于之前的文档，分析..."))
```

---

## 高级特性（未来）

### 1. 消息摘要（Summarization）

**设计**:
- 当消息历史超过阈值（如 100 条）时，自动摘要前 50 条
- 保留摘要 + 最近 50 条详细消息
- 使用 reasoning model 生成摘要

### 2. 语义检索（Semantic Search）

**设计**:
- 将历史消息向量化存储（Embeddings + Vector DB）
- 根据当前对话，检索相关历史片段
- 动态构建上下文（而非固定窗口）

### 3. 层次化 Context

**设计**:
- Session Level: 跨对话的长期记忆（用户偏好、常用技能）
- Conversation Level: 当前对话的完整历史
- Task Level: 当前任务的临时上下文（Subagent）

---

## 相关文件

- `generalAgent/graph/state.py` - AppState 定义
- `generalAgent/graph/message_utils.py` - 消息清理和裁剪工具
- `generalAgent/graph/nodes/planner.py` - 消息历史应用（主 Agent）
- `generalAgent/graph/nodes/finalize.py` - 消息历史应用（Finalize）
- `generalAgent/tools/builtin/call_subagent.py` - Subagent Context 隔离
- `generalAgent/persistence/session_store.py` - Session 持久化
- `generalAgent/config/settings.py` - MAX_MESSAGE_HISTORY 配置

---

## 总结

AgentGraph 的 Context 管理通过以下机制实现高效、可靠的对话管理：

1. **AppState** 作为统一的状态容器
2. **消息历史裁剪** 避免无限增长（配置化窗口）
3. **智能清理** 保证 OpenAI API 兼容性（tool_call 配对）
4. **Subagent 隔离** 避免主 Agent 上下文污染
5. **Session 持久化** 支持跨会话恢复
6. **多层优化** 平衡性能和上下文完整性

这套机制确保了在复杂、长时间对话中，Agent 既能保持必要的上下文，又不会因消息爆炸而失控。
