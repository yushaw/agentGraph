# GeneralAgent - Flexible Agent System

An opinionated LangGraph-based architecture for building various types of agents. This repository provides the **general-purpose agent loop** implementation. Future additions will include workflow-based agents and other specialized agent types.

**Current Implementation**: General-purpose agent with dynamic tool calling, skill loading, and multi-model routing.

## Features

- **Model registry & routing** – register five core model classes (base, reasoning, vision, code, chat) and pick the right model per phase (`plan`, `decompose`, `delegate`, etc.).
- **Skill packages** – discoverable `skills/<id>/SKILL.yaml` descriptors with progressive disclosure and tool allowlists.
- **Governed tool runtime** – declarative metadata (`ToolMeta`) for risk tagging, global read-only utilities, and skill-scoped business tools.
- **Context Management** ⭐ NEW – Intelligent conversation compression with progressive warnings (75% info → 85% warning → 95% auto-compress). Combines Gemini-style summarization with Kimi-style truncation for robust token management.
- **Document Search** ⭐ OPTIMIZED – Industry best practices: BM25 ranking, jieba Chinese segmentation, 400-char smart chunking with 20% overlap. [Details](docs/OPTIMIZATION.md#part-2-document-search-optimization)
- **MCP Integration** – Model Context Protocol support with lazy server startup, manual tool control, and stdio/SSE modes. [Details](docs/FEATURES.md#part-6-mcp-integration)
- **LangGraph flow** – `plan → guard → tools → post → (decompose|delegate) → guard → tools → after → …` with deliverable verification and budgets.
- **Delegation loop** – decomposition into structured plans, delegated delegated agents with scoped tools, and per-step verification.
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

All runtime configuration is sourced from `.env` via **Pydantic BaseSettings** with automatic environment variable loading.

### Settings Structure

```python
Settings (generalAgent/config/settings.py)
├── ModelRoutingSettings     # Model IDs and API credentials
├── GovernanceSettings       # Runtime controls (auto_approve, max_loops)
└── ObservabilitySettings    # Tracing, logging, persistence
```

### Key Environment Variables

**Model Configuration**:
```bash
# Five model slots with flexible aliasing
MODEL_BASE=deepseek-chat                    # Or: MODEL_BASE_ID, MODEL_BASIC_ID
MODEL_BASE_API_KEY=sk-xxx                   # Or: MODEL_BASIC_API_KEY
MODEL_BASE_URL=https://api.deepseek.com     # Or: MODEL_BASIC_BASE_URL

MODEL_REASON=deepseek-reasoner              # Or: MODEL_REASON_ID, MODEL_REASONING_ID
MODEL_REASON_API_KEY=sk-xxx                 # Or: MODEL_REASONING_API_KEY
MODEL_REASON_URL=https://api.deepseek.com   # Or: MODEL_REASONING_BASE_URL

MODEL_VISION=glm-4.5v                       # Or: MODEL_VISION_ID, MODEL_MULTIMODAL_ID
MODEL_VISION_API_KEY=xxx                    # Or: MODEL_MULTIMODAL_API_KEY
MODEL_VISION_URL=https://open.bigmodel.cn/api/paas/v4

MODEL_CODE=code-pro                         # Or: MODEL_CODE_ID
MODEL_CODE_API_KEY=xxx

MODEL_CHAT=kimi-k2-0905-preview             # Or: MODEL_CHAT_ID
MODEL_CHAT_API_KEY=xxx
MODEL_CHAT_URL=https://api.moonshot.cn/v1
```

**Governance**:
```bash
AUTO_APPROVE_WRITES=false
MAX_LOOPS=100                   # Max agent loop iterations (1-500)
MAX_MESSAGE_HISTORY=40          # Message history size (10-100)
```

**Context Management** (NEW):

智能上下文压缩功能，通过渐进式警告和分层压缩策略管理长对话的 Token 使用。

```bash
# 总开关
CONTEXT_MANAGEMENT_ENABLED=true
# 是否启用上下文管理功能
# 默认: true
# 说明: 关闭后不再监控 token 使用，也不会触发压缩

# Token 使用监控阈值 (基于累积 prompt tokens 占模型上下文窗口的比例)
CONTEXT_INFO_THRESHOLD=0.75
# 信息提示阈值
# 默认: 0.75 (75%)，范围: 0.5-0.95 (ge=0.5, le=0.95)
# 说明: 达到此阈值时显示信息提示，建议使用 compact_context 工具
# 影响: 调低会更早触发提示，调高会延迟提示
# 示例: 0.70 = 90K/128K tokens 时提示，0.80 = 102K/128K tokens 时提示

CONTEXT_WARNING_THRESHOLD=0.85
# 警告阈值
# 默认: 0.85 (85%)，范围: 0.6-0.95 (ge=0.6, le=0.95)
# 说明: 达到此阈值时显示强警告，强烈建议立即压缩
# 影响: 调低会更早触发警告，调高会延迟警告（可能导致达到 critical 阈值）
# 示例: 0.80 = 102K/128K tokens 时警告，0.90 = 115K/128K tokens 时警告

CONTEXT_CRITICAL_THRESHOLD=0.95
# 临界阈值
# 默认: 0.95 (95%)，范围: 0.8-0.99 (ge=0.8, le=0.99)
# 说明: 达到此阈值时自动触发 summarize 压缩（极简摘要）
# 影响: 调低会更早自动压缩，调高可能导致接近 token 上限
# 示例: 0.90 = 115K/128K tokens 时自动压缩，0.98 = 125K/128K tokens 时自动压缩

# 分层压缩策略配置
CONTEXT_KEEP_RECENT=10
# 保留最近消息数量
# 默认: 10，范围: 5-50 (ge=5, le=50)
# 说明: 压缩时保持最近 N 条消息完整不压缩（保留当前上下文）
# 影响: 调高会保留更多细节但压缩效果降低，调低会压缩更多但可能丢失近期上下文
# 示例: 5 = 保留最近 5 条（激进压缩），20 = 保留最近 20 条（保守压缩）

CONTEXT_COMPACT_MIDDLE=30
# 详细摘要消息数量
# 默认: 30，范围: 10-100 (ge=10, le=100)
# 说明: 对中间层 N 条消息进行详细摘要（保留技术细节、文件路径、工具调用等）
# 影响: 调高会保留更多技术细节但压缩效果降低，调低会摘要更简略
# 示例: 20 = 中间 20 条详细摘要，50 = 中间 50 条详细摘要

# 动态策略决策配置
CONTEXT_COMPRESSION_RATIO_THRESHOLD=0.4
# 压缩率阈值
# 默认: 0.4 (40%)，范围: 0.2-0.8 (ge=0.2, le=0.8)
# 说明: 当上次压缩率 > 此值时，说明 compact 效果不佳，下次切换为 summarize
# 影响: 调低会更容易切换到 summarize（激进），调高会更倾向使用 compact（保守）
# 示例: 0.3 = 压缩率 > 30% 就切换，0.5 = 压缩率 > 50% 才切换

CONTEXT_COMPACT_CYCLE_LIMIT=3
# 连续 compact 次数限制
# 默认: 3，范围: 1-10 (ge=1, le=10)
# 说明: 连续使用 compact 策略 N 次后，强制切换为 summarize（防止压缩效果递减）
# 影响: 调低会更快切换到 summarize（激进），调高会延长 compact 周期（保守）
# 示例: 2 = compact 两次后切换，5 = compact 五次后切换

# 后备策略（Kimi-inspired）
CONTEXT_MAX_HISTORY=100
# 最大历史消息数量
# 默认: 100，范围: 30-200 (ge=30, le=200)
# 说明: 当 LLM 压缩失败时，降级为简单截断策略，仅保留 SystemMessage + 最近 N 条消息
# 影响: 调高会保留更多历史但可能接近 token 上限，调低会丢失更多历史
# 示例: 50 = 紧急情况保留 50 条，150 = 紧急情况保留 150 条
```

**配置建议**:

1. **保守型配置**（适合需要保留详细上下文的场景）:
   ```bash
   CONTEXT_INFO_THRESHOLD=0.70          # 更早提示
   CONTEXT_KEEP_RECENT=20               # 保留更多最近消息
   CONTEXT_COMPACT_MIDDLE=50            # 详细摘要更多消息
   CONTEXT_COMPRESSION_RATIO_THRESHOLD=0.5  # 更倾向使用 compact
   CONTEXT_COMPACT_CYCLE_LIMIT=5        # 更长的 compact 周期
   ```

2. **激进型配置**（适合需要最大化 token 节省的场景）:
   ```bash
   CONTEXT_INFO_THRESHOLD=0.80          # 更晚提示
   CONTEXT_KEEP_RECENT=5                # 仅保留最近 5 条
   CONTEXT_COMPACT_MIDDLE=20            # 精简摘要
   CONTEXT_COMPRESSION_RATIO_THRESHOLD=0.3  # 更容易切换到 summarize
   CONTEXT_COMPACT_CYCLE_LIMIT=2        # 更快切换到 summarize
   ```

3. **平衡型配置**（默认值，适合大多数场景）:
   ```bash
   # 使用上述默认值即可
   ```

**Pydantic 字段约束说明**:
- `ge` (greater than or equal): 最小值约束，配置不能低于此值
- `le` (less than or equal): 最大值约束，配置不能超过此值
- 示例: `ge=0.5, le=0.95` 表示有效范围是 0.5 ≤ 值 ≤ 0.95
- 违反约束时会在启动时报 ValidationError

**Observability**:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=my-project
LANGCHAIN_API_KEY=xxx           # Or: LANGSMITH_API_KEY
SESSION_DB_PATH=./data/sessions.db  # SQLite session storage
LOG_PROMPT_MAX_LENGTH=500       # Truncate logged prompts
```

### Configuration Features

- **Automatic .env loading** - All settings inherit from `BaseSettings`
- **Multiple aliases** - Provider-specific names (DeepSeek: `MODEL_BASIC_*`, GLM: `MODEL_MULTIMODAL_*`, etc.)
- **Type validation** - Pydantic validates types and ranges
- **No fallbacks needed** - Settings load directly from environment

### Usage Example

```python
from generalAgent.config.settings import get_settings

settings = get_settings()  # Cached singleton
api_key = settings.models.reason_api_key  # Automatically from .env
max_loops = settings.governance.max_loops  # Default: 100
```

See [CLAUDE.md - Settings Architecture](CLAUDE.md#settings-architecture) for implementation details.

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
- `delegate_task` - Delegate tasks to delegated agents
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
6. **delegate** – runs scoped delegated agents per step.
7. **after** – verifies deliverables, advances plan, enforces budgets.

Routing helpers in `generalAgent.graph.routing` decide whether to decompose and when to finish loops.

## Extending the System

1. **Override the model resolver (可选)**  
   默认情况下 `build_application()` 会读取 `.env` 并通过 `langchain-openai` 创建兼容的 `ChatOpenAI` 客户端（DeepSeek/Moonshot/GLM 等 OpenAI-style API）。如需自定义缓存、重试或使用其他 SDK，可实现 `ModelResolver` 并传入。
2. **Add skills**  
   Drop new skill folders under `skills/` with `SKILL.yaml`, templates, scripts, etc. Call `SkillRegistry.reload()` when hot-reloading.
3. **Register tools**  
   Add tool functions/classes, register them with `ToolRegistry`, and maintain their `ToolMeta` entries.
4. **Delegated agent catalogs & deliverables**  
   Expand `delegated agent_catalog` in `runtime/app.py` and extend `deliverable_checkers` for domain-specific outputs.
5. **Observability & persistence**  
   Set `PG_DSN` for Postgres checkpoints and enable tracing via LangSmith env vars.

## Testing

The project includes a comprehensive test suite organized into four tiers:

```bash
# Quick validation before commits (< 30s)
python tests/run_tests.py smoke

# Run specific test types
python tests/run_tests.py unit          # Module-level tests
python tests/run_tests.py integration   # Module interaction tests
python tests/run_tests.py e2e           # Complete business workflows

# Run all tests
python tests/run_tests.py all

# Generate coverage report
python tests/run_tests.py coverage
```

**Test organization:**
- `tests/smoke/` - Fast critical-path validation tests
- `tests/unit/` - Unit tests for individual modules (HITL, MCP, Tools, etc.)
- `tests/integration/` - Integration tests for module interactions
- `tests/e2e/` - End-to-end business workflow tests
- `tests/fixtures/` - Test infrastructure (test MCP servers, etc.)

For detailed testing guidelines and best practices, see [docs/TESTING.md](docs/TESTING.md).

## Documentation

Comprehensive documentation is organized into six core documents by topic and audience:

### For New Users
- **[docs/README.md](docs/README.md)** - Documentation index with quick start guides and topic finder
- **[docs/FEATURES.md](docs/FEATURES.md)** - User-facing features (Workspace, @Mentions, File Upload, MCP, HITL)

### For Developers
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Environment setup, tool/skill development, best practices
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Core architecture, tool system, skill system, design patterns

### For Advanced Topics
- **[docs/OPTIMIZATION.md](docs/OPTIMIZATION.md)** - Performance optimization (KV Cache, Document Search, Text Indexer)
- **[docs/TESTING.md](docs/TESTING.md)** - Comprehensive testing guide (Smoke, Unit, Integration, E2E, HITL)

**Quick links:**
- Architecture overview → [docs/ARCHITECTURE.md - Part 1](docs/ARCHITECTURE.md#part-1-core-architecture)
- Tool development → [docs/DEVELOPMENT.md - Part 2](docs/DEVELOPMENT.md#part-2-developing-tools)
- Skill creation → [docs/DEVELOPMENT.md - Part 3](docs/DEVELOPMENT.md#part-3-developing-skills)
- Performance tuning → [docs/OPTIMIZATION.md - Part 1](docs/OPTIMIZATION.md#part-1-context-management--kv-cache-optimization)

**Note:** Previous documentation has been archived in [docs/archive/](docs/archive/) with a mapping guide.

## Next Steps

- 安装 Python 3.12，并执行 `uv sync`（或 `pip install -e .`）以拉取依赖（含 `langchain-openai`、`python-dotenv`）。
- 运行 `python main.py` 进入多轮 CLI，会基于 `.env` 中的模型配置初始化对话；也可在自己的脚本中调用 `build_application()` 后驱动 `app.invoke(state)`。
- 根据业务补充技能包与工具风险标签，增加测试覆盖治理与路由。

---

## Recent Updates

### 2025-10-27

**Documentation Reorganization** ⭐
- Consolidated 14 documents → 6 core documents (50% reduction)
- Created comprehensive maintenance guide in [docs/README.md](docs/README.md)
- Archived old files with migration mapping

**TODO Tool State Synchronization Fix** ⭐
- Fixed critical bug: `todo_write` now correctly updates `state["todos"]` using LangGraph `Command` objects
- Enhanced TODO reminder to display ALL incomplete tasks with priority tags
- 16 comprehensive tests, 100% passing

**Document Search Optimization** ⭐
- Upgraded with BM25 ranking, jieba Chinese segmentation, smart chunking (400 chars with 20% overlap)
- Performance gains: +40-60% precision, +30-40% Chinese accuracy
- Added `find_files` and `search_file` tools with index-based search

**Document Reading Support**
- Enhanced `read_file` to support PDF, DOCX, XLSX, PPTX with automatic format detection
- Smart preview for large files with search hints
- Global MD5-based indexing system for efficient search

For complete version history and detailed technical explanations, see [CHANGELOG.md](CHANGELOG.md).

