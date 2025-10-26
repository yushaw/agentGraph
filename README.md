# GeneralAgent - Flexible Agent System

An opinionated LangGraph-based architecture for building various types of agents. This repository provides the **general-purpose agent loop** implementation. Future additions will include workflow-based agents and other specialized agent types.

**Current Implementation**: General-purpose agent with dynamic tool calling, skill loading, and multi-model routing.

## Features

- **Model registry & routing** – register five core model classes (base, reasoning, vision, code, chat) and pick the right model per phase (`plan`, `decompose`, `delegate`, etc.).
- **Skill packages** – discoverable `skills/<id>/SKILL.yaml` descriptors with progressive disclosure and tool allowlists.
- **Governed tool runtime** – declarative metadata (`ToolMeta`) for risk tagging, global read-only utilities, and skill-scoped business tools.
- **MCP Integration** ⭐ NEW – Model Context Protocol support with lazy server startup, manual tool control, and stdio/SSE modes. [Quick Start](docs/MCP_QUICKSTART.md) | [Full Guide](docs/MCP_INTEGRATION.md)
- **LangGraph flow** – `plan → guard → tools → post → (decompose|delegate) → guard → tools → after → …` with deliverable verification and budgets.
- **Delegation loop** – decomposition into structured plans, delegated subagents with scoped tools, and per-step verification.
- **Observability hooks** – optional LangSmith tracing + Postgres checkpointer.

## Directory Layout

```
generalAgent/
├── agents/           # Agent factories and model resolver protocol
├── config/           # Pydantic settings objects (.env-aware)
├── graph/            # State, prompts, plan schema, routing, node factories
├── models/           # Model registry & routing heuristics
├── persistence/      # Optional checkpointer integration
├── runtime/          # High-level app assembly (`build_application`)
├── skills/           # Skill registry + loader (expects skills/<id>/SKILL.yaml)
├── telemetry/        # LangSmith / tracing configuration
└── tools/            # Base tools, business stubs, registry, skill tools
```

`main.py` shows a CLI stub that wires the app with a placeholder model resolver; replace it with real LangChain-compatible models before invoking the flow.

## Configuration

All runtime configuration is sourced from `.env` via `generalAgent.config.settings.Settings`. Key variables:

```
MODEL_BASE, MODEL_REASON, MODEL_VISION, MODEL_CODE, MODEL_CHAT
MODEL_BASE_API_KEY, MODEL_REASON_API_KEY, MODEL_VISION_API_KEY, MODEL_CODE_API_KEY, MODEL_CHAT_API_KEY
MODEL_BASE_URL, MODEL_REASON_URL, MODEL_VISION_URL, MODEL_CODE_URL, MODEL_CHAT_URL
AUTO_APPROVE_WRITES         # default governance policy
PG_DSN                      # optional Postgres checkpointing
LANGCHAIN_TRACING_V2        # enable tracing when truthy
LANGCHAIN_PROJECT / LANGCHAIN_API_KEY
```

`.env` is loaded automatically via `python-dotenv`, and `resolve_model_configs()` also inspects provider-specific aliases such as `MODEL_BASIC_*`, `MODEL_REASONING_*`, and `MODEL_MULTIMODAL_*`, so you can drop in DeepSeek / Moonshot / GLM credentials without renaming the keys.

The settings object also exposes `max_loops` and `max_step_calls` to bound delegation loops.

## Skills

Skills are **knowledge packages** (documentation + scripts), NOT tool containers. Each skill provides:

- **SKILL.md** - Main documentation with usage guide
- **scripts/** - Python scripts for specific tasks (e.g., `fill_pdf_form.py`)
- **Reference docs** - Additional documentation (forms.md, reference.md, etc.)

Example structure:
```
skills/pdf/
├── SKILL.md           # Main skill documentation
├── forms.md           # PDF form filling guide
├── reference.md       # Advanced usage reference
└── scripts/           # Executable Python scripts
    ├── fill_fillable_fields.py
    ├── extract_form_field_info.py
    └── convert_pdf_to_images.py
```

When a user mentions `@pdf`, the system:
1. Loads the skill into the session workspace (symlink)
2. Generates a reminder for the agent to read `SKILL.md`
3. Agent reads documentation and executes scripts as needed

**Important**: Skills do NOT have `allowed_tools` - they are documentation packages that guide the agent.

## Workspace Isolation

Each session gets an isolated workspace directory for safe file operations:

```
data/workspace/{session_id}/
├── skills/           # Symlinked skills (read-only)
│   └── pdf/
│       ├── SKILL.md
│       └── scripts/
├── uploads/          # User-uploaded files
├── outputs/          # Agent-generated files
├── temp/             # Temporary files
└── .metadata.json    # Session metadata
```

**File operation tools**:
- `read_file` - Read files from workspace (skills/, uploads/, outputs/)
- `write_file` - Write files to workspace (outputs/, temp/)
- `list_workspace_files` - List workspace directory contents
- `run_bash_command` - Execute bash commands and Python scripts (optional, disabled by default)

**Security features**:
- Path traversal protection (cannot access files outside workspace)
- Write restrictions (can only write to outputs/, temp/, uploads/)
- Skills are read-only (symlinked or copied)
- Automatic cleanup on exit (workspaces older than 7 days)
- Manual cleanup via `/clean` command

## File Upload

Users can upload files to the agent using `#filename` syntax from the `uploads/` directory:

```bash
# Put files in uploads/ directory
uploads/
├── document.pdf
├── screenshot.png
└── data.txt

# Reference in conversation
You> 分析这张图 #screenshot.png
You> 处理这个文档 #document.pdf
```

**Automatic handling**:
- **Images** (.png, .jpg, etc.): Base64 encoded + injected into message → vision model
- **PDFs** (.pdf): Copied to workspace + auto-load @pdf skill
- **Text files** (<10KB): Content directly injected into message
- **Others**: Copied to workspace for agent tool processing

**File type limits**:
- Images: 10MB
- PDFs: 50MB
- Text/Code: 5MB
- Office docs: 20MB

See `uploads/README.md` for examples and detailed usage.

## Tools

Core tools (always enabled):
- `now` - Get current UTC time
- `todo_write`, `todo_read` - Task tracking
- `call_subagent` - Delegate tasks to subagents
- `read_file`, `write_file`, `list_workspace_files` - File operations
- `fetch_web` - Fetch web pages and convert to LLM-friendly markdown (Jina Reader)
- `web_search` - Search the web with LLM-optimized results (Jina Search)

Optional tools (can be enabled via tools.yaml):
- `http_fetch` - HTTP requests (stub, deprecated - use fetch_web instead)
- `extract_links` - Link extraction (stub)
- `ask_vision` - Vision perception (stub)
- `run_bash_command` - Execute bash commands and Python scripts (disabled by default)

**Tool Development**:
- Tools are automatically discovered by scanning `generalAgent/tools/builtin/`
- Multiple tools can be defined in a single file using `__all__` export
- Configuration is managed via `generalAgent/config/tools.yaml`
- See `generalAgent/tools/builtin/file_ops.py` for multi-tool file example

## LangGraph Flow

`generalAgent.graph.builder.build_state_graph` assembles the full flow with these nodes:

1. **plan** – governed planner (scoped tools, Skill discovery).
2. **guard** – policy enforcement & HITL gate.
3. **tools** – executes actual tool calls.
4. **post** – updates active skill and allowlists.
5. **decompose** (conditional) – produces a structured plan (Pydantic validated).
6. **delegate** – runs scoped subagents per step.
7. **after** – verifies deliverables, advances plan, enforces budgets.

Routing helpers in `generalAgent.graph.routing` decide whether to decompose and when to finish loops.

## Extending the System

1. **Override the model resolver (可选)**  
   默认情况下 `build_application()` 会读取 `.env` 并通过 `langchain-openai` 创建兼容的 `ChatOpenAI` 客户端（DeepSeek/Moonshot/GLM 等 OpenAI-style API）。如需自定义缓存、重试或使用其他 SDK，可实现 `ModelResolver` 并传入。
2. **Add skills**  
   Drop new skill folders under `skills/` with `SKILL.yaml`, templates, scripts, etc. Call `SkillRegistry.reload()` when hot-reloading.
3. **Register tools**  
   Add tool functions/classes, register them with `ToolRegistry`, and maintain their `ToolMeta` entries.
4. **Subagent catalogs & deliverables**  
   Expand `subagent_catalog` in `runtime/app.py` and extend `deliverable_checkers` for domain-specific outputs.
5. **Observability & persistence**  
   Set `PG_DSN` for Postgres checkpoints and enable tracing via LangSmith env vars.

## Next Steps

- 安装 Python 3.12，并执行 `uv sync`（或 `pip install -e .`）以拉取依赖（含 `langchain-openai`、`python-dotenv`）。
- 运行 `python main.py` 进入多轮 CLI，会基于 `.env` 中的模型配置初始化对话；也可在自己的脚本中调用 `build_application()` 后驱动 `app.invoke(state)`。
- 根据业务补充技能包与工具风险标签，增加测试覆盖治理与路由。

---

## 更新日志

### 2025-01-24 - 消息历史管理与 Subagent 优化

**问题背景**：
- 消息历史在复杂任务中快速堆积（如读取长 SKILL.md 后继续多轮调试）
- 默认保留 20 条消息导致重要上下文被截断
- Agent 倾向于直接处理复杂任务，导致主上下文污染

**修改内容**：

1. **增加消息历史保留数量**
   - 新增配置项 `MAX_MESSAGE_HISTORY`（默认 40，范围 10-100）
   - 修改文件：`settings.py`, `planner.py`, `finalize.py`, `builder.py`, `runtime/app.py`
   - 配置方式：`.env` 中设置 `MAX_MESSAGE_HISTORY=60`

2. **优化 Prompt 引导使用 Subagent**
   - 修改 `prompts.py` 的 PLANNER_SYSTEM_PROMPT：
     - 明确标注"任务委派（推荐优先使用）"
     - 说明何时应该用 subagent（读长文档、多轮调试、独立子任务）
     - 强调 subagent 的好处（独立上下文、不污染主 agent）
   - 修正错误示例：`call_subagent` 只有 `task` 和 `max_loops` 参数，没有 `allowed_tools`

3. **其他优化**
   - 添加 LOG_PROMPT_MAX_LENGTH 配置（默认 500 字符）
   - 启用 planner 和 finalize 的 prompt 日志输出

**预期效果**：
- 主 agent 消息历史增加 1 倍（20→40），减少重要上下文丢失
- 模型被引导优先使用 subagent 处理复杂任务，主 agent 只做协调
- 典型场景：PDF 转图片任务从主 agent 17+ 条消息变为 3 条（委派+接收结果）

**相关文件**：
- `generalAgent/config/settings.py` - 新增 max_message_history 配置
- `generalAgent/graph/prompts.py` - 优化 subagent 使用引导
- `generalAgent/graph/nodes/planner.py` - 使用配置的消息历史长度
- `generalAgent/graph/nodes/finalize.py` - 同上
- `.env.example` - 添加配置说明

### 2025-10-24 - 修复 web_search language 参数问题

**问题**：
模型会传递 `language="zh"` 参数给 web_search，但 Jina Search API 不支持大多数语言代码（除了 "en"），导致搜索失败并返回 400 错误。

**解决方案**：
1. 在工具实现中忽略 `language` 参数（注释掉传递给 API 的代码）
2. 保留参数定义以保持向后兼容
3. 更新 docstring 移除 language 参数说明
4. 强调查询语言自动检测，无需手动指定

**修复效果**：
- ✅ 模型传递 `language="zh"` 不再导致错误
- ✅ 中文查询正常工作（语言自动检测）
- ✅ 英文查询正常工作

**相关文件**：
- `generalAgent/tools/builtin/jina_search.py` - 注释 language 参数传递，更新 docstring

### 2025-10-24 - Prompt 优化：鼓励引用来源链接

**优化内容**：

在 System Prompt 中添加引用来源的建议，鼓励模型在使用网页工具时提供参考链接。

**修改内容**：

1. **CHARLIE_BASE_IDENTITY** - 基础身份
   - 添加："使用 web_search 或 fetch_web 获取信息时，建议附上来源链接方便用户查阅"

2. **FINALIZE_SYSTEM_PROMPT** - 总结回复阶段
   - 添加"引用来源建议"章节
   - 提供格式参考示例
   - 提示工具返回的 JSON 中包含可用的 URL

**语气调整**：
- 从"必须"改为"建议"
- 简化说明，不过度强调
- 给模型更多灵活性

**相关文件**：
- `generalAgent/graph/prompts.py` - 更新 system prompt 的引用建议

### 2025-10-24 - CLI 显示工具调用详情

**新增功能**：

1. **工具调用可视化**
   - 在 CLI 中显示 agent 的工具调用决策
   - 格式：`🔧 [call] tool_name(arg1="value1", arg2=value2)`
   - 智能参数格式化：长字符串截断、列表简化显示

2. **改进工具结果显示**
   - 工具调用前缀：`>> [call]`（输出方向）
   - 工具结果前缀：`<< [result]`（返回方向）
   - 使用箭头符号清晰显示数据流向

**显示示例**：
```
You> 搜索 Python 最新教程
>> [call] web_search(query="Python 最新教程", num_results=5)
<< [result] {"query": "Python 最新教程", "results": [...]}
Agent> 根据搜索结果，我找到了以下教程...
```

**技术细节**：
- 参数格式化：字符串超过 40 字符自动截断
- 列表超过 3 项显示为 `[N items]`
- 总长度限制 80 字符，超出截断
- 使用箭头符号清晰显示方向（>> 调用、<< 结果）

**相关文件**：
- `generalAgent/cli.py` - 添加 `_format_tool_args()` 方法和工具调用显示逻辑

### 2025-10-24 - 优化工具 Docstring 和添加时间搜索提示

**优化内容**：

1. **精简工具 Docstring**
   - `fetch_web`: 从 ~1500 字符精简到 410 字符（减少 73%）
   - `web_search`: 从 ~2500 字符精简到 812 字符（减少 68%）
   - 移除技术实现细节（API key、速率限制、错误处理等）
   - 专注于"做什么、何时用、怎么用"
   - 使用中文描述，更适合中文 LLM 理解

2. **添加时间搜索提示**
   - 在 `web_search` 的 query 参数说明中添加提示
   - 建议在查询中加入时间词（如 "2025"、"最新"、"recent"）来获取特定时间范围的结果
   - 虽然 API 不支持 date_range 参数，但通过查询词优化可达到类似效果

**相关文件**：
- `generalAgent/tools/builtin/jina_reader.py` - 精简 fetch_web docstring
- `generalAgent/tools/builtin/jina_search.py` - 精简 web_search docstring 并添加时间提示

### 2025-10-24 - System Prompt 添加当前日期时间

**修改内容**：

1. **新增 `get_current_datetime_tag()` 函数**
   - 位置：`generalAgent/graph/prompts.py`
   - 功能：生成 `<current_datetime>YYYY-MM-DD HH:MM:SS UTC</current_datetime>` 格式的时间标签
   - 使用 UTC 时区确保一致性

2. **所有 System Prompt 添加当前时间**
   - 主 Agent（PLANNER_SYSTEM_PROMPT）- `planner.py:221`
   - Subagent（SUBAGENT_SYSTEM_PROMPT）- `planner.py:217`
   - Finalize 阶段（FINALIZE_SYSTEM_PROMPT）- `finalize.py:57`

**格式示例**：
```
<current_datetime>2025-10-24 10:33:23 UTC</current_datetime>

你是 Charlie，一个高效、友好的 AI 助手。
...
```

**相关文件**：
- `generalAgent/graph/prompts.py` - 新增 `get_current_datetime_tag()` 函数
- `generalAgent/graph/nodes/planner.py` - 主 agent 和 subagent prompt 添加时间
- `generalAgent/graph/nodes/finalize.py` - finalize prompt 添加时间

### 2025-01-24 - 添加 Jina AI 网页抓取与搜索工具

**新增功能**：

1. **fetch_web 工具** - 基于 Jina Reader API
   - 将任意网页转换为干净的 Markdown 格式
   - 自动移除广告、导航栏等噪音内容
   - 支持 CSS 选择器精准提取页面特定部分
   - 支持长文档（最高 512K tokens）
   - 支持 29 种语言
   - 使用 Reader-LM 模型优化转换质量

2. **web_search 工具** - 基于 Jina Search API
   - 搜索网页并返回 LLM 优化的结果
   - 每个搜索结果包含完整 Markdown 内容
   - 支持域名白名单过滤（allowed_domains）
   - 支持域名黑名单过滤（blocked_domains）
   - 支持地理位置本地化搜索（location）
   - 支持多语言搜索（language）
   - 专为 RAG 和 LLM 处理优化

**配置变更**：
- 添加 `JINA_API_KEY` 环境变量（.env 和 .env.example）
- 在 `tools.yaml` 的 core 分类中添加 `fetch_web` 和 `web_search`
- 添加 `httpx>=0.27.0` 依赖到 `pyproject.toml`

**文件清单**：
- `generalAgent/tools/builtin/jina_reader.py` - fetch_web 工具实现
- `generalAgent/tools/builtin/jina_search.py` - web_search 工具实现
- `generalAgent/config/tools.yaml` - 工具配置更新
- `.env.example`, `.env` - 添加 JINA_API_KEY
- `pyproject.toml` - 添加 httpx 依赖
- `README.md` - 工具文档更新

**使用示例**：
```python
# 抓取网页内容（支持中文）
fetch_web("https://docs.python.org/3/tutorial/")
fetch_web("https://baike.baidu.com/item/Python")  # 中文网页

# 搜索最新信息（自动检测语言）
web_search("Python async programming 2025", num_results=5)
web_search("人工智能最新进展", num_results=3)  # 中文查询

# 仅搜索特定网站
web_search("AI news", allowed_domains=["techcrunch.com", "theverge.com"])

# 排除特定网站
web_search("machine learning", blocked_domains=["wikipedia.org"])
```

**技术细节**：
- 使用 Jina AI 官方 API（免费，无需额外付费）
- 完整支持中文和多语言（29 种语言）
- 自动检测查询语言，无需手动指定
- Reader API 速率限制：200 RPM（标准）/ 2,000 RPM（高级）
- Search API 速率限制：40 RPM（标准）/ 400 RPM（高级）
- 请求超时设置：30 秒
- 域名过滤在客户端实现（支持子域名匹配）
- 使用 `ensure_ascii=False` 正确处理 Unicode 字符

