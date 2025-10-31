# AgentGraph TODO List

## 优先级说明
- 🔴 高优先级 - 核心功能，影响用户体验
- 🟡 中优先级 - 重要但可以分阶段实现
- 🟢 低优先级 - 优化性功能，可以延后

---

## 1. 🔴 暂停工具 (Pause/Resume)
**目标**: 用户可以中断当前模型请求，输入新要求后继续执行

**实现思路**:
- CLI 层面使用 ESC 键监听暂停信号
- 需要研究 LangGraph 的 `interrupt()` 机制是否支持用户主动中断
- 可能需要结合异步任务取消 (`asyncio.CancelledError`)
- 状态保存：暂停时保存当前 state，恢复时 merge 新指令

**待明确问题**:
- ❓ 暂停后是"丢弃当前 LLM 响应"还是"等待响应完成再暂停"？
- ❓ 新指令如何与原任务合并？是替换还是追加？
- ❓ 暂停是否需要保存中间状态（例如已执行的工具调用）？

**技术调研**:
- LangGraph 的 `interrupt()` 目前用于 HITL，是否支持 user-triggered interrupt？
- 参考 Claude Code 的 `/pause` 实现机制

---

## 2. 🟡 提前安排工作 (Task Queue)
**目标**: 用户可以提前输入多条指令，Agent 在任务间隙读取并更新行动指南

**实现思路**:
- 维护一个任务队列 (FIFO)
- Agent 每次完成一个任务后检查队列
- 将队列内容转化为系统提示或追加到 messages

**已知问题**:
- ⚠️ "实现机制有一些小问题" - 具体是什么问题？
  - 队列何时读取？每个 agent 轮次还是只在 finalize 节点？
  - 如何避免 Agent 在执行中途被新任务干扰？
  - 多任务优先级如何处理？

**待明确问题**:
- ❓ 用户是通过特殊命令（如 `/queue add`）还是自动检测多行输入？
- ❓ 队列任务是否需要用户确认后再执行？
- ❓ 任务之间是否有依赖关系（串行 vs 并行）？

**参考实现**:
- OpenAI Assistants API 的 thread message queue
- LangGraph 的 multi-turn conversation pattern

---

## 3. 🔴 Edit File 前强制 Read File
**目标**: 防止并发修改导致的文件冲突，确保 Agent 基于最新内容编辑

**实现思路**:
- 在 `Edit` tool 执行前，自动调用 `read_file` 获取最新内容
- 可以在 `file_ops.py` 的 `write_file` 工具中增加校验逻辑
- 或者在 `ApprovalChecker` 中增加 pre-check 规则

**技术方案**:
- **方案 A**: 修改 `Edit` tool，内部自动 read + 版本校验
- **方案 B**: 在 LLM 的 SystemMessage 中强调必须先 read
- **方案 C**: 使用文件锁或版本号机制（类似 Git）

**待明确问题**:
- ❓ 如果文件在 read 和 edit 之间被外部修改，如何处理？
- ❓ 是否需要引入文件版本号或 hash 校验？
- ❓ 这个规则是否对所有 Agent 生效还是只针对特定场景？

---

## 4. 🟡 多 Agent 机制优化
**目标**:
- 约束子 Agent 返回内容的 schema
- 研究主 Agent 的 context offload 机制

**子任务**:

### 4.1 子 Agent 返回值 Schema
- 定义标准返回格式（JSON schema）
- 在 `delegate_task` 工具中增加 schema 验证
- 参考 OpenAI Function Calling 的 response_format

### 4.2 Context Offload
- 主 Agent 如何剥离无关上下文给子 Agent
- 子 Agent 是否能访问主 Agent 的完整历史？
- 需要研究 LangGraph 的 parent-child context 传递机制

**待明确问题**:
- ❓ 子 Agent 返回的 schema 是固定的还是动态定义的？
- ❓ 主 Agent context offload 的触发条件是什么？
  - 上下文长度超过阈值？
  - 特定任务类型（如 code review）？
- ❓ Offload 后主 Agent 如何访问被 offload 的内容？

**参考资料**:
- LangGraph subgraphs and message passing
- AutoGPT 的 agent delegation 机制

---

## 5. 🟢 图片加载和描述
**目标**: 支持图片输入和多模态模型调用

**实现思路**:
- 文件上传时检测图片类型（.png, .jpg, .webp 等）
- 将图片编码为 base64 或使用 URL
- 调用 vision model（`MODEL_MULTIMODAL_ID`）生成描述
- 描述结果作为 context 传递给 Agent

**技术细节**:
- 已有 `ModelRegistry` 中的 `vision` 模型槽位
- 参考 LangChain 的 `ChatOpenAI` multimodal message format
- 可能需要在 `file_processor.py` 中增加图片处理逻辑

**待明确问题**:
- ❓ 图片描述是自动生成还是用户手动触发？
- ❓ 是否需要支持图片编辑（如裁剪、标注）？
- ❓ 多张图片如何处理（批量描述 vs 逐个处理）？

---

## 6. 🟡 Call Agent 工具参数传递
**目标**:
- 子 Agent 调用时可以传递文件、变量等参数
- 明确子 Agent 何时能看到主 Agent 的上下文

**实现思路**:

### 6.1 参数传递
- 扩展 `delegate_task` 工具的参数定义
- 支持传递文件路径、JSON 数据、变量引用
- 子 Agent workspace 是否共享主 Agent workspace？

### 6.2 上下文可见性
- **完全隔离**: 子 Agent 只看到传递的参数
- **部分共享**: 子 Agent 可以访问主 Agent 的特定 messages
- **完全共享**: 子 Agent 看到主 Agent 的完整历史

**待明确问题**:
- ❓ 参数传递格式是什么？JSON? 文件路径? 还是直接传递 state？
- ❓ 子 Agent 是否需要修改主 Agent 传递的文件？
- ❓ 上下文共享的粒度如何控制？用户可配置吗？

**参考实现**:
- LangGraph's `parent_config` mechanism
- CrewAI 的 agent task context

---

## 9. 🟢 垂直领域 Agent
**目标**: 开发专用 Agent，如 Deep Research Agent

**示例场景**:

### 9.1 Deep Research Agent
- 多轮网络搜索和信息整合
- 自动生成研究报告
- 引用来源和可信度评估

### 9.2 其他潜在领域
- Code Review Agent
- Data Analysis Agent
- Document Processing Agent

**实现路径**:
- 复用 `shared/` 基础设施
- 定制化 graph 结构和 tools
- 领域特定的 prompts 和 skills

**待明确问题**:
- ❓ Deep Research Agent 的具体功能需求是什么？
- ❓ 是否需要专用的 tools 和 skills？
- ❓ 优先级如何？哪个领域先做？