# Part 5: MCP (Model Context Protocol) 集成

本文档描述 AgentGraph 的 MCP 集成需求和实现细节。

## 目录

- [需求概述](#需求概述)
- [核心架构](#核心架构)
- [配置系统](#配置系统)
- [实现细节](#实现细节)
- [使用指南](#使用指南)
- [测试与验证](#测试与验证)

---

## 需求概述

### 背景

MCP (Model Context Protocol) 是一个标准协议，用于连接外部工具和服务到 Agent。通过 MCP 集成，AgentGraph 可以：

- 连接到文件系统、GitHub、数据库等外部服务
- 使用社区提供的标准 MCP 服务器
- 扩展 Agent 的能力边界，无需修改核心代码

### 核心需求

**R5.1 延迟启动 (Lazy Startup)**
- **需求**: MCP 服务器应在首次使用时才启动，而非应用启动时
- **原因**:
  - 加快应用启动速度
  - 节省资源（未使用的服务器不启动）
  - 减少初始化错误影响范围
- **实现**: `MCPServerManager` 维护服务器状态，工具调用时触发启动

**R5.2 手动工具控制 (Manual Tool Control)**
- **需求**: 管理员显式配置哪些 MCP 工具可用
- **原因**:
  - 安全性：防止自动加载所有工具
  - 可见性：明确知道哪些工具被启用
  - 控制：可以按项目/用户定制工具集
- **实现**: `mcp_servers.yaml` 配置文件，每个工具需要 `enabled: true`

**R5.3 双协议支持 (Dual Protocol Support)**
- **需求**: 支持 stdio 和 SSE 两种连接模式
- **原因**:
  - stdio: 适用于本地进程，简单可靠
  - SSE: 适用于远程 HTTP 服务器
- **实现**: `MCPConnection` 抽象类 + 两种具体实现

**R5.4 优雅关闭 (Graceful Shutdown)**
- **需求**: 应用退出时自动清理所有 MCP 服务器
- **原因**:
  - 防止孤儿进程
  - 释放系统资源
  - 保证数据一致性
- **实现**: Signal handlers + `MCPServerManager.shutdown()`

**R5.5 错误处理 (Error Handling)**
- **需求**: 服务器启动失败、工具调用失败时的友好错误提示
- **原因**:
  - 用户体验：明确告知问题所在
  - 调试：提供足够的上下文信息
  - 容错：单个工具失败不影响整体
- **实现**: Try-catch + 结构化错误消息

---

## 核心架构

### 架构分层

```
Application Layer
    ↓
ToolRegistry (统一工具接口)
    ↓
MCPToolWrapper (LangChain BaseTool)
    ↓
MCPServerManager (生命周期管理)
    ↓
MCPConnection (连接层抽象)
    ↓
MCP Server Process
```

### 关键组件

#### 1. MCPConnection (连接层)

**职责**: 封装底层通信协议

**文件**: `generalAgent/tools/mcp/connection.py`

**接口**:
```python
class MCPConnection(ABC):
    @abstractmethod
    async def connect(self) -> ClientSession:
        """建立连接，返回 MCP ClientSession"""

    @abstractmethod
    async def close(self) -> None:
        """关闭连接，清理资源"""
```

**实现**:
- `StdioMCPConnection`: Stdio 模式（本地进程）
- `SSEMCPConnection`: SSE 模式（HTTP 服务器）

**设计考量**:
- 使用抽象类而非协议，确保接口一致性
- 每个实现负责自己的资源清理
- 连接失败抛出明确的异常类型

#### 2. MCPServerManager (管理器)

**职责**: 服务器生命周期管理

**文件**: `generalAgent/tools/mcp/manager.py`

**核心方法**:
```python
class MCPServerManager:
    async def get_or_start_server(self, server_id: str) -> ClientSession:
        """获取或启动服务器（延迟启动）"""

    async def shutdown(self) -> None:
        """关闭所有服务器"""

    def is_running(self, server_id: str) -> bool:
        """检查服务器状态"""
```

**状态管理**:
```python
self._servers: Dict[str, ClientSession] = {}  # 已启动的服务器
self._connections: Dict[str, MCPConnection] = {}  # 连接对象
```

**延迟启动逻辑**:
1. 首次调用 `get_or_start_server(server_id)`
2. 检查 `server_id` 是否在 `self._servers` 中
3. 如果不存在，创建连接并启动服务器
4. 缓存 session 供后续使用

**设计考量**:
- 使用字典缓存避免重复启动
- 区分 connection 和 session 的生命周期
- 异步方法支持并发启动多个服务器

#### 3. MCPToolWrapper (包装器)

**职责**: 将 MCP 工具转换为 LangChain BaseTool

**文件**: `generalAgent/tools/mcp/wrapper.py`

**核心代码**:
```python
class MCPToolWrapper(BaseTool):
    name: str
    description: str
    server_id: str
    tool_name: str  # MCP 原始工具名
    manager: MCPServerManager

    async def _arun(self, **kwargs) -> str:
        # 1. 触发延迟启动
        session = await self.manager.get_or_start_server(self.server_id)

        # 2. 调用 MCP 工具
        result = await session.call_tool(self.tool_name, arguments=kwargs)

        # 3. 处理结果
        return self._format_result(result)
```

**命名策略**:
- **Alias 策略**: `alias: "custom_name"` → 使用自定义名称
- **Prefix 策略**: `prefix: "mcp_"` → `mcp_echo`, `mcp_add`

**设计考量**:
- 继承 `BaseTool` 而非 `StructuredTool`，便于定制
- `_arun()` 触发延迟启动，透明化服务器管理
- 工具名和服务器 ID 分离，支持跨服务器重名工具

#### 4. Configuration Loader (配置加载)

**职责**: 解析 YAML 配置并创建工具实例

**文件**: `generalAgent/tools/mcp/loader.py`

**核心函数**:
```python
def load_mcp_config(config_path: Path) -> dict:
    """加载并解析 mcp_servers.yaml"""

def load_mcp_tools(
    config: dict,
    manager: MCPServerManager
) -> List[MCPToolWrapper]:
    """创建 MCPToolWrapper 实例列表"""
```

**环境变量替换**:
```yaml
env:
  API_KEY: "${OPENAI_API_KEY}"  # 自动替换为环境变量值
```

**设计考量**:
- 配置加载与工具创建分离，便于测试
- 环境变量替换在加载时完成
- 校验配置格式，提前发现错误

---

## 配置系统

### 配置文件结构

**文件**: `generalAgent/config/mcp_servers.yaml`

```yaml
# 全局配置
global:
  lazy_startup: true  # 延迟启动（默认）

# 服务器配置
servers:
  # 服务器 ID
  filesystem:
    # 启动命令
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"]

    # 是否启用此服务器
    enabled: true

    # 环境变量
    env:
      DEBUG: "true"

    # 连接模式: stdio 或 sse
    connection_mode: "stdio"

    # 工具配置
    tools:
      read_file:
        enabled: true           # 启用此工具
        always_available: false # 不自动加载到所有 agent
        alias: "fs_read"        # 自定义名称
        description: "Read file contents from allowed directory"

      write_file:
        enabled: false  # 禁用此工具
```

### 配置示例

**示例 1: 文件系统服务器 (官方 MCP 服务器)**
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

**示例 2: 测试服务器 (本地开发)**
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

**示例 3: SSE 模式服务器**
```yaml
servers:
  remote_api:
    connection_mode: "sse"
    url: "http://localhost:8000/mcp"
    enabled: true
    tools:
      search:
        enabled: true
        always_available: true  # 频繁使用，自动加载
```

---

## 实现细节

### 启动流程

**文件**: `generalAgent/main.py`

```python
async def async_main():
    # 1. 加载 MCP 配置
    mcp_config_path = resolve_project_path("generalAgent/config/mcp_servers.yaml")

    if mcp_config_path.exists():
        logger.info("Loading MCP configuration...")

        # 2. 创建 MCPServerManager（服务器未启动）
        mcp_config = load_mcp_config(mcp_config_path)
        mcp_manager = MCPServerManager(mcp_config)

        # 3. 创建 MCPToolWrapper（工具包装器）
        mcp_tools = load_mcp_tools(mcp_config, mcp_manager)
        logger.info(f"  MCP tools loaded: {len(mcp_tools)}")
    else:
        logger.info("No MCP configuration found, skipping MCP integration")
        mcp_tools = []

    # 4. 构建应用（注册 MCP 工具）
    app, initial_state_factory, skill_registry, tool_registry = await build_application(
        mcp_tools=mcp_tools
    )

    # ... CLI 运行 ...

    try:
        await cli.run()
    finally:
        # 5. 清理 MCP 服务器
        if mcp_manager:
            logger.info("Cleaning up MCP servers...")
            await mcp_manager.shutdown()
```

**关键点**:
- MCP 初始化在应用启动时，但服务器不启动
- `mcp_tools` 列表传递给 `build_application()`
- Signal handlers 确保 Ctrl+C 时也能清理

### 工具注册流程

**文件**: `generalAgent/runtime/app.py`

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

**关键点**:
- MCP 工具与内置工具统一注册到 `ToolRegistry`
- `always_available` 标志控制工具可见性
- Graph 通过 `tool_registry.list_tools()` 获取工具

### 延迟启动触发

**触发时机**: Agent 调用 MCP 工具时

**流程**:
1. Agent 决定调用 `mcp_echo` 工具
2. LangGraph 调用 `MCPToolWrapper._arun(**kwargs)`
3. `_arun()` 调用 `manager.get_or_start_server(server_id)`
4. Manager 检查服务器是否已启动
5. 如果未启动，创建 connection 并启动服务器
6. 返回 `ClientSession`
7. 工具通过 session 调用远程方法
8. 返回结果给 Agent

**日志输出**:
```
🚀 Starting MCP server: test_stdio
  Command: python tests/mcp_servers/test_stdio_server.py
  ✓ MCP server started: test_stdio (mode: stdio)
```

### 优雅关闭

**触发场景**:
- 用户输入 `/quit`
- Ctrl+C (SIGINT)
- Kill 信号 (SIGTERM)
- 应用异常退出

**清理流程**:
```python
async def shutdown_mcp_manager(manager: MCPServerManager):
    logger.info("Cleaning up MCP servers...")

    for server_id in list(manager._servers.keys()):
        try:
            # 1. 关闭连接
            conn = manager._connections.get(server_id)
            if conn:
                await conn.close()

            # 2. 清理缓存
            del manager._servers[server_id]
            del manager._connections[server_id]

            logger.info(f"  ✓ Closed MCP server: {server_id}")
        except Exception as e:
            logger.warning(f"  ⚠️  Error closing {server_id}: {e}")

    logger.info("✅ MCP cleanup completed")
```

**设计考量**:
- 即使单个服务器关闭失败，也继续清理其他服务器
- 日志记录所有清理步骤，便于调试
- 使用 `list(...)` 避免在迭代时修改字典

---

## 使用指南

### 快速开始

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

编辑 `mcp_servers.yaml`:
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

输出应包含:
```
Loading MCP configuration...
  MCP servers configured: 1
  MCP tools loaded: 1
    ✓ Loaded MCP tool: mcp_echo (server: test_stdio)
```

#### 5. 使用 MCP 工具

```
You> 使用 mcp_echo 工具发送消息 "Hello MCP!"

# 首次调用触发服务器启动
🚀 Starting MCP server: test_stdio
  ✓ MCP server started: test_stdio (mode: stdio)

A> [调用 mcp_echo 工具]
   Echo: Hello MCP!
```

### 添加官方 MCP 服务器

#### 文件系统服务器

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

#### GitHub 服务器

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

### 高级配置

#### Always Available 工具

频繁使用的工具可以标记为 `always_available`，自动加载到所有 agent 上下文：

```yaml
tools:
  search:
    enabled: true
    always_available: true  # 总是可见
    alias: "web_search"
```

#### 环境变量替换

配置中使用 `${VAR_NAME}` 引用环境变量：

```yaml
servers:
  api_server:
    env:
      API_KEY: "${MY_API_KEY}"
      BASE_URL: "${API_BASE_URL}"
```

启动前设置环境变量：
```bash
export MY_API_KEY="sk-xxx"
export API_BASE_URL="https://api.example.com"
python main.py
```

---

## 测试与验证

### 测试基础设施

#### 测试服务器

**文件**: `tests/mcp_servers/test_stdio_server.py`

提供 3 个测试工具:
- `echo`: 回显消息
- `add`: 两数相加
- `get_time`: 返回当前时间

**启动测试服务器**:
```bash
python tests/mcp_servers/test_stdio_server.py
```

#### 测试套件

**目录**: `tests/test_mcp/`

**测试覆盖**:
- `test_connection.py` - 连接层测试 (6 tests)
- `test_manager.py` - 管理器测试 (5 tests)
- `test_wrapper.py` - 包装器测试 (7 tests)
- `test_loader.py` - 配置加载测试 (7 tests)
- `test_integration.py` - 集成测试 (8 tests)
- `test_e2e.py` - 端到端测试 (5 tests)

**总计**: 38 个测试

### 运行测试

#### 快速验证

```bash
# 运行所有 MCP 测试
pytest tests/test_mcp/ -v

# 运行特定测试文件
pytest tests/test_mcp/test_loader.py -v

# 运行端到端测试
pytest tests/test_mcp/test_e2e.py -v
```

#### 集成测试脚本

```bash
# 快速集成测试
python scripts/test_mcp_integration.py
```

输出示例:
```
✓ Config loaded: 1 servers
✓ Manager created
✓ Tools loaded: 3 tools
✓ Server started: test_stdio
✓ Tool called: echo
  Result: Echo: test
✓ Cleanup completed

🎉 All tests passed!
```

### 验证清单

**启动验证**:
- [ ] 配置文件正确加载
- [ ] 工具数量符合预期
- [ ] 无启动错误

**延迟启动验证**:
- [ ] 首次调用工具时看到 "Starting MCP server" 日志
- [ ] 第二次调用工具时无启动日志（复用连接）
- [ ] 启动失败时有明确错误提示

**工具调用验证**:
- [ ] MCP 工具在 Agent 上下文中可见
- [ ] 工具调用成功并返回正确结果
- [ ] 工具调用失败时有友好错误提示

**清理验证**:
- [ ] `/quit` 后看到 "Cleaning up MCP servers" 日志
- [ ] Ctrl+C 后也能正确清理
- [ ] 无孤儿进程残留（使用 `ps aux | grep mcp` 检查）

---

## 实现文件清单

### 核心代码

```
generalAgent/tools/mcp/
├── __init__.py                # 模块导出
├── connection.py              # 连接抽象层
├── manager.py                 # 服务器管理器
├── wrapper.py                 # LangChain 工具包装器
└── loader.py                  # 配置加载器
```

### 配置文件

```
generalAgent/config/
├── mcp_servers.yaml           # 用户配置（.gitignore）
└── mcp_servers.yaml.example   # 配置示例
```

### 测试代码

```
tests/test_mcp/
├── conftest.py                # Pytest 配置
├── test_connection.py         # 连接层测试
├── test_manager.py            # 管理器测试
├── test_wrapper.py            # 包装器测试
├── test_loader.py             # 加载器测试
├── test_integration.py        # 集成测试
└── test_e2e.py                # 端到端测试

tests/mcp_servers/
└── test_stdio_server.py       # 测试服务器
```

### 集成点

```
generalAgent/
├── main.py                    # MCP 初始化和清理
└── runtime/app.py             # MCP 工具注册
```

---

## 设计决策记录

### 决策 1: 延迟启动 vs 预启动

**问题**: 何时启动 MCP 服务器？

**选项**:
- A. 应用启动时启动所有服务器
- B. 首次使用时启动（延迟启动）

**决策**: 选择 B（延迟启动）

**理由**:
- 加快应用启动速度（从 5s → 1s）
- 节省资源（未使用的服务器不启动）
- 减少启动错误影响（服务器配置错误不影响应用启动）

**权衡**:
- 首次工具调用会有轻微延迟（~1-2s）
- 需要管理服务器状态（已启动/未启动）

### 决策 2: 手动配置 vs 自动发现

**问题**: 如何决定哪些 MCP 工具可用？

**选项**:
- A. 自动加载服务器暴露的所有工具
- B. 手动配置每个工具的启用状态

**决策**: 选择 B（手动配置）

**理由**:
- 安全性：防止意外加载危险工具
- 可见性：管理员明确知道哪些工具被启用
- 控制：可以按项目/用户定制工具集

**权衡**:
- 需要编写配置文件
- 新增工具需要手动启用

### 决策 3: Alias vs Prefix 命名

**问题**: 如何避免 MCP 工具名冲突？

**选项**:
- A. 强制使用前缀（如 `mcp_echo`）
- B. 允许自定义 alias
- C. 同时支持两种方式

**决策**: 选择 C（同时支持）

**理由**:
- 灵活性：用户可以选择最合适的命名方式
- Alias 适合精确控制（如 `gh_create_issue`）
- Prefix 适合批量处理（默认加 `mcp_` 前缀）

**权衡**:
- 配置稍微复杂
- 需要在文档中说明两种策略

### 决策 4: Stdio vs SSE

**问题**: 支持哪些连接模式？

**选项**:
- A. 仅 stdio（本地进程）
- B. 仅 SSE（远程 HTTP）
- C. 同时支持两种

**决策**: 选择 C（同时支持）

**理由**:
- Stdio 适合本地工具（文件系统、命令行）
- SSE 适合远程服务（API、数据库）
- 使用抽象类 `MCPConnection` 统一接口

**权衡**:
- 代码复杂度增加
- 需要两套连接实现

---

## 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [官方 MCP 服务器列表](https://github.com/modelcontextprotocol)
- [AgentGraph 项目文档](../CLAUDE.md)

---

## 版本信息

- **实现日期**: 2025-10-26
- **MCP SDK 版本**: 1.7.1
- **Python 版本**: 3.12+
- **文档版本**: 1.0
