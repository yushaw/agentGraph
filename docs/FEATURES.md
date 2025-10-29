# 功能文档

> **注意**：本文档整合了 REQUIREMENTS_PART2、PART3、PART5 和 PART6 的内容，提供关于 AgentGraph 核心功能的全面技术细节。

## 目录

- [第一部分：Workspace 隔离](#第一部分workspace-隔离)
  - [1.1 Workspace 目录结构](#11-workspace-目录结构)
  - [1.2 文件操作工具](#12-文件操作工具)
  - [1.3 路径安全与隔离](#13-路径安全与隔离)
  - [1.4 Workspace 清理](#14-workspace-清理)
  - [1.5 会话管理](#15-会话管理)
  - [1.6 会话持久化 (SQLite)](#16-会话持久化-sqlite)
  - [1.7 模型路由](#17-模型路由)
- [第二部分：@Mention 系统](#第二部分mention-系统)
  - [2.1 三种 Mention 类型](#21-三种-mention-类型)
  - [2.2 Mention 分类](#22-mention-分类)
  - [2.3 按需加载工具](#23-按需加载工具)
  - [2.4 Skill 加载](#24-skill-加载)
  - [2.5 子代理委派](#25-子代理委派)
  - [2.6 动态系统提醒](#26-动态系统提醒)
- [第三部分：文件上传系统](#第三部分文件上传系统)
  - [3.1 文件类型检测](#31-文件类型检测)
  - [3.2 上传处理流程](#32-上传处理流程)
  - [3.3 文件引用注入](#33-文件引用注入)
  - [3.4 自动 Skill 推荐](#34-自动-skill-推荐)
  - [3.5 多文件支持](#35-多文件支持)
- [第四部分：消息历史管理](#第四部分消息历史管理)
  - [4.1 消息历史限制](#41-消息历史限制)
  - [4.2 Clean vs Truncate 策略](#42-clean-vs-truncate-策略)
  - [4.3 消息角色定义](#43-消息角色定义)
  - [4.4 System Prompt 管理](#44-system-prompt-管理)
- [第五部分：子代理系统](#第五部分子代理系统)
  - [5.1 子代理架构](#51-子代理架构)
  - [5.2 delegate_task 工具](#52-delegate_task-工具)
  - [5.3 上下文隔离](#53-上下文隔离)
  - [5.4 子代理系统提示](#54-子代理系统提示)
  - [5.5 使用场景](#55-使用场景)
- [第六部分：MCP 集成](#第六部分mcp-集成)
  - [6.1 MCP 架构](#61-mcp-架构)
  - [6.2 懒启动服务器](#62-懒启动服务器)
  - [6.3 双协议支持 (stdio/SSE)](#63-双协议支持-stdiose)
  - [6.4 MCP 配置](#64-mcp-配置)
  - [6.5 工具注册](#65-工具注册)
  - [6.6 使用示例](#66-使用示例)
- [第七部分：HITL (人机协同)](#第七部分hitl-人机协同)
  - [7.1 两种 HITL 模式](#71-两种-hitl-模式)
  - [7.2 ask_human 工具](#72-ask_human-工具)
  - [7.3 工具审批框架](#73-工具审批框架)
  - [7.4 审批规则系统](#74-审批规则系统)
- [第八部分：自动上下文压缩](#第八部分自动上下文压缩-new) ⭐ NEW
  - [8.1 核心机制](#81-核心机制)
  - [8.2 压缩策略](#82-压缩策略)
  - [8.3 配置选项](#83-配置选项)
  - [8.4 相关文件](#84-相关文件)

---

## 第一部分：Workspace 隔离

### 1.1 Workspace 目录结构

**需求**：每个会话拥有独立的 workspace 目录，灵感来自 OpenAI Code Interpreter 和 E2B。

**目录结构**：
```
data/workspace/{session_id}/
├── skills/           # 符号链接的 skills（只读）
│   └── pdf/
│       ├── SKILL.md
│       ├── forms.md
│       ├── reference.md
│       └── scripts/
├── uploads/          # 用户上传的文件
├── outputs/          # Agent 生成的输出
├── temp/             # 临时文件
└── .metadata.json    # 会话元数据
```

**实现**：
```python
# shared/workspace/manager.py:45-75
class WorkspaceManager:
    def __init__(self, base_dir: Path, skill_registry: SkillRegistry):
        self.base_dir = base_dir
        self.skill_registry = skill_registry
        self.workspace_path: Optional[Path] = None

    def create_workspace(self, session_id: str) -> Path:
        """为会话创建独立的 workspace"""

        workspace = self.base_dir / session_id
        workspace.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (workspace / "skills").mkdir(exist_ok=True)
        (workspace / "uploads").mkdir(exist_ok=True)
        (workspace / "outputs").mkdir(exist_ok=True)
        (workspace / "temp").mkdir(exist_ok=True)

        # 保存元数据
        metadata = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(workspace / ".metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        self.workspace_path = workspace
        return workspace
```

### 1.2 文件操作工具

Agent 可以访问一套全面的文件操作工具，遵循 Unix 哲学（单一职责原则）。

#### find_files - 文件名模式匹配

```python
# generalAgent/tools/builtin/find_files.py:30-60
@tool
def find_files(
    pattern: Annotated[str, "Glob 模式（例如：'*.pdf'、'**/*.py'、'*report*'）"],
    path: Annotated[str, "搜索目录（默认：workspace 根目录）"] = "."
) -> str:
    """通过名称模式查找文件（快速，不读取文件内容）。"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 解析搜索目录
    search_dir = resolve_workspace_path(path, workspace_root, must_exist=True)

    # 查找匹配的文件
    matches = list(search_dir.glob(pattern))

    # 过滤隐藏文件和索引目录
    matches = [
        f for f in matches
        if not any(part.startswith('.') for part in f.parts)
        and '.indexes' not in f.parts
    ]

    # 按修改时间排序（最新的在前）
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return format_results(matches)
```

**特性**：
- 支持 glob 模式（`*.pdf`、`**/*.txt`、`*report*`）
- 过滤隐藏文件和索引目录
- 按修改时间排序
- 显示文件大小

#### read_file - 文件内容读取（增强版）

```python
# generalAgent/tools/builtin/file_ops.py:45-120
@tool
def read_file(file_path: str) -> str:
    """从 workspace 读取文件（文本文件和文档）"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    target_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    file_ext = target_path.suffix.lower()
    settings = get_settings()

    # 策略 1：文本文件
    if file_ext in TEXT_EXTENSIONS:
        file_size = target_path.stat().st_size

        if file_size < settings.documents.text_file_max_size:
            # 读取完整内容
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            # 返回预览并提示使用搜索
            with open(target_path, "r", encoding="utf-8") as f:
                preview = f.read(settings.documents.text_preview_chars)
            return f"{preview}\n\n💡 提示：文件较大，使用 search_file 搜索特定内容"

    # 策略 2：文档文件（PDF、DOCX、XLSX、PPTX）
    if file_ext in DOCUMENT_EXTENSIONS:
        doc_info = get_document_info(target_path)

        if doc_info["pages"] <= 10:
            # 小文档：读取完整内容
            return extract_full_document(target_path)
        else:
            # 大文档：返回预览
            preview = extract_preview(
                target_path,
                max_pages=settings.documents.pdf_preview_pages,
                max_chars=settings.documents.pdf_preview_chars
            )
            return f"{preview}\n\n💡 提示：文档较大，使用 search_file 搜索特定内容"
```

**文档处理能力**：
- PDF：使用 pdfplumber 提取文本和表格
- DOCX：使用 python-docx 提取段落和表格
- XLSX：使用 openpyxl 读取工作表
- PPTX：使用 python-pptx 提取幻灯片文本

**长度限制策略**：
- 文本文件：< 100KB 完整读取，否则预览前 50KB
- PDF/DOCX：≤ 10 页完整，否则预览前 10 页
- XLSX：≤ 3 个工作表完整，否则预览前 3 个工作表
- PPTX：≤ 15 个幻灯片完整，否则预览前 15 个幻灯片

#### search_file - 内容搜索

```python
# generalAgent/tools/builtin/search_file.py:45-120
@tool
def search_file(
    path: Annotated[str, "相对于 workspace 的文件路径"],
    query: Annotated[str, "搜索关键词或短语"],
    max_results: Annotated[int, "返回的最大结果数"] = 5
) -> str:
    """在文件中搜索内容（支持文本文件和文档）。"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    target_path = resolve_workspace_path(path, workspace_root, must_exist=True)

    file_ext = target_path.suffix.lower()

    # 策略 1：文本文件 - 实时扫描
    if file_ext in TEXT_EXTENSIONS:
        return _search_text_file(target_path, query, max_results)

    # 策略 2：文档文件 - 基于索引的搜索
    if file_ext in DOCUMENT_EXTENSIONS:
        return _search_document_file(target_path, query, max_results)
```

**双策略搜索**：

1. **文本文件**：实时逐行扫描
   - 不区分大小写
   - 显示匹配行及前后各 1 行上下文
   - 高亮匹配文本

2. **文档文件**：基于索引的搜索
   - 首次搜索自动创建索引（存储在 `data/indexes/`）
   - 后续搜索即时完成（0.01s vs 0.04s）
   - 多策略评分系统：
     - 短语匹配：+10 分
     - Trigram 匹配：+5 分
     - Bigram 匹配：+3 分
     - 关键词精确匹配：+2 分
     - 关键词模糊匹配：+1 分
     - 覆盖率奖励：+0-2 分

#### 索引管理

```python
# generalAgent/utils/text_indexer.py:150-220
def create_index(file_path: Path) -> Path:
    """创建文档搜索索引"""

    # 计算 MD5 哈希
    file_hash = compute_file_hash(file_path)

    # 检查索引是否存在
    index_path = get_index_path(file_hash)
    if index_path.exists():
        # 仅更新元数据
        return index_path

    # 清理相同文件路径的旧索引（孤儿索引清理）
    cleanup_old_indexes_for_file(file_path, keep_hash=file_hash)

    # 提取并分块文档
    chunks = chunk_document(file_path)

    # 构建索引
    index_data = {
        "file_path": str(file_path),
        "file_hash": file_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chunks": [
            {
                "chunk_id": i,
                "page_num": chunk["page_num"],
                "text": chunk["text"],
                "keywords": extract_keywords(chunk["text"]),
                "bigrams": extract_ngrams(chunk["text"], n=2),
                "trigrams": extract_ngrams(chunk["text"], n=3)
            }
            for i, chunk in enumerate(chunks)
        ]
    }

    # 保存索引
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    return index_path
```

**索引存储策略**：
- **全局存储**：`data/indexes/{hash[:2]}/{hash}.index.json`
- **两级目录结构**：使用哈希的前 2 个字符作为子目录（256 个子目录，避免单目录文件过多）
- **MD5 去重**：相同内容只创建一次索引（跨会话复用）
- **孤儿索引清理**：上传同名但不同内容的文件时自动删除旧索引
- **陈旧检测**：24 小时未访问的索引标记为陈旧

#### 孤儿索引清理机制

```python
# generalAgent/utils/text_indexer.py:100-145
def cleanup_old_indexes_for_file(file_path: Path, keep_hash: str):
    """清理指定文件路径的旧索引（处理同名文件覆盖场景）

    场景：用户在同一会话中上传同名但内容不同的文件（不同的 MD5）
    - 旧索引变成孤儿（file_path 匹配但 hash 不同）
    - 此函数在创建新索引之前自动清理旧索引
    """

    if not INDEXES_DIR.exists():
        return 0

    deleted_count = 0

    # 扫描所有索引文件
    for index_file in INDEXES_DIR.rglob("*.index.json"):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            # 检查索引是否为相同文件路径但不同哈希
            if (index_data.get("file_path") == str(file_path)
                and index_data.get("file_hash") != keep_hash):

                index_file.unlink()
                deleted_count += 1
                LOGGER.info(f"已删除孤儿索引：{index_file.name}（被 {keep_hash[:8]} 替换）")

        except Exception as e:
            LOGGER.debug(f"检查索引 {index_file} 时出错：{e}")
            continue

    return deleted_count
```

**配置**：
```python
# generalAgent/config/settings.py:115-135
class DocumentSettings(BaseModel):
    """文档读取和索引设置"""

    # 文本文件限制
    text_file_max_size: int = 100_000        # 100KB
    text_preview_chars: int = 50_000         # 50KB 预览

    # 文档预览限制
    pdf_preview_pages: int = 10
    pdf_preview_chars: int = 30_000
    docx_preview_pages: int = 10
    docx_preview_chars: int = 30_000
    xlsx_preview_sheets: int = 3
    xlsx_preview_chars: int = 20_000
    pptx_preview_slides: int = 15
    pptx_preview_chars: int = 25_000

    # 搜索设置
    search_max_results_default: int = 5
    index_stale_threshold_hours: int = 24
```

**设计考虑**：
- **Unix 哲学**：三个单一职责的工具（find/read/search），避免功能混合
- **自动索引**：首次搜索自动创建索引，对用户透明
- **全局去重**：相同文件跨会话共享索引，节省存储和计算
- **孤儿清理**：自动处理同名文件覆盖场景，保持索引目录整洁
- **长度保护**：预览机制防止上下文溢出，引导用户使用搜索工具

**工具选择指南**：
- 使用 `find_files` 当：按名称/模式查找文件
- 使用 `read_file` 当：想查看文档内容/预览
- 使用 `search_file` 当：在文件中查找特定关键词或信息
- 对于大文档：始终优先使用 `search_file` 而不是 `read_file` 来查找特定内容

### 1.3 路径安全与隔离

**需求**：工具只能访问 workspace 内的文件，防止路径遍历攻击。

**两步验证机制**：
```python
# generalAgent/utils/file_processor.py:15-50
def resolve_workspace_path(
    file_path: str,
    workspace_root: Path,
    *,
    must_exist: bool = False,
    allow_write: bool = False,
) -> Path:
    """解析并验证 workspace 相对路径"""

    # 步骤 1：解析逻辑路径（跟随符号链接）
    logical_path = (workspace_root / file_path).resolve()

    # 步骤 2：检查解析后的路径是否在 workspace 内
    try:
        logical_path.relative_to(workspace_root.resolve())
    except ValueError:
        raise ValueError(f"路径在 workspace 外：{file_path}")

    # 步骤 3：如果需要，检查存在性
    if must_exist and not logical_path.exists():
        raise FileNotFoundError(f"文件未找到：{file_path}")

    # 步骤 4：检查写权限
    if allow_write:
        allowed_dirs = ["outputs", "temp", "uploads"]
        rel_path = logical_path.relative_to(workspace_root)

        if not any(rel_path.parts[0] == d for d in allowed_dirs):
            raise PermissionError(
                f"无法写入 {rel_path.parts[0]}/。"
                f"只有 {allowed_dirs} 可写。"
            )

    return logical_path
```

**应用到文件工具**：
```python
# generalAgent/tools/builtin/file_ops.py:45-60
@tool
def read_file(file_path: str) -> str:
    """从 workspace 读取文件"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 验证路径
    abs_path = resolve_workspace_path(
        file_path,
        workspace_root,
        must_exist=True,
        allow_write=False,
    )

    # 读取文件
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**设计考虑**：
- `resolve()` 处理符号链接和 `..` 路径
- `relative_to()` 检查路径是否在 workspace 内
- 写权限仅限于 outputs/、temp/、uploads/
- skills/ 目录为只读（符号链接）

**Skill 符号链接**：
```python
# shared/workspace/manager.py:110-145
def load_skill(self, skill_id: str) -> bool:
    """通过创建符号链接将 skill 加载到 workspace"""

    skill = self.skill_registry.get_skill(skill_id)
    if not skill:
        return False

    target_dir = self.workspace_path / "skills" / skill_id

    # 如果不存在则创建符号链接
    if not target_dir.exists():
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        target_dir.symlink_to(skill.path, target_is_directory=True)

    # 如果需要，安装依赖
    requirements = skill.path / "requirements.txt"
    if requirements.exists():
        self._install_skill_dependencies(skill_id, requirements)

    return True
```

**符号链接的好处**：
- 无需文件复制，节省空间
- Skill 更新自动反映到所有会话
- 只读访问防止意外修改

**list_workspace_files 符号链接处理**：
```python
# generalAgent/tools/builtin/file_ops.py:214-241
@tool
def list_workspace_files(directory: str = ".") -> str:
    """列出 workspace 目录中的文件"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 使用逻辑路径（不解析符号链接）
    logical_path = workspace_root / directory

    # 检查是否在 workspace 内
    try:
        logical_path.relative_to(workspace_root)
    except ValueError:
        return f"错误：路径在 workspace 外：{directory}"

    # 列出文件
    items = []
    for item in sorted(logical_path.iterdir()):
        rel_path = item.relative_to(workspace_root)

        if item.is_symlink():
            items.append(f"[SKILL] {rel_path}/")
        elif item.is_dir():
            items.append(f"[DIR]  {rel_path}/")
        else:
            size = item.stat().st_size
            items.append(f"[FILE] {rel_path} ({size} bytes)")

    return "\n".join(items)
```

### 1.4 Workspace 清理

**需求**：自动清理超过 7 天的 workspace。

**清理逻辑**：
```python
# shared/workspace/manager.py:195-225
def cleanup_old_workspaces(self, days: int = 7):
    """删除超过 N 天的 workspace"""

    if not self.base_dir.exists():
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted_count = 0

    for workspace in self.base_dir.iterdir():
        if not workspace.is_dir():
            continue

        # 读取元数据
        metadata_file = workspace / ".metadata.json"
        if not metadata_file.exists():
            continue

        with open(metadata_file) as f:
            metadata = json.load(f)

        # 检查年龄
        created_at = datetime.fromisoformat(metadata["created_at"])
        if created_at < cutoff:
            shutil.rmtree(workspace)
            deleted_count += 1

    return deleted_count
```

**触发时机**：
- 程序退出时自动清理
- 用户执行 `/clean` 命令

**实现**：
```python
# generalAgent/cli.py:95-105
async def handle_command(self, command: str):
    """处理斜杠命令"""

    if command == "/clean":
        count = self.workspace_manager.cleanup_old_workspaces(days=7)
        print(f"✓ 已清理 {count} 个旧 workspace")
        return True

    # ... 其他命令
```

### 1.5 会话管理

**需求**：管理会话的创建、加载、重置和保存生命周期。

**SessionManager 实现**：
```python
# shared/session/manager.py:25-120
class SessionManager:
    def __init__(
        self,
        session_store: SessionStore,
        workspace_manager: WorkspaceManager,
    ):
        self.session_store = session_store
        self.workspace_manager = workspace_manager
        self.current_session_id: Optional[str] = None

    def create_session(self, user_id: str = None) -> str:
        """创建带 workspace 的新会话"""

        thread_id = self._generate_thread_id()

        # 创建会话记录
        self.session_store.create_session(thread_id, user_id)

        # 创建 workspace
        self.workspace_manager.create_workspace(thread_id)

        self.current_session_id = thread_id
        return thread_id

    def load_session(self, thread_id_prefix: str) -> bool:
        """通过 ID 前缀加载现有会话"""

        # 查找匹配的会话
        sessions = self.session_store.list_sessions()
        matches = [s for s in sessions if s["thread_id"].startswith(thread_id_prefix)]

        if not matches:
            return False

        session = matches[0]
        thread_id = session["thread_id"]

        # 加载 workspace
        workspace = self.workspace_manager.base_dir / thread_id
        if not workspace.exists():
            return False

        self.workspace_manager.workspace_path = workspace
        self.current_session_id = thread_id
        return True

    def reset_session(self):
        """重置当前会话（清除状态但保留 workspace）"""

        if not self.current_session_id:
            return

        # 删除检查点（保留会话记录）
        self.session_store.delete_checkpoints(self.current_session_id)

        # 保留 workspace 但清空 temp/
        temp_dir = self.workspace_manager.workspace_path / "temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            temp_dir.mkdir()
```

**CLI 命令集成**：
```python
# generalAgent/cli.py:50-90
async def handle_command(self, command: str) -> bool:
    """处理斜杠命令"""

    if command == "/reset":
        self.session_manager.reset_session()
        print("✓ 会话已重置")
        return True

    if command == "/sessions":
        sessions = self.session_manager.list_sessions()
        for s in sessions:
            print(f"  {s['thread_id'][:8]} - {s['updated_at']}")
        return True

    if command.startswith("/load "):
        prefix = command[6:].strip()
        success = self.session_manager.load_session(prefix)
        if success:
            print(f"✓ 已加载会话：{self.session_manager.current_session_id}")
        else:
            print(f"✗ 会话未找到：{prefix}")
        return True

    if command == "/current":
        if self.session_manager.current_session_id:
            print(f"当前会话：{self.session_manager.current_session_id}")
        else:
            print("无活动会话")
        return True

    return False
```

### 1.6 会话持久化 (SQLite)

**需求**：使用 SQLite 数据库持久化会话状态，支持跨运行的对话恢复。

**数据库结构**：
```python
# shared/session/store.py:25-50
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT UNIQUE NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT
)
"""

CREATE_CHECKPOINTS_TABLE = """
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    checkpoint_data BLOB NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES sessions (thread_id)
)
"""
```

**SessionStore 接口**：
```python
# shared/session/store.py:60-125
class SessionStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def create_session(self, thread_id: str, user_id: str = None) -> dict:
        """创建新会话记录"""

    def get_session(self, thread_id: str) -> Optional[dict]:
        """通过 thread_id 检索会话"""

    def list_sessions(self, user_id: str = None, limit: int = 20) -> List[dict]:
        """列出最近的会话"""

    def delete_session(self, thread_id: str):
        """删除会话及所有检查点"""

    def save_checkpoint(self, thread_id: str, checkpoint: dict):
        """保存对话检查点"""

    def load_checkpoint(self, thread_id: str) -> Optional[dict]:
        """加载最新检查点"""
```

**与 LangGraph Checkpointer 集成**：
```python
# generalAgent/persistence/checkpointer.py:15-40
def build_checkpointer(db_path: str) -> Optional[SqliteSaver]:
    """为 LangGraph 构建 SQLite checkpointer"""

    if not db_path:
        return None

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # 连接到 SQLite
    conn = sqlite3.connect(str(db_file), check_same_thread=False)

    # 创建 LangGraph checkpointer
    checkpointer = SqliteSaver(conn)

    return checkpointer
```

**应用到 Graph**：
```python
# generalAgent/runtime/app.py:125-130
checkpointer = build_checkpointer(settings.observability.session_db_path)
if checkpointer:
    LOGGER.info("会话持久化已启用（SQLite）")

app = graph.build_state_graph(
    ...,
    checkpointer=checkpointer,
)
```

**自动保存会话**：
```python
# generalAgent/cli.py:250-270
async def handle_user_message(self, user_input: str):
    """处理用户消息"""

    # ... 创建用户消息 ...

    # 流式执行 graph
    async for chunk in self.app.astream(...):
        # ... 处理块 ...
        pass

    # 每轮后自动保存会话
    if self.session_manager.current_session_id:
        await self._save_session()

async def _save_session(self):
    """保存当前会话状态"""

    # LangGraph checkpointer 自动保存状态
    # 我们只需要更新会话元数据

    self.session_store.update_session(
        self.session_manager.current_session_id,
        metadata={"last_message": "...", "turn_count": 10}
    )
```

### 1.7 模型路由

**需求**：支持 5 个模型槽位，根据任务类型路由到不同模型。

**模型槽位定义**：
```python
# generalAgent/config/settings.py:45-75
class ModelSlots(BaseModel):
    base: Optional[ModelConfig] = None       # 基础对话
    reasoning: Optional[ModelConfig] = None  # 深度推理
    vision: Optional[ModelConfig] = None     # 视觉理解
    code: Optional[ModelConfig] = None       # 代码生成
    chat: Optional[ModelConfig] = None       # 聊天对话
```

**ModelConfig 定义**：
```python
class ModelConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    id: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
```

**环境变量映射**：
```python
# generalAgent/runtime/model_resolver.py:15-50
def resolve_model_configs(settings: Settings) -> Dict[str, dict]:
    """从环境变量解析模型配置"""

    configs = {}

    # 将提供商别名映射到规范名称
    aliases = {
        "MODEL_BASIC_": "base",
        "MODEL_REASONING_": "reasoning",
        "MODEL_MULTIMODAL_": "vision",
        "MODEL_CODE_": "code",
        "MODEL_CHAT_": "chat",
    }

    for prefix, slot in aliases.items():
        api_key = os.getenv(f"{prefix}API_KEY")
        if api_key:
            configs[slot] = {
                "api_key": api_key,
                "base_url": os.getenv(f"{prefix}BASE_URL"),
                "id": os.getenv(f"{prefix}ID"),
            }

    return configs
```

**模型注册表**：
```python
# generalAgent/models/registry.py:20-70
class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, BaseChatModel] = {}

    def register(self, slot: str, model: BaseChatModel):
        """为槽位注册模型"""
        self._models[slot] = model

    def get(self, slot: str) -> Optional[BaseChatModel]:
        """通过槽位名称获取模型"""
        return self._models.get(slot)

    def list_slots(self) -> List[str]:
        """列出所有已注册的槽位"""
        return list(self._models.keys())

def build_default_registry(model_ids: Dict[str, str]) -> ModelRegistry:
    """从模型 ID 构建注册表"""

    registry = ModelRegistry()

    for slot, model_id in model_ids.items():
        # 从环境获取配置
        config = resolve_model_config(slot)

        # 创建 ChatOpenAI 实例（适用于 OpenAI 兼容 API）
        model = ChatOpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model=model_id,
            temperature=config.get("temperature", 0.7),
        )

        registry.register(slot, model)

    return registry
```

**动态模型解析**：
```python
# generalAgent/runtime/model_resolver.py:55-95
class DefaultModelResolver(ModelResolver):
    def __init__(self, model_configs: Dict[str, dict]):
        self.configs = model_configs

    def resolve(self, state: AppState, node_name: str) -> str:
        """根据上下文解析模型"""

        # 检查用户偏好
        if state.get("model_pref"):
            return state["model_pref"]

        # 检查图像（需要视觉模型）
        if state.get("images"):
            if "vision" in self.configs:
                return "vision"

        # 节点特定路由
        if node_name == "agent":
            # 如果处理代码文件，使用代码模型
            if self._has_code_context(state):
                return "code"

            # 对于复杂任务使用推理模型
            if self._is_complex_task(state):
                return "reasoning"

            # 默认使用基础模型
            return "base"

        elif node_name == "finalize":
            # 对于最终响应使用聊天模型
            return "chat" if "chat" in self.configs else "base"

        return "base"
```

**应用到节点**：
```python
# generalAgent/graph/nodes/planner.py:285-295
def planner_node(state: AppState):
    """具有动态模型选择的 Agent 节点"""

    # 解析模型
    model_slot = model_resolver.resolve(state, "agent")
    model = model_registry.get(model_slot)

    # 调用模型
    result = model.invoke(messages, tools=visible_tools)

    return {"messages": [result], "loops": state["loops"] + 1}
```

---

## 第二部分：@Mention 系统

### 2.1 三种 Mention 类型

**需求**：系统识别用户输入的 @mention 并将其分类为三种类型：tool、skill、agent。

**分类逻辑**：
```python
# generalAgent/utils/mention_classifier.py:10-50
def classify_mention(
    mention: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
) -> Literal["tool", "skill", "agent"]:
    """将 @mention 分类为 tool、skill 或 agent"""

    # 如果存在，去除 @ 前缀
    name = mention.lstrip("@")

    # 优先级 1：检查是否为已注册或已发现的工具
    if tool_registry.has_tool(name):
        return "tool"

    # 优先级 2：检查是否为已注册的 skill
    if skill_registry.has_skill(name):
        return "skill"

    # 优先级 3：检查 agent 关键词
    agent_keywords = ["delegated agent", "agent", "助手", "代理"]
    if any(keyword in name.lower() for keyword in agent_keywords):
        return "agent"

    # 默认：视为工具（可能拼写错误或新工具）
    return "tool"
```

**分类优先级**：
1. **Tool**：已注册或已发现的工具
2. **Skill**：已注册的 skill
3. **Agent**：包含 agent 关键词
4. **默认**：降级为 tool（宽容处理）

### 2.2 Mention 分类

**需求**：从用户输入中提取所有 @mention。

**解析逻辑**：
```python
# generalAgent/cli.py:155-175
def parse_mentions(self, user_input: str) -> List[str]:
    """从用户输入中提取 @mention"""

    import re

    # 匹配 @word 或 @word-with-dash
    pattern = r"@([\w\-]+)"
    matches = re.findall(pattern, user_input)

    return list(set(matches))  # 去重
```

**应用场景**：
```python
# generalAgent/cli.py:240-260
async def handle_user_message(self, user_input: str):
    """处理带 @mention 支持的用户消息"""

    # 解析 @mention
    mentions = self.parse_mentions(user_input)

    # 分类 mention
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

    # ... 用 mention 更新状态
```

### 2.3 按需加载工具

**需求**：当用户 @mention 工具时，从已发现池加载到已注册池。

**加载逻辑**：
```python
# generalAgent/graph/nodes/planner.py:200-220
def build_visible_tools(...):
    """构建可见工具，包括 @mentioned 的工具"""

    visible = []
    seen_names = set()

    # ... 添加持久化和允许的工具 ...

    # 按需加载 @mentioned 的工具
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "tool" and mention not in seen_names:
            # 从已发现池加载
            tool = tool_registry.load_on_demand(mention)

            if tool:
                visible.append(tool)
                seen_names.add(mention)
            else:
                LOGGER.warning(f"工具 '{mention}' 未在注册表中找到")

    return visible
```

**ToolRegistry.load_on_demand**：
```python
# generalAgent/tools/registry.py:85-100
def load_on_demand(self, tool_name: str) -> Optional[Any]:
    """当 @mentioned 时从已发现池加载工具"""

    # 已注册，直接返回
    if tool_name in self._tools:
        return self._tools[tool_name]

    # 从已发现池加载
    if tool_name in self._discovered:
        tool = self._discovered[tool_name]
        self.register_tool(tool)  # 移动到已注册池
        LOGGER.info(f"✓ 按需加载工具：{tool_name}")
        return tool

    LOGGER.warning(f"✗ 工具未在已发现池中找到：{tool_name}")
    return None
```

### 2.4 State 更新与 Reminder 管理

**需求**：跟踪 @mentioned 的工具/技能/代理，并生成一次性提醒（避免重复）。

**双字段设计**：

为了防止 @mention 提醒重复出现，采用"历史字段 + 新增字段"的设计：

```python
# generalAgent/cli.py:126-137
# 更新 state:
# - new_mentioned_agents: 当前轮新 @mention 的 (用于生成 reminder)
# - mentioned_agents: 所有历史 @mention (累加保留，确保工具可用)
state["new_mentioned_agents"] = mentions if mentions else []

if mentions:
    existing_mentions = state.get("mentioned_agents", [])
    all_mentions = list(set(existing_mentions + mentions))
    state["mentioned_agents"] = all_mentions
```

**两种用途分离**：

| 用途 | 使用的字段 | 位置 | 目的 |
|------|-----------|------|------|
| 工具/技能加载 | `mentioned_agents` (历史) | planner.py:102-109 | 确保 @tool/@skill 功能可用 |
| Reminder 生成 | `new_mentioned_agents` (当前轮) | planner.py:177-192 | 只提醒本轮新 @mention |

**Reminder 生成** (planner.py:177-192):
```python
# 使用 NEW mentions (不是全部历史)
new_mentions = state.get("new_mentioned_agents", [])
new_classifications = classify_mentions(new_mentions, tool_registry, skill_registry)
new_grouped_mentions = group_by_type(new_classifications)

dynamic_reminder = build_dynamic_reminder(
    mentioned_tools=new_grouped_mentions.get('tools', []),
    mentioned_skills=new_grouped_mentions.get('skills', []),
    mentioned_agents=new_grouped_mentions.get('agents', []),
)
```

**Planner 清理** (planner.py:318-324):
```python
updates = {
    "messages": [output],
    "loops": current_loops + 1,
    "new_mentioned_agents": [],  # 用完即清，下次不再生成 reminder
}
```

**效果**：
- 第 1 轮（@pdf）：生成 `<system_reminder>用户提到了技能：pdf...</system_reminder>`
- 第 2 轮（继续对话）：不生成 @mention reminder（已清空 `new_mentioned_agents`）
- 第 3 轮（@http_fetch）：只生成 `http_fetch` 的 reminder，不再提醒 `pdf`
- 工具可用性：`pdf` 和 `http_fetch` 始终可用（保留在 `mentioned_agents` 中）

### 2.5 Skill 加载

**需求**：当用户 @mention skill 时，将 skill 加载到 workspace 并生成系统提醒。

**Skill 加载**：
```python
# generalAgent/cli.py:280-300
async def handle_user_message(self, user_input: str):
    """处理用户消息"""

    # ... 解析 mention ...

    # 将 mentioned skills 加载到 workspace
    for skill_id in mentioned_skills:
        success = self.workspace_manager.load_skill(skill_id)
        if success:
            print(f"✓ 已加载 skill：{skill_id}")
        else:
            print(f"✗ Skill 未找到：{skill_id}")

    # ... 继续处理消息 ...
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

**注入到 System Prompt**：
```python
# generalAgent/graph/nodes/planner.py:270-275
dynamic_reminder = build_dynamic_reminder(
    mentioned_skills=mentioned_skills,
    ...
)

if dynamic_reminder:
    system_parts.append(dynamic_reminder)
```

**Skill 配置管理**（2025-10-27 新增）：

Skills 通过 `generalAgent/config/skills.yaml` 配置文件管理：

```yaml
# generalAgent/config/skills.yaml
optional:
  pdf:
    enabled: false  # 不在目录中显示
    auto_load_on_file_types: ["pdf"]
    description: "PDF 处理"

  docx:
    enabled: true  # 在目录中显示
    auto_load_on_file_types: ["docx"]
    description: "DOCX 处理"
```

**Skills 目录过滤**：
- `build_skills_catalog(skill_registry, skill_config)` 只显示 `enabled: true` 的 skills
- 减少 SystemMessage 噪音，防止信息泄露
- 禁用的 skills 仍可通过 @mention 或文件上传触发

**动态文件上传提示**：
- 基于 `auto_load_on_file_types` 动态生成提示
- 示例：上传 `report.docx` → 生成 `[可用 @docx 处理]`
- 使用实际文件扩展名匹配（如 `"docx"`），而不是通用类型（如 `"office"`）

参见：`docs/SKILLS_CONFIGURATION.md`

### 2.5 子代理委派

**需求**：当用户 @mention agent 时，加载 delegate_task 工具。

**加载逻辑**：
```python
# generalAgent/graph/nodes/planner.py:205-225
def build_visible_tools(...):
    """构建可见工具"""

    # ... 添加其他工具 ...

    # 当 mention agent 时加载 delegate_task
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "agent":
            # 加载 delegate_task 工具
            tool = tool_registry.get_tool("delegate_task")
            if tool and "delegate_task" not in seen_names:
                visible.append(tool)
                seen_names.add("delegate_task")

    return visible
```

**系统提醒生成**：
```python
# generalAgent/graph/prompts.py:218-221
if mentioned_agents:
    agents_str = "、".join(mentioned_agents)
    reminders.append(
        f"<system_reminder>用户提到了代理：{agents_str}。"
        f"你可以使用 delegate_task 工具将任务委派给子代理执行。</system_reminder>"
    )
```

### 2.6 动态系统提醒

**需求**：根据上下文动态生成系统提醒，注入到系统提示中。

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
    """根据上下文构建动态系统提醒"""

    reminders = []

    # 活动 skill 提醒
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
            f"你可以使用 delegate_task 工具将任务委派给子代理执行。</system_reminder>"
        )

    # 图像（可选，当前禁用）
    # if has_images:
    #     reminders.append("<system_reminder>用户分享了图片...</system_reminder>")

    return "\n\n".join(reminders) if reminders else ""
```

**应用到 System Prompt**：
```python
# generalAgent/graph/nodes/planner.py:265-280
def planner_node(state: AppState):
    """Agent 节点"""

    # 构建系统提示部分
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # 添加 skills 目录（通过 skill_config 过滤）
    # 只有 skills.yaml 中 enabled: true 的 skills 会显示
    skills_catalog = build_skills_catalog(skill_registry, skill_config)
    if skills_catalog:
        system_parts.append(skills_catalog)

    # 添加动态提醒
    dynamic_reminder = build_dynamic_reminder(
        active_skill=state.get("active_skill"),
        mentioned_tools=...,
        mentioned_skills=...,
        mentioned_agents=...,
    )
    if dynamic_reminder:
        system_parts.append(dynamic_reminder)

    # 组合
    system_prompt = "\n\n---\n\n".join(system_parts)
```

---

## 第三部分：文件上传系统

### 3.1 文件类型检测

**需求**：根据文件扩展名自动检测文件类型。

**实现**：
```python
# generalAgent/utils/file_processor.py:55-85
def detect_file_type(file_path: Path) -> str:
    """从扩展名检测文件类型"""

    ext = file_path.suffix.lower()

    type_map = {
        # 文档
        ".pdf": "pdf",
        ".docx": "document",
        ".doc": "document",
        ".txt": "text",
        ".md": "markdown",
        ".rtf": "document",

        # 电子表格
        ".xlsx": "spreadsheet",
        ".xls": "spreadsheet",
        ".csv": "csv",

        # 代码
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".cpp": "cpp",

        # 数据
        ".json": "json",
        ".yaml": "yaml",
        ".xml": "xml",

        # 图像
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".gif": "image",
        ".bmp": "image",
        ".svg": "image",

        # 压缩包
        ".zip": "archive",
        ".tar": "archive",
        ".gz": "archive",
    }

    return type_map.get(ext, "unknown")
```

### 3.2 上传处理流程

**需求**：用户上传文件后，自动复制到 workspace/uploads/ 目录。

**CLI 处理**：
```python
# generalAgent/cli.py:180-215
def process_file_upload(self, file_path: str) -> dict:
    """处理用户上传的文件"""

    src_path = Path(file_path)

    # 验证存在性
    if not src_path.exists():
        return {"success": False, "error": "文件未找到"}

    # 检测类型
    file_type = detect_file_type(src_path)

    # 复制到 uploads/
    dest_path = self.workspace_path / "uploads" / src_path.name
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_path, dest_path)

    # 生成 workspace 相对路径
    rel_path = f"uploads/{src_path.name}"

    return {
        "success": True,
        "path": rel_path,
        "type": file_type,
        "name": src_path.name,
        "size": dest_path.stat().st_size,
    }
```

### 3.3 文件引用注入

**需求**：在用户消息中自动添加上传文件的引用信息。

**消息增强**：
```python
# generalAgent/cli.py:230-255
async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """处理带文件上传的用户消息"""

    # 处理每个上传的文件
    file_refs = []
    for file_path in uploaded_files:
        result = self.process_file_upload(file_path)

        if result["success"]:
            file_refs.append(
                f"- {result['name']} → {result['path']} "
                f"({result['type']}, {result['size']} bytes)"
            )
        else:
            file_refs.append(f"- {file_path} → 错误：{result['error']}")

    # 将文件引用注入消息
    if file_refs:
        file_list = "\n".join(file_refs)
        enhanced_input = f"{user_input}\n\n上传的文件：\n{file_list}"
    else:
        enhanced_input = user_input

    # 创建 HumanMessage
    message = HumanMessage(content=enhanced_input)

    # ... 继续执行 graph ...
```

**消息示例**：
```
User> 帮我分析这个 PDF

上传的文件：
- report.pdf → uploads/report.pdf (pdf, 245678 bytes)
```

### 3.4 State 更新与 Reminder 管理

**需求**：跟踪上传的文件，并生成一次性提醒（避免重复）。

**双字段设计**：

为了防止文件上传提醒重复出现，采用"历史字段 + 新增字段"的设计：

```python
# generalAgent/cli.py:222-228
# 更新 state:
# - new_uploaded_files: 当前轮新上传的文件 (用于生成 reminder)
# - uploaded_files: 所有历史上传文件 (累加保留)
state["new_uploaded_files"] = [asdict(f) for f in processed_files]
if processed_files:
    existing_files = state.get("uploaded_files", [])
    state["uploaded_files"] = existing_files + [asdict(f) for f in processed_files]
```

**Reminder 生成** (planner.py:251-256):
```python
# 只从 new_uploaded_files 生成 reminder (不是 uploaded_files)
new_uploaded_files = state.get("new_uploaded_files", [])
file_upload_reminder = ""
if new_uploaded_files:
    file_upload_reminder = build_file_upload_reminder(new_uploaded_files, skill_config)
```

**Planner 清理** (planner.py:310-315):
```python
updates = {
    "messages": [output],
    "loops": current_loops + 1,
    "new_uploaded_files": [],  # 用完即清，下次不再生成 reminder
}
```

**效果**：
- 第 1 轮（上传文件）：生成 `<system_reminder>用户上传了 1.pdf...</system_reminder>`
- 第 2 轮（继续对话）：不生成文件上传 reminder（已清空 `new_uploaded_files`）
- 历史记录：`uploaded_files` 仍然保留所有上传过的文件

### 3.5 自动 Skill 推荐

**需求**：根据上传的文件类型自动推荐相关 skills。

**推荐逻辑**：
```python
# generalAgent/cli.py:260-285
def recommend_skills_for_file(self, file_type: str) -> List[str]:
    """根据文件类型推荐 skills"""

    recommendations = {
        "pdf": ["pdf", "document"],
        "spreadsheet": ["excel", "data"],
        "image": ["image", "vision"],
        "code": ["code", "lint"],
        "document": ["document", "text"],
    }

    return recommendations.get(file_type, [])

async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """处理带自动 skill 推荐的消息"""

    # ... 处理上传 ...

    # 推荐 skills
    for file_result in upload_results:
        if file_result["success"]:
            skills = self.recommend_skills_for_file(file_result["type"])

            if skills:
                print(f"💡 推荐技能：{', '.join(['@' + s for s in skills])}")

    # ... 继续 ...
```

**输出示例**：
```
✓ 已上传：report.pdf → uploads/report.pdf
💡 推荐技能：@pdf, @document
```

### 3.5 多文件支持

**需求**：支持一次上传多个文件。

**CLI 接口**：
```python
# generalAgent/cli.py:120-150
async def run(self):
    """主 CLI 循环"""

    while True:
        user_input = input("You> ")

        # 检查 /upload 命令
        if user_input.startswith("/upload "):
            file_paths = user_input[8:].strip().split()

            # 处理多个文件
            for file_path in file_paths:
                result = self.process_file_upload(file_path)
                if result["success"]:
                    print(f"✓ 已上传：{result['name']}")
                else:
                    print(f"✗ 失败：{file_path}")

            continue

        # 正常消息处理
        await self.handle_user_message(user_input)
```

**使用示例**：
```bash
You> /upload report.pdf data.xlsx notes.txt
✓ 已上传：report.pdf
✓ 已上传：data.xlsx
✓ 已上传：notes.txt

You> 帮我分析这三个文件
```

---

## 第四部分：消息历史管理

### 4.1 消息历史限制

**需求**：限制保留的消息历史数量以防止上下文溢出。

**配置**：
```bash
# .env
MAX_MESSAGE_HISTORY=40  # 默认 40，范围 10-100
```

**设置定义**：
```python
# generalAgent/config/settings.py:85-95
class GovernanceConfig(BaseModel):
    max_message_history: int = Field(
        default=40,
        ge=10,
        le=100,
        description="保留的最大消息历史数"
    )
    max_loops: int = Field(
        default=100,
        ge=1,
        le=500,
        description="最大循环迭代次数"
    )
```

### 4.2 Clean vs Truncate 策略

**需求**：提供两种消息清理策略：Clean（清理中间步骤）和 Truncate（简单截断）。

**Clean 策略（推荐）**：
```python
# generalAgent/utils/message_utils.py:15-70
def clean_messages(
    messages: List[BaseMessage],
    max_history: int = 40,
) -> List[BaseMessage]:
    """通过删除中间工具调用来清理消息"""

    if len(messages) <= max_history:
        return messages

    # 保留第一条消息（system/user）
    first_msg = messages[0]

    # 处理剩余消息
    recent = messages[1:]

    # 识别完整的轮次（user → assistant → [tools] → assistant）
    turns = []
    current_turn = []

    for msg in recent:
        current_turn.append(msg)

        # 轮次以 assistant 消息结束（无 tool_calls）
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            turns.append(current_turn)
            current_turn = []

    # 保留最后 N 个轮次
    max_turns = max_history // 4  # 估计每轮约 4 条消息
    kept_turns = turns[-max_turns:]

    # 展平
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
    """简单截断：保留第一条 + 最后 N 条"""

    if len(messages) <= max_history:
        return messages

    return [messages[0]] + messages[-(max_history - 1):]
```

**应用到节点**：
```python
# generalAgent/graph/nodes/planner.py:290-305
def planner_node(state: AppState):
    """Agent 节点"""

    messages = state["messages"]

    # 如果太长则清理消息
    max_history = settings.governance.max_message_history
    if len(messages) > max_history:
        messages = clean_messages(messages, max_history)

    # ... 用清理后的消息调用模型 ...
```

**Clean vs Truncate 比较**：

| 策略 | 优点 | 缺点 | 使用场景 |
|----------|-----------|---------------|-----------|
| Clean | 保持对话完整性，保留完整轮次 | 实现复杂，可能保留过多 | 多轮对话，复杂任务 |
| Truncate | 简单快速，可预测 | 可能切断工具调用链 | 简单对话，实验环境 |

### 4.3 消息角色定义

**需求**：LangChain 消息类型及其角色。

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
# 轮次 1：用户提问
messages = [
    HumanMessage(content="帮我读取 uploads/data.txt"),
]

# 轮次 2：Agent 调用工具
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

# 轮次 3：工具返回结果
messages.append(
    ToolMessage(
        content="文件内容：...",
        tool_call_id="call_123",
    )
)

# 轮次 4：Agent 回应用户
messages.append(
    AIMessage(content="文件内容是：...")
)
```

### 4.4 System Prompt 管理

**需求**：System prompt 不存储在消息历史中，而是在每次调用时动态注入。

**实现**：
```python
# generalAgent/graph/nodes/planner.py:265-285
def planner_node(state: AppState):
    """Agent 节点"""

    # 动态构建系统提示
    system_prompt = build_system_prompt(state)

    # 获取消息历史（无系统消息）
    messages = state["messages"]

    # 使用系统提示调用模型
    result = model.invoke(
        messages,
        system=system_prompt,  # 运行时注入
    )
```

**好处**：
- 系统提示不占用消息历史配额
- 每次可以根据上下文更新系统提示
- 避免系统提示被清理

---

## 第五部分：子代理系统

### 5.1 子代理架构

**需求**：主 Agent 可以将独立的子任务委派给子代理执行。

**核心概念**：
- 子代理拥有独立的上下文（context_id + parent_context）
- 子代理使用相同的 graph 和工具
- 子代理无法访问父 agent 的消息历史
- 子代理执行完成后返回结果

**优势**：
- 避免主 Agent 上下文累积
- 任务失败不污染主历史
- 支持多个子任务的并行执行

### 5.2 delegate_task 工具

**需求**：通过工具调用创建和执行子代理，将复杂任务委派给独立的上下文执行。

**工具定义**：
```python
# generalAgent/tools/builtin/delegate_task.py:26-60
@tool
async def delegate_task(task: str, max_loops: int = 50) -> str:
    """将独立子任务委派给专用子 agent 执行（适合需要多轮迭代的任务）

    ⚠️ **重要：子 agent 在独立上下文中运行**
    - 子 agent 看不到主对话历史

    **何时使用：**
    - 需要多轮工具调用的复杂子任务（深度研究、反复尝试、大文档分析）
    - 可能产生大量中间结果的任务（网页搜索、多次搜索、批量文件处理），避免污染主对话

    **任务描述要求：**
    必须包含：
    1. 目标是什么
    2. 需要哪些上下文信息
    3. 期望的返回格式（Markdown 表格、JSON、文本摘要等）

    Args:
        task: 详细的任务描述（必须自包含！）

    Examples:
        # 深度搜索
        delegate_task("搜索 src/ 目录下所有使用 old_api() 的代码。"
                      "要求：记录文件路径、行号、调用上下文。"
                      "返回：Markdown 表格 [文件 | 行号 | 代码片段]")

        # 反复调试
        delegate_task("运行脚本 scripts/migrate.py，如果出错则分析并修复，重复直到成功。"
                      "返回：1) 最终可运行的代码，2) 遇到的问题和解决方案")

        # 大文档分析
        delegate_task("分析 uploads/report.pdf（80页）："
                      "1) 提取所有表格数据"
                      "2) 计算关键指标（收入、支出、利润）"
                      "返回：结构化 JSON")
    """
```

**实现逻辑**：
```python
# generalAgent/tools/builtin/delegate_task.py:50-120
def _execute_delegated agent(task: str, max_loops: int) -> str:
    """在隔离的上下文中执行子代理"""

    # 获取 app graph（由 runtime/app.py 设置）
    app = get_app_graph()
    if not app:
        return "错误：应用程序 graph 不可用"

    # 生成子代理上下文 ID
    delegated agent_id = f"delegated agent_{uuid.uuid4().hex[:8]}"

    # 从环境获取父状态
    parent_context = os.environ.get("AGENT_CONTEXT_ID", "main")
    workspace_path = os.environ.get("AGENT_WORKSPACE_PATH")

    # 为子代理构建初始状态
    initial_state = {
        "messages": [HumanMessage(content=task)],
        "images": [],
        "active_skill": None,
        "allowed_tools": [],
        "mentioned_agents": [],
        "persistent_tools": [],
        "model_pref": None,
        "todos": [],
        "context_id": delegated agent_id,      # 唯一上下文
        "parent_context": parent_context,  # 链接到父级
        "loops": 0,
        "max_loops": max_loops,
        "workspace_path": workspace_path,  # 共享 workspace
        "thread_id": f"sub_{delegated agent_id}",  # 唯一线程
    }

    # 执行子代理 graph
    try:
        result = app.invoke(initial_state)

        # 提取最终响应
        final_message = result["messages"][-1]
        return final_message.content

    except Exception as e:
        return f"子代理执行失败：{str(e)}"
```

### 5.3 上下文隔离

**需求**：子代理和父 agent 的上下文完全隔离。

**隔离机制**：

1. **独立的 context_id**：
```python
parent_context_id = "main"
delegated agent_context_id = "delegated agent_a1b2c3d4"
```

2. **独立的消息历史**：
```python
# 父消息
parent_messages = [
    HumanMessage("帮我分析这个项目"),
    AIMessage("我来分析..."),
    # ... 10+ 条消息 ...
]

# 子代理消息（全新开始）
delegated agent_messages = [
    HumanMessage("读取 uploads/README.md 并总结")
]
```

3. **共享 workspace**：
```python
# 两者共享相同的 workspace
workspace_path = "/data/workspace/session_123/"
```

4. **独立的 thread_id**：
```python
parent_thread_id = "session_123"
delegated agent_thread_id = "sub_a1b2c3d4"
```

**检测子代理上下文**：
```python
# generalAgent/graph/nodes/planner.py:50-60
def planner_node(state: AppState):
    """Agent 节点"""

    is_delegated agent = state.get("parent_context") is not None

    if is_delegated agent:
        # 为子代理修改系统提示
        system_prompt = DELEGATED_AGENT_SYSTEM_PROMPT
    else:
        system_prompt = PLANNER_SYSTEM_PROMPT
```

### 5.4 子代理系统提示

**需求**：子代理使用不同的系统提示，强调任务执行和完整摘要。

**关键改进（基于 Kimi-CLI 和 Gemini-CLI 最佳实践）**:

1. **强调"最后一条消息"隔离**: 主 Agent 只能看到子 Agent 的最后一条消息，无法看到工具调用历史
2. **完整摘要要求**: 子 Agent 必须在最后消息中包含完整的执行过程和结果
3. **延续机制**: 如果子 Agent 响应过短（< 200 字符），自动请求详细摘要（最多 1 次）

**子代理提示**：
```python
# generalAgent/graph/prompts.py:73-105
SUBAGENT_SYSTEM_PROMPT = """你是任务执行器（Subagent），负责完成主 Agent 委托的具体任务。

⚠️ **重要：你在独立上下文中运行**
- 所有 `user` 消息都来自主 Agent（不是真实用户）
- **主 Agent 看不到你的对话历史，只能看到你的最后一条消息**
- 因此你必须在最后消息中提供完整摘要

**最后消息必须包含：**
1. **做了什么**：使用了哪些工具、读取了哪些文件、尝试了什么方法
2. **发现了什么**：关键信息、问题分析、数据结果
3. **结果是什么**：文件路径、具体数据、建议、下一步行动

**如果修改了文件，必须说明：**
- 修改了哪些文件（完整路径）
- 修改了什么内容
- 为什么修改

**示例摘要：**
"任务完成！搜索了 src/ 下 15 个文件，找到 8 处使用 old_api() 的代码：
1. src/auth.py:45 - 登录函数中调用
2. src/user.py:123 - 用户信息获取
...
建议：这些调用可以统一迁移到 new_api() 接口。"

核心原则：
- 目标导向：只完成任务描述中的具体目标
- 直接执行：收到任务后立即使用工具完成，无需寒暄
- 完整摘要：最后消息必须包含完整的执行过程和结果

限制：不要询问用户（无法使用 ask_human 工具）

技能系统：Skills 是知识包，使用 read_file 读取 `skills/{{skill_id}}/SKILL.md` 获取指导
"""
```

**延续机制实现**:
```python
# generalAgent/tools/builtin/delegate_task.py:146-191
# Check if result is too brief (< 200 chars), request more detailed summary (max 1 retry)
if len(result_text) < 200:
    print(f"[subagent-{context_id[:8]}] ⚠️ 结果太简短（{len(result_text)} chars），请求更详细的摘要...\n")

    # Create continuation prompt
    continuation_prompt = HumanMessage(content="""你的上一次回复太简短了（< 200 字符）。

请提供更详细的摘要，包括：
1. 你做了什么（使用了哪些工具，读取了哪些文件）
2. 发现了什么（关键信息、错误、解决方案）
3. 结果是什么（文件路径、函数名、配置等）

**重要**：主 Agent 无法看到你的工具调用历史，只能看到你的最终回复！""")

    # Continue execution with the continuation prompt (max 1 retry)
    async for state_snapshot in app_graph.astream(
        {**final_state, "messages": messages + [continuation_prompt]},
        config=config,
        stream_mode="values"
    ):
        final_state = state_snapshot
        # ... handle continuation ...
```

**子 agent 用户交互支持** (2025-10-28 新增):

子 agent 现在**可以使用 ask_human 工具**向用户提问：

```python
# 子 agent 执行中可以询问用户
[subagent-abc12345] Starting execution...
[subagent-abc12345] 💬 您想预订哪个城市的酒店？
> 北京
[subagent-abc12345] 好的，正在搜索北京的酒店...
```

**实现机制**：
- delegate_task 在执行后检查 interrupt (generalAgent/tools/builtin/delegate_task.py:137-198)
- 检测到 `user_input_request` 类型的 interrupt 时，打印问题并获取用户输入
- 使用 `Command(resume=answer)` 恢复子 graph 执行
- 问题前缀带 `[subagent-xxx]` 以区分来自子 agent

**主 Agent vs 子 Agent 提示比较**：

| 维度 | 主 Agent | 子 Agent |
|-----------|-----------|-----------|
| 风格 | 友好对话 | 任务执行 |
| 输出 | 解释 + 结果 | 仅结果 |
| 循环 | 长循环（100+） | 短循环（50） |
| 用户交互 | ✅ 可以询问 (ask_human) | ✅ 可以询问 (ask_human) |
| 工具嵌套 | ✅ 可以调用 delegate_task | ❌ 不能调用 delegate_task (防止嵌套) |

### 5.5 使用场景

**需求**：明确何时使用子代理。

**推荐场景**：

1. **独立的子目标**：
```python
# 主任务：分析项目
# 子任务：读取并总结 README.md
delegate_task(task="读取 uploads/README.md 并总结核心功能（不超过 3 句话）")
```

2. **多步骤操作**：
```python
# 子任务：调试脚本
delegate_task(
    task="运行 temp/script.py，如果出错则修复，直到成功运行",
    max_loops=20,
)
```

3. **避免上下文污染**：
```python
# 父 Agent 已有 30 条消息
# 将文件转换任务委派给子 Agent（失败不影响父历史）
delegate_task(task="将 uploads/1.pdf 转换为图片，保存到 outputs/pdf_images/")
```

**不推荐场景**：
- 需要用户交互的任务（子代理无法询问用户）
- 需要访问父 agent 上下文的任务（上下文隔离）
- 简单的单步操作（直接调用工具更快）

---

## 第六部分：MCP 集成

### 6.1 MCP 架构

**背景**：MCP（Model Context Protocol）是将外部工具和服务连接到 Agent 的标准协议。通过 MCP 集成，AgentGraph 可以：

- 连接到外部服务，如文件系统、GitHub、数据库
- 使用社区提供的标准 MCP 服务器
- 无需修改核心代码即可扩展 Agent 能力

**架构层次**：

```
应用层
    ↓
 ToolRegistry（统一工具接口）
    ↓
MCPToolWrapper（LangChain BaseTool）
    ↓
MCPServerManager（生命周期管理）
    ↓
MCPConnection（连接层抽象）
    ↓
MCP Server 进程
```

**关键组件**：

#### 1. MCPConnection（连接层）

**职责**：封装底层通信协议

**文件**：`generalAgent/tools/mcp/connection.py`

**接口**：
```python
class MCPConnection(ABC):
    @abstractmethod
    async def connect(self) -> ClientSession:
        """建立连接，返回 MCP ClientSession"""

    @abstractmethod
    async def close(self) -> None:
        """关闭连接，清理资源"""
```

**实现**：
- `StdioMCPConnection`：Stdio 模式（本地进程）
- `SSEMCPConnection`：SSE 模式（HTTP 服务器）

#### 2. MCPServerManager（管理器）

**职责**：服务器生命周期管理

**文件**：`generalAgent/tools/mcp/manager.py`

**核心方法**：
```python
class MCPServerManager:
    async def get_or_start_server(self, server_id: str) -> ClientSession:
        """获取或启动服务器（懒启动）"""

    async def shutdown(self) -> None:
        """关闭所有服务器"""

    def is_running(self, server_id: str) -> bool:
        """检查服务器状态"""
```

**状态管理**：
```python
self._servers: Dict[str, ClientSession] = {}  # 已启动的服务器
self._connections: Dict[str, MCPConnection] = {}  # 连接对象
```

#### 3. MCPToolWrapper（包装器）

**职责**：将 MCP 工具转换为 LangChain BaseTool

**文件**：`generalAgent/tools/mcp/wrapper.py`

**核心代码**：
```python
class MCPToolWrapper(BaseTool):
    name: str
    description: str
    server_id: str
    tool_name: str  # MCP 原始工具名
    manager: MCPServerManager

    async def _arun(self, **kwargs) -> str:
        # 1. 触发懒启动
        session = await self.manager.get_or_start_server(self.server_id)

        # 2. 调用 MCP 工具
        result = await session.call_tool(self.tool_name, arguments=kwargs)

        # 3. 处理结果
        return self._format_result(result)
```

### 6.2 懒启动服务器

**需求**：MCP 服务器应在首次使用时启动，而不是在应用启动时。

**原因**：
- 加快应用启动速度
- 节省资源（未使用的服务器不启动）
- 减少初始化错误影响

**懒启动逻辑**：
1. 首次调用 `get_or_start_server(server_id)`
2. 检查 `server_id` 是否在 `self._servers` 中
3. 如果不存在，创建连接并启动服务器
4. 缓存 session 供后续使用

**日志输出**：
```
🚀 正在启动 MCP 服务器：test_stdio
  命令：python tests/mcp_servers/test_stdio_server.py
  ✓ MCP 服务器已启动：test_stdio（模式：stdio）
```

### 6.3 双协议支持 (stdio/SSE)

**需求**：支持 stdio 和 SSE 两种连接模式。

**原因**：
- stdio：适用于本地进程，简单可靠
- SSE：适用于远程 HTTP 服务器

**实现**：`MCPConnection` 抽象类 + 两个具体实现

### 6.4 MCP 配置

**配置文件结构**：

**文件**：`generalAgent/config/mcp_servers.yaml`

```yaml
# 全局配置
global:
  lazy_startup: true  # 懒启动（默认）

# 服务器配置
servers:
  # 服务器 ID
  filesystem:
    # 启动命令
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"]

    # 启用此服务器
    enabled: true

    # 环境变量
    env:
      DEBUG: "true"

    # 连接模式：stdio 或 sse
    connection_mode: "stdio"

    # 工具配置
    tools:
      read_file:
        enabled: true           # 启用此工具
        always_available: false # 不自动加载到所有 agent
        alias: "fs_read"        # 自定义名称
        description: "从允许的目录读取文件内容"

      write_file:
        enabled: false  # 禁用此工具
```

**配置示例**：

**示例 1：文件系统服务器（官方 MCP 服务器）**：
```yaml
servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/workspace"]
    enabled: true
    tools:
      read_file:
        enabled: true
        alias: "mcp_read_file"
      write_file:
        enabled: true
        alias: "mcp_write_file"
      list_directory:
        enabled: true
        alias: "mcp_list_dir"
```

**示例 2：测试服务器（本地开发）**：
```yaml
servers:
  test_stdio:
    command: "python"
    args: ["tests/mcp_servers/test_stdio_server.py"]
    enabled: true
    tools:
      echo:
        enabled: true
        alias: "mcp_echo"
      add:
        enabled: true
        alias: "mcp_add"
      get_time:
        enabled: false
```

### 6.5 工具注册

**启动流程**：

**文件**：`generalAgent/main.py`

```python
async def async_main():
    # 1. 加载 MCP 配置
    mcp_config_path = resolve_project_path("generalAgent/config/mcp_servers.yaml")

    if mcp_config_path.exists():
        logger.info("正在加载 MCP 配置...")

        # 2. 创建 MCPServerManager（服务器未启动）
        mcp_config = load_mcp_config(mcp_config_path)
        mcp_manager = MCPServerManager(mcp_config)

        # 3. 创建 MCPToolWrapper（工具包装器）
        mcp_tools = load_mcp_tools(mcp_config, mcp_manager)
        logger.info(f"  已加载 MCP 工具：{len(mcp_tools)}")
    else:
        logger.info("未找到 MCP 配置，跳过 MCP 集成")
        mcp_tools = []

    # 4. 构建应用程序（注册 MCP 工具）
    app, initial_state_factory, skill_registry, tool_registry = await build_application(
        mcp_tools=mcp_tools
    )

    # ... CLI 运行 ...

    try:
        await cli.run()
    finally:
        # 5. 清理 MCP 服务器
        if mcp_manager:
            logger.info("正在清理 MCP 服务器...")
            await mcp_manager.shutdown()
```

**工具注册流程**：

**文件**：`generalAgent/runtime/app.py`

```python
async def build_application(
    mcp_tools: Optional[List[MCPToolWrapper]] = None,
) -> Tuple[...]:
    # 1. 扫描内置工具
    discovered_tools = scan_tools(...)

    # 2. 创建 ToolRegistry
    tool_registry = ToolRegistry()

    # 3. 注册内置工具
    for tool in discovered_tools:
        if tool_config.is_enabled(tool.name):
            tool_registry.register_tool(tool)

    # 4. 注册 MCP 工具
    if mcp_tools:
        for mcp_tool in mcp_tools:
            tool_registry.register_tool(
                tool=mcp_tool,
                always_available=mcp_tool.always_available
            )

    # 5. 构建 Graph
    app = graph.build_state_graph(
        tool_registry=tool_registry,
        # ...
    )

    return app, initial_state_factory, skill_registry, tool_registry
```

### 6.6 使用示例

**快速开始**：

#### 1. 安装 MCP SDK

```bash
pip install mcp
# 或使用 uv
uv pip install mcp
```

#### 2. 创建配置文件

```bash
cp generalAgent/config/mcp_servers.yaml.example generalAgent/config/mcp_servers.yaml
```

#### 3. 配置测试服务器

编辑 `mcp_servers.yaml`：
```yaml
servers:
  test_stdio:
    command: "python"
    args: ["tests/mcp_servers/test_stdio_server.py"]
    enabled: true
    tools:
      echo:
        enabled: true
        alias: "mcp_echo"
```

#### 4. 启动 AgentGraph

```bash
python main.py
```

输出应包括：
```
正在加载 MCP 配置...
  已配置 MCP 服务器：1
  已加载 MCP 工具：1
    ✓ 已加载 MCP 工具：mcp_echo（服务器：test_stdio）
```

#### 5. 使用 MCP 工具

```
You> 使用 mcp_echo 工具发送消息 "Hello MCP!"

# 首次调用触发服务器启动
🚀 正在启动 MCP 服务器：test_stdio
  ✓ MCP 服务器已启动：test_stdio（模式：stdio）

A> [调用 mcp_echo 工具]
   Echo：Hello MCP!
```

**添加官方 MCP 服务器**：

**文件系统服务器**：
```yaml
servers:
  filesystem:
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/Users/yourname/allowed-directory"
    enabled: true
    tools:
      read_file:
        enabled: true
        alias: "fs_read"
      write_file:
        enabled: true
        alias: "fs_write"
      list_directory:
        enabled: true
        alias: "fs_list"
```

**GitHub 服务器**：
```yaml
servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    enabled: true
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    tools:
      create_issue:
        enabled: true
        alias: "gh_create_issue"
      search_repositories:
        enabled: true
        alias: "gh_search_repos"
```

---

## 第七部分：HITL (人机协同)

### 7.1 两种 HITL 模式

AgentGraph 集成了两种 HITL 模式用于安全和交互：

1. **ask_human 工具**：Agent 主动请求用户输入
2. **工具审批框架**：系统级安全检查，拦截危险操作

**模式比较**：

| 特性 | ask_human 工具 | 工具审批框架 |
|---------|---------------|------------------------|
| **触发** | Agent（LLM 主动调用） | 系统（自动检测） |
| **目的** | 获取用户输入 | 安全检查 |
| **用户看到** | 问题 + 输入框 | 工具信息 + 批准/拒绝 |
| **添加到历史** | ✅ 是（ToolMessage） | ❌ 否（透明） |
| **使用场景** | 缺少信息、需要选择 | 危险操作、权限控制 |
| **配置** | 无需配置 | `hitl_rules.yaml` |

### 7.2 ask_human 工具

#### 工具接口

**文件**：`generalAgent/tools/builtin/ask_human.py`

```python
@tool(args_schema=AskHumanInput)
def ask_human(
    question: str,                      # 要问的问题
    context: str = "",                  # 附加上下文
    input_type: Literal["text"] = "text",  # 输入类型（未来扩展）
    default: Optional[str] = None,      # 默认值
    required: bool = True,              # 是否必需
) -> str:
    """向用户询问信息

    当你缺少继续任务所需的必要信息时，使用此工具向用户询问。
    用户会看到你的问题并提供答案，然后你可以继续任务。

    何时使用：
    - 需要用户确认详情（例如，确认删除）
    - 需要用户做出选择（例如，选择城市、日期）
    - 缺少关键参数（例如，不知道用户想要什么）

    参数：
        question：要问用户的问题（清晰简洁）
        context：帮助用户理解的附加上下文
        default：默认答案（如果用户直接按回车）
        required：答案是否必需（默认 True）

    返回：
        用户的答案文本
    """
    # 触发中断
    answer = interrupt({
        "type": "user_input_request",
        "question": question,
        "context": context,
        "default": default,
        "required": required,
    })

    return answer or ""
```

#### 中断处理

**文件**：`generalAgent/cli.py`（第 252-288 行）

```python
async def _handle_message(self, user_input: str):
    # ... 执行 Graph ...

    # 检查中断
    while True:
        graph_state = await self.app.aget_state(config)

        if graph_state.next and graph_state.tasks and \
           hasattr(graph_state.tasks[0], 'interrupts') and \
           graph_state.tasks[0].interrupts:

            # 获取中断数据
            interrupt_value = graph_state.tasks[0].interrupts[0].value

            # 处理中断（用户输入或工具审批）
            resume_value = await self._handle_interrupt(interrupt_value)

            if resume_value is not None:
                # 恢复 Graph 执行
                async for state_snapshot in self.app.astream(
                    Command(resume=resume_value),
                    config=config,
                    stream_mode="values"
                ):
                    await self._print_new_messages(state_snapshot)
        else:
            break
```

#### UI 提示（极简版）

**文件**：`generalAgent/cli.py`（第 370-405 行）

```python
async def _handle_user_input_request(self, data: dict) -> str:
    """处理 ask_human 工具的用户输入请求"""
    question = data.get("question", "")
    context = data.get("context", "")
    default = data.get("default")

    print()
    if context:
        print(f"💡 {context}")
    print(f"💬 {question}")
    if default:
        print(f"   (默认：{default})")

    # 获取用户输入
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(
        None,
        lambda: input("> ").strip()
    )

    # 使用默认值（如果用户未输入）
    if not answer and default:
        answer = default

    return answer
```

#### 示例交互

```
User> 帮我写一个文档

A> 我来帮你写文档。
   [调用 ask_human 工具]

💬 请问文档的主题是什么？
   (默认：工作报告)
> 技术方案设计

A> 好的，我将为你创建一份关于"技术方案设计"的文档。
```

### 7.3 工具审批框架

#### 四层审批规则系统

**优先级 1：工具自定义检查器**（最高优先级）

使用场景：工具特定的复杂逻辑

```python
# generalAgent/hitl/approval_checker.py

def _check_bash_command(args: dict) -> ApprovalDecision:
    """自定义检查器：bash 命令审批"""
    command = args.get("command", "")

    # 高风险模式
    high_risk_patterns = [
        r"rm\s+-rf",        # 递归删除
        r"sudo\s+",         # 超级用户
        r"chmod\s+777",     # 危险权限
        r">\s*/dev/sd",     # 直接磁盘写入
    ]

    for pattern in high_risk_patterns:
        if re.search(pattern, command):
            return ApprovalDecision(
                needs_approval=True,
                reason=f"检测到高风险操作：{pattern}",
                risk_level="high"
            )

    # 安全命令白名单
    safe_commands = ["ls", "pwd", "cat", "echo", "date", "whoami"]
    first_word = command.split()[0] if command.split() else ""

    if first_word in safe_commands:
        return ApprovalDecision(needs_approval=False)

    # 默认：中等风险命令需要审批
    return ApprovalDecision(
        needs_approval=True,
        reason="非白名单命令，需要确认",
        risk_level="medium"
    )
```

**优先级 2：全局风险模式**（跨工具检测）

使用场景：通用风险检测，适用于所有工具

**文件**：`generalAgent/config/hitl_rules.yaml`

```yaml
global:
  risk_patterns:
    critical:
      patterns:
        - "password\\s*[=:]\\s*['\"]?\\w+"
        - "api[_-]?key\\s*[=:]\\s*"
        - "secret\\s*[=:]\\s*"
      action: require_approval
      reason: "检测到敏感信息（密码/密钥/令牌）"

    high:
      patterns:
        - "/etc/passwd"
        - "DROP\\s+(TABLE|DATABASE)"
      action: require_approval
      reason: "检测到高风险操作"
```

**优先级 3：工具配置规则**

使用场景：工具特定的可配置模式匹配

**文件**：`generalAgent/config/hitl_rules.yaml`

```yaml
tools:
  run_bash_command:
    enabled: true
    patterns:
      high_risk:
        - "rm\\s+-rf"
        - "sudo"
        - "chmod\\s+777"
        - "dd\\s+if="
      medium_risk:
        - "curl"
        - "wget"
        - "pip\\s+install"
        - "git\\s+clone"
    actions:
      high_risk: require_approval
      medium_risk: require_approval

  http_fetch:
    enabled: true
    patterns:
      high_risk:
        - "internal\\.company\\.com"  # 阻止内网访问
        - "192\\.168\\."
      medium_risk:
        - "api\\."                     # API 调用需确认
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

**优先级 4：内置默认规则**（回退逻辑）

使用场景：通用回退逻辑，当前三层未匹配时执行

```python
def _check_builtin_rules(self, tool_name: str, args: dict) -> ApprovalDecision:
    """内置默认规则（最低优先级）"""

    # 默认：所有工具都是安全的
    return ApprovalDecision(needs_approval=False)
```

#### ApprovalToolNode 实现

**文件**：`generalAgent/hitl/approval_node.py`

```python
class ApprovalToolNode:
    """包装 ToolNode，拦截工具调用以进行审批"""

    def __init__(
        self,
        tools: List[BaseTool],
        approval_checker: ApprovalChecker,
        enable_approval: bool = True
    ):
        self.tool_node = ToolNode(tools)
        self.approval_checker = approval_checker
        self.enable_approval = enable_approval

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """拦截并检查工具调用"""
        if not self.enable_approval:
            # 审批已禁用，直接执行
            return await self.tool_node.ainvoke(state)

        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None

        if not hasattr(last_msg, "tool_calls"):
            return await self.tool_node.ainvoke(state)

        # 检查每个 tool_call
        for tool_call in last_msg.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

            # 调用审批检查器
            decision = self.approval_checker.check(tool_name, tool_args)

            if decision.needs_approval:
                # 触发中断
                user_decision = interrupt({
                    "type": "tool_approval",
                    "tool": tool_name,
                    "args": tool_args,
                    "reason": decision.reason,
                    "risk_level": decision.risk_level,
                })

                if user_decision == "reject":
                    # 用户拒绝，返回取消消息
                    return {"messages": [ToolMessage(
                        content=f"❌ 操作已取消：{decision.reason}",
                        tool_call_id=tool_call_id,
                    )]}

        # 所有工具通过审批，执行
        return await self.tool_node.ainvoke(state)
```

### 7.4 审批规则系统

**四层架构**：

1. **优先级 1 - 工具自定义检查器**（最高优先级）：特定工具的自定义逻辑
2. **优先级 2 - 全局风险模式**（跨工具检测）：检测所有工具的风险（例如密码泄露）
3. **优先级 3 - 工具特定配置规则**：工具特定的可配置模式
4. **优先级 4 - 内置默认规则**（回退）：通用回退逻辑

**设计原则**：
- **对 LLM 透明**：审批决策不添加到对话上下文
- **能力级粒度**：基于参数的审批，而非整个工具
- **四层架构**：自定义检查器 → 全局模式 → 工具规则 → 默认
- **跨工具检测**：全局模式检测所有工具的风险（例如密码泄露）
- **可扩展**：易于添加新模式和自定义检查器

### 7.5 配置

**配置文件**：`generalAgent/config/hitl_rules.yaml`

```yaml
# 全局配置
global:
  enable_approval: true      # 全局开关
  default_action: "prompt"   # require_approval | allow | deny

# 工具审批规则
tools:
  <tool_name>:
    enabled: true             # 是否启用此工具的审批
    patterns:
      high_risk: [...]        # 高风险模式列表
      medium_risk: [...]      # 中等风险模式列表
      low_risk: [...]         # 低风险模式列表
    actions:
      high_risk: require_approval
      medium_risk: require_approval
      low_risk: allow
```

### 7.6 使用示例

#### ask_human 使用示例

**示例 1：缺少关键信息**：

```
User> 帮我订个酒店

A> 好的，我来帮你预订酒店。
   [调用 ask_human 工具]

💬 请问你要在哪个城市订酒店？
> 北京

💬 入住日期和退房日期分别是？
   (默认：今天入住，明天退房)
> 2025-11-01 到 2025-11-03

A> 好的，我将为你查找 2025-11-01 至 2025-11-03 在北京的酒店。
```

**示例 2：需要用户确认**：

```
User> 帮我写一个删除日志的脚本

A> 我可以帮你写删除日志脚本。
   [调用 ask_human 工具]

💡 删除日志是不可逆操作
💬 确定要删除多少天前的日志？
   (默认：7)
> 30

A> 好的，我将创建一个删除 30 天前日志的脚本。
```

#### 工具审批使用示例

**示例 1：高风险操作**：

```
User> 帮我清理 /tmp 目录

A> 我来帮你清理。
   [调用 run_bash_command：rm -rf /tmp/*]

🛡️  工具审批：run_bash_command
   原因：检测到高风险操作：rm\s+-rf
   参数：{'command': 'rm -rf /tmp/*'}
   批准？[y/n] > n

A> ❌ 操作已取消：检测到高风险操作：rm\s+-rf
   了解，我不会执行删除操作。你可以手动清理该目录。
```

**示例 2：自定义工具审批**：

```yaml
# generalAgent/config/hitl_rules.yaml
tools:
  http_fetch:
    enabled: true
    patterns:
      high_risk:
        - "internal\\.mycompany\\.com"  # 阻止公司内网访问
        - "192\\.168\\."                 # 阻止本地网络访问
      medium_risk:
        - "api\\."                       # API 调用需确认
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

---

## 实现文件清单

### 核心代码

**Workspace 隔离**：
```
shared/workspace/manager.py          # Workspace 管理器
shared/session/store.py              # 会话持久化
shared/session/manager.py            # 会话生命周期
generalAgent/tools/builtin/file_ops.py       # 文件操作工具
generalAgent/tools/builtin/find_files.py     # 文件搜索
generalAgent/tools/builtin/search_file.py    # 内容搜索
generalAgent/utils/file_processor.py         # 文件处理工具
generalAgent/utils/document_extractors.py    # 文档提取
generalAgent/utils/text_indexer.py           # 文本索引
```

**@Mention 系统**：
```
generalAgent/utils/mention_classifier.py     # Mention 分类
generalAgent/tools/registry.py               # 工具注册表
generalAgent/skills/registry.py              # Skill 注册表
generalAgent/graph/prompts.py                # 动态提醒
```

**子代理系统**：
```
generalAgent/tools/builtin/delegate_task.py  # delegate_task 工具
```

**MCP 集成**：
```
generalAgent/tools/mcp/
├── connection.py                # 连接抽象
├── manager.py                   # 服务器管理器
├── wrapper.py                   # LangChain 工具包装器
└── loader.py                    # 配置加载器
```

**HITL 系统**：
```
generalAgent/hitl/
├── approval_checker.py          # 四层审批规则
└── approval_node.py             # ApprovalToolNode 包装器

generalAgent/tools/builtin/ask_human.py     # ask_human 工具
```

### 配置文件

```
generalAgent/config/
├── mcp_servers.yaml             # MCP 服务器配置
├── hitl_rules.yaml             # 审批规则
├── skills.yaml                 # Skills 配置
└── tools.yaml                  # 工具配置
```

### 集成点

```
generalAgent/
├── main.py                     # MCP 初始化和清理
├── cli.py                      # 中断处理
├── runtime/app.py              # 工具注册
└── graph/builder.py            # ApprovalToolNode 集成
```

---

## 第八部分：自动上下文压缩 ⭐ NEW

**功能概述**：当对话 token 使用达到 95% 时，系统自动压缩历史消息，无需用户干预。

> **注意**：本文档部分内容基于旧版手动压缩工具(`compact_context`)。最新的自动压缩架构请参考 [docs/ARCHITECTURE.md - 第 1.5 节](ARCHITECTURE.md#15-上下文管理与自动压缩-new)

### 8.1 核心机制

**工作流程**：

1. **Token 监控** - 每次 LLM 调用后，Planner 节点跟踪 `cumulative_prompt_tokens`
2. **触发检测** - 当使用率达到 95% 时，设置 `needs_compression = True` 标志
3. **路由到压缩** - 条件路由层检测标志，将流程引导到 `summarization` 节点
4. **执行压缩** - Summarization 节点调用 ContextCompressor 压缩历史消息
5. **返回继续** - 压缩后，自动返回 agent 节点继续回答用户问题

**用户体验**：

- ✅ **完全静默** - 无任何通知或中断
- ✅ **无缝继续** - Agent 压缩后立即回答原问题
- ✅ **保留上下文** - LLM 生成详细摘要，保留关键信息

**示例**：

```
用户输入 (302 messages, 123K tokens, 96% usage)
    ↓
Planner: 检测 96% → 设置 needs_compression=True → 跳过 LLM 调用
    ↓
Routing: 检测标志 → 路由到 summarization
    ↓
Summarization:
  - 检查最小消息数 (302 >= 15) ✓
  - 划分: System + Old(291 msgs) + Recent(10 msgs)
  - 压缩 Old 层为 LLM 摘要
  - 清理孤儿 ToolMessage
  - 返回压缩结果
    ↓
Routing: 返回 agent
    ↓
Agent: 以压缩后的上下文调用 LLM → 生成回复
    ↓
结果: 13 messages, 6.5K tokens (95% reduction)
```

### 8.2 压缩策略

**两层分区策略** (`generalAgent/context/compressor.py`):

| 层级 | 策略 | 说明 |
|------|------|------|
| **System** | 完整保留 | 所有 SystemMessage |
| **Old** | LLM 压缩 | 除 Recent 外的所有消息（一次性压缩） |
| **Recent** | 完整保留 | 最近 10 条消息或 15% context window（取先到者） |

**混合保留策略**：

```python
# 配置参数（settings.py）
CONTEXT_KEEP_RECENT_RATIO=0.15      # 保留 15% context window
CONTEXT_KEEP_RECENT_MESSAGES=10     # 或至少 10 条消息

# 示例：128k context window, 302 条消息
# 保留: min(15% * 128k tokens, 10 messages) = 10 messages
# 压缩: 291 条消息 → 单次 LLM 调用生成摘要
```

**压缩输出**（LLM 生成的摘要）：

```markdown
# 对话历史摘要（系统自动生成）

以下是早期对话的摘要（原始 291 条消息）：

## 用户请求和意图
[用户所有请求的详细描述]

## 关键信息
- [重要概念、术语、数据]

## 文件操作
- **文件路径 1**: 操作原因、内容摘要
- **文件路径 2**: ...

## 工具调用记录
- `tool_name(args)` → 结果
  - 原因: ...
  - 影响: ...

## 错误和修复
- **错误描述**: ...
  - 修复方法: ...

## 当前工作
[最新工作进展]
```

### 8.3 配置选项

智能上下文压缩功能通过以下配置参数提供灵活的调优能力。所有参数都包含 Pydantic 验证约束，确保配置合法性。

#### 8.5.1 配置参数详解

**配置位置**：`generalAgent/config/settings.py` 中的 `ContextManagementSettings` 类

所有配置都有硬编码的默认值，无需在 `.env` 文件中配置。如需修改，直接编辑 `settings.py` 中的 `default=` 值。

**配置参数**：

```python
# 总开关
enabled: bool = Field(default=True)
# 是否启用上下文管理功能
# 默认: true
# 说明: 关闭后不再监控 token 使用，也不会触发压缩
# 影响: false = 禁用所有上下文管理功能

# Token 使用监控阈值 (基于累积 prompt tokens 占模型上下文窗口的比例)
info_threshold: float = Field(default=0.75, ge=0.5, le=0.95)
# 信息提示阈值
# 默认: 0.75 (75%)
# 约束: ge=0.5, le=0.95 (有效范围 0.5 ≤ 值 ≤ 0.95)
# 说明: 达到此阈值时显示信息提示，建议使用 compact_context 工具
# 影响:
#   - 调低: 更早触发提示（例如 0.70 = 90K/128K tokens 时提示）
#   - 调高: 延迟提示（例如 0.80 = 102K/128K tokens 时提示）
# 示例:
#   - 保守: 0.70 (更早提示，给用户更多时间处理)
#   - 激进: 0.80 (更晚提示，更充分利用上下文窗口)

warning_threshold: float = Field(default=0.85, ge=0.6, le=0.95)
# 警告阈值
# 默认: 0.85 (85%)
# 约束: ge=0.6, le=0.95 (有效范围 0.6 ≤ 值 ≤ 0.95)
# 说明: 达到此阈值时显示强警告，强烈建议立即压缩
# 影响:
#   - 调低: 更早触发警告，降低接近 critical 阈值的风险
#   - 调高: 延迟警告，但可能快速接近 critical 阈值
# 示例:
#   - 保守: 0.80 (更早警告，更安全)
#   - 激进: 0.90 (更晚警告，更充分利用空间)
# 注意: 必须 > info_threshold 且 < critical_threshold

critical_threshold: float = Field(default=0.95, ge=0.8, le=0.99)
# 临界阈值（自动压缩触发点）
# 默认: 0.95 (95%)
# 约束: ge=0.8, le=0.99 (有效范围 0.8 ≤ 值 ≤ 0.99)
# 说明: 达到此阈值时自动触发压缩
# 影响:
#   - 调低: 更早自动压缩，更安全但可能牺牲部分上下文
#   - 调高: 更晚自动压缩，保留更多上下文但接近 token 上限
# 示例:
#   - 安全: 0.90 (115K/128K tokens 时自动压缩)
#   - 激进: 0.98 (125K/128K tokens 时自动压缩，非常接近上限！)
# 注意: 必须 > warning_threshold

# 分层压缩策略配置（混合模式：Token 比例 + 消息数）
keep_recent_ratio: float = Field(default=0.15, ge=0.05, le=0.5)
# 保留最近消息的 token 比例（相对于 context window）
# 默认: 0.15 (15%)
# 约束: ge=0.05, le=0.5 (有效范围 5%-50%)
# 说明: 压缩时保持最近 N% context window 的消息完整不压缩（保留当前上下文）
# 影响:
#   - 调高: 保留更多细节，适合需要完整最近对话的场景（但压缩效果降低）
#   - 调低: 压缩更多消息，节省更多 tokens（但可能丢失近期上下文细节）
# 示例:
#   - 激进: 0.10 (仅保留 10% context window，最大化 token 节省)
#   - 保守: 0.25 (保留 25% context window，保留更多细节)
#   - 平衡: 0.15 (默认值，适合大多数场景)
# 动态效果:
#   - 128K 模型: 19.2K tokens
#   - 256K 模型: 38.4K tokens（自动适配！）

keep_recent_messages: int = Field(default=10, ge=5, le=50)
# 保留最近消息数量（混合策略）
# 默认: 10
# 约束: ge=5, le=50 (有效范围 5-50)
# 说明: 与 keep_recent_ratio 结合使用，取先达到的限制
# 影响: 防止单条消息过长导致保留过多 tokens

compact_middle_ratio: float = Field(default=0.30, ge=0.1, le=0.7)
# 详细摘要消息的 token 比例（相对于 context window）
# 默认: 0.30 (30%)
# 约束: ge=0.1, le=0.7 (有效范围 10%-70%)
# 说明: 对中间层 N% context window 的消息进行详细摘要（保留技术细节、文件路径、工具调用等）
# 影响:
#   - 调高: 保留更多技术细节，适合技术任务（但压缩效果降低）
#   - 调低: 摘要更简略，节省更多 tokens（但可能丢失技术细节）
# 示例:
#   - 激进: 0.20 (中间 20% context window，最大化压缩)
#   - 保守: 0.40 (中间 40% context window，保留更多技术上下文)
#   - 平衡: 0.30 (默认值)
# 动态效果:
#   - 128K 模型: 38.4K tokens
#   - 256K 模型: 76.8K tokens（自动适配！）

compact_middle_messages: int = Field(default=30, ge=10, le=100)
# 详细摘要消息数量（混合策略）
# 默认: 30
# 约束: ge=10, le=100 (有效范围 10-100)
# 说明: 与 compact_middle_ratio 结合使用，取先达到的限制

# 后备策略（Kimi-inspired）
max_history_messages: int = Field(default=100, ge=30, le=200)
# 最大历史消息数量（紧急截断阈值）
# 默认: 100
# 约束: ge=30, le=200 (有效范围 30-200)
# 说明: 当 LLM 压缩失败时，降级为简单截断策略，仅保留 SystemMessage + 最近 N 条消息
# 影响:
#   - 调高: 保留更多历史，适合需要长期上下文的场景（但可能接近 token 上限）
#   - 调低: 丢失更多历史，但更安全（保证不会 OOM）
# 示例:
#   - 安全: 50 (紧急情况仅保留 50 条)
#   - 平衡: 100 (默认值)
#   - 宽松: 150 (紧急情况保留 150 条，适合长上下文模型)
# 注意: 这是最后的安全网，仅在 LLM 压缩失败时生效
```

#### 8.5.2 Pydantic 字段约束说明

AgentGraph 使用 Pydantic 的字段验证功能确保配置合法性：

```python
# generalAgent/config/settings.py:184-221
class ContextManagementSettings(BaseSettings):
    enabled: bool = Field(default=True, alias="CONTEXT_MANAGEMENT_ENABLED")

    # Token 监控阈值
    info_threshold: float = Field(default=0.75, ge=0.5, le=0.95, alias="CONTEXT_INFO_THRESHOLD")
    warning_threshold: float = Field(default=0.85, ge=0.6, le=0.95, alias="CONTEXT_WARNING_THRESHOLD")
    critical_threshold: float = Field(default=0.95, ge=0.8, le=0.99, alias="CONTEXT_CRITICAL_THRESHOLD")

    # 分层策略配置
    keep_recent_messages: int = Field(default=10, ge=5, le=50, alias="CONTEXT_KEEP_RECENT")
    compact_middle_messages: int = Field(default=30, ge=10, le=100, alias="CONTEXT_COMPACT_MIDDLE")

    # 动态策略决策配置
    compression_ratio_threshold: float = Field(default=0.4, ge=0.2, le=0.8, alias="CONTEXT_COMPRESSION_RATIO_THRESHOLD")
    compact_cycle_limit: int = Field(default=3, ge=1, le=10, alias="CONTEXT_COMPACT_CYCLE_LIMIT")

    # Kimi-inspired 后备策略
    max_history_messages: int = Field(default=100, ge=30, le=200, alias="CONTEXT_MAX_HISTORY")
```

**约束参数说明**:
- **`ge` (greater than or equal)**: 最小值约束，配置不能低于此值
- **`le` (less than or equal)**: 最大值约束，配置不能超过此值
- **示例**: `ge=0.5, le=0.95` 表示有效范围是 `0.5 ≤ 值 ≤ 0.95`
- **违反约束**: 启动时会抛出 `ValidationError`，明确指出配置错误

**错误示例**:
```bash
# ❌ 错误: info_threshold 超出范围
CONTEXT_INFO_THRESHOLD=0.45  # < ge=0.5

# 启动时报错:
# ValidationError: 1 validation error for ContextManagementSettings
# info_threshold
#   Input should be greater than or equal to 0.5 [type=greater_than_equal]

# ✅ 正确: 在有效范围内
CONTEXT_INFO_THRESHOLD=0.70  # 0.5 ≤ 0.70 ≤ 0.95
```

#### 8.5.3 配置建议（三种预设方案）

根据不同场景，我们提供三种预设配置方案：

**方案 1: 保守型配置**（适合需要保留详细上下文的场景）

适用场景：
- 长期技术讨论（需要回溯历史细节）
- 代码重构项目（需要保留完整修改记录）
- 复杂问题诊断（需要完整上下文链条）

```bash
CONTEXT_MANAGEMENT_ENABLED=true

# 更早触发警告，给用户更多准备时间
CONTEXT_INFO_THRESHOLD=0.70          # 70% 就提示
CONTEXT_WARNING_THRESHOLD=0.80       # 80% 就警告
CONTEXT_CRITICAL_THRESHOLD=0.90      # 90% 就自动压缩

# 保留更多最近消息和技术细节
CONTEXT_KEEP_RECENT=20               # 保留最近 20 条
CONTEXT_COMPACT_MIDDLE=50            # 详细摘要 50 条

# 更倾向使用详细摘要策略
CONTEXT_COMPRESSION_RATIO_THRESHOLD=0.5  # 压缩率 > 50% 才切换
CONTEXT_COMPACT_CYCLE_LIMIT=5        # 允许 5 次 compact 周期

# 紧急情况保留更多历史
CONTEXT_MAX_HISTORY=150
```

**效果**:
- ✅ 保留更多上下文细节
- ✅ 更早发出警告，用户有充足时间决策
- ✅ 优先使用详细摘要策略
- ⚠️ 压缩效果相对较弱（可能需要更频繁压缩）

---

**方案 2: 激进型配置**（适合需要最大化 token 节省的场景）

适用场景：
- Token 预算紧张（API 成本敏感）
- 短期对话（不需要长期上下文）
- 简单任务（不需要复杂上下文）

```bash
CONTEXT_MANAGEMENT_ENABLED=true

# 更晚触发警告，更充分利用上下文窗口
CONTEXT_INFO_THRESHOLD=0.80          # 80% 才提示
CONTEXT_WARNING_THRESHOLD=0.88       # 88% 才警告
CONTEXT_CRITICAL_THRESHOLD=0.96      # 96% 才自动压缩

# 保留更少消息，更激进压缩
CONTEXT_KEEP_RECENT=5                # 仅保留最近 5 条
CONTEXT_COMPACT_MIDDLE=20            # 精简摘要 20 条

# 更容易切换到极简摘要策略
CONTEXT_COMPRESSION_RATIO_THRESHOLD=0.3  # 压缩率 > 30% 就切换
CONTEXT_COMPACT_CYCLE_LIMIT=2        # 仅允许 2 次 compact 周期

# 紧急情况仅保留 50 条
CONTEXT_MAX_HISTORY=50
```

**效果**:
- ✅ 最大化 token 节省（压缩率可达 90%+）
- ✅ 更充分利用上下文窗口（接近极限才压缩）
- ✅ 快速切换到极简摘要
- ⚠️ 可能丢失部分历史细节
- ⚠️ 更接近 token 上限（风险稍高）

---

**方案 3: 平衡型配置**（默认值，适合大多数场景）

适用场景：
- 通用对话（大多数日常任务）
- 不确定场景（先用默认值，再根据实际情况调整）

```bash
# 直接使用默认值，无需显式配置
# 或显式指定以下值（与默认值相同）:

CONTEXT_MANAGEMENT_ENABLED=true
CONTEXT_INFO_THRESHOLD=0.75
CONTEXT_WARNING_THRESHOLD=0.85
CONTEXT_CRITICAL_THRESHOLD=0.95
CONTEXT_KEEP_RECENT=10
CONTEXT_COMPACT_MIDDLE=30
CONTEXT_COMPRESSION_RATIO_THRESHOLD=0.4
CONTEXT_COMPACT_CYCLE_LIMIT=3
CONTEXT_MAX_HISTORY=100
```

**效果**:
- ✅ 平衡压缩效果和上下文保留
- ✅ 适合 80% 的使用场景
- ✅ 经过业界实践验证（综合 Gemini/Kimi/Claude Code 最佳实践）

---

#### 8.5.4 配置调优建议

**如何选择配置方案**:

1. **观察 token 使用情况**:
   ```
   # 查看 agent 输出的 token 警告
   💡 提示：Token 使用量达到 78%，建议压缩上下文
   ```

2. **根据压缩报告调整**:
   ```
   ✅ 上下文已压缩
   压缩前: 141 条消息 (~110,000 tokens)
   压缩后: 23 条消息 (~18,000 tokens)
   策略: 详细摘要
   节省: 118 条消息, ~92,000 tokens (84%)
   ```
   - 如果压缩率 < 50%: 说明压缩效果很好，可以考虑更激进的配置
   - 如果压缩率 > 70%: 说明压缩效果较差，可能需要更保守的配置

3. **根据任务类型调整**:
   - 技术任务（代码、调试）→ 保守型配置
   - 聊天对话 → 激进型配置
   - 混合任务 → 平衡型配置

4. **动态调整策略**:
   - 对话初期（前 10 轮）→ 激进型（充分利用空间）
   - 对话中期（10-50 轮）→ 平衡型（根据情况压缩）
   - 对话后期（50+ 轮）→ 保守型（保留完整历史）

### 8.6 使用示例

**场景 1：自动压缩流程**

```
用户> 帮我分析这个大型代码库（100+ 轮对话）
A> 好的，开始分析...

[... 10 轮对话后，token: 5k → 65k]

A> (继续分析...)

[... 第 11 轮，token 达到 105k / 128k = 82%]

A> 💡 提示：Token 使用量达到 82%，建议压缩上下文
   [系统已自动加载 compact_context 工具]

[... Agent 继续工作几轮，token 达到 110k / 128k = 86%]

A> ⚠️ 警告：Token 使用量达到 86%，强烈建议立即压缩！
   让我先压缩上下文，然后继续...

A> [调用] compact_context(strategy="auto")

[系统执行压缩]
✅ 上下文已压缩
压缩前: 141 条消息 (~110,000 tokens)
压缩后: 23 条消息 (~18,000 tokens)
策略: 详细摘要
节省: 118 条消息, ~92,000 tokens (84%)

A> 已压缩上下文，现在继续分析...

[对话继续，从 18k tokens 开始计数]
```

**场景 2：手动压缩**

```
用户> 我们已经分析了很多内容，请压缩一下上下文
A> 好的，让我压缩上下文

A> [调用] compact_context(strategy="compact")

✅ 上下文已压缩
压缩前: 85 条消息 (~75,000 tokens)
压缩后: 18 条消息 (~15,000 tokens)
策略: 详细摘要
节省: 67 条消息, ~60,000 tokens (80%)

A> 已完成压缩，我们可以继续对话了
```

**场景 3：压缩失败降级**

```
[Agent 尝试压缩但 LLM 调用失败]

⚠️ LLM 压缩失败，自动降级到简单截断

[系统日志]
2025-10-28 15:30:45 WARNING LLM compression failed: API timeout
2025-10-28 15:30:45 INFO Falling back to simple truncation
2025-10-28 15:30:45 INFO Truncated messages: 200 → 150 (kept 1 system + 150 recent)

[对话继续，用 150 条最近消息]
```

**State 字段**：

```python
state = {
    "cumulative_prompt_tokens": 105000,        # 累积 prompt tokens
    "cumulative_completion_tokens": 8500,       # 累积 completion tokens
    "last_prompt_tokens": 3200,                 # 上次调用的 prompt tokens
    "compact_count": 2,                         # 压缩次数
    "last_compact_strategy": "compact",         # 上次使用的策略
    "last_compression_ratio": 0.18,             # 上次压缩率 (18%)
    # ... 其他字段
}
```

**与业界对比**：

| 项目 | 策略 | AgentGraph 优势 |
|------|------|----------------|
| **Gemini CLI** | 手动 `/compress` + 可选自动 | ✅ 渐进式警告（75%/85%/95%） |
| **Kimi CLI** | 简单截断（150 条消息） | ✅ LLM 智能摘要 + 分层压缩 |
| **Claude Code** | 95% 自动压缩 | ✅ 更早警告（75% 开始） |
| **AgentGraph** | **混合策略** | ✅ 智能 + 降级 + 透明 |

**关键文件**：

```
generalAgent/context/
├── __init__.py                 # 模块导出
├── token_tracker.py            # Token 监控器 (265 行)
├── compressor.py               # 压缩器 (378 行)
├── truncator.py                # 降级策略 (57 行)
└── manager.py                  # 统一管理器 (172 行)

generalAgent/tools/builtin/
└── compact_context.py          # Agent 工具 (148 行)

generalAgent/graph/nodes/
└── planner.py                  # Token 追踪集成

tests/unit/context/
└── test_token_tracker.py       # 单元测试 (14/14 通过)
```

---

## 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [LangGraph 中断文档](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/breakpoints/)
- [AgentGraph 项目文档](../CLAUDE.md)

---

**文档版本**：1.1
**最后更新**：2025-10-28
