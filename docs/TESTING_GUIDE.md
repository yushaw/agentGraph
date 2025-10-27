# GeneralAgent Testing Guide

**版本**: 2.0
**日期**: 2025-10-27
**更新**: 重新组织测试结构,添加统一入口

---

## 测试架构

### 目录结构

```
tests/
├── run_tests.py                    # 统一测试入口 ⭐
│
├── smoke/                          # 冒烟测试 (< 30s)
│   └── test_smoke.py              # 快速验证核心功能
│
├── unit/                          # 单元测试 (模块级别)
│   ├── test_hitl_approval.py      # HITL 审批规则
│   ├── test_hitl_unit.py          # HITL 场景测试
│   ├── test_hitl_reflective.py    # HITL 反思性测试
│   ├── test_hitl_evaluation.py    # HITL 评估测试
│   ├── hitl_evaluation_framework.py
│   ├── test_mcp/                   # MCP 连接和集成
│   ├── test_file_ops.py           # 文件操作
│   ├── test_document_extractors.py # 文档提取 (PDF/DOCX/XLSX/PPTX)
│   ├── test_text_indexer.py       # 文本索引和搜索
│   ├── test_find_search_tools.py  # 文件查找和内容搜索工具
│   ├── test_tool_scanner.py       # 工具扫描
│   ├── test_tool_config.py        # 工具配置
│   ├── test_workspace_manager.py  # 工作区管理
│   └── ...
│
├── integration/                   # 集成测试 (模块交互)
│   ├── test_mention_types.py      # @Mention 系统
│   ├── test_registry_on_demand.py # 按需加载
│   ├── test_subagent_simple.py    # 子代理
│   └── test_real_scenarios.py     # 真实场景
│
└── e2e/                           # 端到端测试 (业务流程)
    ├── test_agent_workflows.py    # 核心业务流程
    └── reports/                    # 测试报告输出
```

---

## 测试分类

### 1. Smoke Tests (冒烟测试)

**目的**: 快速验证系统基本功能,在提交代码前快速发现明显问题

**特点**:
- ⚡ 执行速度快 (< 30秒)
- 🎯 只测试关键路径
- ✅ 提交前必须通过

**覆盖范围**:
- 配置加载
- 模型注册表初始化
- 工具系统基础功能
- 技能系统基础功能
- 应用构建
- 项目结构完整性

**运行方式**:
```bash
# 使用统一入口
python tests/run_tests.py smoke

# 或直接使用 pytest
pytest tests/smoke/ -v
```

**何时运行**: 每次提交代码前

---

### 2. Unit Tests (单元测试)

**目的**: 测试单个模块的功能,确保每个组件独立工作正常

**特点**:
- 🔬 测试粒度细
- 🚀 执行速度快
- 🎯 针对具体功能

**覆盖范围**:

#### HITL 模块
- 审批规则匹配
- 四层优先级系统
- 全局风险模式
- 反思性测试(使用 reason 模型)
- 评估指标(Accuracy, Precision, Recall, F1)

#### MCP 模块
- 连接管理
- 服务器启动/关闭
- 工具注册
- 协议通信

#### 工具系统
- 工具扫描和发现
- 工具配置加载
- 工具元数据管理

#### 文档处理模块
- 文档内容提取 (test_document_extractors.py)
  - PDF、DOCX、XLSX、PPTX 格式支持
  - 预览提取（限制长度）
  - 完整文档提取
  - 文档分块（用于索引）
- 文本索引系统 (test_text_indexer.py)
  - MD5 哈希计算和去重
  - 索引创建和存储（两级目录结构）
  - 关键词和 N-gram 提取
  - 多策略搜索和评分
  - 孤儿索引清理
  - 过期索引检测
- 文件查找和搜索工具 (test_find_search_tools.py)
  - find_files: glob 模式匹配
  - read_file: 文本和文档读取
  - search_file: 内容搜索（文本 + 文档）
  - 路径安全验证
  - 错误处理

#### 其他模块
- 基础文件操作 (test_file_ops.py)
- 工作区管理 (test_workspace_manager.py)
- 内容清理

**运行方式**:
```bash
# 使用统一入口
python tests/run_tests.py unit

# 或运行特定模块
pytest tests/unit/test_hitl_approval.py -v
pytest tests/unit/test_mcp/ -v
```

**何时运行**: 修改具体模块后

---

### 3. Integration Tests (集成测试)

**目的**: 测试模块之间的交互,确保组件协同工作

**特点**:
- 🔗 测试模块交互
- ⚙️ 验证集成点
- 🎭 模拟真实场景

**覆盖范围**:

#### @Mention 系统
- @tool 按需加载
- @skill 技能激活
- @agent 子代理委派

#### 注册表系统
- 工具动态加载
- 技能依赖管理
- 模型路由

#### 子代理系统
- 上下文隔离
- 消息传递
- 结果返回

**运行方式**:
```bash
# 使用统一入口
python tests/run_tests.py integration

# 或运行特定测试
pytest tests/integration/test_mention_types.py -v
```

**何时运行**: 修改影响多个模块的功能后

---

### 4. E2E Tests (端到端测试)

**目的**: 测试完整的业务流程,模拟真实用户场景

**特点**:
- 🚀 测试完整流程
- 👤 用户视角
- 🎯 业务价值验证

**覆盖范围**:

#### 核心业务流程
- 基础工具使用 (now, file_ops)
- @Mention 系统工作流
- 多轮对话与上下文保持
- 会话持久化与恢复
- 工作区隔离
- 错误处理与恢复
- 复杂工作流 (调研、数据处理)

#### 真实场景
```
场景 1: 文档读取与搜索
用户: "帮我找到 uploads/ 目录下所有 PDF 文件，然后搜索包含 revenue 的内容"
流程: find_files 查找 → 列出匹配文件 → search_file 搜索内容 → 返回结果

场景 2: 大文档处理
用户: "读取这个 50 页的 PDF 报告"
流程: read_file 检测大文档 → 返回预览 → 提示使用 search_file → 用户搜索关键词

场景 3: PDF 表单填写
用户: "@pdf 帮我填写这个表单"
流程: 检测@提及 → 加载技能 → 读取 PDF → 执行脚本 → 输出文件

场景 4: 代码分析
用户: "分析 main.py 的复杂度"
流程: 读取文件 → 分析代码 → 生成报告 → 返回总结

场景 5: 任务协作
用户: "帮我写技术文档"
流程: ask_human 询问 → 生成大纲 → 征求反馈 → 修改完善
```

**运行方式**:
```bash
# 使用统一入口
python tests/run_tests.py e2e

# 或直接使用 pytest
pytest tests/e2e/ -v -s
```

**何时运行**: 发布前、重大功能修改后

---

## 统一测试入口

### 使用方法

```bash
# 查看帮助
python tests/run_tests.py

# 运行冒烟测试 (最快)
python tests/run_tests.py smoke

# 运行单元测试
python tests/run_tests.py unit

# 运行集成测试
python tests/run_tests.py integration

# 运行 E2E 测试
python tests/run_tests.py e2e

# 运行所有测试
python tests/run_tests.py all

# 运行测试并生成覆盖率报告
python tests/run_tests.py coverage
```

### 输出示例

```
================================================================================
🔥 Running Smoke Tests (Quick Validation)
================================================================================
Purpose: Fast critical-path tests to catch obvious breakage
Expected time: < 30 seconds

tests/smoke/test_smoke.py::TestBasicSetup::test_settings_load PASSED
tests/smoke/test_smoke.py::TestBasicSetup::test_model_registry_initialization PASSED
...
==================== 8 passed in 5.23s ====================
```

---

## 测试执行策略

### 开发阶段

```bash
# 1. 提交前: 运行冒烟测试
python tests/run_tests.py smoke

# 2. 修改模块后: 运行相关单元测试
pytest tests/unit/test_hitl_approval.py -v

# 3. 修改交互逻辑: 运行集成测试
python tests/run_tests.py integration
```

### CI/CD 流程

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Smoke Tests
        run: python tests/run_tests.py smoke

  unit:
    runs-on: ubuntu-latest
    needs: smoke
    steps:
      - uses: actions/checkout@v2
      - name: Unit Tests
        run: python tests/run_tests.py unit

  integration:
    runs-on: ubuntu-latest
    needs: unit
    steps:
      - uses: actions/checkout@v2
      - name: Integration Tests
        run: python tests/run_tests.py integration

  e2e:
    runs-on: ubuntu-latest
    needs: integration
    steps:
      - uses: actions/checkout@v2
      - name: E2E Tests
        run: python tests/run_tests.py e2e
```

### 发布前

```bash
# 运行完整测试套件
python tests/run_tests.py all

# 生成覆盖率报告
python tests/run_tests.py coverage
```

---

## 测试最佳实践

### 1. 测试命名规范

```python
# Good
def test_password_detection_in_url():
    """测试 URL 中的密码检测"""
    pass

def test_skill_loading_with_dependencies():
    """测试带依赖的技能加载"""
    pass

# Bad
def test1():
    pass

def test_stuff():
    pass
```

### 2. 测试组织

```python
class TestPasswordDetection:
    """密码检测相关测试"""

    def test_url_format(self):
        """测试 URL 格式密码"""
        pass

    def test_key_value_format(self):
        """测试 key=value 格式密码"""
        pass
```

### 3. 使用 Fixtures

```python
@pytest.fixture
def test_app():
    """创建测试用的 Agent application"""
    app, initial_state_factory, _, _ = build_application()
    return {"app": app, "initial_state_factory": initial_state_factory}

def test_simple_invoke(test_app):
    """使用 fixture"""
    app = test_app["app"]
    # ... test code
```

### 4. 跳过条件测试

```python
@pytest.mark.skipif(
    not get_settings().models.reason_api_key,
    reason="需要配置 reason 模型 API key"
)
def test_reflective_analysis(self):
    """反思性分析测试"""
    pass
```

---

## 性能基准

### Smoke Tests
- **目标时间**: < 30 seconds
- **测试数量**: ~10 tests
- **通过率**: 100%

### Unit Tests
- **目标时间**: < 2 minutes
- **测试数量**: ~50 tests
- **覆盖率**: >= 80%

### Integration Tests
- **目标时间**: < 5 minutes
- **测试数量**: ~20 tests
- **通过率**: >= 95%

### E2E Tests
- **目标时间**: < 10 minutes
- **测试数量**: ~15 tests
- **通过率**: >= 90%

---

## 故障排查

### 测试失败诊断

#### 1. Import 错误
```bash
# 检查 Python 路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 或在项目根目录运行
python tests/run_tests.py smoke
```

#### 2. API Key 未配置
```bash
# 跳过需要 API 的测试
pytest tests/smoke/ -v -m "not slow"

# 或配置 .env 文件
cp .env.example .env
# 编辑 .env 添加 API keys
```

#### 3. 模块未安装
```bash
# 安装依赖
pip install -e .
# 或
uv sync
```

---

## 相关文档

- [HITL Testing SOP](HITL_TESTING_SOP.md) - HITL 模块测试详细说明
- [E2E Testing SOP](E2E_TESTING_SOP.md) - 端到端测试详细说明
- [REQUIREMENTS_PART6_HITL.md](REQUIREMENTS_PART6_HITL.md) - HITL 系统需求
- [REQUIREMENTS_PART5_MCP.md](REQUIREMENTS_PART5_MCP.md) - MCP 集成需求

---

## 快速参考

### 常用命令

```bash
# 提交前快速验证
python tests/run_tests.py smoke

# 测试特定模块
pytest tests/unit/test_hitl_approval.py -v

# 调试单个测试
pytest tests/unit/test_hitl_approval.py::TestGlobalRiskPatterns::test_critical_password_detection -v -s

# 生成覆盖率报告
python tests/run_tests.py coverage

# 运行完整测试套件
python tests/run_tests.py all
```

### 测试类型选择

| 场景 | 运行命令 | 时间 |
|------|---------|------|
| 提交代码前 | `smoke` | < 30s |
| 修改单个模块 | `unit` | < 2min |
| 修改多模块交互 | `integration` | < 5min |
| 发布前验证 | `all` | < 20min |
| 重大功能发布 | `e2e` + `coverage` | < 15min |

---

**维护**: 每次测试结构变更后更新
**反馈**: 发现问题请提交 Issue
