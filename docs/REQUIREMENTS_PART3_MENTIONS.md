# GeneralAgent 详细需求文档 - Part 3: @提及系统与消息管理

## 7. @提及系统需求

### 7.1 三类提及分类

**需求描述**：系统识别用户输入中的 @提及，并分类为三种类型：tool、skill、agent。

**分类逻辑**：
```python
# generalAgent/utils/mention_classifier.py:10-50
def classify_mention(
    mention: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
) -> Literal["tool", "skill", "agent"]:
    """Classify @mention into tool, skill, or agent"""

    # Strip @ prefix if present
    name = mention.lstrip("@")

    # Priority 1: Check if it's a registered or discovered tool
    if tool_registry.has_tool(name):
        return "tool"

    # Priority 2: Check if it's a registered skill
    if skill_registry.has_skill(name):
        return "skill"

    # Priority 3: Check for agent keywords
    agent_keywords = ["subagent", "agent", "助手", "代理"]
    if any(keyword in name.lower() for keyword in agent_keywords):
        return "agent"

    # Default: treat as tool (might be misspelled or new tool)
    return "tool"
```

**分类优先级**：
1. **Tool**: 已注册或已发现的工具
2. **Skill**: 已注册的技能
3. **Agent**: 包含 agent 关键词
4. **Default**: 降级为 tool（宽容处理）

### 7.2 提及解析

**需求描述**：从用户输入中提取所有 @提及。

**解析逻辑**：
```python
# generalAgent/cli.py:155-175
def parse_mentions(self, user_input: str) -> List[str]:
    """Extract @mentions from user input"""

    import re

    # Match @word or @word-with-dash
    pattern = r"@([\w\-]+)"
    matches = re.findall(pattern, user_input)

    return list(set(matches))  # Deduplicate
```

**应用场景**：
```python
# generalAgent/cli.py:240-260
async def handle_user_message(self, user_input: str):
    """Handle user message with @mention support"""

    # Parse @mentions
    mentions = self.parse_mentions(user_input)

    # Classify mentions
    mentioned_tools = []
    mentioned_skills = []
    mentioned_agents = []

    for mention in mentions:
        mention_type = classify_mention(
            mention,
            self.tool_registry,
            self.skill_registry,
        )

        if mention_type == "tool":
            mentioned_tools.append(mention)
        elif mention_type == "skill":
            mentioned_skills.append(mention)
        elif mention_type == "agent":
            mentioned_agents.append(mention)

    # ... update state with mentions
```

### 7.3 工具按需加载（Tool）

**需求描述**：当用户 @提及工具时，从 discovered 池中加载到 registered 池。

**加载逻辑**：
```python
# generalAgent/graph/nodes/planner.py:200-220
def build_visible_tools(...):
    """Build visible tools including @mentioned ones"""

    visible = []
    seen_names = set()

    # ... add persistent and allowed tools ...

    # Load @mentioned tools on-demand
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "tool" and mention not in seen_names:
            # Load from discovered pool
            tool = tool_registry.load_on_demand(mention)

            if tool:
                visible.append(tool)
                seen_names.add(mention)
            else:
                LOGGER.warning(f"Tool '{mention}' not found in registry")

    return visible
```

**ToolRegistry.load_on_demand**：
```python
# generalAgent/tools/registry.py:85-100
def load_on_demand(self, tool_name: str) -> Optional[Any]:
    """Load tool from discovered pool when @mentioned"""

    # Already registered, return directly
    if tool_name in self._tools:
        return self._tools[tool_name]

    # Load from discovered pool
    if tool_name in self._discovered:
        tool = self._discovered[tool_name]
        self.register_tool(tool)  # Move to registered pool
        LOGGER.info(f"✓ Loaded tool on-demand: {tool_name}")
        return tool

    LOGGER.warning(f"✗ Tool not found in discovered pool: {tool_name}")
    return None
```

### 7.4 技能加载（Skill）

**需求描述**：当用户 @提及技能时，加载技能到工作区并生成系统提醒。

**技能加载**：
```python
# generalAgent/cli.py:280-300
async def handle_user_message(self, user_input: str):
    """Handle user message"""

    # ... parse mentions ...

    # Load mentioned skills into workspace
    for skill_id in mentioned_skills:
        success = self.workspace_manager.load_skill(skill_id)
        if success:
            print(f"✓ Loaded skill: {skill_id}")
        else:
            print(f"✗ Skill not found: {skill_id}")

    # ... continue with message ...
```

**系统提醒生成**：
```python
# generalAgent/graph/prompts.py:214-217
if mentioned_skills:
    skills_str = "、".join(mentioned_skills)
    reminders.append(
        f"<system_reminder>用户提到了技能：{skills_str}。"
        f"请先使用 Read 工具读取对应的 SKILL.md 文件"
        f"（位于 skills/{'{skill_id}'}/SKILL.md），"
        f"然后根据文档指导执行操作。</system_reminder>"
    )
```

**注入到系统提示**：
```python
# generalAgent/graph/nodes/planner.py:270-275
dynamic_reminder = build_dynamic_reminder(
    mentioned_skills=mentioned_skills,
    ...
)

if dynamic_reminder:
    system_parts.append(dynamic_reminder)
```

### 7.5 代理委派（Agent）

**需求描述**：当用户 @提及 agent 时，加载 call_subagent 工具。

**加载逻辑**：
```python
# generalAgent/graph/nodes/planner.py:205-225
def build_visible_tools(...):
    """Build visible tools"""

    # ... add other tools ...

    # Load call_subagent when agent mentioned
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "agent":
            # Load call_subagent tool
            tool = tool_registry.get_tool("call_subagent")
            if tool and "call_subagent" not in seen_names:
                visible.append(tool)
                seen_names.add("call_subagent")

    return visible
```

**系统提醒生成**：
```python
# generalAgent/graph/prompts.py:218-221
if mentioned_agents:
    agents_str = "、".join(mentioned_agents)
    reminders.append(
        f"<system_reminder>用户提到了代理：{agents_str}。"
        f"你可以使用 call_subagent 工具将任务委派给子代理执行。</system_reminder>"
    )
```

### 7.6 动态系统提醒

**需求描述**：根据上下文动态生成系统提醒，注入到系统提示中。

**完整实现**：
```python
# generalAgent/graph/prompts.py:177-229
def build_dynamic_reminder(
    *,
    active_skill: str = None,
    mentioned_agents: list = None,
    mentioned_tools: list = None,
    mentioned_skills: list = None,
    has_images: bool = False,
    has_code: bool = False,
) -> str:
    """Build dynamic system reminder based on context"""

    reminders = []

    # Active skill reminder
    if active_skill:
        reminders.append(
            f"<system_reminder>当前激活的技能：{active_skill}。"
            f"优先使用该技能的工具完成任务。</system_reminder>"
        )

    # Mentioned tools
    if mentioned_tools:
        tools_str = "、".join(mentioned_tools)
        reminders.append(
            f"<system_reminder>用户提到了工具：{tools_str}。"
            f"请优先使用这些工具完成任务。</system_reminder>"
        )

    # Mentioned skills
    if mentioned_skills:
        skills_str = "、".join(mentioned_skills)
        reminders.append(
            f"<system_reminder>用户提到了技能：{skills_str}。"
            f"请先使用 Read 工具读取对应的 SKILL.md 文件"
            f"（位于 skills/{'{skill_id}'}/SKILL.md），"
            f"然后根据文档指导执行操作。</system_reminder>"
        )

    # Mentioned agents
    if mentioned_agents:
        agents_str = "、".join(mentioned_agents)
        reminders.append(
            f"<system_reminder>用户提到了代理：{agents_str}。"
            f"你可以使用 call_subagent 工具将任务委派给子代理执行。</system_reminder>"
        )

    # Images (optional, currently disabled)
    # if has_images:
    #     reminders.append("<system_reminder>用户分享了图片...</system_reminder>")

    return "\n\n".join(reminders) if reminders else ""
```

**应用到系统提示**：
```python
# generalAgent/graph/nodes/planner.py:265-280
def planner_node(state: AppState):
    """Agent node"""

    # Build system prompt parts
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

    # Combine
    system_prompt = "\n\n---\n\n".join(system_parts)
```

---

## 8. 消息历史管理需求

### 8.1 消息历史限制

**需求描述**：限制保留的消息历史数量，防止上下文过长。

**配置项**：
```bash
# .env
MAX_MESSAGE_HISTORY=40  # 默认 40，范围 10-100
```

**Settings 定义**：
```python
# generalAgent/config/settings.py:85-95
class GovernanceConfig(BaseModel):
    max_message_history: int = Field(
        default=40,
        ge=10,
        le=100,
        description="Maximum message history to keep"
    )
    max_loops: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum loop iterations"
    )
```

### 8.2 消息清理策略

**需求描述**：提供两种消息清理策略：Clean（清理中间步骤）和 Truncate（简单截断）。

**Clean 策略（推荐）**：
```python
# generalAgent/utils/message_utils.py:15-70
def clean_messages(
    messages: List[BaseMessage],
    max_history: int = 40,
) -> List[BaseMessage]:
    """Clean messages by removing intermediate tool calls"""

    if len(messages) <= max_history:
        return messages

    # Keep first message (system/user)
    first_msg = messages[0]

    # Process remaining messages
    recent = messages[1:]

    # Identify complete turns (user → assistant → [tools] → assistant)
    turns = []
    current_turn = []

    for msg in recent:
        current_turn.append(msg)

        # Turn ends with assistant message (no tool_calls)
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            turns.append(current_turn)
            current_turn = []

    # Keep last N turns
    max_turns = max_history // 4  # Estimate ~4 messages per turn
    kept_turns = turns[-max_turns:]

    # Flatten
    cleaned = [first_msg]
    for turn in kept_turns:
        cleaned.extend(turn)

    return cleaned
```

**Truncate 策略（简单）**：
```python
# generalAgent/utils/message_utils.py:75-85
def truncate_messages(
    messages: List[BaseMessage],
    max_history: int = 40,
) -> List[BaseMessage]:
    """Simple truncation: keep first + last N"""

    if len(messages) <= max_history:
        return messages

    return [messages[0]] + messages[-(max_history - 1):]
```

**应用到节点**：
```python
# generalAgent/graph/nodes/planner.py:290-305
def planner_node(state: AppState):
    """Agent node"""

    messages = state["messages"]

    # Clean messages if too long
    max_history = settings.governance.max_message_history
    if len(messages) > max_history:
        messages = clean_messages(messages, max_history)

    # ... invoke model with cleaned messages ...
```

**Clean vs Truncate 对比**：

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| Clean | 保持对话完整性，保留完整轮次 | 实现复杂，可能保留过多 | 多轮对话，复杂任务 |
| Truncate | 简单快速，可预测 | 可能截断工具调用链 | 简单对话，实验环境 |

### 8.3 消息角色定义

**需求描述**：LangChain 消息类型及其作用。

**消息类型**：
```python
from langchain_core.messages import (
    AIMessage,       # LLM 输出
    HumanMessage,    # 用户输入
    SystemMessage,   # 系统提示
    ToolMessage,     # 工具执行结果
)
```

**消息流示例**：
```python
# Turn 1: User asks question
messages = [
    HumanMessage(content="帮我读取 uploads/data.txt"),
]

# Turn 2: Agent calls tool
messages.append(
    AIMessage(
        content="",
        tool_calls=[
            {
                "name": "read_file",
                "args": {"file_path": "uploads/data.txt"},
                "id": "call_123",
            }
        ]
    )
)

# Turn 3: Tool returns result
messages.append(
    ToolMessage(
        content="File contents: ...",
        tool_call_id="call_123",
    )
)

# Turn 4: Agent responds to user
messages.append(
    AIMessage(content="文件内容是：...")
)
```

### 8.4 System Prompt 管理

**需求描述**：系统提示不存储在消息历史中，而是在每次调用时动态注入。

**实现方式**：
```python
# generalAgent/graph/nodes/planner.py:265-285
def planner_node(state: AppState):
    """Agent node"""

    # Build system prompt dynamically
    system_prompt = build_system_prompt(state)

    # Get message history (no system message)
    messages = state["messages"]

    # Invoke model with system prompt
    result = model.invoke(
        messages,
        system=system_prompt,  # Injected at runtime
    )
```

**好处**：
- 系统提示不占用消息历史配额
- 每次可以根据上下文更新系统提示
- 避免系统提示被清理

---

## 9. 子代理委派需求

### 9.1 子代理架构

**需求描述**：主 Agent 可以将独立子任务委派给子代理（Subagent）执行。

**核心概念**：
- 子代理有独立的上下文（context_id + parent_context）
- 子代理使用相同的图和工具
- 子代理不能访问父代理的消息历史
- 子代理执行完成后返回结果

**优势**：
- 避免主 Agent 上下文堆积
- 任务失败不污染主历史
- 支持并行执行多个子任务

### 9.2 call_subagent 工具

**需求描述**：通过工具调用创建和执行子代理。

**工具定义**：
```python
# generalAgent/tools/builtin/call_subagent.py:20-45
@tool
def call_subagent(
    task: str,
    max_loops: int = 15,
) -> str:
    """Delegate a subtask to a specialized subagent.

    Args:
        task: Clear description of the subtask to accomplish
        max_loops: Maximum execution loops (default 15)

    Returns:
        Subagent execution result

    Use cases:
    - Independent subtasks (file processing, debugging)
    - Multi-step operations that need multiple attempts
    - Tasks that shouldn't pollute main context
    """
```

**实现逻辑**：
```python
# generalAgent/tools/builtin/call_subagent.py:50-120
def _execute_subagent(task: str, max_loops: int) -> str:
    """Execute subagent in isolated context"""

    # Get app graph (set by runtime/app.py)
    app = get_app_graph()
    if not app:
        return "Error: Application graph not available"

    # Generate subagent context ID
    subagent_id = f"subagent_{uuid.uuid4().hex[:8]}"

    # Get parent state from environment
    parent_context = os.environ.get("AGENT_CONTEXT_ID", "main")
    workspace_path = os.environ.get("AGENT_WORKSPACE_PATH")

    # Build initial state for subagent
    initial_state = {
        "messages": [HumanMessage(content=task)],
        "images": [],
        "active_skill": None,
        "allowed_tools": [],
        "mentioned_agents": [],
        "persistent_tools": [],
        "model_pref": None,
        "todos": [],
        "context_id": subagent_id,      # Unique context
        "parent_context": parent_context,  # Link to parent
        "loops": 0,
        "max_loops": max_loops,
        "workspace_path": workspace_path,  # Share workspace
        "thread_id": f"sub_{subagent_id}",  # Unique thread
    }

    # Execute subagent graph
    try:
        result = app.invoke(initial_state)

        # Extract final response
        final_message = result["messages"][-1]
        return final_message.content

    except Exception as e:
        return f"Subagent execution failed: {str(e)}"
```

### 9.3 上下文隔离

**需求描述**：子代理和父代理的上下文完全隔离。

**隔离机制**：

1. **独立 context_id**：
```python
parent_context_id = "main"
subagent_context_id = "subagent_a1b2c3d4"
```

2. **独立消息历史**：
```python
# Parent messages
parent_messages = [
    HumanMessage("帮我分析这个项目"),
    AIMessage("我来分析..."),
    # ... 10+ messages ...
]

# Subagent messages (fresh start)
subagent_messages = [
    HumanMessage("读取 uploads/README.md 并总结")
]
```

3. **共享工作区**：
```python
# Both share same workspace
workspace_path = "/data/workspace/session_123/"
```

4. **独立 thread_id**：
```python
parent_thread_id = "session_123"
subagent_thread_id = "sub_a1b2c3d4"
```

**检测子代理上下文**：
```python
# generalAgent/graph/nodes/planner.py:50-60
def planner_node(state: AppState):
    """Agent node"""

    is_subagent = state.get("parent_context") is not None

    if is_subagent:
        # Modify system prompt for subagent
        system_prompt = SUBAGENT_SYSTEM_PROMPT
    else:
        system_prompt = PLANNER_SYSTEM_PROMPT
```

### 9.4 子代理系统提示

**需求描述**：子代理使用不同的系统提示，强调任务执行而非对话。

**Subagent Prompt**：
```python
# generalAgent/graph/prompts.py:95-120
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
- ✅ "查询结果：北京今天晴天，15-25°C"
- ✅ "代码分析：该函数在 src/auth.py:42 定义"
- ❌ "好的，我来帮您查询天气"（不要寒暄）
- ❌ "让我先理解一下您的需求"（不要拖延）

限制：
- 不要询问用户（无法对话）

技能系统（Skills）：
- 使用 read_file 工具读取该技能的 `skills/{{skill_id}}/SKILL.md` 文件获取详细指导
- 根据指导执行相关操作
- Skills 不是 tools，而是知识包（文档）
"""
```

**对比主 Agent Prompt**：

| 维度 | 主 Agent | 子 Agent |
|------|----------|----------|
| 风格 | 友好对话 | 任务执行 |
| 输出 | 解释 + 结果 | 仅结果 |
| 循环 | 长循环（100+） | 短循环（15） |
| 用户交互 | 可询问 | 不可询问 |

### 9.5 子代理使用场景

**需求描述**：明确何时使用子代理。

**推荐场景**：

1. **独立子目标**：
```python
# 主任务：分析项目
# 子任务：读取并总结 README.md
call_subagent(task="读取 uploads/README.md 并总结核心功能（不超过 3 句话）")
```

2. **多步骤操作**：
```python
# 子任务：调试脚本
call_subagent(
    task="运行 temp/script.py，如果出错则修复，直到成功运行",
    max_loops=20,
)
```

3. **避免上下文污染**：
```python
# 父 Agent 已经有 30 条消息
# 委派文件转换任务给子 Agent（失败也不影响父历史）
call_subagent(task="将 uploads/1.pdf 转换为图片，保存到 outputs/pdf_images/")
```

**不推荐场景**：
- 需要用户交互的任务（子代理无法询问用户）
- 需要访问父代理上下文的任务（上下文隔离）
- 简单的单步骤操作（直接调用工具更快）

---

## 10. 文件上传需求

### 10.1 文件类型检测

**需求描述**：根据文件扩展名自动检测文件类型。

**实现代码**：
```python
# generalAgent/utils/file_processor.py:55-85
def detect_file_type(file_path: Path) -> str:
    """Detect file type from extension"""

    ext = file_path.suffix.lower()

    type_map = {
        # Documents
        ".pdf": "pdf",
        ".docx": "document",
        ".doc": "document",
        ".txt": "text",
        ".md": "markdown",
        ".rtf": "document",

        # Spreadsheets
        ".xlsx": "spreadsheet",
        ".xls": "spreadsheet",
        ".csv": "csv",

        # Code
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".cpp": "cpp",

        # Data
        ".json": "json",
        ".yaml": "yaml",
        ".xml": "xml",

        # Images
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".gif": "image",
        ".bmp": "image",
        ".svg": "image",

        # Archives
        ".zip": "archive",
        ".tar": "archive",
        ".gz": "archive",
    }

    return type_map.get(ext, "unknown")
```

### 10.2 文件上传流程

**需求描述**：用户上传文件后，自动复制到 workspace/uploads/ 目录。

**CLI 处理**：
```python
# generalAgent/cli.py:180-215
def process_file_upload(self, file_path: str) -> dict:
    """Process user-uploaded file"""

    src_path = Path(file_path)

    # Validate existence
    if not src_path.exists():
        return {"success": False, "error": "File not found"}

    # Detect type
    file_type = detect_file_type(src_path)

    # Copy to uploads/
    dest_path = self.workspace_path / "uploads" / src_path.name
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_path, dest_path)

    # Generate workspace-relative path
    rel_path = f"uploads/{src_path.name}"

    return {
        "success": True,
        "path": rel_path,
        "type": file_type,
        "name": src_path.name,
        "size": dest_path.stat().st_size,
    }
```

### 10.3 文件引用注入

**需求描述**：在用户消息中自动添加上传文件的引用信息。

**消息增强**：
```python
# generalAgent/cli.py:230-255
async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """Handle user message with file uploads"""

    # Process each uploaded file
    file_refs = []
    for file_path in uploaded_files:
        result = self.process_file_upload(file_path)

        if result["success"]:
            file_refs.append(
                f"- {result['name']} → {result['path']} "
                f"({result['type']}, {result['size']} bytes)"
            )
        else:
            file_refs.append(f"- {file_path} → Error: {result['error']}")

    # Inject file references into message
    if file_refs:
        file_list = "\n".join(file_refs)
        enhanced_input = f"{user_input}\n\n上传的文件：\n{file_list}"
    else:
        enhanced_input = user_input

    # Create HumanMessage
    message = HumanMessage(content=enhanced_input)

    # ... continue with graph execution ...
```

**消息示例**：
```
User> 帮我分析这个 PDF

上传的文件：
- report.pdf → uploads/report.pdf (pdf, 245678 bytes)
```

### 10.4 自动技能推荐

**需求描述**：根据上传文件类型，自动推荐相关技能。

**推荐逻辑**：
```python
# generalAgent/cli.py:260-285
def recommend_skills_for_file(self, file_type: str) -> List[str]:
    """Recommend skills based on file type"""

    recommendations = {
        "pdf": ["pdf", "document"],
        "spreadsheet": ["excel", "data"],
        "image": ["image", "vision"],
        "code": ["code", "lint"],
        "document": ["document", "text"],
    }

    return recommendations.get(file_type, [])

async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """Handle message with auto skill recommendation"""

    # ... process uploads ...

    # Recommend skills
    for file_result in upload_results:
        if file_result["success"]:
            skills = self.recommend_skills_for_file(file_result["type"])

            if skills:
                print(f"💡 推荐技能: {', '.join(['@' + s for s in skills])}")

    # ... continue ...
```

**输出示例**：
```
✓ Uploaded: report.pdf → uploads/report.pdf
💡 推荐技能: @pdf, @document
```

### 10.5 多文件上传支持

**需求描述**：支持一次上传多个文件。

**CLI 接口**：
```python
# generalAgent/cli.py:120-150
async def run(self):
    """Main CLI loop"""

    while True:
        user_input = input("You> ")

        # Check for /upload command
        if user_input.startswith("/upload "):
            file_paths = user_input[8:].strip().split()

            # Process multiple files
            for file_path in file_paths:
                result = self.process_file_upload(file_path)
                if result["success"]:
                    print(f"✓ Uploaded: {result['name']}")
                else:
                    print(f"✗ Failed: {file_path}")

            continue

        # Normal message handling
        await self.handle_user_message(user_input)
```

**使用示例**：
```bash
You> /upload report.pdf data.xlsx notes.txt
✓ Uploaded: report.pdf
✓ Uploaded: data.xlsx
✓ Uploaded: notes.txt

You> 帮我分析这三个文件
```
