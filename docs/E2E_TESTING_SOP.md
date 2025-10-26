# GeneralAgent E2E Testing SOP

**版本**: 1.0
**日期**: 2025-10-26
**目的**: 端到端测试整个 Agent 业务流程

---

## 测试架构

### 测试分层

```
tests/
├── unit/                    # 单元测试 (模块级别)
│   ├── test_hitl_unit.py           # HITL 审批规则单元测试
│   ├── test_hitl_reflective.py     # HITL 反思性测试
│   ├── test_hitl_evaluation.py     # HITL 评估测试
│   ├── hitl_evaluation_framework.py
│   ├── test_mcp/                   # MCP 连接和集成测试
│   └── ...
│
└── e2e/                     # 端到端测试 (业务流程级别)
    ├── test_agent_workflows.py     # 核心业务流程测试
    ├── test_real_world_scenarios.py # 真实场景测试
    ├── reports/                    # 测试报告输出
    └── ...
```

### 测试类型对比

| 类型 | 目的 | 范围 | 示例 |
|------|------|------|------|
| **Unit Tests** | 测试单个模块功能 | 单个类/函数 | HITL规则匹配、MCP连接 |
| **E2E Tests** | 测试完整业务流程 | 端到端用户场景 | 用户提问→工具调用→返回结果 |

---

## E2E 测试覆盖范围

### 核心业务流程 (test_agent_workflows.py)

#### 1. 基础工具使用流程
- **场景**: 用户提问 → Agent调用工具 → 返回结果
- **测试用例**:
  - 获取当前时间 (now 工具)
  - 文件操作 (read_file, write_file, list_workspace_files)
  - 计算操作

#### 2. @Mention 系统
- **场景**: 用户 @提及 → 动态加载资源 → 使用资源
- **测试用例**:
  - @skill 加载技能
  - @tool 按需加载工具
  - @agent 子代理委派

#### 3. 多轮对话
- **场景**: 持续对话 → 保持上下文 → 智能响应
- **测试用例**:
  - 上下文记忆
  - 工具链式调用
  - 任务跟踪

#### 4. 会话持久化
- **场景**: 会话保存 → 退出 → 恢复 → 继续对话
- **测试用例**:
  - 会话状态保存
  - 会话恢复
  - 跨会话上下文

#### 5. 工作区隔离
- **场景**: 多会话 → 独立工作区 → 文件隔离
- **测试用例**:
  - 会话工作区独立性
  - 文件访问权限控制
  - 路径安全验证

#### 6. 错误处理
- **场景**: 工具错误 → 优雅降级 → 用户友好提示
- **测试用例**:
  - 工具调用失败恢复
  - 文件不存在处理
  - 循环限制防死锁

#### 7. 复杂工作流
- **场景**: 多步骤任务 → 协调执行 → 完整结果
- **测试用例**:
  - 调研和总结
  - 数据处理管道
  - 文档生成流程

### 真实场景测试 (test_real_world_scenarios.py)

#### 1. 文档处理场景
```python
用户: "@pdf 帮我填写这个表单"
流程:
1. 检测 @pdf 提及
2. 加载 pdf 技能
3. 读取 SKILL.md
4. 使用 read_file 读取上传的 PDF
5. 使用 run_bash_command 执行技能脚本
6. 输出处理后的文件
```

#### 2. 代码分析场景
```python
用户: "分析 main.py 文件的复杂度"
流程:
1. read_file 读取代码
2. 分析代码结构
3. write_file 输出分析报告
4. 返回总结
```

#### 3. 数据调研场景
```python
用户: "查询最新的 Python 版本并总结变化"
流程:
1. @web_search 搜索信息
2. http_fetch 获取详细内容
3. 分析和总结
4. write_file 保存报告
```

#### 4. 任务协作场景
```python
用户: "帮我写一个技术文档,包括代码示例"
流程:
1. ask_human 询问文档需求
2. 生成文档大纲
3. write_file 创建草稿
4. ask_human 征求反馈
5. 修改和完善
6. write_file 保存最终版本
```

---

## 测试执行流程

### 1. 运行所有 E2E 测试

```bash
# 运行所有 E2E 测试
pytest tests/e2e/ -v -s

# 只运行核心业务流程测试
pytest tests/e2e/test_agent_workflows.py -v

# 只运行真实场景测试
pytest tests/e2e/test_real_world_scenarios.py -v
```

### 2. 运行单元测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行 HITL 单元测试
pytest tests/unit/test_hitl_unit.py -v

# 运行 MCP 单元测试
pytest tests/unit/test_mcp/ -v
```

### 3. 完整测试套件

```bash
# 运行所有测试 (单元 + E2E)
pytest tests/ -v --tb=short

# 生成覆盖率报告
pytest tests/ --cov=generalAgent --cov-report=html
```

---

## E2E 测试编写规范

### 测试命名规范

```python
class TestRealWorldScenario:
    """真实场景: <场景名称>"""

    def test_<business_flow>_<expected_outcome>(self):
        """测试 <业务流程描述>

        场景:
        用户: "<用户输入>"

        预期流程:
        1. <步骤1>
        2. <步骤2>
        ...

        预期结果:
        - <结果1>
        - <结果2>
        """
```

### 测试结构模板

```python
def test_document_generation_workflow(self, test_app, temp_workspace):
    """测试文档生成完整流程"""
    # 1. 准备环境
    app = test_app["app"]
    initial_state = test_app["initial_state_factory"]()

    # 2. 设置用户输入
    state = initial_state.copy()
    state["messages"] = [HumanMessage(content="用户请求...")]

    # 3. 运行 Agent
    config = {"configurable": {"thread_id": "test-doc-gen-001"}}
    result = app.invoke(state, config)

    # 4. 验证结果
    ## 验证消息流
    assert len(result["messages"]) > 1

    ## 验证工具调用
    messages_str = str(result["messages"])
    assert "expected_tool" in messages_str

    ## 验证最终输出
    last_message = result["messages"][-1]
    assert isinstance(last_message, AIMessage)
    assert "expected_content" in last_message.content

    ## 验证文件输出
    output_file = temp_workspace / "expected_file.txt"
    assert output_file.exists()
    assert "expected_content" in output_file.read_text()
```

---

## 评估指标

### 业务流程成功率

| 指标 | 描述 | 目标值 |
|------|------|--------|
| **Flow Completion Rate** | 完整流程执行成功率 | >= 90% |
| **Tool Call Accuracy** | 工具调用准确率 | >= 95% |
| **Context Retention** | 上下文保持准确率 | >= 85% |
| **Error Recovery Rate** | 错误恢复成功率 | >= 80% |

### 性能指标

| 指标 | 描述 | 目标值 |
|------|------|--------|
| **Average Response Time** | 平均响应时间 | <= 5s |
| **Tool Execution Time** | 工具执行时间 | <= 2s |
| **Session Load Time** | 会话加载时间 | <= 1s |

---

## 问题排查

### E2E 测试失败诊断

#### 1. 工具调用失败
```
症状: Agent 没有调用预期的工具
诊断步骤:
1. 检查工具是否在 allowed_tools 中
2. 检查 System Prompt 是否正确
3. 查看 Agent 推理日志
4. 验证工具配置 (tools.yaml)
```

#### 2. 上下文丢失
```
症状: Agent 忘记之前的对话内容
诊断步骤:
1. 检查 thread_id 是否一致
2. 验证 checkpoint 是否正常保存
3. 检查消息历史限制配置
4. 查看 Clean 策略是否正确
```

#### 3. 工作区隔离失败
```
症状: 会话间文件互相访问
诊断步骤:
1. 检查 workspace_manager 初始化
2. 验证环境变量 AGENT_WORKSPACE_PATH
3. 检查文件路径解析逻辑
4. 验证符号链接处理
```

---

## 持续集成

### CI/CD 集成

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run E2E tests
        run: pytest tests/e2e/ -v --tb=short
      - name: Generate report
        run: pytest tests/e2e/ --cov=generalAgent --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### 每日自动化测试

```bash
# scripts/daily_e2e_test.sh
#!/bin/bash

# 运行完整 E2E 测试套件
pytest tests/e2e/ -v --tb=short > e2e_results.txt 2>&1

# 生成报告
python tests/e2e/generate_report.py

# 发送通知
if [ $? -eq 0 ]; then
    echo "✅ E2E 测试全部通过" | notify
else
    echo "❌ E2E 测试失败，请检查" | notify
fi
```

---

## 相关文档

- [Unit Testing SOP](HITL_TESTING_SOP.md) - 单元测试规范
- [REQUIREMENTS_PART6_HITL.md](REQUIREMENTS_PART6_HITL.md) - HITL 系统需求
- [REQUIREMENTS_PART5_MCP.md](REQUIREMENTS_PART5_MCP.md) - MCP 集成需求
- [REQUIREMENTS_PART3_MENTIONS.md](REQUIREMENTS_PART3_MENTIONS.md) - @Mention 系统需求

---

**维护**: 每次重大功能更新后更新本文档
**反馈**: 发现问题请提交 Issue
