# GeneralAgent 详细需求文档 - Part 2: 工作区隔离与会话管理

## 4. 工作区隔离需求

### 4.1 工作区目录结构

**需求描述**：每个会话拥有独立的工作区目录，灵感来自 OpenAI Code Interpreter 和 E2B。

**目录结构**：
```
data/workspace/{session_id}/
├── skills/           # 符号链接的技能（只读）
│   └── pdf/
│       ├── SKILL.md
│       ├── forms.md
│       ├── reference.md
│       └── scripts/
├── uploads/          # 用户上传文件
├── outputs/          # Agent 生成的输出
├── temp/             # 临时文件
└── .metadata.json    # 会话元数据
```

**实现代码**：
```python
# shared/workspace/manager.py:45-75
class WorkspaceManager:
    def __init__(self, base_dir: Path, skill_registry: SkillRegistry):
        self.base_dir = base_dir
        self.skill_registry = skill_registry
        self.workspace_path: Optional[Path] = None

    def create_workspace(self, session_id: str) -> Path:
        """Create isolated workspace for session"""

        workspace = self.base_dir / session_id
        workspace.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (workspace / "skills").mkdir(exist_ok=True)
        (workspace / "uploads").mkdir(exist_ok=True)
        (workspace / "outputs").mkdir(exist_ok=True)
        (workspace / "temp").mkdir(exist_ok=True)

        # Save metadata
        metadata = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(workspace / ".metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        self.workspace_path = workspace
        return workspace
```

### 4.2 路径隔离与安全

**需求描述**：工具只能访问工作区内的文件，防止路径遍历攻击。

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
    """Resolve and validate workspace-relative path"""

    # Step 1: Resolve logical path (follow symlinks)
    logical_path = (workspace_root / file_path).resolve()

    # Step 2: Check if resolved path is within workspace
    try:
        logical_path.relative_to(workspace_root.resolve())
    except ValueError:
        raise ValueError(f"Path outside workspace: {file_path}")

    # Step 3: Check existence if required
    if must_exist and not logical_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Step 4: Check write permissions
    if allow_write:
        allowed_dirs = ["outputs", "temp", "uploads"]
        rel_path = logical_path.relative_to(workspace_root)

        if not any(rel_path.parts[0] == d for d in allowed_dirs):
            raise PermissionError(
                f"Cannot write to {rel_path.parts[0]}/. "
                f"Only {allowed_dirs} are writable."
            )

    return logical_path
```

**应用到文件工具**：
```python
# generalAgent/tools/builtin/file_ops.py:45-60
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # Validate path
    abs_path = resolve_workspace_path(
        file_path,
        workspace_root,
        must_exist=True,
        allow_write=False,
    )

    # Read file
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**设计考量**：
- `resolve()` 处理符号链接和 `..` 路径
- `relative_to()` 检查是否在工作区内
- 写入权限仅限 outputs/, temp/, uploads/
- skills/ 目录只读（符号链接）

### 4.3 技能符号链接

**需求描述**：当用户 @提及技能时，将技能目录符号链接到工作区。

**符号链接逻辑**：
```python
# shared/workspace/manager.py:110-145
def load_skill(self, skill_id: str) -> bool:
    """Load skill into workspace by creating symlink"""

    skill = self.skill_registry.get_skill(skill_id)
    if not skill:
        return False

    target_dir = self.workspace_path / "skills" / skill_id

    # Create symlink if not exists
    if not target_dir.exists():
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        target_dir.symlink_to(skill.path, target_is_directory=True)

    # Install dependencies if needed
    requirements = skill.path / "requirements.txt"
    if requirements.exists():
        self._install_skill_dependencies(skill_id, requirements)

    return True
```

**符号链接的好处**：
- 不复制文件，节省空间
- 技能更新自动反映到所有会话
- 只读访问，防止误修改

**list_workspace_files 处理符号链接**：
```python
# generalAgent/tools/builtin/file_ops.py:214-241
@tool
def list_workspace_files(directory: str = ".") -> str:
    """List files in workspace directory"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # Use logical path (don't resolve symlinks)
    logical_path = workspace_root / directory

    # Check within workspace
    try:
        logical_path.relative_to(workspace_root)
    except ValueError:
        return f"Error: Path outside workspace: {directory}"

    # List files
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

### 4.4 文件上传处理

**需求描述**：用户上传的文件自动复制到 `uploads/` 目录。

**文件类型检测**：
```python
# generalAgent/utils/file_processor.py:55-80
def detect_file_type(file_path: Path) -> str:
    """Detect file type from extension"""

    ext = file_path.suffix.lower()

    type_map = {
        ".pdf": "pdf",
        ".docx": "document",
        ".xlsx": "spreadsheet",
        ".csv": "csv",
        ".txt": "text",
        ".md": "markdown",
        ".py": "python",
        ".json": "json",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
    }

    return type_map.get(ext, "unknown")
```

**上传处理流程**：
```python
# generalAgent/cli.py:180-210
def process_file_upload(self, file_path: str) -> dict:
    """Process uploaded file"""

    src_path = Path(file_path)

    if not src_path.exists():
        return {"success": False, "error": "File not found"}

    # Detect type
    file_type = detect_file_type(src_path)

    # Copy to uploads/
    dest_path = self.workspace_path / "uploads" / src_path.name
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_path, dest_path)

    # Generate relative path
    rel_path = f"uploads/{src_path.name}"

    return {
        "success": True,
        "path": rel_path,
        "type": file_type,
        "name": src_path.name,
    }
```

**在消息中引用上传文件**：
```python
# generalAgent/cli.py:230-245
async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """Handle user message with uploaded files"""

    # Process uploads
    file_refs = []
    for file_path in uploaded_files:
        result = self.process_file_upload(file_path)
        if result["success"]:
            file_refs.append(f"- {result['name']} → {result['path']} ({result['type']})")

    # Add file references to message
    if file_refs:
        file_list = "\n".join(file_refs)
        user_input = f"{user_input}\n\n上传的文件：\n{file_list}"

    # ... continue with normal message handling
```

### 4.5 工作区清理

**需求描述**：自动清理超过 7 天的旧工作区。

**清理逻辑**：
```python
# shared/workspace/manager.py:195-225
def cleanup_old_workspaces(self, days: int = 7):
    """Delete workspaces older than N days"""

    if not self.base_dir.exists():
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted_count = 0

    for workspace in self.base_dir.iterdir():
        if not workspace.is_dir():
            continue

        # Read metadata
        metadata_file = workspace / ".metadata.json"
        if not metadata_file.exists():
            continue

        with open(metadata_file) as f:
            metadata = json.load(f)

        # Check age
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
    """Handle slash commands"""

    if command == "/clean":
        count = self.workspace_manager.cleanup_old_workspaces(days=7)
        print(f"✓ Cleaned up {count} old workspaces")
        return True

    # ... other commands
```

### 4.6 文档读取与搜索工具

**需求描述**：提供文件查找、读取和内容搜索能力，支持文本文件和文档格式（PDF、DOCX、XLSX、PPTX）。

**核心工具**：

#### find_files - 文件名模式匹配
```python
# generalAgent/tools/builtin/find_files.py:30-60
@tool
def find_files(
    pattern: Annotated[str, "Glob pattern (e.g., '*.pdf', '**/*.py', '*report*')"],
    path: Annotated[str, "Directory to search (default: workspace root)"] = "."
) -> str:
    """Find files by name pattern (fast, doesn't read file content)."""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # Resolve search directory
    search_dir = resolve_workspace_path(path, workspace_root, must_exist=True)

    # Find matching files
    matches = list(search_dir.glob(pattern))

    # Filter hidden files and index directories
    matches = [
        f for f in matches
        if not any(part.startswith('.') for part in f.parts)
        and '.indexes' not in f.parts
    ]

    # Sort by modification time (newest first)
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return format_results(matches)
```

**特点**：
- 支持 glob 模式（`*.pdf`, `**/*.txt`, `*report*`）
- 过滤隐藏文件和索引目录
- 按修改时间排序
- 显示文件大小

#### read_file - 文件内容读取（增强版）
```python
# generalAgent/tools/builtin/file_ops.py:45-120
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace (text files and documents)"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    target_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    file_ext = target_path.suffix.lower()
    settings = get_settings()

    # Strategy 1: Text files
    if file_ext in TEXT_EXTENSIONS:
        file_size = target_path.stat().st_size

        if file_size < settings.documents.text_file_max_size:
            # Read full content
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            # Return preview with search hint
            with open(target_path, "r", encoding="utf-8") as f:
                preview = f.read(settings.documents.text_preview_chars)
            return f"{preview}\n\n💡 提示：文件较大，使用 search_file 搜索特定内容"

    # Strategy 2: Document files (PDF, DOCX, XLSX, PPTX)
    if file_ext in DOCUMENT_EXTENSIONS:
        doc_info = get_document_info(target_path)

        if doc_info["pages"] <= 10:
            # Small document: read full content
            return extract_full_document(target_path)
        else:
            # Large document: return preview
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
- 文本文件：< 100KB 全量读取，否则预览前 50KB
- PDF/DOCX：≤ 10 页全量，否则预览前 10 页
- XLSX：≤ 3 sheets 全量，否则预览前 3 sheets
- PPTX：≤ 15 slides 全量，否则预览前 15 slides

#### search_file - 内容搜索
```python
# generalAgent/tools/builtin/search_file.py:45-120
@tool
def search_file(
    path: Annotated[str, "File path relative to workspace"],
    query: Annotated[str, "Search keywords or phrase"],
    max_results: Annotated[int, "Maximum results to return"] = 5
) -> str:
    """Search for content in a file (supports text files and documents)."""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    target_path = resolve_workspace_path(path, workspace_root, must_exist=True)

    file_ext = target_path.suffix.lower()

    # Strategy 1: Text files - Real-time scanning
    if file_ext in TEXT_EXTENSIONS:
        return _search_text_file(target_path, query, max_results)

    # Strategy 2: Document files - Index-based search
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
   - 后续搜索秒级响应（0.01s vs 0.04s）
   - 多策略评分系统：
     - 短语匹配：+10 分
     - 三元组匹配：+5 分
     - 二元组匹配：+3 分
     - 关键词精确：+2 分
     - 关键词模糊：+1 分
     - 覆盖率奖励：+0-2 分

**索引管理**：
```python
# generalAgent/utils/text_indexer.py:150-220
def create_index(file_path: Path) -> Path:
    """创建文档搜索索引"""

    # Compute MD5 hash
    file_hash = compute_file_hash(file_path)

    # Check if index exists
    index_path = get_index_path(file_hash)
    if index_path.exists():
        # Update metadata only
        return index_path

    # Clean up old indexes for same file path (orphan cleanup)
    cleanup_old_indexes_for_file(file_path, keep_hash=file_hash)

    # Extract and chunk document
    chunks = chunk_document(file_path)

    # Build index
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

    # Save index
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    return index_path
```

**索引存储策略**：
- **全局存储**：`data/indexes/{hash[:2]}/{hash}.index.json`
- **两级目录结构**：使用 hash 前两位作为子目录（256 个子目录，避免单目录过多文件）
- **MD5 去重**：相同内容只创建一次索引（跨会话复用）
- **孤儿索引清理**：上传同名文件时自动删除旧索引
- **过期检测**：24 小时未访问的索引标记为 stale

**孤儿索引清理机制**：
```python
# generalAgent/utils/text_indexer.py:100-145
def cleanup_old_indexes_for_file(file_path: Path, keep_hash: str):
    """清理指定文件路径的旧索引（处理同名文件覆盖场景）

    场景：用户在同一 session 上传同名文件但内容不同（MD5 不同）
    - 旧索引成为孤儿（file_path 匹配但 hash 不同）
    - 此函数在创建新索引前自动清理旧索引
    """

    if not INDEXES_DIR.exists():
        return 0

    deleted_count = 0

    # Scan all index files
    for index_file in INDEXES_DIR.rglob("*.index.json"):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            # Check if index is for same file path but different hash
            if (index_data.get("file_path") == str(file_path)
                and index_data.get("file_hash") != keep_hash):

                index_file.unlink()
                deleted_count += 1
                LOGGER.info(f"Deleted orphan index: {index_file.name} (replaced by {keep_hash[:8]})")

        except Exception as e:
            LOGGER.debug(f"Error checking index {index_file}: {e}")
            continue

    return deleted_count
```

**配置**：
```python
# generalAgent/config/settings.py:115-135
class DocumentSettings(BaseModel):
    """Document reading and indexing settings"""

    # Text file limits
    text_file_max_size: int = 100_000        # 100KB
    text_preview_chars: int = 50_000         # 50KB preview

    # Document preview limits
    pdf_preview_pages: int = 10
    pdf_preview_chars: int = 30_000
    docx_preview_pages: int = 10
    docx_preview_chars: int = 30_000
    xlsx_preview_sheets: int = 3
    xlsx_preview_chars: int = 20_000
    pptx_preview_slides: int = 15
    pptx_preview_chars: int = 25_000

    # Search settings
    search_max_results_default: int = 5
    index_stale_threshold_hours: int = 24
```

**设计考量**：
- **Unix 哲学**：三个工具各司其职（find/read/search），避免功能混杂
- **自动索引**：首次搜索时自动创建索引，用户无感知
- **全局去重**：相同文件跨会话共享索引，节省存储和计算
- **孤儿清理**：自动处理同名文件覆盖场景，保持索引目录整洁
- **长度保护**：预览机制防止上下文溢出，引导用户使用搜索工具

---

## 5. 会话管理需求

### 5.1 会话持久化（SQLite）

**需求描述**：使用 SQLite 数据库持久化会话状态，支持跨次运行恢复对话。

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
        """Create new session record"""

    def get_session(self, thread_id: str) -> Optional[dict]:
        """Retrieve session by thread_id"""

    def list_sessions(self, user_id: str = None, limit: int = 20) -> List[dict]:
        """List recent sessions"""

    def delete_session(self, thread_id: str):
        """Delete session and all checkpoints"""

    def save_checkpoint(self, thread_id: str, checkpoint: dict):
        """Save conversation checkpoint"""

    def load_checkpoint(self, thread_id: str) -> Optional[dict]:
        """Load latest checkpoint"""
```

**与 LangGraph Checkpointer 集成**：
```python
# generalAgent/persistence/checkpointer.py:15-40
def build_checkpointer(db_path: str) -> Optional[SqliteSaver]:
    """Build SQLite checkpointer for LangGraph"""

    if not db_path:
        return None

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # Connect to SQLite
    conn = sqlite3.connect(str(db_file), check_same_thread=False)

    # Create LangGraph checkpointer
    checkpointer = SqliteSaver(conn)

    return checkpointer
```

**应用到图**：
```python
# generalAgent/runtime/app.py:125-130
checkpointer = build_checkpointer(settings.observability.session_db_path)
if checkpointer:
    LOGGER.info("Session persistence enabled (SQLite)")

app = graph.build_state_graph(
    ...,
    checkpointer=checkpointer,
)
```

### 5.2 会话生命周期

**需求描述**：管理会话的创建、加载、重置、保存流程。

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
        """Create new session with workspace"""

        thread_id = self._generate_thread_id()

        # Create session record
        self.session_store.create_session(thread_id, user_id)

        # Create workspace
        self.workspace_manager.create_workspace(thread_id)

        self.current_session_id = thread_id
        return thread_id

    def load_session(self, thread_id_prefix: str) -> bool:
        """Load existing session by ID prefix"""

        # Find matching session
        sessions = self.session_store.list_sessions()
        matches = [s for s in sessions if s["thread_id"].startswith(thread_id_prefix)]

        if not matches:
            return False

        session = matches[0]
        thread_id = session["thread_id"]

        # Load workspace
        workspace = self.workspace_manager.base_dir / thread_id
        if not workspace.exists():
            return False

        self.workspace_manager.workspace_path = workspace
        self.current_session_id = thread_id
        return True

    def reset_session(self):
        """Reset current session (clear state but keep workspace)"""

        if not self.current_session_id:
            return

        # Delete checkpoints (keep session record)
        self.session_store.delete_checkpoints(self.current_session_id)

        # Keep workspace but clear temp/
        temp_dir = self.workspace_manager.workspace_path / "temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            temp_dir.mkdir()
```

**CLI 命令集成**：
```python
# generalAgent/cli.py:50-90
async def handle_command(self, command: str) -> bool:
    """Handle slash commands"""

    if command == "/reset":
        self.session_manager.reset_session()
        print("✓ Session reset")
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
            print(f"✓ Loaded session: {self.session_manager.current_session_id}")
        else:
            print(f"✗ Session not found: {prefix}")
        return True

    if command == "/current":
        if self.session_manager.current_session_id:
            print(f"Current session: {self.session_manager.current_session_id}")
        else:
            print("No active session")
        return True

    return False
```

### 5.3 会话自动保存

**需求描述**：每轮对话结束后自动保存会话状态。

**实现方式**：
```python
# generalAgent/cli.py:250-270
async def handle_user_message(self, user_input: str):
    """Handle user message"""

    # ... create user message ...

    # Stream graph execution
    async for chunk in self.app.astream(...):
        # ... process chunks ...
        pass

    # Auto-save session after turn
    if self.session_manager.current_session_id:
        await self._save_session()

async def _save_session(self):
    """Save current session state"""

    # LangGraph checkpointer automatically saves state
    # We only need to update session metadata

    self.session_store.update_session(
        self.session_manager.current_session_id,
        metadata={"last_message": "...", "turn_count": 10}
    )
```

**设计考量**：
- LangGraph Checkpointer 自动保存图状态
- SessionStore 保存额外元数据
- 每轮对话后自动触发

---

## 6. 模型路由需求

### 6.1 多模型插槽系统

**需求描述**：支持 5 种模型插槽，根据任务类型路由到不同模型。

**模型插槽定义**：
```python
# generalAgent/config/settings.py:45-75
class ModelSlots(BaseModel):
    base: Optional[ModelConfig] = None       # 基础对话
    reasoning: Optional[ModelConfig] = None  # 深度推理
    vision: Optional[ModelConfig] = None     # 图文理解
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
    """Resolve model configs from environment variables"""

    configs = {}

    # Map provider aliases to canonical names
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

### 6.2 模型注册表

**需求描述**：统一管理所有已配置的模型实例。

**ModelRegistry 实现**：
```python
# generalAgent/models/registry.py:20-70
class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, BaseChatModel] = {}

    def register(self, slot: str, model: BaseChatModel):
        """Register model for a slot"""
        self._models[slot] = model

    def get(self, slot: str) -> Optional[BaseChatModel]:
        """Get model by slot name"""
        return self._models.get(slot)

    def list_slots(self) -> List[str]:
        """List all registered slots"""
        return list(self._models.keys())

def build_default_registry(model_ids: Dict[str, str]) -> ModelRegistry:
    """Build registry from model IDs"""

    registry = ModelRegistry()

    for slot, model_id in model_ids.items():
        # Get config from environment
        config = resolve_model_config(slot)

        # Create ChatOpenAI instance (works with OpenAI-compatible APIs)
        model = ChatOpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model=model_id,
            temperature=config.get("temperature", 0.7),
        )

        registry.register(slot, model)

    return registry
```

### 6.3 动态模型解析

**需求描述**：根据任务特征和用户偏好动态选择模型。

**ModelResolver 接口**：
```python
# generalAgent/agents/model_resolver.py:10-30
class ModelResolver:
    def resolve(self, state: AppState, node_name: str) -> str:
        """Resolve model slot for current node"""
        raise NotImplementedError
```

**默认实现**：
```python
# generalAgent/runtime/model_resolver.py:55-95
class DefaultModelResolver(ModelResolver):
    def __init__(self, model_configs: Dict[str, dict]):
        self.configs = model_configs

    def resolve(self, state: AppState, node_name: str) -> str:
        """Resolve model based on context"""

        # Check user preference
        if state.get("model_pref"):
            return state["model_pref"]

        # Check images (need vision model)
        if state.get("images"):
            if "vision" in self.configs:
                return "vision"

        # Node-specific routing
        if node_name == "agent":
            # Use code model if working with code files
            if self._has_code_context(state):
                return "code"

            # Use reasoning model for complex tasks
            if self._is_complex_task(state):
                return "reasoning"

            # Default to base model
            return "base"

        elif node_name == "finalize":
            # Use chat model for final response
            return "chat" if "chat" in self.configs else "base"

        return "base"
```

**应用到节点**：
```python
# generalAgent/graph/nodes/planner.py:285-295
def planner_node(state: AppState):
    """Agent node with dynamic model selection"""

    # Resolve model
    model_slot = model_resolver.resolve(state, "agent")
    model = model_registry.get(model_slot)

    # Invoke model
    result = model.invoke(messages, tools=visible_tools)

    return {"messages": [result], "loops": state["loops"] + 1}
```

**设计考量**：
- 可扩展（自定义 ModelResolver）
- 上下文感知（检测图片、代码、复杂度）
- 用户可覆盖（model_pref）
