# Part 6: HITL (Human-in-the-Loop) 机制

本文档描述 AgentGraph 的 HITL 集成需求和实现细节。

## 目录

- [需求概述](#需求概述)
- [核心架构](#核心架构)
- [实现细节](#实现细节)
- [使用指南](#使用指南)
- [配置与扩展](#配置与扩展)

---

## 需求概述

### 背景

HITL (Human-in-the-Loop) 是 Agent 系统中至关重要的安全和交互机制。AgentGraph 集成了两种 HITL 模式：

1. **ask_human 工具**: Agent 主动请求用户输入
2. **Tool Approval Framework**: 系统级安全检查，拦截危险操作

### 核心需求

**R6.1 Agent 主动交互 (ask_human)**
- **需求**: Agent 可以主动向用户提问获取信息
- **原因**:
  - Agent 可能缺少完成任务所需的关键信息
  - 需要用户确认重要决策
  - 提供更好的用户体验（交互式对话）
- **实现**: `ask_human` 工具 + LangGraph `interrupt()`

**R6.2 系统级安全检查 (Tool Approval)**
- **需求**: 自动检测并拦截潜在危险操作，要求用户批准
- **原因**:
  - 防止 Agent 执行破坏性操作（如 `rm -rf`）
  - 安全审计（记录用户批准/拒绝）
  - 细粒度控制（基于工具参数，非整个工具）
- **实现**: `ApprovalToolNode` + `ApprovalChecker` + `hitl_rules.yaml`

**R6.3 Capability-Level 审批粒度**
- **需求**: 审批基于具体操作内容，而非工具名称
- **示例**:
  - `ls /tmp` → 安全，自动通过
  - `rm -rf /` → 危险，需要批准
  - 同一个 `run_bash_command` 工具，不同参数有不同审批策略
- **实现**: 四层审批规则系统（自定义检查器 → 全局模式 → 工具规则 → 内置默认）

**R6.4 LLM 上下文透明性**
- **需求**: 审批决策**不**应加入 LLM 对话历史
- **原因**:
  - 审批是系统级行为，非对话内容
  - 防止 LLM 学习绕过审批机制
  - 保持对话历史的纯净性
- **实现**: `interrupt()` 暂停 Graph，用户决策后直接恢复执行
- **对比**: `ask_human` 的回答**会**加入历史（作为 ToolMessage）

**R6.5 极简版 UI**
- **需求**: 用户界面提示简洁、清晰、易懂
- **原因**:
  - 减少用户认知负担
  - 快速做出决策
  - 避免信息过载
- **实现**: CLI 提示使用最少文字表达关键信息

---

## 核心架构

### 架构概览

```
Agent Node (LLM 决策)
    ↓ tool_calls
ApprovalToolNode (拦截)
    ↓
ApprovalChecker (检查规则)
    ↓ needs_approval?
interrupt() (暂停 Graph)
    ↓
CLI 用户交互
    ↓ approve/reject
Command(resume=value) (恢复 Graph)
    ↓
ToolNode (执行工具) / ToolMessage (取消)
    ↓
Agent Node (处理结果)
```

### 两种 HITL 模式对比

| 特性 | ask_human 工具 | Tool Approval 框架 |
|------|---------------|------------------|
| **触发者** | Agent (LLM 主动调用) | System (自动检测) |
| **目的** | 获取用户输入 | 安全检查 |
| **用户看到** | 问题 + 输入框 | 工具信息 + 批准/拒绝 |
| **加入历史** | ✅ 是 (ToolMessage) | ❌ 否 (透明) |
| **使用场景** | 缺少信息、需要选择 | 危险操作、权限控制 |
| **配置方式** | 无需配置 | `hitl_rules.yaml` |

---

## 实现细节

### 1. ask_human 工具

#### 工具接口

**文件**: `generalAgent/tools/builtin/ask_human.py`

```python
@tool(args_schema=AskHumanInput)
def ask_human(
    question: str,                      # 要问的问题
    context: str = "",                  # 额外上下文
    input_type: Literal["text"] = "text",  # 输入类型（未来扩展）
    default: Optional[str] = None,      # 默认值
    required: bool = True,              # 是否必填
) -> str:
    """向用户询问信息

    当你缺少必要信息无法继续任务时，使用此工具向用户提问。
    用户会看到你的问题并提供回答，然后你可以继续执行任务。

    何时使用：
    - 需要用户确认细节（如：确认删除操作）
    - 需要用户做选择（如：选择城市、日期）
    - 缺少关键参数（如：不知道用户想要什么）

    参数：
        question: 要问用户的问题（清晰、简洁）
        context: 额外的上下文信息，帮助用户理解
        default: 默认答案（如果用户直接按回车）
        required: 是否必须回答（默认 True）

    返回：
        用户的回答文本
    """
    # 触发 interrupt
    answer = interrupt({
        "type": "user_input_request",
        "question": question,
        "context": context,
        "default": default,
        "required": required,
    })

    return answer or ""
```

#### Interrupt 处理

**文件**: `generalAgent/cli.py` (Lines 252-288)

```python
async def _handle_message(self, user_input: str):
    # ... 执行 Graph ...

    # 检查是否有 interrupt
    while True:
        graph_state = await self.app.aget_state(config)

        if graph_state.next and graph_state.tasks and \
           hasattr(graph_state.tasks[0], 'interrupts') and \
           graph_state.tasks[0].interrupts:

            # 获取 interrupt 数据
            interrupt_value = graph_state.tasks[0].interrupts[0].value

            # 处理 interrupt（用户输入或工具审批）
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

**文件**: `generalAgent/cli.py` (Lines 370-405)

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
        print(f"   (默认: {default})")

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
   (默认: 工作报告)
> 技术方案设计

A> 好的，我将为你创建一份关于"技术方案设计"的文档。
```

#### 未来扩展

工具接口已预留扩展字段：

```python
input_type: Literal["text", "choice", "multi_choice"] = "text"
choices: Optional[List[str]] = None
```

**未来支持**:
- **choice**: 单选（从列表中选一个）
- **multi_choice**: 多选（选择多个选项）

**示例用法** (未来):
```python
# 单选
city = ask_human(
    question="选择目标城市",
    input_type="choice",
    choices=["北京", "上海", "深圳", "杭州"]
)

# 多选
features = ask_human(
    question="选择需要的功能",
    input_type="multi_choice",
    choices=["用户认证", "数据导出", "API 集成", "报表生成"]
)
```

---

### 2. Tool Approval Framework

#### 四层审批规则系统

**Priority 1: 工具自定义检查器** (最高优先级)

适用场景：工具特定的复杂逻辑

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
        r">\s*/dev/sd",     # 直接写硬盘
    ]

    for pattern in high_risk_patterns:
        if re.search(pattern, command):
            return ApprovalDecision(
                needs_approval=True,
                reason=f"检测到高风险操作: {pattern}",
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

**Priority 2: 全局风险模式** (跨工具检测)

适用场景：通用风险检测，适用于所有工具

**文件**: `generalAgent/config/hitl_rules.yaml`

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

**Priority 3: 工具配置规则**

适用场景：工具特定的可配置模式匹配

**文件**: `generalAgent/config/hitl_rules.yaml`

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
        - "internal\\.company\\.com"  # 阻止访问内网
        - "192\\.168\\."
      medium_risk:
        - "api\\."                     # API 调用需确认
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

**Priority 4: 内置默认规则** (兜底逻辑)

适用场景：通用兜底逻辑，当前面三层都不匹配时执行

```python
def _check_builtin_rules(self, tool_name: str, args: dict) -> ApprovalDecision:
    """内置默认规则（最低优先级）"""

    # 默认：所有工具都安全
    return ApprovalDecision(needs_approval=False)
```

#### ApprovalToolNode 实现

**文件**: `generalAgent/hitl/approval_node.py`

```python
class ApprovalToolNode:
    """包装 ToolNode，拦截工具调用进行审批"""

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
            # 审批功能禁用，直接执行
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
                # 触发 interrupt
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
                        content=f"❌ 操作已取消: {decision.reason}",
                        tool_call_id=tool_call_id,
                    )]}

        # 所有工具都通过审批，执行
        return await self.tool_node.ainvoke(state)
```

#### UI 提示（极简版）

**文件**: `generalAgent/cli.py` (Lines 407-443)

```python
async def _handle_tool_approval(self, data: dict) -> str:
    """处理工具审批请求"""
    tool = data.get("tool", "")
    args = data.get("args", {})
    reason = data.get("reason", "")
    risk_level = data.get("risk_level", "medium")

    print()
    print(f"🛡️  工具审批: {tool}")
    if reason:
        print(f"   原因: {reason}")
    print(f"   参数: {self._format_tool_args(args, max_length=60)}")

    # 获取用户决策
    loop = asyncio.get_event_loop()
    choice = await loop.run_in_executor(
        None,
        lambda: input("   批准? [y/n] > ").strip().lower()
    )

    if choice in ["y", "yes", "是"]:
        return "approve"
    elif choice in ["n", "no", "否"]:
        return "reject"
    else:
        # 默认拒绝
        return "reject"

def _format_tool_args(self, args: dict, max_length: int = 60) -> str:
    """格式化工具参数（简洁显示）"""
    if not args:
        return "{}"

    # 单行显示，超长截断
    args_str = str(args)
    if len(args_str) > max_length:
        args_str = args_str[:max_length] + "..."

    return args_str
```

#### 示例交互

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

#### Graph 集成

**文件**: `generalAgent/graph/builder.py` (Lines 79-91)

```python
def build_state_graph(
    tool_registry: "ToolRegistry",
    approval_checker: Optional["ApprovalChecker"] = None,
    # ... 其他参数 ...
) -> StateGraph:
    """构建 LangGraph 状态图"""

    # 如果提供了 approval_checker，使用 ApprovalToolNode
    if approval_checker:
        from generalAgent.hitl import ApprovalToolNode

        tools_node = ApprovalToolNode(
            tools=tool_registry.list_tools(),
            approval_checker=approval_checker,
            enable_approval=True,
        )
    else:
        # 否则使用标准 ToolNode
        from langgraph.prebuilt import ToolNode

        tools_node = ToolNode(tool_registry.list_tools())

    graph.add_node("tools", tools_node)
```

**关键点**:
- `approval_checker` 是可选参数，向后兼容
- ApprovalToolNode 完全包装 ToolNode，对 Graph 其他部分透明
- 禁用审批时（`enable_approval=False`）可以快速回退到标准行为

---

## 使用指南

### ask_human 使用示例

#### 示例 1: 缺少关键信息

```
User> 帮我订个酒店

A> 好的，我来帮你预订酒店。
   [调用 ask_human 工具]

💬 请问你要在哪个城市订酒店？
> 北京

💬 入住日期和退房日期分别是？
   (默认: 今天入住，明天退房)
> 2025-11-01 到 2025-11-03

A> 好的，我将为你查找 2025-11-01 至 2025-11-03 在北京的酒店。
```

#### 示例 2: 需要用户确认

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

### Tool Approval 配置示例

#### 示例 1: 添加新的高风险模式

编辑 `generalAgent/config/hitl_rules.yaml`:

```yaml
tools:
  run_bash_command:
    enabled: true
    patterns:
      high_risk:
        - "rm\\s+-rf"
        - "sudo"
        - "mkfs"          # 新增：格式化文件系统
        - "dd\\s+if="     # 新增：直接磁盘写入
```

#### 示例 2: 自定义工具审批

```yaml
tools:
  http_fetch:
    enabled: true
    patterns:
      high_risk:
        - "internal\\.mycompany\\.com"  # 阻止访问公司内网
        - "192\\.168\\."                 # 阻止访问本地网络
      medium_risk:
        - "api\\."                       # API 调用需确认
    actions:
      high_risk: require_approval
      medium_risk: require_approval
```

#### 示例 3: 创建自定义检查器

**文件**: `generalAgent/hitl/approval_checker.py`

```python
def _check_http_fetch(args: dict) -> ApprovalDecision:
    """自定义检查器：HTTP 请求审批"""
    url = args.get("url", "")

    # 检查是否访问本地网络
    if any(pattern in url for pattern in ["localhost", "127.0.0.1", "192.168."]):
        return ApprovalDecision(
            needs_approval=True,
            reason="尝试访问本地网络",
            risk_level="high"
        )

    # 检查是否访问已知的安全域名
    safe_domains = ["github.com", "stackoverflow.com", "wikipedia.org"]
    if any(domain in url for domain in safe_domains):
        return ApprovalDecision(needs_approval=False)

    # 默认：需要审批
    return ApprovalDecision(
        needs_approval=True,
        reason="访问外部 URL 需确认",
        risk_level="medium"
    )

# 注册到 ApprovalChecker
self.custom_checkers = {
    "run_bash_command": self._check_bash_command,
    "http_fetch": self._check_http_fetch,  # 新增
}
```

---

## 配置与扩展

### 配置文件

**文件**: `generalAgent/config/hitl_rules.yaml`

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

### 扩展 ask_human 工具

#### 添加 choice 输入类型

```python
# generalAgent/tools/builtin/ask_human.py

async def _handle_user_input_request(self, data: dict) -> Union[str, List[str]]:
    input_type = data.get("input_type", "text")

    if input_type == "choice":
        choices = data.get("choices", [])
        print(f"💬 {question}")
        for i, choice in enumerate(choices, 1):
            print(f"   {i}. {choice}")

        while True:
            answer = input("   选择 (输入数字) > ").strip()
            try:
                idx = int(answer) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            except ValueError:
                pass
            print("   ⚠️  无效选择，请重试")

    elif input_type == "multi_choice":
        # TODO: 实现多选逻辑
        pass

    else:  # text
        return await self._handle_text_input(data)
```

### 扩展审批规则

#### 添加新的风险级别

```python
# generalAgent/hitl/approval_checker.py

@dataclass
class ApprovalDecision:
    needs_approval: bool
    reason: str = ""
    risk_level: str = "low"  # low | medium | high | critical
```

#### 添加审批日志

```python
# generalAgent/hitl/approval_node.py

if decision.needs_approval:
    # 记录审批请求
    logger.info(f"Approval requested for {tool_name}: {decision.reason}")

    user_decision = interrupt({...})

    # 记录用户决策
    logger.info(f"User decision for {tool_name}: {user_decision}")
```

---

## 设计决策记录

### 决策 1: 两种 HITL 模式

**问题**: 应该如何实现 HITL？

**选项**:
- A. 仅 ask_human 工具（Agent 主动）
- B. 仅 Tool Approval（系统自动）
- C. 同时支持两种

**决策**: 选择 C（两种都支持）

**理由**:
- ask_human: 适用于缺少信息的场景，由 Agent 判断何时提问
- Tool Approval: 适用于安全检查，由系统自动拦截
- 两种模式互补，覆盖不同使用场景

**权衡**:
- 代码复杂度增加
- 用户需要理解两种模式的区别

### 决策 2: Capability-Level 审批

**问题**: 审批粒度应该多细？

**选项**:
- A. Tool-level: 整个工具需要审批
- B. Capability-level: 基于工具参数内容

**决策**: 选择 B（Capability-level）

**理由**:
- `ls /tmp` 和 `rm -rf /` 是同一个工具的不同能力
- Tool-level 会导致过度审批（安全操作也要批准）
- Capability-level 更精确，减少用户打扰

**权衡**:
- 需要编写复杂的检查逻辑
- 规则维护成本较高

### 决策 3: 审批决策不加入 LLM 历史

**问题**: 审批交互是否应该加入对话历史？

**选项**:
- A. 加入历史（作为 HumanMessage）
- B. 不加入历史（透明）

**决策**: 选择 B（不加入历史）

**理由**:
- 审批是系统行为，非对话内容
- 防止 LLM 学习到审批模式
- 保持对话历史的语义连贯性

**对比**:
- ask_human 的回答**会**加入历史（因为是任务相关信息）

### 决策 4: 三层审批规则

**问题**: 如何组织审批规则？

**选项**:
- A. 仅配置文件
- B. 仅代码实现
- C. 三层系统（自定义 → 配置 → 默认）

**决策**: 选择 C（三层系统）

**理由**:
- 自定义检查器：适合复杂逻辑（如 bash 命令解析）
- 配置文件：适合简单模式匹配（易修改）
- 默认规则：兜底逻辑，保证向后兼容

**权衡**:
- 规则优先级需要明确文档化
- 调试时需要检查三个层次

---

## 实现文件清单

### 核心代码

```
generalAgent/hitl/
├── __init__.py                # 模块导出
├── approval_checker.py        # 四层审批规则系统（含全局风险模式检测）
└── approval_node.py           # ApprovalToolNode 包装器
```

### 工具实现

```
generalAgent/tools/builtin/
└── ask_human.py               # ask_human 工具
```

### 配置文件

```
generalAgent/config/
├── hitl_rules.yaml            # 审批规则配置
└── tools.yaml                 # ask_human 工具配置
```

### 集成点

```
generalAgent/
├── graph/builder.py           # ApprovalToolNode 集成 (Lines 79-91)
├── runtime/app.py             # ApprovalChecker 初始化 (Lines 165-168)
└── cli.py                     # Interrupt 处理 (Lines 252-443)
```

---

## 相关资源

- [LangGraph Interrupt 文档](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/breakpoints/)
- [AgentGraph 项目文档](../CLAUDE.md)
- [REQUIREMENTS Part 1: 核心架构](REQUIREMENTS_PART1_ARCHITECTURE.md)

---

## 版本信息

- **实现日期**: 2025-10-26
- **LangGraph 版本**: 0.2.58+
- **文档版本**: 1.0
