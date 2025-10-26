# Context Management in AgentGraph

本文档详细说明 AgentGraph 中的 Context（上下文）管理机制，包括消息历史、状态管理、内存优化和 Subagent 隔离等核心概念。

## 目录

1. [架构概览](#架构概览)
2. [AppState 详解](#appstate-详解)
3. [消息历史管理](#消息历史管理)
4. [Context 隔离机制](#context-隔离机制)
5. [Session 持久化](#session-持久化)
6. [内存优化策略](#内存优化策略)
7. [最佳实践](#最佳实践)

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
