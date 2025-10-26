# GeneralAgent Tests

完整的测试套件,包含冒烟测试、单元测试、集成测试和端到端测试。

## 快速开始

### 运行冒烟测试 (< 30秒)

```bash
python tests/run_tests.py smoke
```

### 运行所有测试

```bash
python tests/run_tests.py all
```

## 测试类型

| 类型 | 目录 | 目的 | 运行时间 |
|------|------|------|----------|
| **Smoke** | `smoke/` | 快速验证核心功能 | < 30s |
| **Unit** | `unit/` | 测试单个模块 | < 2min |
| **Integration** | `integration/` | 测试模块交互 | < 5min |
| **E2E** | `e2e/` | 测试完整业务流程 | < 10min |

## 统一入口

使用 `run_tests.py` 作为统一入口:

```bash
python tests/run_tests.py [smoke|unit|integration|e2e|all|coverage]
```

### 示例

```bash
# 提交前: 运行冒烟测试
python tests/run_tests.py smoke

# 修改模块后: 运行单元测试
python tests/run_tests.py unit

# 发布前: 运行所有测试
python tests/run_tests.py all

# 生成覆盖率报告
python tests/run_tests.py coverage
```

## 测试结构

```
tests/
├── run_tests.py          # 统一测试入口 ⭐
├── README.md             # 本文件
│
├── smoke/                # 冒烟测试 (< 30s)
│   └── test_smoke.py
│
├── unit/                 # 单元测试
│   ├── test_hitl_*.py    # HITL 模块测试
│   ├── test_mcp/         # MCP 模块测试
│   └── ...
│
├── integration/          # 集成测试
│   ├── test_mention_types.py
│   └── ...
│
├── e2e/                  # 端到端测试
│   └── test_agent_workflows.py
│
└── fixtures/             # 测试基础设施 (test fixtures)
    ├── test_stdio_server.py  # 测试用 MCP 服务器
    └── README.md
```

## 详细文档

完整的测试指南请查看: [docs/TESTING_GUIDE.md](../docs/TESTING_GUIDE.md)

## Agent 使用测试

当 Agent 完成功能时,可以顺便运行相关测试验证:

```python
# Agent 可以调用统一入口
user: "帮我修复 HITL 模块的 bug"

agent:
1. 修改代码
2. 运行测试验证: python tests/run_tests.py unit
3. 检查测试结果
4. 如果失败,继续修复
```

### 测试命令示例

```bash
# 修改 HITL 模块后
python tests/run_tests.py unit

# 修改工具系统后
pytest tests/unit/test_tool_scanner.py -v

# 修改 @mention 系统后
pytest tests/integration/test_mention_types.py -v

# 添加新功能后
python tests/run_tests.py all
```

## 快速参考

### 提交前检查清单

- [ ] 运行冒烟测试: `python tests/run_tests.py smoke`
- [ ] 相关单元测试通过
- [ ] 代码格式化: `black .`
- [ ] 类型检查 (如果启用): `mypy generalAgent`

### CI/CD 流程

测试会在以下情况自动运行:
1. 提交到任何分支
2. 创建 Pull Request
3. 合并到主分支前

### 覆盖率目标

- **Unit Tests**: >= 80%
- **Integration Tests**: >= 70%
- **E2E Tests**: >= 60%
- **Overall**: >= 75%
