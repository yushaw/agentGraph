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

## 7. 🔴 Compact 工具
**目标**:
- 满足条件后提醒 LLM 主动 compact
- 上下文长度超限后自动 compact
- Compact 只处理部分 context，保留最新几条消息

**实现思路**:

### 7.1 触发条件
- **主动触发**: Agent 调用 `compact_context` 工具
- **自动触发**:
  - 上下文长度超过阈值（如 80% max_tokens）
  - 消息数量超过阈值（如 50 条）

### 7.2 Compact 策略
- **保留**:
  - SystemMessage
  - 最近 N 条消息（如最近 10 条）
  - 关键信息（TODOs, @mentions）
- **压缩**:
  - 中间历史消息 → 摘要
  - 工具调用结果 → 关键信息提取

### 7.3 收益评估
- 压缩前后 token 数量对比
- 如果收益 < 阈值（如压缩率 < 30%），提示使用 summarize

**待明确问题**:
- ❓ Compact 和 Summarize 的区别是什么？
  - Compact: 删除冗余，保留结构？
  - Summarize: 生成摘要，丢失细节？
- ❓ 如何判断 compact 收益太小？具体阈值是多少？
- ❓ Compact 后如何恢复被压缩的信息（如果需要）？

**参考实现**:
- LangChain's `ConversationSummaryMemory`
- Anthropic's "sliding window" context management

---

## 8. 🟡 Summarize 工具
**目标**: 当 compact 收益太小时，使用 summarize 生成摘要

**实现思路**:
- 调用 LLM 生成对话历史的摘要
- 摘要替换原始 messages，大幅减少 token 消耗
- 保留最近消息 + 摘要的混合模式

**Compact vs Summarize**:
| 维度 | Compact | Summarize |
|------|---------|-----------|
| 处理方式 | 删除冗余，保留原始消息 | 生成摘要，丢失细节 |
| 压缩率 | 中等（30-50%） | 高（70-90%） |
| 信息损失 | 低 | 中-高 |
| 适用场景 | 早期对话，信息密度低 | 后期对话，信息量大 |

**待明确问题**:
- ❓ Summarize 的触发条件？
  - Compact 后压缩率 < X%？
  - 用户手动调用？
  - 上下文长度超过硬限制？
- ❓ 摘要的粒度？
  - 每 N 轮对话一个摘要？
  - 按任务/主题分段摘要？
- ❓ 摘要是否需要用户确认？

**参考实现**:
- LangChain's `ConversationSummaryBufferMemory`
- Claude's "extended context" handling

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

---

## 10. 🔴 文档搜索与索引 (Document Search & Indexing)
**目标**: 提供强大的文档搜索能力，支持纯文本和结构化文档（PDF、Word、Excel 等）

**功能需求**:

### 10.1 纯文本搜索（已有基础）
- ✅ **Glob**: 按文件名模式搜索（`*.py`, `**/*.md`）
- ✅ **Grep**: 按内容正则搜索（支持 ripgrep）
- 🚧 **优化方向**:
  - 增加搜索结果排序（按相关度、修改时间）
  - 支持模糊搜索（fuzzy matching）
  - 搜索结果高亮和上下文预览

### 10.2 文档索引与搜索（新功能）
- **支持的文档类型**:
  - PDF（提取文本、OCR 扫描件）
  - Word/Excel/PowerPoint（.docx, .xlsx, .pptx）
  - Markdown/HTML
  - 代码文档（docstrings, comments）

- **索引策略**:
  - **全文索引**: 使用向量数据库（如 Chroma, FAISS）或倒排索引（Whoosh）
  - **混合检索**: BM25（关键词）+ 向量检索（语义）
  - **增量更新**: 文件修改时自动重新索引

- **搜索能力**:
  - 关键词搜索（精确匹配）
  - 语义搜索（向量相似度）
  - 混合搜索（关键词 + 语义，重排序）
  - 跨文档搜索（搜索整个 workspace）

**技术选型**:

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Whoosh** | 纯 Python，轻量级，无外部依赖 | 性能一般，不支持向量检索 | 小规模文档，关键词搜索 |
| **ChromaDB** | 向量数据库，语义搜索强，易集成 | 需要 embedding 模型，存储占用大 | 大规模文档，语义搜索 |
| **LlamaIndex** | 文档处理全流程，RAG 工具链完整 | 较重，依赖多，学习曲线陡 | 复杂 RAG 场景 |
| **LangChain Retriever** | 集成度高，支持多种向量数据库 | 抽象层多，性能损耗 | 快速原型，混合检索 |
| **PyPDF2 + FAISS** | 自定义灵活，性能好 | 需要自己实现索引和检索逻辑 | 定制化需求高 |

**推荐方案**（分阶段实现）:

### 阶段 1: 基础文档搜索（MVP）
```python
# 技术栈: PyPDF2 + python-docx + Whoosh
# 功能: 文档文本提取 + 关键词全文索引

search_documents(
    query="合同条款",
    doc_types=["pdf", "docx"],
    workspace="current"  # 或指定路径
)
```

### 阶段 2: 向量语义搜索
```python
# 技术栈: ChromaDB + sentence-transformers
# 功能: 语义检索，找到"意思相似"的内容

semantic_search(
    query="产品退货政策相关条款",
    top_k=5,
    similarity_threshold=0.7
)
```

### 阶段 3: 混合检索 + 重排序
```python
# 技术栈: BM25 + Vector Search + Reranker
# 功能: 关键词 + 语义双重保障，精准度最高

hybrid_search(
    query="2023年第四季度销售报告",
    strategy="hybrid",  # "keyword", "semantic", "hybrid"
    rerank=True  # 使用 LLM 重排序
)
```

**实现架构**:

```
generalAgent/
├── tools/
│   └── builtin/
│       └── document_search.py    # 搜索工具入口
├── search/
│   ├── __init__.py
│   ├── indexer.py                # 索引管理器
│   ├── extractors/
│   │   ├── pdf_extractor.py      # PDF 文本提取
│   │   ├── docx_extractor.py     # Word 文本提取
│   │   └── xlsx_extractor.py     # Excel 文本提取
│   ├── retrievers/
│   │   ├── keyword_retriever.py  # 关键词检索（Whoosh）
│   │   ├── vector_retriever.py   # 向量检索（ChromaDB）
│   │   └── hybrid_retriever.py   # 混合检索
│   └── reranker.py               # 结果重排序
└── config/
    └── search_config.yaml        # 索引配置
```

**索引存储**:
```
data/
├── workspace/{session_id}/
│   ├── uploads/          # 用户上传的文档
│   └── .index/           # 索引数据
│       ├── keyword/      # Whoosh 索引
│       ├── vector/       # ChromaDB 向量库
│       └── metadata.json # 索引元数据
```

**工具接口设计**:

```python
# 工具 1: 构建索引
@tool
def build_document_index(
    directory: str = "uploads",  # 索引哪个目录
    doc_types: list[str] = ["pdf", "docx", "xlsx"],
    index_type: str = "keyword"  # "keyword", "vector", "hybrid"
) -> str:
    """为指定目录的文档建立搜索索引"""
    pass

# 工具 2: 搜索文档
@tool
def search_documents(
    query: str,
    search_type: str = "keyword",  # "keyword", "semantic", "hybrid"
    doc_types: list[str] = None,  # 过滤文档类型
    top_k: int = 5,
    min_score: float = 0.0
) -> str:
    """在已索引的文档中搜索相关内容"""
    pass

# 工具 3: 更新索引
@tool
def update_document_index(
    file_path: str
) -> str:
    """文件修改后增量更新索引"""
    pass
```

**使用流程**:

```
User> 上传了 10 份 PDF 合同文件到 workspace

Agent> [自动检测到 PDF 文件]
       [调用 build_document_index(directory="uploads", doc_types=["pdf"])]
       ✓ 已为 10 份文档建立索引

User> 帮我找出所有提到"违约金"的合同条款

Agent> [调用 search_documents(query="违约金", doc_types=["pdf"])]
       找到 3 份合同包含相关条款：
       1. 合同A.pdf (第12页): "甲方违约需支付合同金额30%作为违约金"
       2. 合同B.pdf (第8页): "乙方提前终止合同，违约金为..."
       3. 合同C.pdf (第15页): "双方约定违约金上限为..."
```

**已确认需求**:
- ✅ **文档类型**：全部支持（PDF、Word、Excel、PPT、Markdown、HTML）
- ✅ **索引策略**：纯关键词检索（Whoosh），先不做向量语义搜索
- ✅ **索引时机**：文件上传时自动索引
- ✅ **索引持久化**：跨 session 共享（全局索引库）
- ✅ **文件验证**：使用 MD5 校验避免重复索引

**技术决策**:

### MVP 方案（阶段 1）
```
技术栈: Whoosh + PyPDF2 + python-docx + openpyxl + python-pptx
功能: 关键词全文索引，跨文档搜索
```

### 索引架构调整
```
data/
├── index/               # 全局索引库（跨 session 共享）
│   ├── whoosh/          # Whoosh 索引文件
│   ├── metadata.json    # 索引元数据（文件 MD5、路径、索引时间）
│   └── file_registry.json  # 文件注册表
└── workspace/{session_id}/
    └── uploads/         # 用户上传文件
```

### 索引流程
1. **文件上传** → 计算 MD5 hash
2. **去重检查** → 查询 `file_registry.json`
3. **文本提取** → 根据文件类型调用对应 extractor
4. **建立索引** → Whoosh 索引文档内容
5. **更新注册表** → 记录 MD5、路径、元数据

### 文件去重逻辑
```python
# file_registry.json 结构
{
  "md5_hash_1": {
    "original_path": "session_abc/uploads/doc1.pdf",
    "indexed_at": "2025-10-27T10:30:00Z",
    "file_size": 1024000,
    "doc_type": "pdf"
  },
  "md5_hash_2": {
    "original_path": "session_xyz/uploads/contract.docx",
    "indexed_at": "2025-10-27T11:00:00Z",
    "file_size": 512000,
    "doc_type": "docx"
  }
}
```

**性能优化**:
- MD5 计算使用流式读取（避免大文件内存溢出）
- 索引构建异步化（不阻塞用户交互）
- 搜索结果缓存（相同查询 5 分钟内复用）

**待解决问题**:
- ❓ 索引更新策略：如果用户上传同名但内容不同的文件，如何处理？
  - 方案 A: 覆盖旧索引（基于 MD5 判断内容是否变化）
  - 方案 B: 保留多版本（增加版本号字段）
- ❓ 索引清理：全局索引库会无限增长，何时清理？
  - 定期清理（如 30 天未访问的文档）？
  - 磁盘空间不足时触发？
  - 用户手动 `/clean-index` 命令？

**依赖清单**（MVP 阶段）:

```bash
# 核心依赖
pip install whoosh              # 全文索引引擎
pip install pypdf2              # PDF 文本提取
pip install python-docx         # Word 文档处理
pip install openpyxl            # Excel 文档处理
pip install python-pptx         # PowerPoint 文档处理
pip install markdown            # Markdown 解析
pip install beautifulsoup4      # HTML 解析
```

**性能考虑**（关键词索引）:
- **索引时间**: 1000 份文档预计 5-15 分钟（纯文本索引）
- **搜索时间**: 关键词搜索 < 100ms
- **存储占用**: 索引约为原文档大小的 10-20%
- **MD5 计算**: 流式读取，100MB 文件约 1-2 秒

**参考实现**:
- Whoosh 官方文档: https://whoosh.readthedocs.io/
- PyPDF2 text extraction best practices
- Document processing pipelines in enterprise search systems

---

## 实施建议

### 第一阶段（高优先级）
1. ✅ Edit File 前强制 Read File（安全性）
2. ✅ 暂停工具（用户体验）
3. ✅ Compact 工具（上下文管理）
4. ✅ 文档搜索与索引（核心能力提升）

### 第二阶段（中优先级）
5. 提前安排工作（任务队列）
6. 多 Agent 机制优化（schema + context offload）
7. Call Agent 参数传递

### 第三阶段（低优先级 + 扩展）
8. Summarize 工具
9. 图片加载和描述
10. 垂直领域 Agent

---

## 问题汇总（需要你的输入）

### 关于暂停工具
1. 暂停后是"丢弃当前 LLM 响应"还是"等待响应完成再暂停"？
2. 新指令如何与原任务合并？是替换还是追加？

### 关于任务队列
3. 用户是通过特殊命令（如 `/queue add`）还是自动检测多行输入？
4. 队列任务是否需要用户确认后再执行？

### 关于多 Agent
5. 子 Agent 返回的 schema 是固定的还是动态定义的？
6. 主 Agent context offload 的触发条件是什么？

### 关于 Call Agent 参数
7. 参数传递格式是什么？JSON? 文件路径? 还是直接传递 state？
8. 子 Agent 是否需要修改主 Agent 传递的文件？

### 关于 Compact/Summarize
9. Compact 和 Summarize 的区别具体是什么？
10. 如何判断 compact 收益太小？具体阈值是多少？

### 关于垂直领域 Agent
11. Deep Research Agent 的具体功能需求是什么？
12. 优先级如何？哪个领域先做？

### 关于文档搜索与索引
13. ✅ 文档类型：全部支持（PDF、Word、Excel、PPT、Markdown、HTML）
14. ✅ 索引策略：纯关键词（Whoosh），暂不做向量
15. ✅ 索引时机：文件上传时自动索引
16. ✅ 索引持久化：跨 session 共享（全局索引库）
17. ✅ 文件验证：MD5 校验去重
18. ❓ 索引更新策略：同名不同内容文件如何处理？覆盖 vs 多版本？
19. ❓ 索引清理策略：何时清理过期索引？定期 vs 手动 vs 空间触发？

---

## 备注
- 本文档会随着开发进度持续更新
- 每个任务完成后标记 ✅
- 遇到阻塞问题及时记录在对应任务下
