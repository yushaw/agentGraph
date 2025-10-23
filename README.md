# AgentGraph Universal Agent Skeleton

This repository contains an opinionated LangGraph-based architecture for building extensible agents. The goal is to make it easy to manage models, skills, tools, governance policies, and complex task execution flows while remaining provider-agnostic.

## Features

- **Model registry & routing** – register five core model classes (base, reasoning, vision, code, chat) and pick the right model per phase (`plan`, `decompose`, `delegate`, etc.).
- **Skill packages** – discoverable `skills/<id>/SKILL.yaml` descriptors with progressive disclosure and tool allowlists.
- **Governed tool runtime** – declarative metadata (`ToolMeta`) for risk tagging, global read-only utilities, and skill-scoped business tools.
- **LangGraph flow** – `plan → guard → tools → post → (decompose|delegate) → guard → tools → after → …` with deliverable verification and budgets.
- **Delegation loop** – decomposition into structured plans, delegated subagents with scoped tools, and per-step verification.
- **Observability hooks** – optional LangSmith tracing + Postgres checkpointer.

## Directory Layout

```
agentgraph/
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

All runtime configuration is sourced from `.env` via `agentgraph.config.settings.Settings`. Key variables:

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
- `run_skill_script` - Execute Python scripts from skills (optional, disabled by default)

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

Optional tools (can be enabled via tools.yaml):
- `http_fetch` - HTTP requests (stub)
- `extract_links` - Link extraction (stub)
- `ask_vision` - Vision perception (stub)
- `run_skill_script` - Execute Python scripts (disabled by default)
- `run_bash_command` - Execute bash commands (disabled by default)

**Tool Development**:
- Tools are automatically discovered by scanning `agentgraph/tools/builtin/`
- Multiple tools can be defined in a single file using `__all__` export
- Configuration is managed via `agentgraph/config/tools.yaml`
- See `agentgraph/tools/builtin/file_ops.py` for multi-tool file example

## LangGraph Flow

`agentgraph.graph.builder.build_state_graph` assembles the full flow with these nodes:

1. **plan** – governed planner (scoped tools, Skill discovery).
2. **guard** – policy enforcement & HITL gate.
3. **tools** – executes actual tool calls.
4. **post** – updates active skill and allowlists.
5. **decompose** (conditional) – produces a structured plan (Pydantic validated).
6. **delegate** – runs scoped subagents per step.
7. **after** – verifies deliverables, advances plan, enforces budgets.

Routing helpers in `agentgraph.graph.routing` decide whether to decompose and when to finish loops.

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
