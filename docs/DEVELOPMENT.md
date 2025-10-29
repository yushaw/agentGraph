# 开发指南

> **注意**：AgentGraph 开发和扩展的实用指南

## 目录

- [第一部分：环境配置](#第一部分环境配置)
  - [1.1 前置要求](#11-前置要求)
  - [1.2 安装](#12-安装)
  - [1.3 环境配置 (.env)](#13-环境配置-env)
  - [1.4 Pydantic 设置](#14-pydantic-设置)
  - [1.5 模型配置](#15-模型配置)
- [第二部分：开发工具](#第二部分开发工具)
  - [2.1 工具基础](#21-工具基础)
  - [2.2 创建新工具](#22-创建新工具)
  - [2.3 工具配置 (tools.yaml)](#23-工具配置-toolsyaml)
  - [2.4 工具元数据](#24-工具元数据)
  - [2.5 多工具文件 (\_\_all\_\_ 导出)](#25-多工具文件-__all__-导出)
  - [2.6 测试工具](#26-测试工具)
  - [2.7 最佳实践](#27-最佳实践)
- [第三部分：开发技能](#第三部分开发技能)
  - [3.1 技能结构](#31-技能结构)
  - [3.2 创建技能包](#32-创建技能包)
  - [3.3 SKILL.md 文档](#33-skillmd-文档)
  - [3.4 技能脚本](#34-技能脚本)
  - [3.5 依赖管理 (requirements.txt)](#35-依赖管理-requirementstxt)
  - [3.6 技能配置 (skills.yaml)](#36-技能配置-skillsyaml)
  - [3.7 测试技能](#37-测试技能)
- [第四部分：扩展系统](#第四部分扩展系统)
  - [4.1 添加自定义节点](#41-添加自定义节点)
  - [4.2 自定义路由逻辑](#42-自定义路由逻辑)
  - [4.3 集成第三方服务](#43-集成第三方服务)
  - [4.4 自定义模型解析器](#44-自定义模型解析器)
  - [4.5 子代理目录](#45-子代理目录)
- [第五部分：开发最佳实践](#第五部分开发最佳实践)
  - [5.1 代码组织](#51-代码组织)
  - [5.2 命名约定](#52-命名约定)
  - [5.3 错误处理模式](#53-错误处理模式)
  - [5.4 日志指南](#54-日志指南)
  - [5.5 配置管理](#55-配置管理)
  - [5.6 路径处理](#56-路径处理)
- [第六部分：调试和故障排除](#第六部分调试和故障排除)
  - [6.1 日志和追踪](#61-日志和追踪)
  - [6.2 LangSmith 集成](#62-langsmith-集成)
  - [6.3 常见问题](#63-常见问题)
  - [6.4 调试工具](#64-调试工具)
- [第七部分：贡献](#第七部分贡献)
  - [7.1 代码风格](#71-代码风格)
  - [7.2 测试要求](#72-测试要求)
  - [7.3 文档](#73-文档)
  - [7.4 Pull Request 流程](#74-pull-request-流程)

---

## 第一部分：环境配置

### 1.1 前置要求

**必需**：
- Python 3.12 或更高版本
- uv（推荐）或 pip
- Git

**可选**：
- Docker（用于容器化开发）
- PostgreSQL（用于持久化检查点）

### 1.2 安装

#### 方法 1：使用 uv（推荐）

```bash
# 克隆仓库
git clone https://github.com/yushaw/agentGraph.git
cd agentGraph

# 使用 uv 安装依赖
uv sync

# 验证安装
python -c "import generalAgent; print('OK')"
```

#### 方法 2：使用 pip

```bash
# 克隆仓库
git clone https://github.com/yushaw/agentGraph.git
cd agentGraph

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 以可编辑模式安装
pip install -e .

# 验证安装
python -c "import generalAgent; print('OK')"
```

#### 方法 3：开发模式

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 或使用 uv
uv sync --all-extras
```

### 1.3 环境配置 (.env)

在项目根目录创建 `.env` 文件：

```bash
# 复制模板
cp .env.example .env

# 编辑配置
vim .env
```

**完整的 .env 模板**（基于实际的 `.env.example`）：

```bash
#=============================================================================
# 模型配置（必需）
#=============================================================================

# 五个模型槽位，每个槽位有 4 个字段：ID, API_KEY, BASE_URL, CONTEXT_WINDOW
# 支持多种别名（如 MODEL_BASIC_* 和 MODEL_BASE_* 都可以）

# ===== 基础模型（general chat/analysis）=====
MODEL_BASIC_API_KEY=                               # 或：MODEL_BASE_API_KEY
MODEL_BASIC_BASE_URL=https://api.deepseek.com      # 或：MODEL_BASE_BASE_URL
MODEL_BASIC_ID=deepseek-chat                       # 或：MODEL_BASE_ID
MODEL_BASIC_CONTEXT_WINDOW=128000                  # 或：MODEL_BASE_CONTEXT_WINDOW（总容量：输入+输出）
MODEL_BASIC_MAX_COMPLETION_TOKENS=4096             # 或：MODEL_BASE_MAX_COMPLETION_TOKENS（最大输出 tokens，防止工具调用被截断，默认 2048）

# ===== 推理模型（reasoning / 深度思考）=====
MODEL_REASONING_API_KEY=                           # 或：MODEL_REASON_API_KEY
MODEL_REASONING_BASE_URL=https://api.deepseek.com  # 或：MODEL_REASON_BASE_URL
MODEL_REASONING_ID=deepseek-reasoner               # 或：MODEL_REASON_ID
MODEL_REASONING_CONTEXT_WINDOW=128000              # 或：MODEL_REASON_CONTEXT_WINDOW（总容量：输入+输出）
MODEL_REASONING_MAX_COMPLETION_TOKENS=8192         # 或：MODEL_REASON_MAX_COMPLETION_TOKENS（推理模型建议更高的输出限制，默认 2048）

# ===== 多模态模型（图文理解）=====
MODEL_MULTIMODAL_API_KEY=                                    # 或：MODEL_VISION_API_KEY
MODEL_MULTIMODAL_BASE_URL=https://open.bigmodel.cn/api/paas/v4  # 或：MODEL_VISION_BASE_URL
MODEL_MULTIMODAL_ID=glm-4.5v                                 # 或：MODEL_VISION_ID
MODEL_MULTIMODAL_CONTEXT_WINDOW=64000                        # 或：MODEL_VISION_CONTEXT_WINDOW（总容量：输入+输出）
MODEL_MULTIMODAL_MAX_COMPLETION_TOKENS=4096                  # 或：MODEL_VISION_MAX_COMPLETION_TOKENS（最大输出 tokens，默认 2048）

# ===== 代码模型（代码理解与生成）=====
MODEL_CODE_API_KEY=
MODEL_CODE_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_CODE_ID=glm-4.6
MODEL_CODE_CONTEXT_WINDOW=200000                             # 总容量：输入+输出
MODEL_CODE_MAX_COMPLETION_TOKENS=8192                        # 代码生成建议更高的输出限制（默认 2048）

# ===== 聊天模型（主对话）=====
MODEL_CHAT_API_KEY=
MODEL_CHAT_BASE_URL=https://api.moonshot.cn/v1
MODEL_CHAT_ID=kimi-k2-0905-preview
MODEL_CHAT_CONTEXT_WINDOW=256000                             # 总容量：输入+输出
MODEL_CHAT_MAX_COMPLETION_TOKENS=4096                        # 最大输出 tokens（Kimi 默认 1024 太低，建议 4096+，默认 2048）

#=============================================================================
# Jina AI 配置（用于网页抓取与搜索）
#=============================================================================

JINA_API_KEY=
JINA_STRIP_IMAGES=true           # 过滤 Markdown 中的图片链接以节省流量（true/false，默认 true）
JINA_REMOVE_SELECTORS=nav,footer,header,.sidebar,.navigation,.menu,aside  # 移除的 CSS 选择器（逗号分隔）
JINA_CONTENT_CLEANING=true       # 使用 LLM 清洗内容以去除噪音（true/false，默认 true）
JINA_CLEANING_MIN_LENGTH=2000    # 触发内容清洗的最小长度（字符数，默认 2000）

#=============================================================================
# LangSmith 配置（可选）
#=============================================================================

LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=                # 或：LANGCHAIN_API_KEY

#=============================================================================
# 运行控制（可选，已注释表示使用默认值）
#=============================================================================

# MAX_MESSAGE_HISTORY=40          # 最大消息历史保留数 (10-100，默认 40)
# MAX_LOOPS=100                   # 最大循环次数 (1-500，默认 100)

#=============================================================================
# 日志配置（可选）
#=============================================================================

# LOG_PROMPT_MAX_LENGTH=500       # Prompt 日志最大显示字符数 (100-5000，默认 500)
```

**重要说明**：

1. **模型配置别名**：
   - `MODEL_BASIC_*` = `MODEL_BASE_*`
   - `MODEL_REASONING_*` = `MODEL_REASON_*`
   - `MODEL_MULTIMODAL_*` = `MODEL_VISION_*`
   - 两种写法都可以，系统会自动识别

2. **CONTEXT_WINDOW vs MAX_COMPLETION_TOKENS**：
   - **CONTEXT_WINDOW**（上下文窗口）：模型的总容量限制（输入 tokens + 输出 tokens）
     - 用于 KV Cache 优化和消息历史管理
     - 示例：Kimi k2 的 CONTEXT_WINDOW=256000 表示输入+输出总共不能超过 256K tokens

   - **MAX_COMPLETION_TOKENS**（最大完成 tokens）：单次输出的最大 token 数（仅控制输出）
     - **关键用途**：防止工具调用被截断（tool call JSON 不完整导致解析失败）
     - 默认值：2048（如未配置）
     - **推荐值**：
       - 基础/多模态模型：4096
       - 推理/代码模型：8192（需要更长的输出）
       - Kimi API 默认仅 1024，**强烈建议设置为 4096+**
     - **向后兼容**：也支持旧名称 `MODEL_*_MAX_TOKENS`

3. **Jina AI 配置**：
   - 用于 `fetch_web` 和 `web_search` 工具
   - 支持内容清洗、图片过滤、选择器移除等高级功能

4. **文档处理配置**：
   - 不在 .env 中配置，使用代码中的默认值
   - 如需自定义，请修改 `generalAgent/config/settings.py` 中的 `DocumentSettings` 类

**环境变量优先级**：

1. **.env 文件中的值** - 最高优先级
2. **系统环境变量** - 次优先级
3. **Pydantic Field 默认值** - 兜底默认值

### 1.4 Pydantic 设置

AgentGraph 使用 **Pydantic BaseSettings** 实现自动环境变量加载和类型验证。

**设置架构** (`generalAgent/config/settings.py`)：

```python
Settings
├── ModelRoutingSettings     # 模型 ID 和凭证
├── GovernanceSettings       # 运行时控制（auto_approve, max_loops）
├── ObservabilitySettings    # 追踪、日志、持久化
└── DocumentSettings         # 文档处理参数
```

**主要特性**：

1. **自动 .env 加载** - 所有设置类继承自 `BaseSettings`
2. **多别名** - `AliasChoices` 支持提供商特定名称
3. **类型验证** - Pydantic 验证类型、范围（如 `max_loops: int = Field(ge=1, le=500)`）
4. **无需后备** - 直接从环境加载设置

**使用示例**：

```python
from generalAgent.config.settings import get_settings

# 获取单例实例（缓存）
settings = get_settings()

# 访问设置（自动从 .env 加载）
api_key = settings.models.reason_api_key
max_loops = settings.governance.max_loops
db_path = settings.observability.session_db_path
```

**添加新设置**：

1. 添加到设置类：

```python
# generalAgent/config/settings.py
class GovernanceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_loops: int = Field(default=100, ge=1, le=500)
    max_retries: int = Field(default=3, ge=1, le=10)  # 新增
```

2. 添加到 `.env`：

```bash
MAX_RETRIES=5
```

3. 在代码中使用：

```python
settings = get_settings()
retries = settings.governance.max_retries
```

### 1.5 模型配置

**支持的模型槽位**：

1. **base** - 通用模型（大多数任务的默认）
2. **reasoning** - 复杂推理任务
3. **vision** - 图像处理任务
4. **code** - 代码生成/分析
5. **chat** - 对话任务

**提供商示例**：

#### DeepSeek

```bash
MODEL_BASIC_API_KEY=sk-xxx
MODEL_BASIC_BASE_URL=https://api.deepseek.com
MODEL_BASIC_ID=deepseek-chat

MODEL_REASONING_API_KEY=sk-xxx
MODEL_REASONING_BASE_URL=https://api.deepseek.com
MODEL_REASONING_ID=deepseek-reasoner
```

#### GLM（智谱 AI）

```bash
MODEL_MULTIMODAL_API_KEY=xxx
MODEL_MULTIMODAL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_MULTIMODAL_ID=glm-4.5v
```

#### Moonshot（Kimi）

```bash
MODEL_CHAT_API_KEY=xxx
MODEL_CHAT_BASE_URL=https://api.moonshot.cn/v1
MODEL_CHAT_ID=kimi-k2-0905-preview
```

#### OpenAI

```bash
MODEL_BASE_API_KEY=sk-xxx
MODEL_BASE_BASE_URL=https://api.openai.com/v1
MODEL_BASE_ID=gpt-4-turbo-preview
```

**模型解析流程**：

```python
# generalAgent/runtime/model_resolver.py
def resolve(self, state: AppState, node_name: str) -> str:
    """带回退的模型解析"""

    # 优先使用视觉模型处理图像
    if state.get("images") and "vision" in self.configs:
        return "vision"

    # 优先使用推理模型处理复杂任务
    if node_name == "decompose" and "reasoning" in self.configs:
        return "reasoning"

    # 回退到基础模型
    if "base" in self.configs:
        return "base"

    # 最终回退：第一个可用的
    return list(self.configs.keys())[0]
```

---

## 第二部分：开发工具

### 2.1 工具基础

**什么是工具？**

工具是代理可以调用以执行特定操作的 Python 函数：
- 读/写文件
- 发起 HTTP 请求
- 执行命令
- 搜索文档
- 调用外部 API

**工具架构**：

```
工具系统
├── 发现层 (_discovered)     # 所有扫描到的工具（包括禁用的）
├── 注册层 (_tools)            # 已启用的工具（立即可用）
└── 可见性层                   # 每个上下文的动态可见性
```

**工具类型**：

1. **核心工具** - 始终启用（如 `now`, `todo_write`, `read_file`）
2. **可选工具** - 可启用/禁用（如 `http_fetch`, `run_bash_command`）
3. **按需工具** - 被 @提及时加载（如 `@extract_links`）

### 2.2 创建新工具

#### 步骤 1：创建工具文件

在 `generalAgent/tools/builtin/` 或 `generalAgent/tools/custom/` 中创建新文件：

```python
# generalAgent/tools/custom/my_calculator.py
from langchain_core.tools import tool
import logging

LOGGER = logging.getLogger(__name__)

@tool
def calculate_sum(numbers: list[float]) -> float:
    """计算数字列表的总和。

    Args:
        numbers: 要求和的数字列表

    Returns:
        所有数字的总和
    """
    try:
        result = sum(numbers)
        LOGGER.info(f"计算总和：{result}")
        return result
    except Exception as e:
        LOGGER.error(f"计算失败：{e}")
        return f"错误：{e}"

@tool
def calculate_average(numbers: list[float]) -> float:
    """计算数字列表的平均值。

    Args:
        numbers: 要计算平均值的数字列表

    Returns:
        所有数字的平均值
    """
    try:
        if not numbers:
            return 0.0
        result = sum(numbers) / len(numbers)
        LOGGER.info(f"计算平均值：{result}")
        return result
    except Exception as e:
        LOGGER.error(f"计算失败：{e}")
        return f"错误：{e}"

# 显式导出工具
__all__ = ["calculate_sum", "calculate_average"]
```

**关键点**：

1. 使用 `langchain_core.tools` 的 `@tool` 装饰器
2. 提供清晰的文档字符串（用于工具描述）
3. 为参数和返回值添加类型提示
4. 优雅地处理错误
5. 返回字符串结果（代理将工具输出视为文本）
6. 使用 `__all__` 导出多个工具

#### 步骤 2：添加工具配置

编辑 `generalAgent/config/tools.yaml`：

```yaml
optional:
  calculate_sum:
    enabled: true                      # 启动时加载
    available_to_subagent: false            # 非全局可见（默认）
    category: "compute"                # 工具类别
    tags: ["math", "calculation"]      # 可搜索标签
    description: "对数字列表求和"

  calculate_average:
    enabled: true
    available_to_subagent: false
    category: "compute"
    tags: ["math", "calculation", "statistics"]
    description: "计算数字平均值"
```

#### 步骤 3：测试工具

```bash
# 运行应用
python main.py

# 在 CLI 中测试
You> @calculate_sum 帮我计算 [1, 2, 3, 4, 5] 的和
Agent> [调用 calculate_sum([1, 2, 3, 4, 5])]
       总和是 15。
```

### 2.3 工具配置 (tools.yaml)

**配置结构**：

```yaml
# 核心工具 - 始终加载
core:
  now:
    category: "meta"
    tags: ["meta", "time"]
    description: "获取当前 UTC 时间"

  todo_write:
    category: "meta"
    tags: ["meta", "task"]
    description: "写任务列表"

# 可选工具 - 可启用/禁用
optional:
  http_fetch:
    enabled: true                      # 启动时加载
    available_to_subagent: false            # 非全局可见
    category: "network"
    tags: ["network", "read"]
    description: "获取网页内容"

  run_bash_command:
    enabled: false                     # 启动时不加载
    available_to_subagent: false
    category: "system"
    tags: ["system", "dangerous"]
    description: "执行 bash 命令"
```

**配置选项**：

- `enabled: true/false` - 是否在启动时加载
- `available_to_subagent: true/false` - 是否全局可见（谨慎使用）
- `category` - 用于组织的工具类别
- `tags` - 可搜索标签
- `description` - 人类可读的描述

**加载行为**：

| 设置 | 行为 |
|---------|----------|
| `core: tool` | 始终加载，始终可见 |
| `enabled: true` | 启动时加载，默认可见 |
| `enabled: false` | 不加载，但可通过 @提及使用 |
| `available_to_subagent: true` | 添加到所有代理上下文（谨慎使用）|

### 2.4 工具元数据

**ToolMeta 结构** (`generalAgent/tools/registry.py`)：

```python
@dataclass
class ToolMeta:
    name: str                           # 工具名称（如 "read_file"）
    category: str                       # 类别（如 "file", "network"）
    tags: list[str]                     # 标签（如 ["read", "file"]）
    description: str                    # 人类可读描述
    available_to_subagent: bool = False      # 全局可见性标志
```

**使用**：

```python
from generalAgent.tools.registry import ToolRegistry

registry = ToolRegistry()

# 使用元数据注册工具
registry.register_tool(read_file_tool)
registry.add_metadata(ToolMeta(
    name="read_file",
    category="file",
    tags=["read", "file", "workspace"],
    description="从工作区读取文件",
    available_to_subagent=False,
))

# 查询元数据
meta = registry.get_metadata("read_file")
print(f"类别：{meta.category}")
print(f"标签：{meta.tags}")
```

### 2.5 多工具文件 (\_\_all\_\_ 导出)

**问题**：如何从单个文件导出多个工具？

**解决方案**：使用 `__all__` 显式声明导出。

**示例** (`generalAgent/tools/builtin/file_ops.py`)：

```python
from langchain_core.tools import tool

@tool
def read_file(file_path: str) -> str:
    """从工作区读取文件"""
    pass

@tool
def write_file(file_path: str, content: str) -> str:
    """写文件到工作区"""
    pass

@tool
def list_workspace_files(directory: str = ".") -> str:
    """列出目录中的文件"""
    pass

# 显式导出所有工具
__all__ = ["read_file", "write_file", "list_workspace_files"]
```

**工具扫描器** (`generalAgent/tools/scanner.py`)：

```python
def _extract_tools_from_module(file_path: Path) -> Dict[str, Any]:
    """从模块中提取所有工具"""

    tools = {}

    # 方法 1：如果定义了 __all__ 则使用（推荐）
    if hasattr(module, "__all__"):
        tool_names = module.__all__
        for name in tool_names:
            obj = getattr(module, name)
            if isinstance(obj, BaseTool):
                tools[obj.name] = obj

    # 方法 2：内省所有属性（回退）
    else:
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool) and not name.startswith("_"):
                tools[obj.name] = obj

    return tools
```

**最佳实践**：

1. 始终使用 `__all__` 进行显式控制
2. 在一个文件中分组相关工具（如所有文件操作）
3. 避免导出私有工具（以 `_` 前缀）

### 2.6 测试工具

#### 单元测试示例

```python
# tests/unit/test_calculator_tools.py
import pytest
from generalAgent.tools.custom.my_calculator import calculate_sum, calculate_average

def test_calculate_sum():
    """测试求和计算"""
    result = calculate_sum.invoke({"numbers": [1, 2, 3, 4, 5]})
    assert result == 15.0

def test_calculate_sum_empty():
    """测试空列表求和"""
    result = calculate_sum.invoke({"numbers": []})
    assert result == 0.0

def test_calculate_average():
    """测试平均值计算"""
    result = calculate_average.invoke({"numbers": [2, 4, 6, 8, 10]})
    assert result == 6.0

def test_calculate_average_error():
    """测试错误处理"""
    result = calculate_average.invoke({"numbers": []})
    assert result == 0.0
```

#### 集成测试示例

```python
# tests/integration/test_calculator_integration.py
import pytest
from generalAgent.tools.registry import ToolRegistry
from generalAgent.tools.config_loader import load_tool_config

def test_calculator_tools_loaded():
    """测试计算器工具被注册表加载"""

    # 加载配置
    config = load_tool_config()

    # 创建注册表
    registry = ToolRegistry()

    # 加载工具
    from generalAgent.tools.scanner import scan_tools_directory
    tools_dir = Path("generalAgent/tools/custom")
    discovered = scan_tools_directory(tools_dir)

    for tool in discovered:
        if config.is_enabled(tool.name):
            registry.register_tool(tool)

    # 验证工具已加载
    assert registry.get_tool("calculate_sum") is not None
    assert registry.get_tool("calculate_average") is not None
```

### 2.7 最佳实践

#### 错误处理

始终返回友好的错误消息而不是抛出异常：

```python
@tool
def read_file(file_path: str) -> str:
    """从工作区读取文件"""
    try:
        workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
        abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return f"错误：文件未找到：{file_path}"
    except PermissionError:
        return f"错误：权限被拒绝：{file_path}"
    except Exception as e:
        LOGGER.error(f"读取文件失败：{e}", exc_info=True)
        return f"错误：读取文件失败：{e}"
```

#### 使用错误边界装饰器

```python
# generalAgent/tools/decorators.py
from functools import wraps
import logging

LOGGER = logging.getLogger(__name__)

def with_error_boundary(func):
    """捕获和格式化工具错误的装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except FileNotFoundError as e:
            error_msg = f"文件未找到：{e.filename}"
            LOGGER.error(f"工具 '{func.__name__}' 失败：{error_msg}")
            return f"错误：{error_msg}"

        except PermissionError as e:
            error_msg = f"权限被拒绝：{e}"
            LOGGER.error(f"工具 '{func.__name__}' 失败：{error_msg}")
            return f"错误：{error_msg}"

        except Exception as e:
            error_msg = f"意外错误：{type(e).__name__}: {e}"
            LOGGER.error(f"工具 '{func.__name__}' 失败：{error_msg}", exc_info=True)
            return f"错误：{error_msg}"

    return wrapper

# 使用
@tool
@with_error_boundary
def read_file(file_path: str) -> str:
    """从工作区读取文件"""
    # 不需要 try-except，装饰器处理
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

#### 日志

使用结构化日志进行调试：

```python
import logging

LOGGER = logging.getLogger(__name__)

@tool
def my_tool(param: str) -> str:
    """我的工具描述"""

    LOGGER.info(f"工具调用参数：{param}")

    try:
        result = process(param)
        LOGGER.info(f"✓ 工具成功：{result}")
        return result

    except Exception as e:
        LOGGER.error(f"✗ 工具失败：{e}", exc_info=True)
        return f"错误：{e}"
```

#### 路径安全

始终验证路径以防止目录遍历：

```python
from generalAgent.utils.file_processor import resolve_workspace_path

@tool
def read_file(file_path: str) -> str:
    """从工作区读取文件"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 验证路径在工作区内
    abs_path = resolve_workspace_path(
        file_path,
        workspace_root,
        must_exist=True,        # 检查文件存在
        allow_write=False,      # 只读操作
    )

    with open(abs_path, "r") as f:
        return f.read()
```

#### 环境变量

使用环境变量获取上下文：

```python
import os
from pathlib import Path

@tool
def my_tool() -> str:
    """我的工具描述"""

    # 获取工作区路径
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # 获取会话 ID
    session_id = os.environ.get("AGENT_CONTEXT_ID")

    # 获取用户 ID
    user_id = os.environ.get("AGENT_USER_ID", "anonymous")

    # 使用上下文...
```

---

## 第三部分：开发技能

### 3.1 技能结构

**什么是技能？**

技能是**知识包**（文档 + 脚本），不是工具容器。它们提供：
- **SKILL.md** - 带使用指南的主文档
- **scripts/** - 特定任务的 Python 脚本
- **参考文档** - 额外的文档
- **requirements.txt** - Python 依赖（可选）

**目录结构**：

```
skills/<skill_id>/
├── SKILL.md           # 主技能文档（必需）
├── requirements.txt   # Python 依赖（可选）
├── reference.md       # 额外参考（可选）
├── forms.md           # 特定指南（可选）
└── scripts/           # Python 脚本（可选）
    ├── script1.py
    └── script2.py
```

**重要**：技能没有 `allowed_tools` - 它们是指导代理的文档包。

### 3.2 创建技能包

#### 步骤 1：创建技能目录

```bash
mkdir -p generalAgent/skills/my-skill/scripts
cd generalAgent/skills/my-skill
```

#### 步骤 2：编写 SKILL.md

```markdown
# 我的技能

> 简要描述此技能的功能

## 概述

此技能提供 [描述能力] 的能力。

## 使用

### 基础使用

1. 使用 `read_file` 工具读取输入文件
2. 使用提供的脚本处理数据
3. 使用 `write_file` 工具写入输出

### 示例

用户：@my-skill 处理文件 uploads/data.txt

代理工作流：
1. 读取 SKILL.md（此文件）
2. 读取输入文件：`read_file("uploads/data.txt")`
3. 执行处理脚本：`run_bash_command("python skills/my-skill/scripts/process.py")`
4. 写入输出：`write_file("outputs/result.txt", content)`

## 脚本

### process.py

处理输入数据并生成输出。

**使用**：
```bash
python skills/my-skill/scripts/process.py
```

**输入**：从 stdin 读取（JSON 格式）
```json
{
  "input_file": "uploads/data.txt",
  "output_file": "outputs/result.txt",
  "options": {
    "format": "json"
  }
}
```

**输出**：打印到 stdout（JSON 格式）
```json
{
  "status": "success",
  "output_file": "outputs/result.txt",
  "records_processed": 100
}
```

## 依赖

此技能需要以下 Python 包：
- pandas>=2.0.0
- numpy>=1.24.0

安装：`pip install -r requirements.txt`

## 错误处理

常见错误和解决方案：

1. **缺少输入文件**
   - 错误："文件未找到：uploads/data.txt"
   - 解决方案：确保文件已上传到工作区

2. **无效格式**
   - 错误："不支持的格式：xyz"
   - 解决方案：使用支持的格式（csv、json、xlsx）

## 参考

- [外部文档](https://example.com/docs)
- [API 参考](https://example.com/api)
```

#### 步骤 3：创建脚本

```python
# scripts/process.py
import json
import sys
import os
from pathlib import Path

def main():
    # 1. 从环境读取工作区路径
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")
    if not workspace:
        print(json.dumps({"error": "AGENT_WORKSPACE_PATH 未设置"}))
        sys.exit(1)

    workspace_path = Path(workspace)

    # 2. 从 stdin 读取参数（JSON）
    try:
        args = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"无效的 JSON 输入：{e}"}))
        sys.exit(1)

    # 3. 验证必需参数
    required = ["input_file", "output_file"]
    missing = [k for k in required if k not in args]
    if missing:
        print(json.dumps({"error": f"缺少参数：{missing}"}))
        sys.exit(1)

    # 4. 执行逻辑
    input_path = workspace_path / args["input_file"]
    output_path = workspace_path / args["output_file"]

    try:
        # 读取输入
        with open(input_path, "r") as f:
            data = f.read()

        # 处理（你的逻辑在这里）
        result = process_data(data, args.get("options", {}))

        # 写入输出
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result)

        # 5. 打印结果到 stdout（JSON）
        print(json.dumps({
            "status": "success",
            "output_file": str(args["output_file"]),
            "records_processed": len(result.split("\n")),
        }))

    except Exception as e:
        # 6. 打印错误（JSON）
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

def process_data(data: str, options: dict) -> str:
    """处理输入数据"""
    # 你的处理逻辑在这里
    return data.upper()  # 示例：转换为大写

if __name__ == "__main__":
    main()
```

**脚本接口要求**：

1. 从 `AGENT_WORKSPACE_PATH` 环境变量读取工作区路径
2. 从 stdin 读取参数（JSON 格式）
3. 验证必需参数
4. 使用工作区相对路径执行逻辑
5. 将结果打印到 stdout（JSON 格式）
6. 将错误打印到 stdout（JSON 格式）并以非零代码退出

#### 步骤 4：添加依赖

```txt
# requirements.txt
pandas>=2.0.0
numpy>=1.24.0
```

#### 步骤 5：配置技能

编辑 `generalAgent/config/skills.yaml`：

```yaml
optional:
  my-skill:
    enabled: true                           # 在目录中显示
    available_to_subagent: false
    description: "用于数据处理的自定义技能"
    auto_load_on_file_types: ["txt", "csv"]  # 为这些文件类型自动加载
```

### 3.3 SKILL.md 文档

**最佳实践**：

1. **清晰的概述** - 描述技能的功能
2. **分步使用** - 提供工作流示例
3. **脚本文档** - 记录每个脚本的使用
4. **示例工作流** - 显示完整的代理工作流
5. **错误处理** - 列出常见错误和解决方案
6. **依赖** - 记录所需包
7. **参考** - 链接到外部资源

**模板**：

```markdown
# [技能名称]

> 一行描述

## 概述

[能力的详细描述]

## 使用

### 基础使用

[分步指南]

### 示例

[完整的工作流示例]

## 脚本

### [script_name.py]

[脚本描述]

**使用**：
```bash
[命令示例]
```

**输入**：
```json
[输入格式]
```

**输出**：
```json
[输出格式]
```

## 依赖

[依赖列表]

## 错误处理

[常见错误和解决方案]

## 参考

[外部链接]
```

### 3.4 技能脚本

**脚本设计原则**：

1. **Stdin/Stdout 通信** - 使用标准 I/O 进行数据交换
2. **JSON 格式** - 结构化输入/输出
3. **环境变量** - 从 `AGENT_WORKSPACE_PATH` 获取上下文
4. **错误处理** - 返回 JSON 错误，以非零退出
5. **工作区相对路径** - 所有路径相对于工作区

**完整示例**：

```python
#!/usr/bin/env python
"""
PDF 表单填写脚本

从 JSON 读取表单数据并填写 PDF 表单。
"""
import json
import sys
import os
from pathlib import Path

# 导入依赖
try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    print(json.dumps({
        "error": "缺少依赖：pypdf2",
        "solution": "安装：pip install pypdf2"
    }))
    sys.exit(1)

def main():
    # 读取工作区路径
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")
    if not workspace:
        print(json.dumps({"error": "AGENT_WORKSPACE_PATH 未设置"}))
        sys.exit(1)

    workspace_path = Path(workspace)

    # 从 stdin 读取参数
    try:
        args = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"无效的 JSON：{e}"}))
        sys.exit(1)

    # 验证参数
    required = ["input_pdf", "output_pdf", "fields"]
    missing = [k for k in required if k not in args]
    if missing:
        print(json.dumps({"error": f"缺少：{missing}"}))
        sys.exit(1)

    # 构建路径
    input_path = workspace_path / args["input_pdf"]
    output_path = workspace_path / args["output_pdf"]

    # 验证输入
    if not input_path.exists():
        print(json.dumps({"error": f"输入未找到：{args['input_pdf']}"}))
        sys.exit(1)

    try:
        # 填写 PDF 表单
        result = fill_pdf_form(
            str(input_path),
            str(output_path),
            args["fields"]
        )

        # 返回成功
        print(json.dumps({
            "status": "success",
            "output_file": args["output_pdf"],
            "fields_filled": result["fields_filled"],
        }))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

def fill_pdf_form(input_pdf: str, output_pdf: str, fields: dict) -> dict:
    """填写 PDF 表单字段"""
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    # 复制页面
    for page in reader.pages:
        writer.add_page(page)

    # 填写字段
    if "/AcroForm" in reader.trailer["/Root"]:
        writer.update_page_form_field_values(writer.pages[0], fields)

    # 写入输出
    Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)

    return {"fields_filled": len(fields)}

if __name__ == "__main__":
    main()
```

**脚本调用**（代理使用 `run_bash_command` 工具）：

```python
# 代理调用：
run_bash_command(
    command='python skills/my-skill/scripts/fill_form.py',
    input_json={
        "input_pdf": "uploads/form.pdf",
        "output_pdf": "outputs/filled.pdf",
        "fields": {
            "name": "张三",
            "date": "2025-01-24"
        }
    }
)
```

### 3.5 依赖管理 (requirements.txt)

**自动安装**：

当用户首次 @提及技能时，依赖会自动安装。

**工作原理**：

1. 用户输入 `@my-skill` 或上传匹配文件
2. WorkspaceManager 将技能链接到工作区
3. WorkspaceManager 检查 `requirements.txt`
4. 如果找到，运行 `pip install -r requirements.txt`
5. 标记依赖已安装（缓存）

**代码** (`shared/workspace/manager.py`)：

```python
def _link_skill(self, skill_id: str, skill_path: Path):
    """将技能链接到工作区并安装依赖"""

    target_dir = self.workspace_path / "skills" / skill_id

    # 创建符号链接
    if not target_dir.exists():
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        target_dir.symlink_to(skill_path, target_is_directory=True)

    # 检查 requirements.txt
    requirements = skill_path / "requirements.txt"
    if requirements.exists() and not self._is_dependencies_installed(skill_id):
        self._install_skill_dependencies(skill_id, requirements)

def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    """使用 pip 安装依赖"""

    try:
        LOGGER.info(f"正在为技能 '{skill_id}' 安装依赖...")

        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True,
            timeout=120,  # 2 分钟超时
        )

        # 标记为已安装
        self._skill_registry.mark_dependencies_installed(skill_id)

        LOGGER.info(f"✓ 已为 '{skill_id}' 安装依赖")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        LOGGER.warning(f"安装依赖失败：{error_msg}")
        # 不要让整个会话失败，只是警告

    except subprocess.TimeoutExpired:
        LOGGER.warning(f"'{skill_id}' 依赖安装超时")
```

**错误处理**：

如果安装失败，代理会收到友好的错误：

```python
# generalAgent/tools/builtin/run_bash_command.py
except ImportError as e:
    missing_module = str(e).split("'")[1] if "'" in str(e) else "unknown"
    return f"""脚本执行失败：缺少依赖

错误：缺少 Python 模块 '{missing_module}'

建议操作：
1. 检查 skills/{skill_id}/requirements.txt 是否包含此依赖
2. 手动安装：pip install {missing_module}
3. 或联系技能维护者添加依赖声明
"""
```

### 3.6 技能配置 (skills.yaml)

**配置文件**：`generalAgent/config/skills.yaml`

```yaml
# 全局设置
global:
  enabled: true                    # 启用/禁用整个技能系统
  auto_load_on_file_upload: true  # 上传匹配文件时自动加载技能

# 核心技能 - 启动时始终加载
core: []  # 默认为空

# 可选技能 - 按需加载
optional:
  pdf:
    enabled: false                           # 在目录中显示？
    available_to_subagent: false                  # 在所有会话中保持加载？
    description: "PDF 处理和表单填写"
    auto_load_on_file_types: ["pdf"]        # 上传 .pdf 时自动加载

  my-skill:
    enabled: true
    available_to_subagent: false
    description: "我的自定义技能"
    auto_load_on_file_types: ["txt", "csv"]

# 技能目录
directories:
  builtin: "generalAgent/skills"
```

**配置选项**：

- `enabled: true` - 在目录中显示并在启动时加载
- `enabled: false` - 从目录隐藏，只通过 @提及或文件上传加载
- `available_to_subagent: true` - 在所有会话中保持加载（不推荐）
- `auto_load_on_file_types` - 触发自动加载的文件扩展名

**行为**：

| 设置 | 目录 | 启动 | @提及 | 文件上传 |
|---------|---------|---------|----------|-------------|
| `enabled: true` | ✓ 可见 | ✓ 已加载 | ✓ 工作 | ✓ 自动加载 |
| `enabled: false` | ✗ 隐藏 | ✗ 未加载 | ✓ 工作 | ✓ 自动加载 |

**使用场景**：

1. **隐藏实验性技能**：设置 `enabled: false`
2. **默认技能**：设置 `enabled: true`
3. **渐进式披露**：从 `enabled: false` 开始，文件上传时自动加载

### 3.7 测试技能

#### 手动测试

```bash
# 启动 CLI
python main.py

# 测试技能加载
You> @my-skill 处理文件 uploads/data.txt

# 检查日志
tail -f logs/agentgraph_*.log | grep "my-skill"
```

#### 单元测试（脚本）

```python
# tests/unit/test_my_skill_script.py
import json
import subprocess
import sys
from pathlib import Path

def test_process_script():
    """测试 process.py 脚本"""

    script_path = Path("generalAgent/skills/my-skill/scripts/process.py")

    # 准备输入
    input_data = {
        "input_file": "uploads/test.txt",
        "output_file": "outputs/result.txt",
        "options": {"format": "json"}
    }

    # 运行脚本
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env={"AGENT_WORKSPACE_PATH": "/tmp/test_workspace"},
    )

    # 检查结果
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["status"] == "success"
    assert "output_file" in output
```

#### 集成测试

```python
# tests/integration/test_my_skill_integration.py
import pytest
from pathlib import Path
from generalAgent.skills.registry import SkillRegistry

def test_skill_loading():
    """测试技能正确加载"""

    registry = SkillRegistry(skills_root=Path("generalAgent/skills"))

    # 检查技能存在
    skill = registry.get_skill("my-skill")
    assert skill is not None
    assert skill.id == "my-skill"
    assert skill.name == "My Skill"

    # 检查 SKILL.md 存在
    skill_md = skill.path / "SKILL.md"
    assert skill_md.exists()

    # 检查脚本存在
    scripts_dir = skill.path / "scripts"
    assert scripts_dir.exists()
    assert (scripts_dir / "process.py").exists()
```

---

## 第四部分：扩展系统

### 4.1 添加自定义节点

自定义节点允许您在 LangGraph 流中添加新的逻辑点。

**示例：添加"验证"节点**：

```python
# generalAgent/graph/nodes/validation.py
from typing import Any
from langchain_core.messages import AIMessage
import logging

LOGGER = logging.getLogger(__name__)

def validation_node(state: dict[str, Any]) -> dict[str, Any]:
    """在最终化之前验证代理输出"""

    messages = state["messages"]
    last_message = messages[-1]

    # 检查输出是否符合标准
    if isinstance(last_message, AIMessage):
        content = last_message.content

        # 示例验证：检查最小长度
        if len(content) < 10:
            LOGGER.warning("输出太短，请求更多细节")

            # 添加验证消息
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(
                content="请提供更详细的回答（至少10个字符）。"
            ))

            return {
                "messages": messages,
                "needs_replan": True,  # 触发重新规划
            }

    # 验证通过
    LOGGER.info("✓ 输出验证通过")
    return {"needs_replan": False}
```

**集成到图中**：

```python
# generalAgent/graph/builder.py
from generalAgent.graph.nodes.validation import validation_node

def build_state_graph(...):
    workflow = StateGraph(AppState)

    # 添加节点
    workflow.add_node("plan", planner_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("validation", validation_node)  # 新增
    workflow.add_node("finalize", finalize_node)

    # 添加边
    workflow.add_edge("plan", "tools")
    workflow.add_edge("tools", "validation")  # 新增

    # 添加条件边
    workflow.add_conditional_edges(
        "validation",
        lambda state: "plan" if state.get("needs_replan") else "finalize",
        {"plan": "plan", "finalize": "finalize"}
    )

    return workflow.compile()
```

### 4.2 自定义路由逻辑

**示例：添加图像检测路由**：

```python
# generalAgent/graph/routing.py
from typing import Literal
from generalAgent.graph.state import AppState

def agent_route(state: AppState) -> Literal["tools", "vision", "finalize"]:
    """根据内容路由代理"""

    messages = state["messages"]
    last = messages[-1]

    # 检查循环限制
    if state["loops"] >= state["max_loops"]:
        return "finalize"

    # 检查状态中的图像
    if state.get("images"):
        return "vision"  # 路由到视觉节点

    # LLM 想调用工具
    if last.tool_calls:
        return "tools"

    # LLM 完成
    return "finalize"
```

**添加视觉节点**：

```python
# generalAgent/graph/nodes/vision.py
from generalAgent.models.registry import ModelRegistry
from langchain_core.messages import HumanMessage

def vision_node(state: dict) -> dict:
    """使用视觉模型处理图像"""

    model_registry = ModelRegistry.get_instance()
    vision_model = model_registry.get_model("vision")

    # 准备带图像的消息
    messages = state["messages"]
    images = state.get("images", [])

    # 将图像添加到最后一条消息
    last_message = messages[-1]
    content = [
        {"type": "text", "text": last_message.content},
        *[{"type": "image_url", "image_url": {"url": img}} for img in images]
    ]

    # 调用视觉模型
    result = vision_model.invoke([HumanMessage(content=content)])

    return {
        "messages": [result],
        "images": [],  # 处理后清除图像
    }
```

### 4.3 集成第三方服务

**示例：添加天气服务**：

```python
# generalAgent/services/weather.py
import requests
from typing import Optional

class WeatherService:
    """天气数据服务"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.weather.com/v1"

    def get_weather(self, city: str) -> Optional[dict]:
        """获取城市天气"""

        try:
            response = requests.get(
                f"{self.base_url}/weather",
                params={"city": city, "apikey": self.api_key},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            LOGGER.error(f"天气 API 失败：{e}")
            return None
```

**创建使用服务的工具**：

```python
# generalAgent/tools/builtin/weather.py
from langchain_core.tools import tool
from generalAgent.services.weather import WeatherService
import os

@tool
def get_weather(city: str) -> str:
    """获取城市的当前天气。

    Args:
        city: 城市名称（如 "北京"、"上海"）

    Returns:
        天气描述
    """
    api_key = os.environ.get("WEATHER_API_KEY")
    if not api_key:
        return "错误：WEATHER_API_KEY 未配置"

    service = WeatherService(api_key)
    weather = service.get_weather(city)

    if not weather:
        return f"错误：无法获取 {city} 的天气"

    return f"{city} 的天气：{weather['description']}，{weather['temp']}°C"
```

**添加到 .env**：

```bash
WEATHER_API_KEY=your-api-key-here
```

### 4.4 自定义模型解析器

**示例：为专门任务添加自定义解析器**：

```python
# generalAgent/runtime/custom_model_resolver.py
from typing import Dict, Optional
from generalAgent.graph.state import AppState

class CustomModelResolver:
    """带有任务特定逻辑的自定义模型解析器"""

    def __init__(self, configs: Dict[str, dict]):
        self.configs = configs

    def resolve(self, state: AppState, node_name: str) -> str:
        """根据任务复杂度和内容解析模型"""

        # 分析任务复杂度
        complexity = self._analyze_complexity(state)

        # 根据复杂度路由
        if complexity == "high":
            # 为复杂任务使用推理模型
            if "reasoning" in self.configs:
                return "reasoning"

        # 根据内容类型路由
        if state.get("images"):
            if "vision" in self.configs:
                return "vision"

        # 检查任务是否涉及代码
        if self._is_code_task(state):
            if "code" in self.configs:
                return "code"

        # 默认使用基础模型
        if "base" in self.configs:
            return "base"

        # 回退到第一个可用的
        return list(self.configs.keys())[0]

    def _analyze_complexity(self, state: AppState) -> str:
        """分析任务复杂度"""

        messages = state.get("messages", [])
        if not messages:
            return "low"

        last_message = messages[-1]
        content = last_message.content if hasattr(last_message, "content") else ""

        # 简单启发式：更长的消息 = 更复杂
        if len(content) > 1000:
            return "high"
        elif len(content) > 500:
            return "medium"
        else:
            return "low"

    def _is_code_task(self, state: AppState) -> bool:
        """检查任务是否涉及代码"""

        messages = state.get("messages", [])
        if not messages:
            return False

        last_message = messages[-1]
        content = last_message.content if hasattr(last_message, "content") else ""

        # 查找代码相关关键字
        code_keywords = ["代码", "函数", "class", "def", "import", "编程"]
        return any(keyword in content.lower() for keyword in code_keywords)
```

**使用自定义解析器**：

```python
# main.py
from generalAgent.runtime.app import build_application
from generalAgent.runtime.custom_model_resolver import CustomModelResolver

# 使用自定义解析器构建应用
app, state_factory, skill_registry, tool_registry = build_application()

# 替换默认解析器
custom_resolver = CustomModelResolver(configs=app.model_configs)
app.model_resolver = custom_resolver
```

### 4.5 子代理目录

**示例：添加专门的子代理**：

```python
# generalAgent/agents/data_analysis_agent.py
from typing import Dict, Any
from langchain_core.messages import SystemMessage

class DataAnalysisAgent:
    """用于数据分析任务的专门代理"""

    def __init__(self, model, tools):
        self.model = model
        self.tools = tools
        self.system_prompt = """你是数据分析专家。

核心能力：
- 数据清洗和预处理
- 统计分析
- 可视化生成
- 趋势预测

工作流程：
1. 理解数据结构
2. 进行数据分析
3. 生成可视化报告
4. 提供分析结论
"""

    def invoke(self, task: str, context: Dict[str, Any]) -> str:
        """执行数据分析任务"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=task)
        ]

        result = self.model.invoke(messages, tools=self.tools)
        return result.content
```

**在子代理目录中注册**：

```python
# generalAgent/runtime/app.py
def build_application():
    # ... 现有代码 ...

    # 创建子代理目录
    delegated agent_catalog = {
        "data-analyst": {
            "name": "数据分析师",
            "description": "专门负责数据分析、统计和可视化",
            "capabilities": ["数据清洗", "统计分析", "可视化", "趋势预测"],
            "allowed_tools": ["read_file", "write_file", "run_python_script"],
        },
        # ... 其他子代理 ...
    }

    # 注册代理工厂
    def create_delegated agent(agent_type: str):
        if agent_type == "data-analyst":
            from generalAgent.agents.data_analysis_agent import DataAnalysisAgent
            model = model_registry.get_model("base")
            tools = [tool_registry.get_tool(t) for t in ["read_file", "write_file"]]
            return DataAnalysisAgent(model, tools)
        # ... 其他代理 ...

    return app, state_factory, skill_registry, tool_registry, create_delegated agent
```

---

## 第五部分：开发最佳实践

### 5.1 代码组织

**项目结构最佳实践**：

1. **共享基础设施** (`shared/`) - 可重用组件
2. **代理特定逻辑** (`generalAgent/`) - 业务逻辑
3. **清晰分离** - 基础设施 vs 业务逻辑

**模块组织**：

```
generalAgent/
├── agents/           # 代理工厂
├── config/           # 设置和配置
├── graph/            # 状态、节点、路由
│   ├── nodes/        # 单独的节点实现
│   ├── prompts.py    # 提示词模板
│   ├── routing.py    # 路由逻辑
│   ├── state.py      # 状态定义
│   └── builder.py    # 图组装
├── models/           # 模型注册表和路由
├── runtime/          # 应用组装
├── skills/           # 技能包
├── tools/            # 工具系统
│   ├── builtin/      # 内置工具
│   ├── custom/       # 自定义工具
│   ├── registry.py   # 工具注册表
│   └── scanner.py    # 工具发现
└── utils/            # 实用函数
```

**最佳实践**：

1. **每个模块一个职责** - 每个文件应该有明确的目的
2. **避免循环导入** - 使用依赖注入
3. **分组相关功能** - 工具、节点、实用程序
4. **清晰命名** - 模块名称反映其目的

### 5.2 命名约定

**文件**：
- `snake_case.py` - Python 模块
- `PascalCase` - 类
- `UPPER_CASE.md` - 文档文件

**函数和变量**：
```python
# ✓ 好
def build_skills_catalog(skill_registry: SkillRegistry) -> str:
    enabled_skills = skill_registry.get_enabled_skills()
    return format_catalog(enabled_skills)

# ✗ 不好
def BuildSkillsCatalog(sr):
    es = sr.GetEnabledSkills()
    return FormatCatalog(es)
```

**类**：
```python
# ✓ 好
class ToolRegistry:
    def register_tool(self, tool: BaseTool) -> None:
        pass

# ✗ 不好
class tool_registry:
    def RegisterTool(self, t):
        pass
```

**常量**：
```python
# ✓ 好
MAX_LOOPS = 100
DEFAULT_TIMEOUT = 30
SKILL_CONFIG_PATH = "generalAgent/config/skills.yaml"

# ✗ 不好
maxLoops = 100
default_timeout = 30
skillConfigPath = "generalAgent/config/skills.yaml"
```

**环境变量**：
```python
# ✓ 好
MODEL_BASE_API_KEY
MODEL_REASON_BASE_URL
AGENT_WORKSPACE_PATH

# ✗ 不好
modelBaseApiKey
model_reason_url
agentWorkspace
```

### 5.3 错误处理模式

**模式 1：返回错误消息（工具）**

工具应该返回错误消息而不是抛出异常：

```python
# ✓ 好
@tool
def read_file(file_path: str) -> str:
    """从工作区读取文件"""
    try:
        workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
        abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return f"错误：文件未找到：{file_path}"
    except PermissionError:
        return f"错误：权限被拒绝：{file_path}"
    except Exception as e:
        LOGGER.error(f"读取文件失败：{e}", exc_info=True)
        return f"错误：{e}"

# ✗ 不好
@tool
def read_file(file_path: str) -> str:
    """从工作区读取文件"""
    # 抛出异常 - 代理无法处理
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**模式 2：优雅降级（服务）**

当功能不可用时，服务应优雅降级：

```python
# ✓ 好
def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    try:
        subprocess.run([...], check=True, timeout=120)
        self._skill_registry.mark_dependencies_installed(skill_id)

    except subprocess.CalledProcessError as e:
        # 不要让整个会话失败，只是警告
        LOGGER.warning(f"为 '{skill_id}' 安装依赖失败：{e}")
        LOGGER.warning("技能脚本可能无法工作。需要手动安装。")

    except subprocess.TimeoutExpired:
        LOGGER.warning(f"'{skill_id}' 依赖安装超时")

# ✗ 不好
def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    # 抛出异常 - 整个会话失败
    subprocess.run([...], check=True, timeout=120)
    self._skill_registry.mark_dependencies_installed(skill_id)
```

**模式 3：错误边界装饰器**

使用装饰器集中错误处理：

```python
# ✓ 好
from generalAgent.tools.decorators import with_error_boundary

@tool
@with_error_boundary
def my_tool(param: str) -> str:
    """我的工具"""
    # 不需要 try-except
    return process(param)

# ✗ 不好
@tool
def my_tool(param: str) -> str:
    """我的工具"""
    try:
        return process(param)
    except Exception as e:
        # 每个工具中重复的错误处理
        return f"错误：{e}"
```

### 5.4 日志指南

**日志级别**：

- `DEBUG` - 用于调试的详细信息
- `INFO` - 关于执行的一般信息
- `WARNING` - 意外但不严重的事情
- `ERROR` - 应该调查的错误

**设置日志**：

```python
# generalAgent/__init__.py
import logging

def setup_logging(level=logging.INFO):
    """设置结构化日志"""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("logs/app.log"),
            logging.StreamHandler(),
        ],
    )
```

**使用模块日志器**：

```python
import logging

LOGGER = logging.getLogger(__name__)  # 使用模块名称

def my_function():
    LOGGER.info("函数被调用")
    LOGGER.debug(f"参数值：{param}")
    LOGGER.warning("意外情况")
    LOGGER.error("操作失败", exc_info=True)
```

**日志最佳实践**：

```python
# ✓ 好 - 结构化且有信息
LOGGER.info(f"按需加载工具：{tool_name}")
LOGGER.info(f"✓ 工具已加载：{tool_name}")
LOGGER.warning(f"✗ 工具未找到：{tool_name}")
LOGGER.error(f"加载工具 '{tool_name}' 失败：{e}", exc_info=True)

# ✗ 不好 - 模糊且不一致
LOGGER.info("加载工具")
LOGGER.info("完成")
LOGGER.warning("未找到")
LOGGER.error("错误")
```

**日志提示词截断**：

```python
# 对于长提示词
max_length = 500
if len(system_prompt) > max_length:
    preview = system_prompt[:max_length] + f"... ({len(system_prompt)} 字符)"
else:
    preview = system_prompt

LOGGER.debug(f"系统提示词：\n{preview}")
```

### 5.5 配置管理

**使用 Pydantic 设置**：

```python
# ✓ 好 - 类型安全、已验证、自动加载
from generalAgent.config.settings import get_settings

settings = get_settings()
max_loops = settings.governance.max_loops  # 从 .env，已验证

# ✗ 不好 - 手动解析，无验证
import os

max_loops = int(os.getenv("MAX_LOOPS", "100"))  # 容易出错
```

**配置层次结构**：

1. **环境变量**（.env 文件）
2. **默认值**（Pydantic Field 默认值）
3. **运行时覆盖**（函数参数）

**YAML 配置**：

```python
# ✓ 好 - 集中配置
# generalAgent/config/tools.yaml
optional:
  http_fetch:
    enabled: true
    category: "network"
    tags: ["network", "read"]

# 使用类型安全加载器加载
from generalAgent.tools.config_loader import load_tool_config
config = load_tool_config()
enabled_tools = config.get_all_enabled_tools()

# ✗ 不好 - 在 Python 中硬编码
ENABLED_TOOLS = {"http_fetch", "extract_links"}  # 难以维护
```

### 5.6 路径处理

**始终使用 Path 对象**：

```python
from pathlib import Path

# ✓ 好
workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
file_path = workspace_root / "uploads" / "data.txt"

if file_path.exists():
    content = file_path.read_text()

# ✗ 不好
workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")
file_path = os.path.join(workspace_root, "uploads", "data.txt")

if os.path.exists(file_path):
    with open(file_path, "r") as f:
        content = f.read()
```

**安全：验证路径**：

```python
from generalAgent.utils.file_processor import resolve_workspace_path

# ✓ 好 - 验证路径在工作区内
abs_path = resolve_workspace_path(
    file_path,
    workspace_root,
    must_exist=True,
    allow_write=False,
)

# ✗ 不好 - 无验证，路径遍历漏洞
abs_path = workspace_root / file_path  # 允许 ../../../etc/passwd
```

**项目根解析**：

```python
from generalAgent.config.project_root import resolve_project_path

# ✓ 好 - 从任何目录工作
skills_root = resolve_project_path("generalAgent/skills")
config_path = resolve_project_path("generalAgent/config/tools.yaml")

# ✗ 不好 - 从不同目录运行时中断
skills_root = Path("generalAgent/skills")  # 仅从项目根工作
```

---

## 第六部分：调试和故障排除

### 6.1 日志和追踪

**启用调试日志**：

```bash
# 在 .env 中
LOG_LEVEL=DEBUG

# 或在运行时
export LOG_LEVEL=DEBUG
python main.py
```

**检查日志**：

```bash
# 查看最新日志
tail -f logs/agentgraph_*.log

# 搜索错误
grep "ERROR" logs/agentgraph_*.log

# 搜索特定工具
grep "read_file" logs/agentgraph_*.log
```

**日志文件位置**：

```
logs/
├── agentgraph_20250124.log      # 每日日志文件
├── agentgraph_20250125.log
└── error.log                     # 仅错误日志（如果配置）
```

### 6.2 LangSmith 集成

**启用 LangSmith 追踪**：

```bash
# 在 .env 中
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=my-project
LANGCHAIN_API_KEY=your-api-key
```

**查看追踪**：

1. 访问 https://smith.langchain.com
2. 选择您的项目
3. 查看每次对话轮次的追踪

**追踪信息**：

- 每个节点的输入/输出
- 工具调用和结果
- Token 使用
- 延迟
- 错误

**使用 LangSmith 调试**：

```python
# 向追踪添加自定义元数据
from langchain_core.tracers import ConsoleCallbackHandler

# 在代码中
result = agent.invoke(
    input_data,
    config={
        "callbacks": [ConsoleCallbackHandler()],
        "metadata": {
            "session_id": session_id,
            "user_id": user_id,
        }
    }
)
```

### 6.3 常见问题

#### 问题 1：工具未加载

**症状**：
- @提及时工具不可用
- "工具未找到"错误

**调试**：

```bash
# 检查工具配置
cat generalAgent/config/tools.yaml | grep my_tool

# 检查工具文件存在
ls generalAgent/tools/builtin/my_tool.py

# 检查日志
grep "扫描工具" logs/agentgraph_*.log
grep "my_tool" logs/agentgraph_*.log
```

**解决方案**：

1. **检查工具已启用** 在 `tools.yaml` 中：
   ```yaml
   optional:
     my_tool:
       enabled: true  # 启动加载必须为 true
   ```

2. **检查 __all__ 导出**：
   ```python
   __all__ = ["my_tool"]  # 必须导出
   ```

3. **检查工具装饰器**：
   ```python
   @tool  # 必须有装饰器
   def my_tool(...):
       pass
   ```

#### 问题 2：技能未自动加载

**症状**：
- 上传文件时技能不加载
- 未显示文件上传提示

**调试**：

```bash
# 检查技能配置
cat generalAgent/config/skills.yaml | grep my-skill

# 检查文件类型配置
grep "auto_load_on_file_types" generalAgent/config/skills.yaml

# 检查日志
grep "auto-load" logs/agentgraph_*.log
grep "my-skill" logs/agentgraph_*.log
```

**解决方案**：

1. **检查自动加载已启用**：
   ```yaml
   global:
     auto_load_on_file_upload: true
   ```

2. **检查文件类型匹配**：
   ```yaml
   optional:
     my-skill:
       auto_load_on_file_types: ["txt", "csv"]  # 必须匹配文件扩展名
   ```

3. **检查日志中的文件扩展名解析**：
   ```
   [INFO] 文件已上传：data.txt（扩展名：txt）
   [INFO] 自动加载技能：my-skill
   ```

#### 问题 3：模型 API 错误

**症状**：
- "未找到 API 密钥"错误
- "连接被拒绝"错误
- "未找到模型"错误

**调试**：

```bash
# 检查环境变量
echo $MODEL_BASE_API_KEY
echo $MODEL_BASE_BASE_URL

# 检查 .env 文件
cat .env | grep MODEL_BASE

# 检查日志
grep "MODEL" logs/agentgraph_*.log
grep "API" logs/agentgraph_*.log
```

**解决方案**：

1. **验证 API 密钥** 在 `.env` 中：
   ```bash
   MODEL_BASE_API_KEY=sk-xxx  # 必须是有效密钥
   ```

2. **验证基础 URL**：
   ```bash
   MODEL_BASE_BASE_URL=https://api.deepseek.com  # 必须是正确端点
   ```

3. **手动测试 API**：
   ```bash
   curl -X POST https://api.deepseek.com/v1/chat/completions \
     -H "Authorization: Bearer $MODEL_BASE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'
   ```

#### 问题 4：工作区权限错误

**症状**：
- "权限被拒绝"错误
- "无法写入 skills/"错误

**调试**：

```bash
# 检查工作区权限
ls -la data/workspace/session_123/

# 检查日志
grep "Permission" logs/agentgraph_*.log
grep "write" logs/agentgraph_*.log
```

**解决方案**：

1. **检查写入目录**：
   ```python
   # ✓ 可以写入这些
   "outputs/result.txt"
   "temp/cache.json"
   "uploads/data.txt"

   # ✗ 不能写入这些
   "skills/pdf/SKILL.md"  # 只读
   "../../../etc/passwd"  # 工作区外
   ```

2. **使用 resolve_workspace_path**：
   ```python
   abs_path = resolve_workspace_path(
       file_path,
       workspace_root,
       allow_write=True,  # 检查写入权限
   )
   ```

### 6.4 调试工具

#### 交互式 Python Shell

```bash
# 启动带有项目导入的 Python shell
python -i -c "from generalAgent.config.settings import get_settings; settings = get_settings()"

# 现在你可以检查设置
>>> settings.governance.max_loops
100
>>> settings.models.base_api_key
'sk-xxx'
```

#### 工具测试脚本

```python
# test_tool.py
from generalAgent.tools.registry import ToolRegistry
from generalAgent.tools.scanner import scan_tools_directory
from pathlib import Path

# 设置
registry = ToolRegistry()
tools_dir = Path("generalAgent/tools/builtin")
tools = scan_tools_directory(tools_dir)

for tool in tools:
    registry.register_tool(tool)

# 测试工具
my_tool = registry.get_tool("read_file")
result = my_tool.invoke({"file_path": "test.txt"})
print(result)
```

#### 技能测试脚本

```python
# test_skill.py
from generalAgent.skills.registry import SkillRegistry
from pathlib import Path

# 设置
registry = SkillRegistry(skills_root=Path("generalAgent/skills"))

# 测试技能
skill = registry.get_skill("pdf")
print(f"技能：{skill.name}")
print(f"路径：{skill.path}")
print(f"SKILL.md 存在：{(skill.path / 'SKILL.md').exists()}")
```

---

## 第七部分：贡献

### 7.1 代码风格

**Python 风格指南**：

- 遵循 PEP 8
- 使用 Black 进行格式化（行长度：88）
- 使用 isort 排序导入
- 使用类型提示

**格式化工具**：

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 使用 Black 格式化代码
black generalAgent/ tests/

# 排序导入
isort generalAgent/ tests/

# 使用 flake8 检查
flake8 generalAgent/ tests/
```

**Pre-commit Hook** (`.pre-commit-config.yaml`)：

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

**安装 pre-commit**：

```bash
pip install pre-commit
pre-commit install
```

### 7.2 测试要求

**测试覆盖率**：

- 新代码最低 80% 覆盖率
- 所有关键路径必须有测试
- 面向用户功能的集成测试

**运行测试**：

```bash
# 快速冒烟测试
python tests/run_tests.py smoke

# 完整测试套件
python tests/run_tests.py all

# 覆盖率报告
python tests/run_tests.py coverage
```

**测试金字塔**：

```
        E2E 测试（少量）
       ╱              ╲
      ╱   集成测试    ╲
     ╱                ╲
    ╱   单元测试      ╲
   ╱    （大量）      ╲
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

**必需的测试**：

1. **单元测试** - 所有新函数/类
2. **集成测试** - 功能工作流
3. **E2E 测试** - 关键用户旅程（可选）

### 7.3 文档

**必需的文档**：

1. **文档字符串** - 所有公共函数/类
2. **CHANGELOG.md** - 所有更改
3. **代码注释** - 复杂逻辑
4. **README 更新** - 新功能

**文档字符串格式**：

```python
def my_function(param1: str, param2: int) -> str:
    """函数的一行摘要。

    函数功能的详细描述。
    可以是多个段落。

    Args:
        param1: param1 的描述
        param2: param2 的描述

    Returns:
        返回值的描述

    Raises:
        ValueError: 当 param1 无效时
        FileNotFoundError: 当文件未找到时

    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        'test-42'
    """
    pass
```

### 7.4 Pull Request 流程

**提交 PR 之前**：

1. **运行测试**：`python tests/run_tests.py all`
2. **格式化代码**：`black generalAgent/ tests/`
3. **检查风格**：`flake8 generalAgent/ tests/`
4. **更新 CHANGELOG.md**
5. **更新文档**

**PR 模板**：

```markdown
## 描述

更改的简要描述。

## 更改类型

- [ ] Bug 修复
- [ ] 新功能
- [ ] 破坏性更改
- [ ] 文档更新

## 测试

- [ ] 已添加/更新单元测试
- [ ] 已添加/更新集成测试
- [ ] 所有测试在本地通过

## 检查清单

- [ ] 代码遵循项目风格
- [ ] 文档已更新
- [ ] CHANGELOG.md 已更新
- [ ] 无破坏性更改（或已记录）
- [ ] 测试已添加/更新
- [ ] 所有测试通过

## 相关问题

修复 #123
相关 #456
```

**审查流程**：

1. **自动检查** - CI/CD 运行测试
2. **代码审查** - 维护者审查代码
3. **反馈** - 处理审查意见
4. **批准** - 至少需要一个批准
5. **合并** - Squash 并合并

---

## 总结

本开发指南涵盖：

1. **环境配置** - 安装、配置、模型设置
2. **开发工具** - 创建、配置、测试工具
3. **开发技能** - 技能结构、脚本、配置
4. **扩展系统** - 自定义节点、路由、服务
5. **最佳实践** - 代码组织、错误处理、日志
6. **调试** - 日志、追踪、常见问题
7. **贡献** - 代码风格、测试、文档、PR

更多详情，请参阅：
- [CLAUDE.md](CLAUDE.md) - 项目概述和架构
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - 全面的测试指南
- [REQUIREMENTS_PART4_TRICKS.md](REQUIREMENTS_PART4_TRICKS.md) - 实现技巧
- [SKILLS_CONFIGURATION.md](SKILLS_CONFIGURATION.md) - 技能配置指南
