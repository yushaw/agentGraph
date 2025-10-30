# Agent System 测试文档

本目录包含 Agent 系统（Handoff Pattern + Agent Registry）的测试文件。

## 测试文件说明

### 1. `test_agent_call_stack.py` - 循环检测测试

**目的**: 验证 Agent 调用栈和循环检测机制

**测试内容**:
- ✅ 允许顺序调用同一个 agent（非嵌套）
- ✅ 阻止嵌套循环（call_stack 检测）
- ✅ 调用栈深度限制（最大5层）
- ✅ Push/Pop 机制验证

**运行**:
```bash
uv run python tests/test_agent_call_stack.py
```

**关键验证**:
```python
# ✅ 允许: agent → simple → (返回) → simple
agent_call_stack = []  # simple 已返回，栈为空
agent_call_history = ["simple"]  # 历史记录

# ❌ 阻止: agent → simple → simple (嵌套)
agent_call_stack = ["simple"]  # simple 在栈中未返回
```

---

### 2. `test_handoff_pattern.py` - Handoff Pattern 集成测试

**目的**: 验证完整的 Handoff Pattern 实现

**测试内容**:
- ✅ Agent Registry 初始化
- ✅ Handoff Tools 自动生成
- ✅ Graph 结构（动态 agent 节点）
- ✅ Agent Catalog（精简模式 + 详细模式）
- ✅ 初始状态正确性

**运行**:
```bash
uv run python tests/test_handoff_pattern.py
```

**关键验证**:
```python
# Agent Registry 统计
stats = {
    'discovered': 2,
    'enabled': 1,
    'available_to_subagent': 1,
}

# 自动生成的 handoff tools
handoff_tools = ['transfer_to_simple']

# Graph 结构包含 agent 节点
graph_nodes = ['agent', 'tools', 'finalize', 'simple']
```

---

### 3. `test_agent_registry_integration.py` - Agent Registry 详细测试

**目的**: 验证 Agent Registry 的查询和 catalog 功能

**测试内容**:
- ✅ 组件导入
- ✅ 从配置加载 agents
- ✅ 查询 agents（by skill, by tag, by capability）
- ✅ Agent Catalog 生成
- ✅ call_agent 工具集成
- ✅ Agent Card 结构验证

**运行**:
```bash
uv run python tests/test_agent_registry_integration.py
```

**关键验证**:
```python
# 按技能查询
results = agent_registry.query_by_skill("quick_analysis")

# 按标签查询
results = agent_registry.query_by_tags(["lightweight"])

# Agent Catalog 生成
catalog = agent_registry.get_catalog_text()
```

---

## 测试覆盖率

| 组件 | 测试文件 | 覆盖内容 |
|------|---------|---------|
| **Agent Call Stack** | test_agent_call_stack.py | 循环检测、深度限制、push/pop |
| **Handoff Pattern** | test_handoff_pattern.py | 端到端集成、graph 结构 |
| **Agent Registry** | test_agent_registry_integration.py | 查询、catalog、配置加载 |
| **Handoff Tools** | test_handoff_pattern.py | 自动生成、工具结构 |
| **Agent Nodes** | test_handoff_pattern.py | 节点注册、路由映射 |

---

## 运行所有 Agent 测试

```bash
# 方式 1: 单独运行每个测试
uv run python tests/test_agent_call_stack.py
uv run python tests/test_handoff_pattern.py
uv run python tests/test_agent_registry_integration.py

# 方式 2: 使用 pytest（如果配置）
pytest tests/test_agent*.py -v

# 方式 3: 使用测试运行器
uv run python tests/run_tests.py all
```

---

## 测试结果示例

### test_agent_call_stack.py
```
======================================================================
总计: 4/4 测试通过
======================================================================
✅ PASSED: 顺序调用允许
✅ PASSED: 嵌套循环阻止
✅ PASSED: 调用栈深度限制
✅ PASSED: Push/Pop 机制
```

### test_handoff_pattern.py
```
======================================================================
总计: 5/5 测试通过
======================================================================
✅ PASSED: Handoff Pattern Initialization
✅ PASSED: Compact Agent Catalog Mode
✅ PASSED: Agent Routing Configuration
✅ PASSED: Handoff Tool Structure
✅ PASSED: Graph Structure with Agent Nodes
```

### test_agent_registry_integration.py
```
======================================================================
✅ All tests passed!
======================================================================
[Test 1] Importing components... ✓
[Test 2] Loading agents from config... ✓
[Test 3] Verifying enabled agents... ✓
[Test 4] Testing query by skill... ✓
[Test 5] Testing query by tag... ✓
[Test 6] Generating Agent Catalog... ✓
[Test 7] Testing call_agent tool... ✓
[Test 8] Verifying Agent Card structure... ✓
```

---

## 测试历史

### 已删除的测试文件

- ❌ `verify_agents_startup.py` - 临时验证脚本（功能已被正式测试覆盖）
- ❌ `test_agent_loop_prevention.py` - 旧版本循环检测（使用错误的 agent_call_history 逻辑）

**删除原因**:
- `verify_agents_startup.py`: 一次性验证脚本，test_handoff_pattern.py 已提供相同功能
- `test_agent_loop_prevention.py`: 使用错误的循环检测逻辑（检查 history 而不是 call_stack），已被 test_agent_call_stack.py 替代

---

## 相关文档

- [Handoff Pattern 实现文档](../docs/ARCHITECTURE.md#第五部分agent-系统handoff-pattern)
- [Agent Registry 设计](../generalAgent/config/agents.yaml)
- [循环检测机制](../generalAgent/agents/handoff_tools.py)

---

**最后更新**: 2025-10-30
**测试状态**: ✅ 所有测试通过 (13/13)
