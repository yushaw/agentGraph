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

Skill manifests live under `skills/<skill_id>/SKILL.yaml`:

```yaml
id: pptx
name: Make a presentation
description: Create a PPTX deck from a topic outline.
version: 0.1.0
inputs_schema:
  type: object
  properties:
    topic: { type: string }
allowed_tools: [draft_outline, generate_pptx]
```

Example: `skills/weather/SKILL.yaml` exposes the `get_weather` tool, which calls the Open-Meteo geocoding + forecast APIs to return real-time conditions for a requested city.

Use `SkillRegistry` to reload manifests at runtime. Skills are accessed by reading `SKILL.md` files directly using the Read tool.

## Tools

- `agentgraph.tools.base` – always-on, read-only utilities (`now`, `calc`, `format_json`).
- `agentgraph.tools.base` – always-on, read-only utilities (`now`, `calc`, `format_json`, `start_decomposition`).
- `agentgraph.tools.business` – example business tools (outline generation, HTTP stub, PPTX stub, vision placeholder, weather lookup).
- `agentgraph.tools.system` – binds skill discovery tools to the active registry.
- `agentgraph.skills.weather.toolkit` – reusable Open-Meteo client utilities (`fetch_weather`, `WeatherReport`).
- `ToolMeta` records risk tags and whether a tool is globally available.

Update `ToolMeta` when adding new tools so the guard node can enforce policies.

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
