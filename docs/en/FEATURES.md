# Features Documentation

> **Note**: This document consolidates REQUIREMENTS_PART2, PART3, PART5, and PART6, providing comprehensive technical details about AgentGraph's core features.

## Table of Contents

- [Part 1: Workspace Isolation](#part-1-workspace-isolation)
  - [1.1 Workspace Directory Structure](#11-workspace-directory-structure)
  - [1.2 File Operation Tools](#12-file-operation-tools)
  - [1.3 Path Security and Isolation](#13-path-security-and-isolation)
  - [1.4 Workspace Cleanup](#14-workspace-cleanup)
  - [1.5 Session Management](#15-session-management)
  - [1.6 Session Persistence (SQLite)](#16-session-persistence-sqlite)
  - [1.7 Model Routing](#17-model-routing)
- [Part 2: @Mention System](#part-2-mention-system)
  - [2.1 Three Types of Mentions](#21-three-types-of-mentions)
  - [2.2 Mention Classification](#22-mention-classification)
  - [2.3 On-Demand Tool Loading](#23-on-demand-tool-loading)
  - [2.4 Skill Loading](#24-skill-loading)
  - [2.5 Delegated agent Delegation](#25-delegated agent-delegation)
  - [2.6 Dynamic System Reminders](#26-dynamic-system-reminders)
- [Part 3: File Upload System](#part-3-file-upload-system)
  - [3.1 File Type Detection](#31-file-type-detection)
  - [3.2 Upload Processing Flow](#32-upload-processing-flow)
  - [3.3 File Reference Injection](#33-file-reference-injection)
  - [3.4 Auto Skill Recommendation](#34-auto-skill-recommendation)
  - [3.5 Multi-File Support](#35-multi-file-support)
- [Part 4: Message History Management](#part-4-message-history-management)
  - [4.1 Message History Limits](#41-message-history-limits)
  - [4.2 Clean vs Truncate Strategies](#42-clean-vs-truncate-strategies)
  - [4.3 Message Role Definitions](#43-message-role-definitions)
  - [4.4 System Prompt Management](#44-system-prompt-management)
- [Part 5: Delegated agent System](#part-5-delegated agent-system)
  - [5.1 Delegated agent Architecture](#51-delegated agent-architecture)
  - [5.2 delegate_task Tool](#52-delegate_task-tool)
  - [5.3 Context Isolation](#53-context-isolation)
  - [5.4 Delegated agent System Prompts](#54-delegated agent-system-prompts)
  - [5.5 Use Cases](#55-use-cases)
- [Part 6: MCP Integration](#part-6-mcp-integration)
  - [6.1 MCP Architecture](#61-mcp-architecture)
  - [6.2 Lazy Server Startup](#62-lazy-server-startup)
  - [6.3 Dual Protocol Support (stdio/SSE)](#63-dual-protocol-support-stdiose)
  - [6.4 MCP Configuration](#64-mcp-configuration)
  - [6.5 Tool Registration](#65-tool-registration)
  - [6.6 Usage Examples](#66-usage-examples)
- [Part 7: HITL (Human-in-the-Loop)](#part-7-hitl-human-in-the-loop)
  - [7.1 Two HITL Patterns](#71-two-hitl-patterns)
  - [7.2 ask_human Tool](#72-ask_human-tool)
  - [7.3 Tool Approval Framework](#73-tool-approval-framework)
  - [7.4 Approval Rules System](#74-approval-rules-system)
  - [7.5 Configuration](#75-configuration)
  - [7.6 Usage Examples](#76-usage-examples)

---

## Part 1: Workspace Isolation

### 1.1 Workspace Directory Structure

**Requirement**: Each session has an isolated workspace directory inspired by OpenAI Code Interpreter and E2B.

**Directory Structure**:
```
data/workspace/{session_id}/
├── skills/           # Symlinked skills (read-only)
│   └── pdf/
│       ├── SKILL.md
│       ├── forms.md
│       ├── reference.md
│       └── scripts/
├── uploads/          # User-uploaded files
├── outputs/          # Agent-generated outputs
├── temp/             # Temporary files
└── .metadata.json    # Session metadata
```

**Implementation**:
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

### 1.2 File Operation Tools

The agent has access to a comprehensive set of file operation tools following the Unix philosophy (single responsibility principle).

#### find_files - File Name Pattern Matching

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

**Features**:
- Supports glob patterns (`*.pdf`, `**/*.txt`, `*report*`)
- Filters hidden files and index directories
- Sorted by modification time
- Displays file sizes

#### read_file - File Content Reading (Enhanced)

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

**Document Processing Capabilities**:
- PDF: Uses pdfplumber to extract text and tables
- DOCX: Uses python-docx to extract paragraphs and tables
- XLSX: Uses openpyxl to read worksheets
- PPTX: Uses python-pptx to extract slide text

**Length Limit Strategy**:
- Text files: < 100KB full read, otherwise preview first 50KB
- PDF/DOCX: ≤ 10 pages full, otherwise preview first 10 pages
- XLSX: ≤ 3 sheets full, otherwise preview first 3 sheets
- PPTX: ≤ 15 slides full, otherwise preview first 15 slides

#### search_file - Content Search

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

**Dual Strategy Search**:

1. **Text Files**: Real-time line-by-line scanning
   - Case-insensitive
   - Shows matching line with 1 line context before/after
   - Highlights matching text

2. **Document Files**: Index-based search
   - First search automatically creates index (stored in `data/indexes/`)
   - Subsequent searches are instant (0.01s vs 0.04s)
   - Multi-strategy scoring system:
     - Phrase match: +10 points
     - Trigram match: +5 points
     - Bigram match: +3 points
     - Keyword exact: +2 points
     - Keyword fuzzy: +1 point
     - Coverage bonus: +0-2 points

#### Index Management

```python
# generalAgent/utils/text_indexer.py:150-220
def create_index(file_path: Path) -> Path:
    """Create document search index"""

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

**Index Storage Strategy**:
- **Global storage**: `data/indexes/{hash[:2]}/{hash}.index.json`
- **Two-level directory structure**: Uses first 2 chars of hash as subdirectory (256 subdirs, avoid too many files per directory)
- **MD5 deduplication**: Same content only creates index once (cross-session reuse)
- **Orphan index cleanup**: Automatically deletes old index when uploading same-name file with different content
- **Staleness detection**: Indexes not accessed for 24 hours are marked as stale

#### Orphan Index Cleanup Mechanism

```python
# generalAgent/utils/text_indexer.py:100-145
def cleanup_old_indexes_for_file(file_path: Path, keep_hash: str):
    """Clean up old indexes for specified file path (handles same-name file overwrite scenario)

    Scenario: User uploads same-name file with different content (different MD5) in same session
    - Old index becomes orphan (file_path matches but hash differs)
    - This function automatically cleans up old index before creating new one
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

**Configuration**:
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

**Design Considerations**:
- **Unix Philosophy**: Three tools with single responsibility (find/read/search), avoid feature mixing
- **Automatic indexing**: First search automatically creates index, transparent to user
- **Global deduplication**: Same file shares index across sessions, saves storage and computation
- **Orphan cleanup**: Automatically handles same-name file overwrite scenario, keeps index directory clean
- **Length protection**: Preview mechanism prevents context overflow, guides user to use search tool

**Tool Selection Guide**:
- Use `find_files` when: Looking for files by name/pattern
- Use `read_file` when: Want to see document content/preview
- Use `search_file` when: Looking for specific keywords or information within a file
- For large documents: Always prefer `search_file` over `read_file` for finding specific content

### 1.3 Path Security and Isolation

**Requirement**: Tools can only access files within workspace, preventing path traversal attacks.

**Two-Step Validation Mechanism**:
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

**Application to File Tools**:
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

**Design Considerations**:
- `resolve()` handles symlinks and `..` paths
- `relative_to()` checks if path is within workspace
- Write permissions only for outputs/, temp/, uploads/
- skills/ directory is read-only (symlinked)

**Skill Symlinks**:
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

**Symlink Benefits**:
- No file copying, saves space
- Skill updates automatically reflect in all sessions
- Read-only access prevents accidental modification

**list_workspace_files Symlink Handling**:
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

### 1.4 Workspace Cleanup

**Requirement**: Automatically clean up workspaces older than 7 days.

**Cleanup Logic**:
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

**Trigger Timing**:
- Automatic cleanup on program exit
- User executes `/clean` command

**Implementation**:
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

### 1.5 Session Management

**Requirement**: Manage session creation, loading, reset, and save lifecycle.

**SessionManager Implementation**:
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

**CLI Command Integration**:
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

### 1.6 Session Persistence (SQLite)

**Requirement**: Use SQLite database to persist session state, supporting cross-run conversation recovery.

**Database Structure**:
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

**SessionStore Interface**:
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

**Integration with LangGraph Checkpointer**:
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

**Application to Graph**:
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

**Auto-Save Session**:
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

### 1.7 Model Routing

**Requirement**: Support 5 model slots, routing to different models based on task type.

**Model Slot Definition**:
```python
# generalAgent/config/settings.py:45-75
class ModelSlots(BaseModel):
    base: Optional[ModelConfig] = None       # Basic conversation
    reasoning: Optional[ModelConfig] = None  # Deep reasoning
    vision: Optional[ModelConfig] = None     # Vision understanding
    code: Optional[ModelConfig] = None       # Code generation
    chat: Optional[ModelConfig] = None       # Chat dialogue
```

**ModelConfig Definition**:
```python
class ModelConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    id: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
```

**Environment Variable Mapping**:
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

**Model Registry**:
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

**Dynamic Model Resolution**:
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

**Application to Node**:
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

---

## Part 2: @Mention System

### 2.1 Three Types of Mentions

**Requirement**: System recognizes user input @mentions and classifies them into three types: tool, skill, agent.

**Classification Logic**:
```python
# generalAgent/utils/mention_classifier.py:10-50
def classify_mention(
    mention: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
) -> Literal["tool", "skill", "agent"]:
    """Classify @mention into tool, skill, or agent"""

    # Strip @ prefix if present
    name = mention.lstrip("@")

    # Priority 1: Check if it's a registered or discovered tool
    if tool_registry.has_tool(name):
        return "tool"

    # Priority 2: Check if it's a registered skill
    if skill_registry.has_skill(name):
        return "skill"

    # Priority 3: Check for agent keywords
    agent_keywords = ["delegated agent", "agent", "助手", "代理"]
    if any(keyword in name.lower() for keyword in agent_keywords):
        return "agent"

    # Default: treat as tool (might be misspelled or new tool)
    return "tool"
```

**Classification Priority**:
1. **Tool**: Registered or discovered tool
2. **Skill**: Registered skill
3. **Agent**: Contains agent keywords
4. **Default**: Downgrade to tool (permissive handling)

### 2.2 Mention Classification

**Requirement**: Extract all @mentions from user input.

**Parsing Logic**:
```python
# generalAgent/cli.py:155-175
def parse_mentions(self, user_input: str) -> List[str]:
    """Extract @mentions from user input"""

    import re

    # Match @word or @word-with-dash
    pattern = r"@([\w\-]+)"
    matches = re.findall(pattern, user_input)

    return list(set(matches))  # Deduplicate
```

**Application Scenario**:
```python
# generalAgent/cli.py:240-260
async def handle_user_message(self, user_input: str):
    """Handle user message with @mention support"""

    # Parse @mentions
    mentions = self.parse_mentions(user_input)

    # Classify mentions
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

    # ... update state with mentions
```

### 2.3 On-Demand Tool Loading

**Requirement**: When user @mentions a tool, load it from discovered pool to registered pool.

**Loading Logic**:
```python
# generalAgent/graph/nodes/planner.py:200-220
def build_visible_tools(...):
    """Build visible tools including @mentioned ones"""

    visible = []
    seen_names = set()

    # ... add persistent and allowed tools ...

    # Load @mentioned tools on-demand
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "tool" and mention not in seen_names:
            # Load from discovered pool
            tool = tool_registry.load_on_demand(mention)

            if tool:
                visible.append(tool)
                seen_names.add(mention)
            else:
                LOGGER.warning(f"Tool '{mention}' not found in registry")

    return visible
```

**ToolRegistry.load_on_demand**:
```python
# generalAgent/tools/registry.py:85-100
def load_on_demand(self, tool_name: str) -> Optional[Any]:
    """Load tool from discovered pool when @mentioned"""

    # Already registered, return directly
    if tool_name in self._tools:
        return self._tools[tool_name]

    # Load from discovered pool
    if tool_name in self._discovered:
        tool = self._discovered[tool_name]
        self.register_tool(tool)  # Move to registered pool
        LOGGER.info(f"✓ Loaded tool on-demand: {tool_name}")
        return tool

    LOGGER.warning(f"✗ Tool not found in discovered pool: {tool_name}")
    return None
```

### 2.4 Skill Loading

**Requirement**: When user @mentions a skill, load skill to workspace and generate system reminder.

**Skill Loading**:
```python
# generalAgent/cli.py:280-300
async def handle_user_message(self, user_input: str):
    """Handle user message"""

    # ... parse mentions ...

    # Load mentioned skills into workspace
    for skill_id in mentioned_skills:
        success = self.workspace_manager.load_skill(skill_id)
        if success:
            print(f"✓ Loaded skill: {skill_id}")
        else:
            print(f"✗ Skill not found: {skill_id}")

    # ... continue with message ...
```

**System Reminder Generation**:
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

**Inject to System Prompt**:
```python
# generalAgent/graph/nodes/planner.py:270-275
dynamic_reminder = build_dynamic_reminder(
    mentioned_skills=mentioned_skills,
    ...
)

if dynamic_reminder:
    system_parts.append(dynamic_reminder)
```

**Skill Configuration Management** (Added 2025-10-27):

Skills are managed through `generalAgent/config/skills.yaml` configuration file:

```yaml
# generalAgent/config/skills.yaml
optional:
  pdf:
    enabled: false  # Not shown in catalog
    auto_load_on_file_types: ["pdf"]
    description: "PDF processing"

  docx:
    enabled: true  # Shown in catalog
    auto_load_on_file_types: ["docx"]
    description: "DOCX processing"
```

**Skills Catalog Filtering**:
- `build_skills_catalog(skill_registry, skill_config)` only shows skills with `enabled: true`
- Reduces SystemMessage noise, prevents information leakage
- Disabled skills can still be triggered via @mention or file upload

**Dynamic File Upload Hints**:
- Dynamically generated hints based on `auto_load_on_file_types`
- Example: Upload `report.docx` → generates `[可用 @docx 处理]`
- Uses actual file extension matching (e.g., `"docx"`), not generic types (e.g., `"office"`)

See: `docs/SKILLS_CONFIGURATION.md`

### 2.5 Delegated agent Delegation

**Requirement**: When user @mentions agent, load delegate_task tool.

**Loading Logic**:
```python
# generalAgent/graph/nodes/planner.py:205-225
def build_visible_tools(...):
    """Build visible tools"""

    # ... add other tools ...

    # Load delegate_task when agent mentioned
    for mention in state.get("mentioned_agents", []):
        mention_type = classify_mention(mention, tool_registry, skill_registry)

        if mention_type == "agent":
            # Load delegate_task tool
            tool = tool_registry.get_tool("delegate_task")
            if tool and "delegate_task" not in seen_names:
                visible.append(tool)
                seen_names.add("delegate_task")

    return visible
```

**System Reminder Generation**:
```python
# generalAgent/graph/prompts.py:218-221
if mentioned_agents:
    agents_str = "、".join(mentioned_agents)
    reminders.append(
        f"<system_reminder>用户提到了代理：{agents_str}。"
        f"你可以使用 delegate_task 工具将任务委派给子代理执行。</system_reminder>"
    )
```

### 2.6 Dynamic System Reminders

**Requirement**: Dynamically generate system reminders based on context, inject into system prompt.

**Complete Implementation**:
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
    """Build dynamic system reminder based on context"""

    reminders = []

    # Active skill reminder
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

    # Images (optional, currently disabled)
    # if has_images:
    #     reminders.append("<system_reminder>用户分享了图片...</system_reminder>")

    return "\n\n".join(reminders) if reminders else ""
```

**Application to System Prompt**:
```python
# generalAgent/graph/nodes/planner.py:265-280
def planner_node(state: AppState):
    """Agent node"""

    # Build system prompt parts
    system_parts = [PLANNER_SYSTEM_PROMPT]

    # Add skills catalog (filtered by skill_config)
    # Only skills with enabled: true in skills.yaml are shown
    skills_catalog = build_skills_catalog(skill_registry, skill_config)
    if skills_catalog:
        system_parts.append(skills_catalog)

    # Add dynamic reminders
    dynamic_reminder = build_dynamic_reminder(
        active_skill=state.get("active_skill"),
        mentioned_tools=...,
        mentioned_skills=...,
        mentioned_agents=...,
    )
    if dynamic_reminder:
        system_parts.append(dynamic_reminder)

    # Combine
    system_prompt = "\n\n---\n\n".join(system_parts)
```

---

## Part 3: File Upload System

### 3.1 File Type Detection

**Requirement**: Automatically detect file type based on file extension.

**Implementation**:
```python
# generalAgent/utils/file_processor.py:55-85
def detect_file_type(file_path: Path) -> str:
    """Detect file type from extension"""

    ext = file_path.suffix.lower()

    type_map = {
        # Documents
        ".pdf": "pdf",
        ".docx": "document",
        ".doc": "document",
        ".txt": "text",
        ".md": "markdown",
        ".rtf": "document",

        # Spreadsheets
        ".xlsx": "spreadsheet",
        ".xls": "spreadsheet",
        ".csv": "csv",

        # Code
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".cpp": "cpp",

        # Data
        ".json": "json",
        ".yaml": "yaml",
        ".xml": "xml",

        # Images
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".gif": "image",
        ".bmp": "image",
        ".svg": "image",

        # Archives
        ".zip": "archive",
        ".tar": "archive",
        ".gz": "archive",
    }

    return type_map.get(ext, "unknown")
```

### 3.2 Upload Processing Flow

**Requirement**: After user uploads file, automatically copy to workspace/uploads/ directory.

**CLI Processing**:
```python
# generalAgent/cli.py:180-215
def process_file_upload(self, file_path: str) -> dict:
    """Process user-uploaded file"""

    src_path = Path(file_path)

    # Validate existence
    if not src_path.exists():
        return {"success": False, "error": "File not found"}

    # Detect type
    file_type = detect_file_type(src_path)

    # Copy to uploads/
    dest_path = self.workspace_path / "uploads" / src_path.name
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_path, dest_path)

    # Generate workspace-relative path
    rel_path = f"uploads/{src_path.name}"

    return {
        "success": True,
        "path": rel_path,
        "type": file_type,
        "name": src_path.name,
        "size": dest_path.stat().st_size,
    }
```

### 3.3 File Reference Injection

**Requirement**: Automatically add uploaded file reference information in user message.

**Message Enhancement**:
```python
# generalAgent/cli.py:230-255
async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """Handle user message with file uploads"""

    # Process each uploaded file
    file_refs = []
    for file_path in uploaded_files:
        result = self.process_file_upload(file_path)

        if result["success"]:
            file_refs.append(
                f"- {result['name']} → {result['path']} "
                f"({result['type']}, {result['size']} bytes)"
            )
        else:
            file_refs.append(f"- {file_path} → Error: {result['error']}")

    # Inject file references into message
    if file_refs:
        file_list = "\n".join(file_refs)
        enhanced_input = f"{user_input}\n\n上传的文件：\n{file_list}"
    else:
        enhanced_input = user_input

    # Create HumanMessage
    message = HumanMessage(content=enhanced_input)

    # ... continue with graph execution ...
```

**Message Example**:
```
User> 帮我分析这个 PDF

上传的文件：
- report.pdf → uploads/report.pdf (pdf, 245678 bytes)
```

### 3.4 Auto Skill Recommendation

**Requirement**: Automatically recommend relevant skills based on uploaded file type.

**Recommendation Logic**:
```python
# generalAgent/cli.py:260-285
def recommend_skills_for_file(self, file_type: str) -> List[str]:
    """Recommend skills based on file type"""

    recommendations = {
        "pdf": ["pdf", "document"],
        "spreadsheet": ["excel", "data"],
        "image": ["image", "vision"],
        "code": ["code", "lint"],
        "document": ["document", "text"],
    }

    return recommendations.get(file_type, [])

async def handle_user_message(self, user_input: str, uploaded_files: List[str]):
    """Handle message with auto skill recommendation"""

    # ... process uploads ...

    # Recommend skills
    for file_result in upload_results:
        if file_result["success"]:
            skills = self.recommend_skills_for_file(file_result["type"])

            if skills:
                print(f"💡 推荐技能: {', '.join(['@' + s for s in skills])}")

    # ... continue ...
```

**Output Example**:
```
✓ Uploaded: report.pdf → uploads/report.pdf
💡 推荐技能: @pdf, @document
```

### 3.5 Multi-File Support

**Requirement**: Support uploading multiple files at once.

**CLI Interface**:
```python
# generalAgent/cli.py:120-150
async def run(self):
    """Main CLI loop"""

    while True:
        user_input = input("You> ")

        # Check for /upload command
        if user_input.startswith("/upload "):
            file_paths = user_input[8:].strip().split()

            # Process multiple files
            for file_path in file_paths:
                result = self.process_file_upload(file_path)
                if result["success"]:
                    print(f"✓ Uploaded: {result['name']}")
                else:
                    print(f"✗ Failed: {file_path}")

            continue

        # Normal message handling
        await self.handle_user_message(user_input)
```

**Usage Example**:
```bash
You> /upload report.pdf data.xlsx notes.txt
✓ Uploaded: report.pdf
✓ Uploaded: data.xlsx
✓ Uploaded: notes.txt

You> 帮我分析这三个文件
```

---

## Part 4: Message History Management

### 4.1 Message History Limits

**Requirement**: Limit the number of retained message history to prevent context overflow.

**Configuration**:
```bash
# .env
MAX_MESSAGE_HISTORY=40  # Default 40, range 10-100
```

**Settings Definition**:
```python
# generalAgent/config/settings.py:85-95
class GovernanceConfig(BaseModel):
    max_message_history: int = Field(
        default=40,
        ge=10,
        le=100,
        description="Maximum message history to keep"
    )
    max_loops: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum loop iterations"
    )
```

### 4.2 Clean vs Truncate Strategies

**Requirement**: Provide two message cleaning strategies: Clean (clean intermediate steps) and Truncate (simple truncation).

**Clean Strategy (Recommended)**:
```python
# generalAgent/utils/message_utils.py:15-70
def clean_messages(
    messages: List[BaseMessage],
    max_history: int = 40,
) -> List[BaseMessage]:
    """Clean messages by removing intermediate tool calls"""

    if len(messages) <= max_history:
        return messages

    # Keep first message (system/user)
    first_msg = messages[0]

    # Process remaining messages
    recent = messages[1:]

    # Identify complete turns (user → assistant → [tools] → assistant)
    turns = []
    current_turn = []

    for msg in recent:
        current_turn.append(msg)

        # Turn ends with assistant message (no tool_calls)
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            turns.append(current_turn)
            current_turn = []

    # Keep last N turns
    max_turns = max_history // 4  # Estimate ~4 messages per turn
    kept_turns = turns[-max_turns:]

    # Flatten
    cleaned = [first_msg]
    for turn in kept_turns:
        cleaned.extend(turn)

    return cleaned
```

**Truncate Strategy (Simple)**:
```python
# generalAgent/utils/message_utils.py:75-85
def truncate_messages(
    messages: List[BaseMessage],
    max_history: int = 40,
) -> List[BaseMessage]:
    """Simple truncation: keep first + last N"""

    if len(messages) <= max_history:
        return messages

    return [messages[0]] + messages[-(max_history - 1):]
```

**Application to Node**:
```python
# generalAgent/graph/nodes/planner.py:290-305
def planner_node(state: AppState):
    """Agent node"""

    messages = state["messages"]

    # Clean messages if too long
    max_history = settings.governance.max_message_history
    if len(messages) > max_history:
        messages = clean_messages(messages, max_history)

    # ... invoke model with cleaned messages ...
```

**Clean vs Truncate Comparison**:

| Strategy | Advantages | Disadvantages | Use Cases |
|----------|-----------|---------------|-----------|
| Clean | Maintains dialogue integrity, preserves complete turns | Complex implementation, may retain too much | Multi-turn dialogues, complex tasks |
| Truncate | Simple and fast, predictable | May cut tool call chains | Simple dialogues, experimental environments |

### 4.3 Message Role Definitions

**Requirement**: LangChain message types and their roles.

**Message Types**:
```python
from langchain_core.messages import (
    AIMessage,       # LLM output
    HumanMessage,    # User input
    SystemMessage,   # System prompt
    ToolMessage,     # Tool execution result
)
```

**Message Flow Example**:
```python
# Turn 1: User asks question
messages = [
    HumanMessage(content="帮我读取 uploads/data.txt"),
]

# Turn 2: Agent calls tool
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

# Turn 3: Tool returns result
messages.append(
    ToolMessage(
        content="File contents: ...",
        tool_call_id="call_123",
    )
)

# Turn 4: Agent responds to user
messages.append(
    AIMessage(content="文件内容是：...")
)
```

### 4.4 System Prompt Management

**Requirement**: System prompt is not stored in message history, but dynamically injected at each invocation.

**Implementation**:
```python
# generalAgent/graph/nodes/planner.py:265-285
def planner_node(state: AppState):
    """Agent node"""

    # Build system prompt dynamically
    system_prompt = build_system_prompt(state)

    # Get message history (no system message)
    messages = state["messages"]

    # Invoke model with system prompt
    result = model.invoke(
        messages,
        system=system_prompt,  # Injected at runtime
    )
```

**Benefits**:
- System prompt doesn't occupy message history quota
- Can update system prompt based on context each time
- Avoids system prompt being cleaned

---

## Part 5: Delegated agent System

### 5.1 Delegated agent Architecture

**Requirement**: Main Agent can delegate independent subtasks to Delegated agent for execution.

**Core Concepts**:
- Delegated agent has independent context (context_id + parent_context)
- Delegated agent uses same graph and tools
- Delegated agent cannot access parent agent's message history
- Delegated agent returns result after execution completes

**Advantages**:
- Avoids main Agent context accumulation
- Task failures don't pollute main history
- Supports parallel execution of multiple subtasks

### 5.2 delegate_task Tool

**Requirement**: Create and execute delegated agent through tool invocation.

**Tool Definition**:
```python
# generalAgent/tools/builtin/delegate_task.py:20-45
@tool
def delegate_task(
    task: str,
    max_loops: int = 15,
) -> str:
    """Delegate a subtask to a specialized delegated agent.

    Args:
        task: Clear description of the subtask to accomplish
        max_loops: Maximum execution loops (default 15)

    Returns:
        Delegated agent execution result

    Use cases:
    - Independent subtasks (file processing, debugging)
    - Multi-step operations that need multiple attempts
    - Tasks that shouldn't pollute main context
    """
```

**Implementation Logic**:
```python
# generalAgent/tools/builtin/delegate_task.py:50-120
def _execute_delegated agent(task: str, max_loops: int) -> str:
    """Execute delegated agent in isolated context"""

    # Get app graph (set by runtime/app.py)
    app = get_app_graph()
    if not app:
        return "Error: Application graph not available"

    # Generate delegated agent context ID
    delegated agent_id = f"delegated agent_{uuid.uuid4().hex[:8]}"

    # Get parent state from environment
    parent_context = os.environ.get("AGENT_CONTEXT_ID", "main")
    workspace_path = os.environ.get("AGENT_WORKSPACE_PATH")

    # Build initial state for delegated agent
    initial_state = {
        "messages": [HumanMessage(content=task)],
        "images": [],
        "active_skill": None,
        "allowed_tools": [],
        "mentioned_agents": [],
        "persistent_tools": [],
        "model_pref": None,
        "todos": [],
        "context_id": delegated agent_id,      # Unique context
        "parent_context": parent_context,  # Link to parent
        "loops": 0,
        "max_loops": max_loops,
        "workspace_path": workspace_path,  # Share workspace
        "thread_id": f"sub_{delegated agent_id}",  # Unique thread
    }

    # Execute delegated agent graph
    try:
        result = app.invoke(initial_state)

        # Extract final response
        final_message = result["messages"][-1]
        return final_message.content

    except Exception as e:
        return f"Delegated agent execution failed: {str(e)}"
```

### 5.3 Context Isolation

**Requirement**: Delegated agent and parent agent contexts are completely isolated.

**Isolation Mechanism**:

1. **Independent context_id**:
```python
parent_context_id = "main"
delegated agent_context_id = "delegated agent_a1b2c3d4"
```

2. **Independent message history**:
```python
# Parent messages
parent_messages = [
    HumanMessage("帮我分析这个项目"),
    AIMessage("我来分析..."),
    # ... 10+ messages ...
]

# Delegated agent messages (fresh start)
delegated agent_messages = [
    HumanMessage("读取 uploads/README.md 并总结")
]
```

3. **Shared workspace**:
```python
# Both share same workspace
workspace_path = "/data/workspace/session_123/"
```

4. **Independent thread_id**:
```python
parent_thread_id = "session_123"
delegated agent_thread_id = "sub_a1b2c3d4"
```

**Detecting Delegated agent Context**:
```python
# generalAgent/graph/nodes/planner.py:50-60
def planner_node(state: AppState):
    """Agent node"""

    is_delegated agent = state.get("parent_context") is not None

    if is_delegated agent:
        # Modify system prompt for delegated agent
        system_prompt = DELEGATED_AGENT_SYSTEM_PROMPT
    else:
        system_prompt = PLANNER_SYSTEM_PROMPT
```

### 5.4 Delegated agent System Prompts

**Requirement**: Delegated agent uses different system prompts, emphasizing task execution rather than dialogue.

**Delegated agent Prompt**:
```python
# generalAgent/graph/prompts.py:95-120
DELEGATED_AGENT_SYSTEM_PROMPT = """你是任务执行器（Delegated agent），负责完成主 Agent 委托的具体任务。

核心原则：
- 目标导向：只完成任务描述中的具体目标
- 直接执行：收到任务后立即使用工具完成，无需寒暄、确认、解释
- 返回结果：提供具体数据/分析，不是对话

工作流程：
1. 理解任务目标
2. 使用工具执行（如需外部信息/操作）或直接返回结果（如可直接回答）
3. 返回结果后立即停止

输出要求：
- ✅ "查询结果：北京今天晴天，15-25°C"
- ✅ "代码分析：该函数在 src/auth.py:42 定义"
- ❌ "好的，我来帮您查询天气"（不要寒暄）
- ❌ "让我先理解一下您的需求"（不要拖延）

限制：
- 不要询问用户（无法对话）

技能系统（Skills）：
- 使用 read_file 工具读取该技能的 `skills/{{skill_id}}/SKILL.md` 文件获取详细指导
- 根据指导执行相关操作
- Skills 不是 tools，而是知识包（文档）
"""
```

**Main Agent vs Sub Agent Prompt Comparison**:

| Dimension | Main Agent | Sub Agent |
|-----------|-----------|-----------|
| Style | Friendly dialogue | Task execution |
| Output | Explanation + result | Only result |
| Loops | Long loops (100+) | Short loops (15) |
| User interaction | Can ask | Cannot ask |

### 5.5 Use Cases

**Requirement**: Clarify when to use delegated agent.

**Recommended Scenarios**:

1. **Independent Sub-goals**:
```python
# Main task: Analyze project
# Subtask: Read and summarize README.md
delegate_task(task="读取 uploads/README.md 并总结核心功能（不超过 3 句话）")
```

2. **Multi-step Operations**:
```python
# Subtask: Debug script
delegate_task(
    task="运行 temp/script.py，如果出错则修复，直到成功运行",
    max_loops=20,
)
```

3. **Avoid Context Pollution**:
```python
# Parent Agent already has 30 messages
# Delegate file conversion task to Sub Agent (failure doesn't affect parent history)
delegate_task(task="将 uploads/1.pdf 转换为图片，保存到 outputs/pdf_images/")
```

**Not Recommended Scenarios**:
- Tasks requiring user interaction (delegated agent cannot ask user)
- Tasks requiring access to parent agent context (context isolated)
- Simple single-step operations (calling tool directly is faster)

---

## Part 6: MCP Integration

### 6.1 MCP Architecture

**Background**: MCP (Model Context Protocol) is a standard protocol for connecting external tools and services to Agent. Through MCP integration, AgentGraph can:

- Connect to external services like filesystem, GitHub, databases
- Use community-provided standard MCP servers
- Extend Agent capabilities without modifying core code

**Architecture Layers**:

```
Application Layer
    ↓
 ToolRegistry (unified tool interface)
    ↓
MCPToolWrapper (LangChain BaseTool)
    ↓
MCPServerManager (lifecycle management)
    ↓
MCPConnection (connection layer abstraction)
    ↓
MCP Server Process
```

**Key Components**:

#### 1. MCPConnection (Connection Layer)

**Responsibility**: Encapsulate underlying communication protocol

**File**: `generalAgent/tools/mcp/connection.py`

**Interface**:
```python
class MCPConnection(ABC):
    @abstractmethod
    async def connect(self) -> ClientSession:
        """Establish connection, return MCP ClientSession"""

    @abstractmethod
    async def close(self) -> None:
        """Close connection, cleanup resources"""
```

**Implementations**:
- `StdioMCPConnection`: Stdio mode (local process)
- `SSEMCPConnection`: SSE mode (HTTP server)

#### 2. MCPServerManager (Manager)

**Responsibility**: Server lifecycle management

**File**: `generalAgent/tools/mcp/manager.py`

**Core Methods**:
```python
class MCPServerManager:
    async def get_or_start_server(self, server_id: str) -> ClientSession:
        """Get or start server (lazy startup)"""

    async def shutdown(self) -> None:
        """Close all servers"""

    def is_running(self, server_id: str) -> bool:
        """Check server status"""
```

**State Management**:
```python
self._servers: Dict[str, ClientSession] = {}  # Started servers
self._connections: Dict[str, MCPConnection] = {}  # Connection objects
```

#### 3. MCPToolWrapper (Wrapper)

**Responsibility**: Convert MCP tool to LangChain BaseTool

**File**: `generalAgent/tools/mcp/wrapper.py`

**Core Code**:
```python
class MCPToolWrapper(BaseTool):
    name: str
    description: str
    server_id: str
    tool_name: str  # MCP original tool name
    manager: MCPServerManager

    async def _arun(self, **kwargs) -> str:
        # 1. Trigger lazy startup
        session = await self.manager.get_or_start_server(self.server_id)

        # 2. Call MCP tool
        result = await session.call_tool(self.tool_name, arguments=kwargs)

        # 3. Process result
        return self._format_result(result)
```

### 6.2 Lazy Server Startup

**Requirement**: MCP servers should start on first use, not at application startup.

**Reasons**:
- Speed up application startup
- Save resources (unused servers don't start)
- Reduce initialization error impact

**Lazy Startup Logic**:
1. First call to `get_or_start_server(server_id)`
2. Check if `server_id` is in `self._servers`
3. If not exists, create connection and start server
4. Cache session for subsequent use

**Log Output**:
```
🚀 Starting MCP server: test_stdio
  Command: python tests/mcp_servers/test_stdio_server.py
  ✓ MCP server started: test_stdio (mode: stdio)
```

### 6.3 Dual Protocol Support (stdio/SSE)

**Requirement**: Support both stdio and SSE connection modes.

**Reasons**:
- stdio: Suitable for local processes, simple and reliable
- SSE: Suitable for remote HTTP servers

**Implementation**: `MCPConnection` abstract class + two concrete implementations

### 6.4 MCP Configuration

**Configuration File Structure**:

**File**: `generalAgent/config/mcp_servers.yaml`

```yaml
# Global configuration
global:
  lazy_startup: true  # Lazy startup (default)

# Server configuration
servers:
  # Server ID
  filesystem:
    # Startup command
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"]

    # Enable this server
    enabled: true

    # Environment variables
    env:
      DEBUG: "true"

    # Connection mode: stdio or sse
    connection_mode: "stdio"

    # Tool configuration
    tools:
      read_file:
        enabled: true           # Enable this tool
        always_available: false # Don't auto-load to all agents
        alias: "fs_read"        # Custom name
        description: "Read file contents from allowed directory"

      write_file:
        enabled: false  # Disable this tool
```

**Configuration Examples**:

**Example 1: Filesystem Server (Official MCP Server)**:
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

**Example 2: Test Server (Local Development)**:
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

### 6.5 Tool Registration

**Startup Flow**:

**File**: `generalAgent/main.py`

```python
async def async_main():
    # 1. Load MCP configuration
    mcp_config_path = resolve_project_path("generalAgent/config/mcp_servers.yaml")

    if mcp_config_path.exists():
        logger.info("Loading MCP configuration...")

        # 2. Create MCPServerManager (servers not started)
        mcp_config = load_mcp_config(mcp_config_path)
        mcp_manager = MCPServerManager(mcp_config)

        # 3. Create MCPToolWrapper (tool wrappers)
        mcp_tools = load_mcp_tools(mcp_config, mcp_manager)
        logger.info(f"  MCP tools loaded: {len(mcp_tools)}")
    else:
        logger.info("No MCP configuration found, skipping MCP integration")
        mcp_tools = []

    # 4. Build application (register MCP tools)
    app, initial_state_factory, skill_registry, tool_registry = await build_application(
        mcp_tools=mcp_tools
    )

    # ... CLI running ...

    try:
        await cli.run()
    finally:
        # 5. Cleanup MCP servers
        if mcp_manager:
            logger.info("Cleaning up MCP servers...")
            await mcp_manager.shutdown()
```

**Tool Registration Flow**:

**File**: `generalAgent/runtime/app.py`

```python
async def build_application(
    mcp_tools: Optional[List[MCPToolWrapper]] = None,
) -> Tuple[...]:
    # 1. Scan builtin tools
    discovered_tools = scan_tools(...)

    # 2. Create ToolRegistry
    tool_registry = ToolRegistry()

    # 3. Register builtin tools
    for tool in discovered_tools:
        if tool_config.is_enabled(tool.name):
            tool_registry.register_tool(tool)

    # 4. Register MCP tools
    if mcp_tools:
        for mcp_tool in mcp_tools:
            tool_registry.register_tool(
                tool=mcp_tool,
                always_available=mcp_tool.always_available
            )

    # 5. Build Graph
    app = graph.build_state_graph(
        tool_registry=tool_registry,
        # ...
    )

    return app, initial_state_factory, skill_registry, tool_registry
```

### 6.6 Usage Examples

**Quick Start**:

#### 1. Install MCP SDK

```bash
pip install mcp
# Or use uv
uv pip install mcp
```

#### 2. Create Configuration File

```bash
cp generalAgent/config/mcp_servers.yaml.example generalAgent/config/mcp_servers.yaml
```

#### 3. Configure Test Server

Edit `mcp_servers.yaml`:
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

#### 4. Start AgentGraph

```bash
python main.py
```

Output should include:
```
Loading MCP configuration...
  MCP servers configured: 1
  MCP tools loaded: 1
    ✓ Loaded MCP tool: mcp_echo (server: test_stdio)
```

#### 5. Use MCP Tool

```
You> 使用 mcp_echo 工具发送消息 "Hello MCP!"

# First call triggers server startup
🚀 Starting MCP server: test_stdio
  ✓ MCP server started: test_stdio (mode: stdio)

A> [调用 mcp_echo 工具]
   Echo: Hello MCP!
```

**Adding Official MCP Servers**:

**Filesystem Server**:
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

**GitHub Server**:
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

## Part 7: HITL (Human-in-the-Loop)

### 7.1 Two HITL Patterns

AgentGraph integrates two HITL patterns for safety and interaction:

1. **ask_human tool**: Agent actively requests user input
2. **Tool Approval Framework**: System-level safety check, intercepts dangerous operations

**Pattern Comparison**:

| Feature | ask_human Tool | Tool Approval Framework |
|---------|---------------|------------------------|
| **Trigger** | Agent (LLM actively calls) | System (auto-detection) |
| **Purpose** | Get user input | Safety check |
| **User sees** | Question + input box | Tool info + approve/reject |
| **Added to history** | ✅ Yes (ToolMessage) | ❌ No (transparent) |
| **Use cases** | Missing info, need choice | Dangerous operations, permission control |
| **Configuration** | No config needed | `hitl_rules.yaml` |

### 7.2 ask_human Tool

#### Tool Interface

**File**: `generalAgent/tools/builtin/ask_human.py`

```python
@tool(args_schema=AskHumanInput)
def ask_human(
    question: str,                      # Question to ask
    context: str = "",                  # Additional context
    input_type: Literal["text"] = "text",  # Input type (future extension)
    default: Optional[str] = None,      # Default value
    required: bool = True,              # Whether required
) -> str:
    """Ask user for information

    When you lack necessary information to continue task, use this tool to ask user.
    User will see your question and provide answer, then you can continue task.

    When to use:
    - Need user to confirm details (e.g., confirm deletion)
    - Need user to make choice (e.g., choose city, date)
    - Missing key parameters (e.g., don't know what user wants)

    Args:
        question: Question to ask user (clear and concise)
        context: Additional context to help user understand
        default: Default answer (if user presses enter directly)
        required: Whether answer is required (default True)

    Returns:
        User's answer text
    """
    # Trigger interrupt
    answer = interrupt({
        "type": "user_input_request",
        "question": question,
        "context": context,
        "default": default,
        "required": required,
    })

    return answer or ""
```

#### Interrupt Handling

**File**: `generalAgent/cli.py` (Lines 252-288)

```python
async def _handle_message(self, user_input: str):
    # ... execute Graph ...

    # Check for interrupt
    while True:
        graph_state = await self.app.aget_state(config)

        if graph_state.next and graph_state.tasks and \
           hasattr(graph_state.tasks[0], 'interrupts') and \
           graph_state.tasks[0].interrupts:

            # Get interrupt data
            interrupt_value = graph_state.tasks[0].interrupts[0].value

            # Handle interrupt (user input or tool approval)
            resume_value = await self._handle_interrupt(interrupt_value)

            if resume_value is not None:
                # Resume Graph execution
                async for state_snapshot in self.app.astream(
                    Command(resume=resume_value),
                    config=config,
                    stream_mode="values"
                ):
                    await self._print_new_messages(state_snapshot)
        else:
            break
```

#### UI Prompt (Minimalist Version)

**File**: `generalAgent/cli.py` (Lines 370-405)

```python
async def _handle_user_input_request(self, data: dict) -> str:
    """Handle ask_human tool's user input request"""
    question = data.get("question", "")
    context = data.get("context", "")
    default = data.get("default")

    print()
    if context:
        print(f"💡 {context}")
    print(f"💬 {question}")
    if default:
        print(f"   (默认: {default})")

    # Get user input
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(
        None,
        lambda: input("> ").strip()
    )

    # Use default value (if user didn't input)
    if not answer and default:
        answer = default

    return answer
```

#### Example Interaction

```
User> 帮我写一个文档

A> 我来帮你写文档。
   [调用 ask_human 工具]

💬 请问文档的主题是什么？
   (默认: 工作报告)
> 技术方案设计

A> 好的，我将为你创建一份关于"技术方案设计"的文档。
```

### 7.3 Tool Approval Framework

#### Four-Layer Approval Rules System

**Priority 1: Tool Custom Checker** (Highest Priority)

Use case: Tool-specific complex logic

```python
# generalAgent/hitl/approval_checker.py

def _check_bash_command(args: dict) -> ApprovalDecision:
    """Custom checker: bash command approval"""
    command = args.get("command", "")

    # High-risk patterns
    high_risk_patterns = [
        r"rm\s+-rf",        # Recursive delete
        r"sudo\s+",         # Super user
        r"chmod\s+777",     # Dangerous permissions
        r">\s*/dev/sd",     # Direct disk write
    ]

    for pattern in high_risk_patterns:
        if re.search(pattern, command):
            return ApprovalDecision(
                needs_approval=True,
                reason=f"检测到高风险操作: {pattern}",
                risk_level="high"
            )

    # Safe command whitelist
    safe_commands = ["ls", "pwd", "cat", "echo", "date", "whoami"]
    first_word = command.split()[0] if command.split() else ""

    if first_word in safe_commands:
        return ApprovalDecision(needs_approval=False)

    # Default: medium risk commands need approval
    return ApprovalDecision(
        needs_approval=True,
        reason="非白名单命令，需要确认",
        risk_level="medium"
    )
```

**Priority 2: Global Risk Patterns** (Cross-tool Detection)

Use case: General risk detection, applicable to all tools

**File**: `generalAgent/config/hitl_rules.yaml`

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

**Priority 3: Tool Configuration Rules**

Use case: Tool-specific configurable pattern matching

**File**: `generalAgent/config/hitl_rules.yaml`

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
        - "internal\\.company\\.com"  # Block internal network access
        - "192\\.168\\."
      medium_risk:
        - "api\\."                     # API calls need confirmation
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

**Priority 4: Builtin Default Rules** (Fallback Logic)

Use case: General fallback logic, executes when first three layers don't match

```python
def _check_builtin_rules(self, tool_name: str, args: dict) -> ApprovalDecision:
    """Builtin default rules (lowest priority)"""

    # Default: all tools are safe
    return ApprovalDecision(needs_approval=False)
```

#### ApprovalToolNode Implementation

**File**: `generalAgent/hitl/approval_node.py`

```python
class ApprovalToolNode:
    """Wrap ToolNode, intercept tool calls for approval"""

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
        """Intercept and check tool calls"""
        if not self.enable_approval:
            # Approval disabled, execute directly
            return await self.tool_node.ainvoke(state)

        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None

        if not hasattr(last_msg, "tool_calls"):
            return await self.tool_node.ainvoke(state)

        # Check each tool_call
        for tool_call in last_msg.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

            # Call approval checker
            decision = self.approval_checker.check(tool_name, tool_args)

            if decision.needs_approval:
                # Trigger interrupt
                user_decision = interrupt({
                    "type": "tool_approval",
                    "tool": tool_name,
                    "args": tool_args,
                    "reason": decision.reason,
                    "risk_level": decision.risk_level,
                })

                if user_decision == "reject":
                    # User rejected, return cancel message
                    return {"messages": [ToolMessage(
                        content=f"❌ 操作已取消: {decision.reason}",
                        tool_call_id=tool_call_id,
                    )]}

        # All tools passed approval, execute
        return await self.tool_node.ainvoke(state)
```

### 7.4 Approval Rules System

**Four-Layer Architecture**:

1. **Priority 1 - Tool Custom Checkers** (Highest priority): Custom logic for specific tools
2. **Priority 2 - Global Risk Patterns** (Cross-tool detection): Detect risks across all tools (e.g., password leaks)
3. **Priority 3 - Tool-Specific Config Rules**: Tool-specific configurable patterns
4. **Priority 4 - Builtin Default Rules** (Fallback): General fallback logic

**Design Principles**:
- **Transparent to LLM**: Approval decisions NOT added to conversation context
- **Capability-level granularity**: Approval based on arguments, not entire tool
- **Four-layer architecture**: Custom checkers → Global patterns → Tool rules → Default
- **Cross-tool detection**: Global patterns detect risks across all tools (e.g., password leaks)
- **Extensible**: Easy to add new patterns and custom checkers

### 7.5 Configuration

**Configuration File**: `generalAgent/config/hitl_rules.yaml`

```yaml
# Global configuration
global:
  enable_approval: true      # Global switch
  default_action: "prompt"   # require_approval | allow | deny

# Tool approval rules
tools:
  <tool_name>:
    enabled: true             # Whether to enable this tool's approval
    patterns:
      high_risk: [...]        # High-risk pattern list
      medium_risk: [...]      # Medium-risk pattern list
      low_risk: [...]         # Low-risk pattern list
    actions:
      high_risk: require_approval
      medium_risk: require_approval
      low_risk: allow
```

### 7.6 Usage Examples

#### ask_human Usage Examples

**Example 1: Missing Key Information**:

```
User> 帮我订个酒店

A> 好的,我来帮你预订酒店。
   [调用 ask_human 工具]

💬 请问你要在哪个城市订酒店？
> 北京

💬 入住日期和退房日期分别是？
   (默认: 今天入住，明天退房)
> 2025-11-01 到 2025-11-03

A> 好的，我将为你查找 2025-11-01 至 2025-11-03 在北京的酒店。
```

**Example 2: Need User Confirmation**:

```
User> 帮我写一个删除日志的脚本

A> 我可以帮你写删除日志脚本。
   [调用 ask_human 工具]

💡 删除日志是不可逆操作
💬 确定要删除多少天前的日志？
   (默认: 7)
> 30

A> 好的，我将创建一个删除 30 天前日志的脚本。
```

#### Tool Approval Usage Examples

**Example 1: High-Risk Operation**:

```
User> 帮我清理 /tmp 目录

A> 我来帮你清理。
   [调用 run_bash_command: rm -rf /tmp/*]

🛡️  工具审批: run_bash_command
   原因: 检测到高风险操作: rm\s+-rf
   参数: {'command': 'rm -rf /tmp/*'}
   批准? [y/n] > n

A> ❌ 操作已取消: 检测到高风险操作: rm\s+-rf
   了解，我不会执行删除操作。你可以手动清理该目录。
```

**Example 2: Custom Tool Approval**:

```yaml
# generalAgent/config/hitl_rules.yaml
tools:
  http_fetch:
    enabled: true
    patterns:
      high_risk:
        - "internal\\.mycompany\\.com"  # Block company internal network access
        - "192\\.168\\."                 # Block local network access
      medium_risk:
        - "api\\."                       # API calls need confirmation
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

---

## Implementation File Checklist

### Core Code

**Workspace Isolation**:
```
shared/workspace/manager.py          # Workspace manager
shared/session/store.py              # Session persistence
shared/session/manager.py            # Session lifecycle
generalAgent/tools/builtin/file_ops.py       # File operation tools
generalAgent/tools/builtin/find_files.py     # File search
generalAgent/tools/builtin/search_file.py    # Content search
generalAgent/utils/file_processor.py         # File processing utilities
generalAgent/utils/document_extractors.py    # Document extraction
generalAgent/utils/text_indexer.py           # Text indexing
```

**@Mention System**:
```
generalAgent/utils/mention_classifier.py     # Mention classification
generalAgent/tools/registry.py               # Tool registry
generalAgent/skills/registry.py              # Skill registry
generalAgent/graph/prompts.py                # Dynamic reminders
```

**Delegated agent System**:
```
generalAgent/tools/builtin/delegate_task.py  # delegate_task tool
```

**MCP Integration**:
```
generalAgent/tools/mcp/
├── connection.py                # Connection abstraction
├── manager.py                   # Server manager
├── wrapper.py                   # LangChain tool wrapper
└── loader.py                    # Configuration loader
```

**HITL System**:
```
generalAgent/hitl/
├── approval_checker.py          # Four-layer approval rules
└── approval_node.py             # ApprovalToolNode wrapper

generalAgent/tools/builtin/ask_human.py     # ask_human tool
```

### Configuration Files

```
generalAgent/config/
├── mcp_servers.yaml             # MCP server configuration
├── hitl_rules.yaml             # Approval rules
├── skills.yaml                 # Skills configuration
└── tools.yaml                  # Tools configuration
```

### Integration Points

```
generalAgent/
├── main.py                     # MCP initialization and cleanup
├── cli.py                      # Interrupt handling
├── runtime/app.py              # Tool registration
└── graph/builder.py            # ApprovalToolNode integration
```

---

## Related Resources

- [MCP Official Documentation](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [LangGraph Interrupt Documentation](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/breakpoints/)
- [AgentGraph Project Documentation](../CLAUDE.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-27
