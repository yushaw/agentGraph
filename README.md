# GeneralAgent - Flexible Agent System

An opinionated LangGraph-based architecture for building various types of agents. This repository provides the **general-purpose agent loop** implementation. Future additions will include workflow-based agents and other specialized agent types.

**Current Implementation**: General-purpose agent with dynamic tool calling, skill loading, and multi-model routing.

## ⚠️ Development Requirements

**For Contributors and Developers**:

1. **Use `uv` for all operations** - This project uses `uv` for package management
   ```bash
   uv sync              # Install dependencies
   uv run python main.py  # Run the application
   uv run pytest tests/  # Run tests
   ```

2. **Configuration Management**
   - ❌ **DO NOT** write feature configs to `.env`
   - ✅ **ALWAYS** write configs to `generalAgent/config/` YAML files
   - ✅ `.env` is ONLY for API keys and sensitive credentials
   - ✅ See `CLAUDE.md` for detailed configuration rules

3. **Testing is Mandatory**
   - Write smoke + unit + integration + e2e tests for all features
   - Run smoke tests before commits: `uv run python tests/run_tests.py smoke`
   - See `tests/` directory structure and `CLAUDE.md` for guidelines

## Features

- **Model registry & routing** – register five core model classes (base, reasoning, vision, code, chat) and pick the right model per phase (`plan`, `decompose`, `delegate`, etc.).
- **Skill packages** – discoverable `skills/<id>/SKILL.yaml` descriptors with progressive disclosure and tool allowlists.
- **Governed tool runtime** – declarative metadata (`ToolMeta`) for risk tagging, global read-only utilities, and skill-scoped business tools.
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

Configuration is split between two locations:

1. **`.env` file** - API keys and sensitive credentials ONLY (loaded via Pydantic BaseSettings)
2. **`generalAgent/config/` YAML files** - All feature flags, thresholds, and behavior settings

### Settings Structure

```python
Settings (generalAgent/config/settings.py)
├── ModelRoutingSettings     # Model IDs and API credentials (from .env)
├── GovernanceSettings       # Runtime controls (from .env)
├── ContextManagementSettings # Token tracking & compression (from .env)
└── ObservabilitySettings    # Tracing, logging, persistence (from .env)
```

**⚠️ Important**: Only credentials go in `.env`. Feature configs go in YAML files under `generalAgent/config/`.

### API Credentials (.env file)

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

