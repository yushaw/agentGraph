# GeneralAgent 完整生命周期流程图

> 本文档详细描述了 generalAgent 从启动到执行的完整生命周期，包括所有核心机制、外部依赖和代码位置索引。

---

## 目录

- [启动阶段](#启动阶段)
- [CLI 初始化](#cli-初始化)
- [用户输入处理](#用户输入处理)
- [LangGraph 执行循环](#langgraph-执行循环)
- [核心机制详解](#核心机制详解)
  - [MCP 集成](#mcp-集成)
  - [delegate_task 委托](#delegate_task-委托)
  - [Agent Handoff](#agent-handoff)
  - [文档索引与搜索](#文档索引与搜索)
  - [自动上下文压缩](#自动上下文压缩)
  - [HITL 机制](#hitl-机制)
- [核心工具实现](#核心工具实现)
- [外部依赖清单](#外部依赖清单)

---

## 启动阶段

### 程序入口

```
main.py → generalAgent/main.py:main()
                ↓
        generalAgent/main.py:async_main()
```

**代码位置**: `main.py:1-6`, `generalAgent/main.py:25-119`

### 1. 应用初始化

**代码位置**: `generalAgent/runtime/app.py:build_application()`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  应用初始化 (runtime/app.py:151-267)                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  [外部依赖]                                                                  │
│  • Settings (Pydantic BaseSettings) ← .env                                  │
│  • LangSmith Tracing (observability)                                        │
│  • SQLite (session_store.db, indexes/)                                      │
│                                                                              │
│  [核心组件构建]                                                               │
│  ① ModelRegistry (models/registry.py:build_default_registry)                │
│     代码: generalAgent/models/registry.py:40-98                              │
│     - 5 slots: base/reasoning/vision/code/chat                             │
│     - 支持 DeepSeek/Moonshot/GLM 等 OpenAI-compatible APIs                  │
│                                                                              │
│  ② SkillRegistry (skills/registry.py)                                       │
│     代码: generalAgent/skills/registry.py:14-156                             │
│     - 扫描 skills/*/SKILL.md                                                │
│     - 加载 skills.yaml 配置 (enabled, auto_load_on_file_types)              │
│                                                                              │
│  ③ ToolRegistry (tools/registry.py)                                         │
│     代码: generalAgent/tools/registry.py:15-207                              │
│     - 3层架构:                                                               │
│       • _discovered: 所有扫描到的工具 (builtin + custom + MCP)              │
│       • _tools: 启用的工具 (tools.yaml enabled:true)                        │
│       • load_on_demand(): @mention 时动态加载                                │
│                                                                              │
│  ④ AgentRegistry (agents/registry.py)                                       │
│     代码: generalAgent/agents/registry.py:16-227                             │
│     - 扫描 agents.yaml 配置的专业 agent (simple/general/...)                │
│     - 生成 handoff tools (LangGraph 切换模式)                                │
│                                                                              │
│  ⑤ ApprovalChecker (hitl/approval_checker.py)                               │
│     代码: generalAgent/hitl/approval_checker.py:20-231                       │
│     - 4层规则: Custom Checkers → Global Patterns → Tool Rules → Defaults   │
│     - 配置: config/hitl_rules.yaml                                           │
│                                                                              │
│  ⑥ LangGraph 构建 (graph/builder.py:build_state_graph)                      │
│     代码: generalAgent/graph/builder.py:30-176                               │
│     - Nodes: agent, tools, finalize, summarization, [agent_nodes...]       │
│     - Routing: agent_route, tools_route, summarization_route               │
│     - Checkpointer: SQLite (data/sessions.db)                              │
│                                                                              │
│  ⑦ SessionManager (shared/session/manager.py)                               │
│     代码: shared/session/manager.py:17-196                                   │
│     - SessionStore: 会话持久化 (SQLite)                                      │
│     - WorkspaceManager: 隔离的文件工作区 (data/workspace/{session_id}/)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### MCP 集成

**代码位置**: `generalAgent/main.py:32-59`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MCP (Model Context Protocol) 集成                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/main.py:36-59                                            │
│  工具: generalAgent/tools/mcp/                                               │
│                                                                              │
│  ① 加载配置: config/mcp_servers.yaml                                        │
│     格式: {server_id, command, args, env, enabled}                          │
│                                                                              │
│  ② 创建 MCPServerManager (延迟启动模式)                                      │
│     代码: generalAgent/tools/mcp/manager.py:19-157                           │
│     - 服务器未启动, 只配置                                                    │
│                                                                              │
│  ③ 创建 MCP Tool Wrappers                                                   │
│     代码: generalAgent/tools/mcp/wrapper.py:13-99                            │
│     - 每个 MCP tool 包装为 LangChain tool                                    │
│     - tool.invoke() → 启动 server → 调用 tool → 返回结果                     │
│                                                                              │
│  ④ 注册到 ToolRegistry                                                      │
│     - _discovered (可 @mention)                                              │
│     - _tools (立即可用, 如果 enabled:true)                                   │
│                                                                              │
│  ⑤ 程序退出时自动清理                                                        │
│     代码: generalAgent/main.py:103-106                                       │
│     - await mcp_manager.shutdown()                                          │
│     - 关闭所有 MCP server 进程                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## CLI 初始化

**代码位置**: `generalAgent/cli.py:31-106`, `generalAgent/main.py:64-96`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLI 启动 (cli.py:GeneralAgentCLI)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/main.py:74-95                                            │
│                                                                              │
│  • 创建新会话: session_id = UUID4                                            │
│    代码: shared/session/manager.py:50-74                                     │
│                                                                              │
│  • 初始化 workspace: data/workspace/{session_id}/                           │
│    代码: shared/workspace/manager.py:55-107                                  │
│    - uploads/    (用户上传文件)                                              │
│    - outputs/    (Agent 生成文件)                                            │
│    - skills/     (符号链接到项目 skills/)                                    │
│    - temp/       (临时文件)                                                  │
│                                                                              │
│  • 初始化 state:                                                             │
│    代码: generalAgent/runtime/app.py:241-264                                 │
│    {                                                                         │
│      messages: [],                                                           │
│      todos: [],                                                              │
│      mentioned_agents: [],                                                   │
│      workspace_path: str,                                                    │
│      uploaded_files: [],                                                     │
│      ...                                                                     │
│    }                                                                         │
│                                                                              │
│  • 打印欢迎信息: Session ID, Log file                                        │
│    代码: generalAgent/cli.py:96-104                                          │
│                                                                              │
│  • 进入交互循环: You>                                                         │
│    代码: shared/cli/base_cli.py:67-100                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 用户输入处理

**代码位置**: `generalAgent/cli.py:111-241`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  用户输入处理 (cli.py:handle_user_message)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  [步骤1] 解析 @mentions                                                      │
│  代码: generalAgent/cli.py:121-155                                           │
│  工具: generalAgent/utils/__init__.py:parse_mentions()                       │
│        generalAgent/utils/mention_classifier.py:classify_mentions()          │
│                                                                              │
│    • @tool    → 动态加载工具到 visible_tools                                 │
│    • @skill   → 符号链接到 workspace/skills/ + 生成 reminder                │
│    • @agent   → 加载 call_agent/delegate_task 工具                          │
│                                                                              │
│  [步骤2] 解析 #filename (file upload)                                        │
│  代码: generalAgent/cli.py:124-194                                           │
│  工具: generalAgent/utils/__init__.py:parse_file_mentions()                  │
│        generalAgent/utils/file_processor.py:process_file()                   │
│                                                                              │
│    • 移动文件到 workspace/uploads/                                           │
│    • 图片: 转 base64 注入 HumanMessage                                       │
│    • 文本: 直接注入 message content                                          │
│    • 自动加载技能: 根据 skills.yaml auto_load_on_file_types                  │
│                                                                              │
│  [步骤3] 构建 HumanMessage                                                   │
│  代码: generalAgent/cli.py:196-230                                           │
│                                                                              │
│    message_content = [                                                       │
│      {type: "text", text: cleaned_input},                                   │
│      {type: "image_url", image_url: "data:base64,..."},  # 如果有图片        │
│      ...                                                                     │
│    ]                                                                         │
│                                                                              │
│  [步骤4] 设置环境变量                                                         │
│  代码: generalAgent/cli.py:246-249                                           │
│                                                                              │
│    os.environ["AGENT_WORKSPACE_PATH"] = workspace_path                       │
│                                                                              │
│  [步骤5] 配置 LangGraph 执行                                                 │
│  代码: generalAgent/cli.py:251-258                                           │
│                                                                              │
│    • recursion_limit = max_loops * 3 (agent+tools+finalize)                │
│    • config = {thread_id, recursion_limit}                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph 执行循环

**代码位置**: `generalAgent/cli.py:260-330`, `generalAgent/graph/`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LangGraph 执行循环 (app.astream)                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/cli.py:264-330                                           │
│                                                                              │
│  流程: START → agent ⇄ tools → agent ⇄ summarization → finalize → END      │
└─────────────────────────────────────────────────────────────────────────────┘

       ├───► [Node: agent] (graph/nodes/planner.py:planner_node)
       │     代码: generalAgent/graph/nodes/planner.py:109-482
       │
       │     ├─ [A. 组装 visible_tools] (行 118-181)
       │     │   • persistent_global_tools (core tools)
       │     │   • @mention tools (load_on_demand)
       │     │   • @agent → call_agent + delegate_task
       │     │   • 能力检测: code/vision tags
       │     │   • 委托过滤: subagent 不可用 delegate_task
       │     │
       │     ├─ [B. 构建 SystemMessage (固定, KV Cache 优化)] (行 86-106)
       │     │   代码: generalAgent/graph/prompts.py:PLANNER_SYSTEM_PROMPT
       │     │   • 静态部分: PLANNER_SYSTEM_PROMPT + skills_catalog + agents_catalog
       │     │   • 时间戳: <current_datetime>YYYY-MM-DD HH:MM UTC</> (启动时固定)
       │     │   • 位置: 时间戳在底部 (最大化 KV Cache 复用)
       │     │
       │     ├─ [C. 构建 Dynamic Reminders (动态, 追加到最后一条 HumanMessage)] (行 213-306)
       │     │   代码: generalAgent/graph/prompts.py:build_dynamic_reminder()
       │     │   • @mention 提示: 新加载的 tools/skills/agents
       │     │   • Todo 提醒: in_progress + pending 任务列表
       │     │   • 文件上传提示: 新上传文件 + 可用技能提示
       │     │   • Token 警告: info/warning/critical 级别
       │     │
       │     ├─ [D. Context Management (token tracking)] (行 308-360)
       │     │   代码: generalAgent/context/token_tracker.py:TokenTracker
       │     │   • 累积 prompt_tokens (API 返回当前 context size)
       │     │   • 检查 token_status: info(<75%) / warning(<85%) / critical(<95%)
       │     │   • critical → 跳过 LLM, 返回 needs_compression=True (路由触发压缩)
       │     │   • info/warning → 动态加载 compact_context tool
       │     │
       │     ├─ [E. Model Selection] (行 410-423)
       │     │   代码: generalAgent/agents/invoke_planner.py:invoke_planner()
       │     │   [外部依赖: OpenAI-compatible API]
       │     │   • 优先级: preference > vision > code > base
       │     │   • ModelResolver: 根据能力选择模型
       │     │   • bind_tools(visible_tools)
       │     │
       │     ├─ [F. LLM 调用] (行 410-423)
       │     │   • 输入: SystemMessage + message_history (with reminders)
       │     │   • 输出: AIMessage (content + tool_calls)
       │     │   • 错误处理: handle_model_error() → ModelInvocationError
       │     │
       │     └─ [G. 更新 state] (行 428-478)
       │         • messages.append(AIMessage)
       │         • loops += 1
       │         • cumulative_prompt_tokens = API response
       │         • new_uploaded_files = [] (清空一次性提醒)
       │         • new_mentioned_agents = [] (清空一次性提醒)
       │
       ├───► [Routing: agent_route] (graph/routing.py:agent_route)
       │     代码: generalAgent/graph/routing.py:14-62
       │
       │     ├─ Check: loops >= max_loops? → "finalize"
       │     ├─ Check: needs_compression && !auto_compressed? → "summarization"
       │     ├─ Check: tool_calls? → "tools"
       │     └─ Default → "finalize"
       │
       ├───► [Node: summarization] (如果 critical token)
       │     代码: generalAgent/graph/nodes/summarization.py:build_summarization_node()
       │
       │     [外部依赖: LLM API]
       │     ├─ [A. 分层消息] (context/compressor.py:232-288)
       │     │   • system: 保留所有 SystemMessage
       │     │   • old: 待压缩部分 (早期消息)
       │     │   • recent: 保留部分 (15% context window 或 10条消息)
       │     │
       │     ├─ [B. LLM 压缩] (context/compressor.py:301-341)
       │     │   • Prompt: COMPACT_PROMPT (7部分结构化摘要)
       │     │   • 调用 LLM (max_tokens=1440)
       │     │   • 生成 SystemMessage("# 对话历史摘要...")
       │     │
       │     ├─ [C. 清理孤儿 ToolMessage] (context/compressor.py:342-379)
       │     │   • 过滤没有对应 tool_call_id 的 ToolMessage
       │     │
       │     ├─ [D. 降级策略] (如果 LLM 压缩失败)
       │     │   代码: context/compressor.py:201-208
       │     │   • 简单截断: 保留最近 MAX_MESSAGE_HISTORY 条
       │     │
       │     └─ [E. 更新 state]
       │         • messages = [system, summary, ...recent]
       │         • auto_compressed_this_request = True
       │         • compact_count += 1
       │         • 压缩报告: before/after count, tokens, ratio
       │
       ├───► [Routing: summarization_route]
       │     代码: generalAgent/graph/routing.py:87-98
       │     └─ Always → "agent" (继续处理原始请求)
       │
       ├───► [Node: tools] (hitl/approval_node.py:ApprovalToolNode)
       │     代码: generalAgent/hitl/approval_node.py:35-110
       │
       │     [外部依赖: 工具执行环境 (bash, Python, network...)]
       │     ├─ [A. HITL 审批检查] (4层规则)
       │     │   代码: generalAgent/hitl/approval_checker.py:check()
       │     │   • Layer 1: Custom Checkers (tool-specific logic)
       │     │   • Layer 2: Global Patterns (sensitive info, passwords...)
       │     │   • Layer 3: Tool Config Rules (hitl_rules.yaml)
       │     │   • Layer 4: Default Rules (safe commands)
       │     │   │
       │     │   └─ 需要审批? → interrupt({"type": "tool_approval", ...})
       │     │       代码: hitl/approval_node.py:74-92
       │     │       ┌─────────────────────────────────────┐
       │     │       │ [HITL: 用户审批] (cli.py:467-503)   │
       │     │       │ • 打印: 工具名, 参数, 风险级别         │
       │     │       │ • 用户选择: y/n                      │
       │     │       │ • 返回: "approve"/"reject"           │
       │     │       └─────────────────────────────────────┘
       │     │
       │     ├─ [B. 工具执行] (ToolNode)
       │     │   代码: langgraph.prebuilt.ToolNode
       │     │   • 调用 tool_func(**args)
       │     │   • 生成 ToolMessage(result)
       │     │   • 错误处理: ToolMessage(error)
       │     │
       │     └─ [C. 更新 state]
       │         • messages.append(ToolMessage)
       │
       ├───► [Routing: tools_route]
       │     代码: generalAgent/graph/routing.py:65-84
       │
       │     ├─ Check: 是否 handoff? (Command.goto) → target_agent
       │     └─ Default → current_agent (or "agent")
       │
       ├───► [Node: finalize] (graph/nodes/finalize.py:finalize_node)
       │     代码: generalAgent/graph/nodes/finalize.py:45-97
       │
       │     [仅在最后一条消息是 ToolMessage 时触发]
       │     ├─ [A. 构建 Finalize Prompt (固定, KV Cache)] (行 34-42)
       │     │   • FINALIZE_SYSTEM_PROMPT + 固定时间戳
       │     │
       │     ├─ [B. LLM 调用 (无 tools)] (行 79-92)
       │     │   • 输入: SystemMessage + recent_history
       │     │   • 输出: AIMessage (final response)
       │     │
       │     └─ [C. 更新 state]
       │         • messages.append(AIMessage)
       │
       └───► [END]
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  HITL 中断处理循环 (cli.py:_handle_interrupt)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/cli.py:279-320, 410-503                                  │
│                                                                              │
│  [循环检查 graph_state.tasks[0].interrupts]                                  │
│                                                                              │
│  ① interrupt_type = "user_input_request" (ask_human tool)                  │
│     代码: generalAgent/cli.py:430-465                                        │
│     • 打印: question, context, default                                      │
│     • 用户输入: answer                                                        │
│     • Resume: Command(resume=answer)                                        │
│                                                                              │
│  ② interrupt_type = "tool_approval" (HITL approval)                        │
│     代码: generalAgent/cli.py:467-503                                        │
│     • 打印: tool, args, reason, risk_level                                 │
│     • 用户输入: y/n                                                          │
│     • Resume: Command(resume="approve"/"reject")                           │
│                                                                              │
│  • 继续 app.astream(Command(resume=...))                                    │
│  • 打印新消息 (避免重复)                                                      │
│  • 直到 no more interrupts                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  会话保存 (session_manager.save_current_session)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: shared/session/manager.py:130-147                                     │
│                                                                              │
│  [外部依赖: SQLite]                                                          │
│  • SessionStore.save(session_id, state)                                     │
│  • 保存到 data/sessions.db (messages, todos, uploaded_files...)             │
│  • 日志: Session {id} saved ({N} messages)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心机制详解

### MCP 集成

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [启动阶段] MCP 集成 (generalAgent/main.py)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/main.py:36-59                                            │
│                                                                              │
│  ① 加载配置: generalAgent/config/mcp_servers.yaml                           │
│     - server_id, command, args, env                                         │
│     - enabled servers only                                                  │
│                                                                              │
│  ② 创建 MCPServerManager (延迟启动模式)                                      │
│     代码: generalAgent/tools/mcp/manager.py:19-157                           │
│     - 服务器未启动, 只配置                                                    │
│                                                                              │
│  ③ 创建 MCP Tool Wrappers                                                   │
│     代码: generalAgent/tools/mcp/wrapper.py:13-99                            │
│     - 每个 MCP tool 包装为 LangChain tool                                    │
│     - tool.invoke() → 启动 server → 调用 tool → 返回结果                     │
│                                                                              │
│  ④ 注册到 ToolRegistry                                                      │
│     代码: generalAgent/runtime/app.py:82-88                                  │
│     - _discovered (可 @mention)                                              │
│     - _tools (立即可用, 如果 enabled:true)                                   │
│                                                                              │
│  ⑤ 程序退出时自动清理                                                        │
│     代码: generalAgent/main.py:103-106                                       │
│     - await mcp_manager.shutdown()                                          │
│     - 关闭所有 MCP server 进程                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### delegate_task 委托

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Tools Node] delegate_task 工具调用                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/delegate_task.py:39-304                    │
│                                                                              │
│  ① 获取 parent state (通过 config injection) (行 88-94)                     │
│     - mentioned_agents, active_skill, workspace_path, uploaded_files        │
│                                                                              │
│  ② 创建独立 subagent state (行 96-125)                                       │
│     - context_id: subagent-{uuid8}                                          │
│     - messages: [HumanMessage(task)]                                        │
│     - 继承: mentioned_agents, workspace_path, uploaded_files                │
│     - 独立: todos=[], loops=0, max_loops=50                                 │
│                                                                              │
│  ③ 执行 subagent (app.astream) (行 136-167)                                 │
│     ┌─────────────────────────────────────────────────────────────┐         │
│     │  Subagent Loop (独立 LangGraph 执行)                          │         │
│     │  • agent → tools → agent → ... → finalize                   │         │
│     │  • 可见工具: 继承自 parent 的 @mentioned tools                │         │
│     │  • 不可见: delegate_task (防止嵌套)                          │         │
│     │  • HITL 支持: ask_human interrupt 传递给用户                 │         │
│     └─────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ④ 实时输出: [subagent-{uuid8}] ... (行 158-165)                            │
│                                                                              │
│  ⑤ HITL 中断处理 (行 168-229)                                                │
│     - 检测 interrupt (ask_human)                                            │
│     - 打印问题给用户                                                          │
│     - 用户输入 → resume execution                                            │
│                                                                              │
│  ⑥ 结果长度检查 (行 242-283)                                                 │
│     - 如果结果 < 200 chars → 自动请求详细摘要 (max 1 retry)                   │
│     - 继续执行: "请提供更详细的摘要..."                                        │
│                                                                              │
│  ⑦ 返回 JSON 结果 (行 285-295)                                               │
│     {"ok": true, "result": "...", "context_id": "...", "loops": N}          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent Handoff

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Graph Build] Agent Handoff 工具生成 (runtime/app.py)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/runtime/app.py:188-207                                   │
│                                                                              │
│  ① AgentRegistry 扫描 (agents.yaml)                                         │
│     代码: generalAgent/agents/scanner.py:scan_agents_from_config()           │
│     - simple: SimpleAgent (通用对话, 无技能要求)                             │
│     - general: GeneralAgent (通用任务, 工具丰富)                             │
│     - ...                                                                   │
│                                                                              │
│  ② 为每个 enabled agent 生成 handoff tool                                   │
│     代码: generalAgent/agents/handoff_tools.py:22-61                         │
│     - tool name: transfer_to_{agent_id}                                     │
│     - description: agent.description + skills                               │
│     - func: 返回 Command(goto=agent_id, update={...})                       │
│                                                                              │
│  ③ 防循环检测逻辑 (行 114-158)                                               │
│     • agent_call_stack: [agent, simple, ...]                               │
│     • 检测1: agent_id 已在栈中? → 拒绝 (返回 ToolMessage error)              │
│     • 检测2: 栈深度 >= 5? → 拒绝 (防止栈溢出)                                │
│                                                                              │
│  ④ 注册到 ToolRegistry (行 199-203)                                          │
│     - 立即启用 (core tools)                                                  │
│     - 所有 agent 可见                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [Tools Node] transfer_to_{agent_id} 执行                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/agents/handoff_tools.py:100-181                          │
│                                                                              │
│  ① 防循环检测 (行 114-158)                                                   │
│     - agent_call_stack 包含 agent_id? → 返回 error ToolMessage              │
│     - 栈深度 >= 5? → 返回 error ToolMessage                                  │
│                                                                              │
│  ② 创建 handoff 消息 (行 160-169)                                            │
│     - ToolMessage: "✓ Transferred to {agent_name}"                          │
│     - HumanMessage: task (新任务描述)                                        │
│                                                                              │
│  ③ 更新状态 (行 170-176)                                                     │
│     - agent_call_stack.append(agent_id)                                     │
│     - agent_call_history.append(agent_id)                                   │
│     - current_agent = agent_id                                              │
│                                                                              │
│  ④ 返回 Command (行 178-181)                                                 │
│     return Command(goto=agent_id, update={...})                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [Routing] tools_route 处理 handoff                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/graph/routing.py:65-84                                   │
│                                                                              │
│  • 检查 state["current_agent"]                                               │
│  • 返回 current_agent (e.g., "simple")                                      │
│  • LangGraph 路由到对应 agent node                                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [Agent Node: simple] SimpleAgent 执行                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/graph/nodes/agent_node.py:build_agent_node_from_card()   │
│                                                                              │
│  • 使用专用 SystemMessage (SIMPLE_AGENT_PROMPT)                              │
│  • 只有基础工具 (无 delegate_task, 无复杂工具)                               │
│  • 完成后返回 Command(goto="agent", ...) 回到主 agent                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 文档索引与搜索

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Tool: search_file] 文档内容搜索                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/search_file.py:31-94                       │
│                                                                              │
│  ① 检查文件类型 (行 82-90)                                                   │
│     • 文档类型 (PDF/DOCX/XLSX/PPTX) → 索引搜索流程                           │
│     • 文本文件 (.txt/.log/.py...) → 实时 Grep 搜索                           │
│                                                                              │
│  ② 检查索引是否存在                                                          │
│     代码: generalAgent/utils/text_indexer.py:103-129                         │
│     [外部依赖: SQLite, data/indexes.db]                                      │
│     • 计算 MD5: file_hash = md5(file_content)                               │
│     • 查询: SELECT indexed_at FROM file_metadata WHERE file_hash=?          │
│     • 检查过期: indexed_at < now - 24h? → 重建                               │
│                                                                              │
│  ③ 创建索引 (如果不存在或过期)                                               │
│     代码: generalAgent/utils/text_indexer.py:154-226                         │
│     [外部依赖: PyMuPDF, python-docx, openpyxl, python-pptx, jieba]          │
│     ┌─────────────────────────────────────────────────────────────┐         │
│     │ A. 文档分块                                                  │         │
│     │   代码: generalAgent/utils/document_extractors.py:239-264    │         │
│     │   • PDF: 按页提取 → 内容感知分块 (400 chars, 20% overlap)   │         │
│     │   • DOCX: 提取段落 → 内容感知分块                            │         │
│     │   • XLSX: 按 sheet → 行批次 (20行/批, 2行重叠)              │         │
│     │   • PPTX: 按 slide → 大 slide 拆分                          │         │
│     │                                                              │         │
│     │ B. 中文预处理 (jieba, 可配置)                                │         │
│     │   代码: text_indexer.py:132-151                              │         │
│     │   • jieba.cut_for_search(text) → "中文 分词 结果"           │         │
│     │                                                              │         │
│     │ C. 存入 SQLite FTS5                                          │         │
│     │   代码: text_indexer.py:43-100                               │         │
│     │   • file_metadata: 文件信息 + full_text                     │         │
│     │   • chunks_fts: FTS5 表 (text, text_jieba)                  │         │
│     │   • chunks_meta: chunk 元数据 (page, offset)                │         │
│     └─────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ④ 搜索策略选择                                                              │
│     代码: generalAgent/utils/text_indexer.py:229-268                         │
│     • 检测查询类型: _should_use_fts5(query, use_regex)                       │
│     • 简单查询 ("baseline", "section 4.1") → FTS5                            │
│     • 复杂正则 (\d{3}-\d{4}, ^ERROR.*) → FTS5 提取关键词 + re 后处理         │
│     • 超复杂正则 (.*(?<!\d)\|...) → 直接 Grep full_text                      │
│                                                                              │
│  ⑤ FTS5 搜索 (高性能路径)                                                    │
│     代码: generalAgent/utils/text_indexer.py:520-702                         │
│     ┌─────────────────────────────────────────────────────────────┐         │
│     │ • 转义特殊字符: "4.1" (数字小数点自动加引号)                 │         │
│     │   代码: text_indexer.py:335-360                              │         │
│     │ • 双字段搜索:                                                │         │
│     │   - text MATCH query (英文, Porter stemmer)                 │         │
│     │   - text_jieba MATCH query (中文分词)                       │         │
│     │   代码: text_indexer.py:606-641                              │         │
│     │ • BM25 排序: ORDER BY bm25(chunks_fts)                      │         │
│     │ • 扩展上下文: 从相邻 chunk 获取更多文本                      │         │
│     │   代码: text_indexer.py:439-517                              │         │
│     │ • 正则过滤 (如果 use_regex): re.search(pattern, text)       │         │
│     │   代码: text_indexer.py:395-436                              │         │
│     └─────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ⑥ Grep 搜索 (全正则支持路径)                                                │
│     代码: generalAgent/utils/text_indexer.py:271-332                         │
│     ┌─────────────────────────────────────────────────────────────┐         │
│     │ • 从 file_metadata 读取 full_text                            │         │
│     │ • Python re.finditer(pattern, full_text)                    │         │
│     │ • 提取上下文 (context_chars)                                │         │
│     │ • 添加省略号 "..."                                           │         │
│     └─────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ⑦ 返回结果 (行 185-213)                                                     │
│     [{"chunk_id": 0, "page": 5, "text": "...", "score": 12.34}, ...]       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [索引管理] 全局索引数据库 (data/indexes.db)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/utils/text_indexer.py:29-807                             │
│                                                                              │
│  • MD5 去重: 相同内容只索引一次                                              │
│  • 过期检测: 24小时后标记为 stale, 重建索引                                  │
│  • 孤儿清理: 同名文件覆盖时, 自动删除旧 hash 的索引                          │
│    代码: text_indexer.py:731-753                                             │
│  • 定期清理: cleanup_old_indexes(days=30)                                   │
│    代码: text_indexer.py:755-783                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 自动上下文压缩

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Routing 触发] 自动压缩检测                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/graph/nodes/planner.py:308-356                           │
│                                                                              │
│  ① Token 追踪                                                                │
│     • cumulative_prompt_tokens (API 返回当前 context size)                   │
│     • TokenTracker.check_status() → {level, usage_ratio, message}          │
│                                                                              │
│  ② 阈值检测                                                                  │
│     • info: <75%                                                             │
│     • warning: 75-85%                                                        │
│     • critical: >95% → 设置 needs_compression=True                           │
│                                                                              │
│  ③ 路由决策                                                                  │
│     代码: generalAgent/graph/routing.py:37-45                                │
│     • needs_compression && !auto_compressed → "summarization"               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [Node: summarization] 压缩执行                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/graph/nodes/summarization.py:32-102                      │
│                                                                              │
│  ① 检查条件 (行 39-47)                                                       │
│     • 消息数 >= 15?                                                          │
│     • context.enabled?                                                       │
│                                                                              │
│  ② 调用 ContextManager.compress_context()                                   │
│     代码: generalAgent/context/manager.py:24-81                              │
│     ┌─────────────────────────────────────────────────────────────┐         │
│     │ A. 分层消息                                                  │         │
│     │   代码: context/compressor.py:232-288                        │         │
│     │   • system: 保留所有 SystemMessage                          │         │
│     │   • old: 待压缩 (早期消息)                                  │         │
│     │   • recent: 保留 (15% context window 或 10 条)              │         │
│     │                                                              │         │
│     │ B. LLM 压缩                                                  │         │
│     │   代码: context/compressor.py:301-341                        │         │
│     │   • Prompt: COMPACT_PROMPT (7 部分结构化摘要)               │         │
│     │   • 调用 base model (max_tokens=1440)                       │         │
│     │   • 生成摘要 SystemMessage                                   │         │
│     │                                                              │         │
│     │ C. 清理孤儿 ToolMessage                                      │         │
│     │   代码: context/compressor.py:342-379                        │         │
│     │   • 过滤没有对应 tool_call_id 的 ToolMessage                │         │
│     │                                                              │         │
│     │ D. 降级策略 (失败时)                                         │         │
│     │   代码: context/compressor.py:201-208                        │         │
│     │   • 简单截断: 保留最近 150 条                                │         │
│     └─────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ③ 更新状态 (行 70-80)                                                       │
│     • messages = compressed                                                  │
│     • auto_compressed_this_request = True                                    │
│     • compact_count += 1                                                     │
│     • cumulative_prompt_tokens = 0 (重置)                                    │
│                                                                              │
│  ④ 路由回 agent (继续处理原始请求)                                           │
│     代码: generalAgent/graph/routing.py:87-98                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### HITL 机制

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Tool Approval] 4层规则系统                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/hitl/approval_checker.py:40-231                          │
│  配置: generalAgent/config/hitl_rules.yaml                                   │
│                                                                              │
│  ① Layer 1: Custom Checkers (tool-specific logic)                          │
│     代码: approval_checker.py:157-231                                        │
│     示例: check_bash_command() 检测 rm -rf                                   │
│                                                                              │
│  ② Layer 2: Global Patterns (cross-tool detection)                         │
│     代码: approval_checker.py:86-122                                         │
│     配置: hitl_rules.yaml:global.risk_patterns                               │
│     • password/api_key/secret 检测                                           │
│     • /etc/passwd, DROP TABLE 检测                                           │
│                                                                              │
│  ③ Layer 3: Tool Config Rules                                               │
│     代码: approval_checker.py:124-155                                        │
│     配置: hitl_rules.yaml:tools.{tool_name}                                  │
│     • 每个工具独立配置                                                        │
│     • high_risk/medium_risk patterns                                         │
│                                                                              │
│  ④ Layer 4: Default Rules (fallback)                                        │
│     • SAFE_COMMANDS = ["ls", "pwd", "cat", ...]                             │
│     • 默认允许安全命令                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [ApprovalToolNode] 工具执行拦截                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/hitl/approval_node.py:35-110                             │
│                                                                              │
│  ① 拦截 tool_calls (行 48-69)                                                │
│     • 检查 AIMessage.tool_calls                                              │
│                                                                              │
│  ② 逐个检查审批 (行 64-92)                                                   │
│     • decision = approval_checker.check(tool_name, args)                    │
│     • needs_approval? → interrupt({"type": "tool_approval"})                │
│                                                                              │
│  ③ 用户决策处理 (行 84-107)                                                  │
│     • user_decision == "reject" → 生成错误 ToolMessage                       │
│     • user_decision == "approve" → 继续执行                                  │
│                                                                              │
│  ④ 执行工具 (行 109-110)                                                     │
│     • await ToolNode.ainvoke(state)                                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [ask_human] 主动请求用户输入                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/ask_human.py:26-101                        │
│                                                                              │
│  ① Agent 调用 (行 71-90)                                                     │
│     • ask_human(question, context, default, required)                       │
│     • 触发 interrupt({"type": "user_input_request"})                        │
│                                                                              │
│  ② CLI 处理 interrupt (行 430-465)                                           │
│     代码: generalAgent/cli.py:430-465                                        │
│     • 打印问题: 💬 question                                                  │
│     • 用户输入: answer                                                        │
│     • Resume: Command(resume=answer)                                        │
│                                                                              │
│  ③ 返回结果 (行 90-100)                                                      │
│     • answer (用户输入)                                                      │
│     • default (如果用户直接回车)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心工具实现

### 1. 文件操作工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  read_file(path)                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/file_ops.py:30-161                         │
│                                                                              │
│  [安全检查] (行 54-90)                                                       │
│  • 拒绝路径遍历: ".." 或 "/" 前缀 → Error                                    │
│  • 工作区隔离: path.relative_to(workspace_root)                              │
│  • 符号链接解析后仍需在 workspace 内                                         │
│                                                                              │
│  [读取策略]                                                                  │
│  ① 文本文件 (行 98-116)                                                      │
│     • <100KB: 完整内容                                                       │
│     • >100KB: 前 50K chars + 截断提示                                        │
│                                                                              │
│  ② 文档文件 (行 118-151)                                                     │
│     代码: generalAgent/utils/document_extractors.py                          │
│     [外部依赖: PyMuPDF, python-docx, openpyxl, python-pptx]                 │
│     • PDF/DOCX: 前 10 页 (~30K chars)                                       │
│     • XLSX: 前 3 sheets (~20K chars)                                        │
│     • PPTX: 前 15 slides (~25K chars)                                       │
│                                                                              │
│  [无 workspace 回退] (行 59-74)                                              │
│  • 允许读取项目 skills/ 目录 (只读访问 SKILL.md)                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  write_file(path, content)                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/file_ops.py:164-235                        │
│                                                                              │
│  [安全限制] (行 189-223)                                                     │
│  • 只能写入: uploads/, outputs/, temp/ (禁止 skills/)                        │
│  • 拒绝路径遍历: ".." 或 "/" 前缀                                            │
│  • 自动创建父目录: parent.mkdir(parents=True)                                │
│                                                                              │
│  [写入策略] (行 225-230)                                                     │
│  • 覆盖模式: 存在则覆盖                                                      │
│  • UTF-8 编码: encoding="utf-8"                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  edit_file(path, old_string, new_string, replace_all)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/edit_file.py:17-122                        │
│                                                                              │
│  [安全] (行 49-77)                                                           │
│  • 只能编辑: uploads/, outputs/, temp/                                       │
│                                                                              │
│  [替换逻辑] (行 87-109)                                                      │
│  ① 检查 old_string 存在性                                                    │
│  ② 统计出现次数                                                              │
│  ③ replace_all=False 且出现多次 → Error                                     │
│  ④ replace_all=True → 替换所有出现                                           │
│                                                                              │
│  [典型用法]                                                                  │
│  • 精确替换单个位置: replace_all=False (默认)                                │
│  • 批量重命名变量: replace_all=True                                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  list_workspace_files(directory)                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/file_ops.py:238-316                        │
│                                                                              │
│  [安全] (行 251-278)                                                         │
│  • 只能列出 workspace 内目录                                                 │
│  • 过滤隐藏文件: 跳过 .metadata.json, .indexes/                              │
│                                                                              │
│  [输出格式] (行 284-309)                                                     │
│  📁 uploads/                                                                 │
│  📄 uploads/report.pdf (1024 bytes)                                          │
│  📄 outputs/result.txt (256 bytes)                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. 搜索工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  find_files(pattern, path)                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/find_files.py:18-146                       │
│                                                                              │
│  [Glob 模式] (行 22-32)                                                      │
│  • "*": 匹配任意字符                                                         │
│  • "**": 递归匹配目录                                                        │
│  • "?": 匹配单个字符                                                         │
│  • "[abc]": 匹配字符集                                                       │
│  • "{pdf,docx}": 匹配多个扩展名                                              │
│                                                                              │
│  [执行] (行 86-106)                                                          │
│  • matches = search_path.glob(pattern)                                      │
│  • 过滤: 只返回文件, 跳过隐藏文件, 跳过 .indexes/                            │
│                                                                              │
│  [排序] (行 119)                                                             │
│  • 按修改时间降序 (newest first)                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  search_file(path, query, max_results, context_chars, use_regex)           │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/search_file.py:31-268                      │
│                                                                              │
│  [路由策略] (行 82-90)                                                       │
│  • 文本文件 → _search_text_file() (实时扫描)                                │
│  • 文档文件 → _search_document_file() (索引搜索)                             │
│                                                                              │
│  [文本文件搜索] (行 97-158)                                                  │
│  ① 逐行扫描: if query_lower in line.lower()                                 │
│  ② 提取上下文: 前后各 1 行                                                   │
│  ③ 高亮匹配: **match** (markdown bold)                                      │
│                                                                              │
│  [文档文件搜索] (行 161-213)                                                 │
│  [外部依赖: SQLite FTS5, jieba, PyMuPDF, python-docx, openpyxl, pptx]       │
│  ① 检查索引: index_exists() (行 165)                                         │
│  ② 创建索引: create_index() (首次或过期) (行 167-175)                        │
│  ③ 执行搜索: search_in_index() (行 178-182)                                  │
│     - FTS5 搜索 (简单查询)                                                   │
│     - FTS5 + re 后处理 (复杂正则)                                            │
│     - Grep full_text (超复杂正则)                                            │
│  ④ 格式化输出 (行 194-213)                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3. Bash 执行工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  run_bash_command(command, timeout)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/run_bash_command.py:18-96                  │
│                                                                              │
│  [执行环境] (行 42-66)                                                       │
│  • 工作目录: workspace_path (隔离)                                           │
│  • 环境变量:                                                                 │
│    - PATH: 继承系统 PATH (访问 brew, system tools)                           │
│    - HOME: workspace_path (隔离)                                             │
│    - AGENT_WORKSPACE_PATH: workspace_path                                    │
│    - VIRTUAL_ENV: venv path (如果在虚拟环境)                                 │
│                                                                              │
│  [安全限制]                                                                  │
│  • 默认超时: 30s                                                             │
│  • 工作目录限制: 只能访问 workspace                                          │
│                                                                              │
│  [执行] (行 68-85)                                                           │
│  • subprocess.run(command, shell=True, cwd=workspace_path, env=env)         │
│  • 返回 stdout + stderr                                                     │
│  • 失败: "Command failed (exit code N)"                                     │
│  • 超时: "Error: Command timeout (Ns)"                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4. 任务管理工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  todo_write(todos)                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/todo_write.py:12-96                        │
│                                                                              │
│  [数据结构]                                                                  │
│  todos: [                                                                    │
│    {                                                                         │
│      id: "uuid8",                                                            │
│      content: "任务描述",                                                     │
│      status: "pending" | "in_progress" | "completed",                       │
│      priority: "low" | "medium" | "high"                                    │
│    }                                                                         │
│  ]                                                                           │
│                                                                              │
│  [规则验证] (行 31-77)                                                       │
│  • 必须字段: content, status                                                 │
│  • 只能一个 in_progress (同一时间只做一件事)                                 │
│  • 自动生成 id (如果缺失)                                                    │
│  • 默认 priority: medium                                                     │
│                                                                              │
│  [状态更新] (行 83-93)                                                       │
│  • state["todos"] = todos                                                    │
│  • 返回 ToolMessage: "✅ TODO 列表已更新: N 个待完成, M 个已完成"             │
│                                                                              │
│  [集成 Planner]                                                              │
│  代码: generalAgent/graph/nodes/planner.py:237-281                           │
│  • Planner 读取 state["todos"]                                               │
│  • 生成动态 reminder (未完成任务提醒)                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5. 上下文管理工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  compact_context(strategy)                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/compact_context.py:53-164                  │
│                                                                              │
│  [外部依赖: LLM API (base model)]                                            │
│                                                                              │
│  [压缩策略] (行 56-63)                                                       │
│  • auto: 自动选择 (基于历史效果)                                             │
│  • compact: 详细摘要 (保留技术细节、文件路径、工具调用)                      │
│  • summarize: 极简摘要 (<200 字, 仅核心信息)                                 │
│                                                                              │
│  [执行流程]                                                                  │
│  ① 检查配置: CONTEXT_MANAGEMENT_ENABLED=true? (行 82-90)                     │
│  ② 检查消息数: len(messages) >= 15? (行 103-110)                             │
│  ③ 调用 ContextManager.compress_context() (行 115-126)                      │
│     代码: generalAgent/context/manager.py:24-81                              │
│  ④ 更新状态 (行 138-149)                                                     │
│     • messages = [RemoveMessage(REMOVE_ALL_MESSAGES)] + compressed           │
│     • compact_count += 1                                                     │
│     • cumulative_prompt_tokens = 0 (重置)                                    │
│                                                                              │
│  [返回] (行 129)                                                             │
│  • 压缩报告: 前/后消息数, tokens, 压缩率, 策略                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6. HITL 工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ask_human(question, context, default, required)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/ask_human.py:26-101                        │
│                                                                              │
│  [工作流]                                                                    │
│  ① Agent 调用 (行 71-90)                                                     │
│     • ask_human(question, ...)                                              │
│     • 触发 interrupt({type: "user_input_request", ...})                     │
│                                                                              │
│  ② CLI 捕获 interrupt (行 430-465)                                           │
│     代码: generalAgent/cli.py:430-465                                        │
│     • 打印问题给用户                                                          │
│     • 用户输入 answer                                                        │
│     • Resume: Command(resume=answer)                                        │
│                                                                              │
│  ③ 返回结果 (行 90-100)                                                      │
│     • answer (用户输入)                                                      │
│     • default (如果用户直接回车)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7. Agent 协作工具

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  delegate_task(task, max_loops)                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/tools/builtin/delegate_task.py:39-304                    │
│                                                                              │
│  • 独立上下文: context_id = subagent-{uuid8}                                 │
│  • 状态继承: mentioned_agents, workspace_path, uploaded_files               │
│  • HITL 支持: ask_human interrupt 传递给用户                                 │
│  • 实时输出: [subagent-{uuid8}] ...                                         │
│  • 结果检查: <200 chars → 自动请求详细摘要                                   │
│  • 返回 JSON: {ok, result, context_id, loops}                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  transfer_to_{agent_id}(task)                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  代码: generalAgent/agents/handoff_tools.py:22-191                           │
│                                                                              │
│  • 动态生成: 为每个 enabled agent 生成 handoff tool                          │
│  • 防循环检测:                                                               │
│    - agent_call_stack 检测 (agent → simple → agent 拒绝)                    │
│    - 深度限制 (最大 5 层)                                                    │
│  • 状态传递: agent_call_stack, agent_call_history, current_agent            │
│  • 返回 Command: Command(goto=agent_id, update={...})                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 外部依赖清单

### Python 包依赖

| 包名 | 用途 | 代码位置 |
|------|------|----------|
| `openai` | OpenAI-compatible API 客户端 | `generalAgent/models/registry.py` |
| `langchain-core` | LangChain 核心库 | 全局使用 |
| `langgraph` | LangGraph 状态图 | `generalAgent/graph/builder.py` |
| `langsmith` | Tracing (可选) | `generalAgent/telemetry/tracing.py` |
| `PyMuPDF` (fitz) | PDF 处理 | `generalAgent/utils/document_extractors.py:271-368` |
| `python-docx` | DOCX 处理 | `generalAgent/utils/document_extractors.py:373-465` |
| `openpyxl` | XLSX 处理 | `generalAgent/utils/document_extractors.py:470-603` |
| `python-pptx` | PPTX 处理 | `generalAgent/utils/document_extractors.py:608-744` |
| `jieba` | 中文分词 (可选) | `generalAgent/utils/text_indexer.py:132-151` |
| `sqlite3` | SQLite 数据库 (built-in) | `generalAgent/utils/text_indexer.py`, `shared/session/store.py` |
| `pydantic` | 数据验证 | `generalAgent/config/settings.py` |
| `pyyaml` | YAML 解析 | `generalAgent/config/*.py` |
| `mcp` | Model Context Protocol SDK | `generalAgent/tools/mcp/` |

### 外部服务

| 服务 | 用途 | 配置位置 |
|------|------|----------|
| DeepSeek/Moonshot/GLM/OpenAI | LLM API 提供商 | `.env` (MODEL_*) |
| LangSmith | Tracing/Observability (可选) | `.env` (LANGCHAIN_*) |
| MCP Servers | 外部工具服务 | `generalAgent/config/mcp_servers.yaml` |

### 本地存储

| 路径 | 用途 | 代码位置 |
|------|------|----------|
| `data/sessions.db` | 会话持久化 | `shared/session/store.py:22-142` |
| `data/indexes.db` | 文档索引 (FTS5) | `generalAgent/utils/text_indexer.py:29` |
| `data/workspace/{session_id}/` | 隔离工作区 | `shared/workspace/manager.py:55-107` |
| `logs/` | 日志文件 | `generalAgent/utils/logging_utils.py` |
| `uploads/` | 临时上传目录 | CLI 文件处理 |
| `skills/` | 技能包目录 | `generalAgent/skills/` |

---

## 关键配置文件

| 文件 | 用途 | 代码位置 |
|------|------|----------|
| `.env` | 环境变量 (API keys, 模型配置) | `generalAgent/config/settings.py` |
| `generalAgent/config/tools.yaml` | 工具配置 | `generalAgent/tools/config_loader.py` |
| `generalAgent/config/skills.yaml` | 技能配置 | `generalAgent/config/skill_config_loader.py` |
| `generalAgent/config/agents.yaml` | Agent 配置 | `generalAgent/agents/scanner.py` |
| `generalAgent/config/hitl_rules.yaml` | HITL 规则 | `generalAgent/hitl/approval_checker.py` |
| `generalAgent/config/mcp_servers.yaml` | MCP 服务器配置 | `generalAgent/tools/mcp/loader.py` |

---

## 完整工具清单

| 工具名称 | 分类 | 功能 | 代码位置 |
|----------|------|------|----------|
| `read_file` | 文件操作 | 读取文本/文档 | `tools/builtin/file_ops.py:30-161` |
| `write_file` | 文件操作 | 写入文件 | `tools/builtin/file_ops.py:164-235` |
| `edit_file` | 文件操作 | 精确替换 | `tools/builtin/edit_file.py:17-122` |
| `list_workspace_files` | 文件操作 | 列出目录 | `tools/builtin/file_ops.py:238-316` |
| `find_files` | 搜索 | 按文件名 (Glob) | `tools/builtin/find_files.py:18-146` |
| `search_file` | 搜索 | 按内容 (FTS5/Grep) | `tools/builtin/search_file.py:31-268` |
| `run_bash_command` | 执行 | Bash 命令 | `tools/builtin/run_bash_command.py:18-96` |
| `todo_write` | 任务管理 | TODO 列表 | `tools/builtin/todo_write.py:12-96` |
| `compact_context` | 上下文管理 | 压缩对话 | `tools/builtin/compact_context.py:53-164` |
| `ask_human` | HITL | 请求用户输入 | `tools/builtin/ask_human.py:26-101` |
| `delegate_task` | Agent 协作 | 委托子任务 | `tools/builtin/delegate_task.py:39-304` |
| `transfer_to_*` | Agent 协作 | Agent Handoff | `agents/handoff_tools.py:22-191` |
| `now` | 元数据 | 当前时间 | `tools/builtin/now.py` |
| `http_fetch` | 网络 | HTTP 请求 | `tools/builtin/http_fetch.py` (如果存在) |
| `google_search` | 网络 | Google 搜索 | `tools/builtin/google_search.py` |
| `jina_reader` | 网络 | Jina Reader | `tools/builtin/jina_reader.py` |

---

## 架构设计亮点

### 1. KV Cache 优化
- **固定 SystemMessage**: 启动时生成, 分钟级时间戳, 永不改变
- **动态 Reminders**: 追加到最后一条 HumanMessage (不污染 system prompt)
- **效果**: 70-90% KV Cache 复用, 60-80% 成本降低
- **代码**: `generalAgent/graph/nodes/planner.py:86-106, 370-386`

### 2. 三层工具架构
- **_discovered**: 所有扫描到的工具 (包括禁用的)
- **_tools**: 启用的工具 (立即可用)
- **load_on_demand()**: @mention 动态加载
- **代码**: `generalAgent/tools/registry.py:15-207`

### 3. 工作区隔离
- **独立目录**: `data/workspace/{session_id}/`
- **符号链接**: skills/ 只读
- **路径保护**: 工具只能访问 workspace 内文件
- **代码**: `shared/workspace/manager.py:55-107`

### 4. 智能搜索策略
- **简单查询** → FTS5 (高性能)
- **复杂正则** → FTS5 + Python re 后处理
- **超复杂正则** → 直接 Grep full_text
- **代码**: `generalAgent/utils/text_indexer.py:229-268, 520-702`

### 5. 内容感知分块
- **按段落/句子分块** (非固定长度)
- **20% 重叠** (避免信息丢失)
- **分文档类型优化** (PDF/DOCX/XLSX/PPTX)
- **代码**: `generalAgent/utils/document_extractors.py:26-181, 239-744`

### 6. 4层 HITL 规则
- **Layer 1**: Custom Checkers (工具特定逻辑)
- **Layer 2**: Global Patterns (跨工具检测)
- **Layer 3**: Tool Config Rules (配置驱动)
- **Layer 4**: Default Rules (安全命令白名单)
- **代码**: `generalAgent/hitl/approval_checker.py:40-231`

---

**文档版本**: v1.0
**最后更新**: 2025-01-XX
**维护者**: AgentGraph Team
