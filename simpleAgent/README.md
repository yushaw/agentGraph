# SimpleAgent

**轻量级垂直领域 Agent** - 高度定制化的简化版 Agent 框架

## 特点

- **无状态**: 每次调用独立，不保存会话历史
- **轻量级**: 精简的 Agent Loop（agent → tools → finalize → END）
- **可配置**: 支持 Prompt 模板定制和工具白名单
- **双接口**: CLI 交互式 + 函数调用式
- **可集成**: 可被 GeneralAgent 或其他代码调用

## 架构

```
SimpleAgent
├── simple_agent.py          # 核心 Agent 类（可被调用）
├── cli.py                   # CLI 接口（继承 BaseCLI）
├── runtime/
│   └── app.py              # 应用组装
├── graph/
│   ├── builder.py          # LangGraph 构建
│   ├── state.py            # State 定义（精简版）
│   └── nodes/
│       ├── agent.py        # Agent 节点
│       └── finalize.py     # 终止节点
├── config/
│   ├── settings.py         # Pydantic 配置
│   ├── tools.yaml          # 工具配置
│   └── prompt_templates/   # Prompt 模板库
│       ├── default.jinja2
│       └── data_analyst.jinja2
└── utils/
    └── prompt_builder.py   # Prompt 模板构建器
```

## 使用方式

### 1. CLI 模式（交互式）

```bash
# 基本使用
python simple_main.py

# 使用自定义模板
python simple_main.py --template "你是{role}。任务: {task}" \
  --params '{"role": "数据分析师", "task": "分析数据"}'

# 使用模板文件
python simple_main.py --template-file simpleAgent/config/prompt_templates/data_analyst.jinja2 \
  --params '{"task": "分析季度销售数据"}'

# 指定可用工具
python simple_main.py --tools read_file,write_file,ask_human

# 单次运行（非交互）
python simple_main.py --message "你好，请介绍一下自己" --no-interactive
```

### 2. 函数调用模式

```python
from simpleAgent import SimpleAgent

# 方式 1: 基本调用
agent = SimpleAgent()
result = await agent.run(
    template="你是 {role}。任务: {task}",
    params={"role": "数据分析师", "task": "分析 sales.csv"},
    user_message="开始分析",
    tools=["read_file", "write_file"],
)

# 方式 2: 使用模板文件
agent = SimpleAgent(
    template_path="simpleAgent/config/prompt_templates/data_analyst.jinja2"
)
result = await agent.run(
    params={"task": "分析季度销售数据"},
    user_message="开始分析",
)

# 方式 3: 指定模型类型
result = await agent.run(
    template="你是代码专家",
    user_message="解释这段代码",
    model_type="code",  # 使用 MODEL_CODE_* 配置
)
```

### 3. 被 GeneralAgent 调用

```python
# 在 GeneralAgent 中集成 SimpleAgent
from simpleAgent import SimpleAgent

# 创建专业 Agent 实例
data_agent = SimpleAgent(
    template_path="simpleAgent/config/prompt_templates/data_analyst.jinja2"
)

# 委派任务
result = await data_agent.run(
    params={"task": "分析用户流失率"},
    user_message="请分析 uploads/users.csv 的流失率",
)
```

## Prompt 模板系统

### 支持两种格式

**1. f-string 格式**（推荐代码调用）

```python
template = "你是 {role}。任务: {task}"
params = {"role": "分析师", "task": "分析数据"}

agent.run(template=template, params=params, format="f-string")
```

**2. Jinja2 格式**（推荐配置文件）

```jinja2
你是一位专业的 {{ role }}。

当前任务: {{ task }}

{% if urgent %}
⚠️  这是一个紧急任务！
{% endif %}

可用工具:
{% for tool in tools %}
- {{ tool }}
{% endfor %}
```

```python
agent.run(
    template=jinja2_template,
    params={"role": "分析师", "task": "分析数据", "urgent": True},
    format="jinja2"
)
```

### 模板示例

参考 `simpleAgent/config/prompt_templates/` 目录：

- `default.jinja2` - 通用模板
- `data_analyst.jinja2` - 数据分析专用模板

## 工具配置

编辑 `simpleAgent/config/tools.yaml`：

```yaml
core:
  now:
    category: "meta"
    description: "获取当前时间"

optional:
  read_file:
    enabled: true  # 启动时加载
    category: "file"

  run_bash_command:
    enabled: false  # 默认不加载（安全考虑）
    category: "system"
```

## 模型配置

支持 5 种模型类型（通过 `.env` 配置）：

- `base` - 基础模型（MODEL_BASIC_*）
- `reasoning` - 推理模型（MODEL_REASONING_*）
- `vision` - 视觉模型（MODEL_MULTIMODAL_*）
- `code` - 代码模型（MODEL_CODE_*）
- `chat` - 对话模型（MODEL_CHAT_*）

```python
# 在代码中指定模型类型
agent.run(user_message="...", model_type="reasoning")
```

或在配置中设置默认模型：

```python
agent.settings.model_type = "code"
```

## 与 GeneralAgent 的区别

| 特性 | GeneralAgent | SimpleAgent |
|------|--------------|-------------|
| 会话管理 | SQLite 持久化 | 无状态（不保存） |
| 工具系统 | @mention 动态加载 | 配置预加载 |
| Skills 支持 | 完整支持 | 不支持 |
| Agent Loop | 复杂（含压缩、委派） | 简化（3 节点） |
| Prompt 定制 | 固定 SystemMessage | 高度可定制 |
| HITL 审批 | 支持 | 自动执行 |
| 使用场景 | 通用对话 + 任务执行 | 垂直领域专业任务 |

## 使用场景

### 适合 SimpleAgent

- 垂直领域专业任务（数据分析、代码审查、文档生成）
- 固定流程的自动化（报告生成、批量处理）
- 作为 GeneralAgent 的子任务处理器
- 需要高度定制 Prompt 的场景

### 适合 GeneralAgent

- 通用对话和任务执行
- 需要会话历史和上下文
- 复杂的多轮交互
- 需要动态加载技能

## 开发指南

### 添加新模板

1. 创建模板文件：`simpleAgent/config/prompt_templates/my_template.jinja2`
2. 使用模板：

```python
agent = SimpleAgent(template_path="simpleAgent/config/prompt_templates/my_template.jinja2")
result = await agent.run(params={...}, user_message="...")
```

### 自定义工具配置

编辑 `simpleAgent/config/tools.yaml`，添加或修改工具配置。

### 扩展 CLI 命令

编辑 `simpleAgent/cli.py`，覆盖 `_build_command_handlers()` 方法：

```python
def _build_command_handlers(self):
    handlers = super()._build_command_handlers()
    handlers["/custom"] = self._handle_custom
    return handlers

async def _handle_custom(self, args: str):
    print("自定义命令逻辑")
```

## 测试

```bash
# 运行单元测试
pytest tests/unit/test_simple_agent.py -v

# 运行集成测试
python simple_main.py --message "测试消息" --no-interactive
```

## 许可证

与 AgentGraph 项目相同
