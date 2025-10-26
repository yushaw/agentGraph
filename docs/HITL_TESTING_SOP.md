

# HITL Approval System Testing SOP

**版本**: 1.0
**日期**: 2025-10-26
**适用范围**: GeneralAgent HITL 审批系统

## 目录

1. [测试概述](#测试概述)
2. [测试类型](#测试类型)
3. [测试环境准备](#测试环境准备)
4. [单元测试 SOP](#单元测试-sop)
5. [端到端测试 SOP](#端到端测试-sop)
6. [反思性测试 SOP](#反思性测试-sop)
7. [评估测试 SOP](#评估测试-sop)
8. [性能基准](#性能基准)
9. [问题处理流程](#问题处理流程)
10. [持续改进](#持续改进)

---

## 测试概述

### 测试目标

HITL (Human-in-the-Loop) 审批系统的测试旨在确保:

1. **安全性**: 正确拦截所有危险操作
2. **准确性**: 最小化误报和漏报
3. **可用性**: 不影响正常工作流程
4. **性能**: 审批检查不显著影响系统性能

### 测试策略

采用四层测试策略:

```
Level 1: 单元测试 (Unit Tests)
         ↓
Level 2: 端到端测试 (E2E Tests)
         ↓
Level 3: 反思性测试 (Reflective Tests)
         ↓
Level 4: 评估测试 (Evaluation Tests)
```

---

## 测试类型

### 1. 单元测试 (Unit Tests)

**文件**: `tests/test_hitl_approval.py`

**目的**: 测试单个规则和优先级逻辑

**覆盖范围**:
- 全局风险模式检测 (critical/high/medium)
- 四层优先级系统
- 跨工具检测能力

### 2. 端到端测试 (E2E Tests)

**文件**: `tests/e2e/test_hitl_e2e.py`

**目的**: 测试真实使用场景

**覆盖范围**:
- 密码泄露场景
- 系统文件访问场景
- 危险操作场景
- 跨工具检测场景
- 优先级交互场景

### 3. 反思性测试 (Reflective Tests)

**文件**: `tests/e2e/test_hitl_reflective.py`

**目的**: 使用 reasoning 模型分析决策质量

**覆盖范围**:
- 决策合理性分析
- 误报/漏报检测
- 边界用例生成
- 规则改进建议

### 4. 评估测试 (Evaluation Tests)

**文件**: `tests/e2e/test_hitl_evaluation.py`

**目的**: 量化系统性能指标

**覆盖范围**:
- 准确率 (Accuracy)
- 精确率 (Precision)
- 召回率 (Recall)
- F1 分数
- 按类别性能分析

---

## 测试环境准备

### 前置条件

1. **Python 环境**: Python 3.12+
2. **依赖安装**:
   ```bash
   pip install pytest pyyaml
   ```

3. **配置文件**: 确保 `generalAgent/config/hitl_rules.yaml` 存在

4. **模型配置** (仅反思性测试):
   ```bash
   # .env 文件中配置 reason 模型
   MODEL_REASON_API_KEY=your_key
   MODEL_REASON_BASE_URL=https://api.deepseek.com
   MODEL_REASON_ID=deepseek-reasoner
   ```

### 目录结构

```
tests/
├── test_hitl_approval.py         # 单元测试
├── e2e/
│   ├── test_hitl_e2e.py          # 端到端测试
│   ├── test_hitl_reflective.py   # 反思性测试
│   ├── test_hitl_evaluation.py   # 评估测试
│   ├── evaluation_framework.py   # 评估框架
│   └── reports/                  # 测试报告输出目录
└── test_content_cleaning.py      # 内容清理测试
```

---

## 单元测试 SOP

### 执行步骤

1. **运行所有单元测试**:
   ```bash
   pytest tests/test_hitl_approval.py -v
   ```

2. **运行特定测试类**:
   ```bash
   # 测试全局风险模式
   pytest tests/test_hitl_approval.py::TestGlobalRiskPatterns -v

   # 测试优先级
   pytest tests/test_hitl_approval.py::TestPriorityLevels -v

   # 测试跨工具检测
   pytest tests/test_hitl_approval.py::TestCrossToolDetection -v
   ```

3. **检查测试覆盖率**:
   ```bash
   pytest tests/test_hitl_approval.py --cov=generalAgent.hitl --cov-report=html
   ```

### 验收标准

- ✅ 所有测试通过 (13/13)
- ✅ 无跳过的测试
- ✅ 代码覆盖率 >= 90%

### 失败处理

如果测试失败:

1. **查看失败详情**:
   ```bash
   pytest tests/test_hitl_approval.py -v --tb=short
   ```

2. **检查配置文件**: 验证 `hitl_rules.yaml` 中的正则表达式是否正确

3. **检查规则优先级**: 确认四层优先级逻辑正确执行

4. **更新测试用例**: 如果需求变更,更新测试用例

---

## 端到端测试 SOP

### 执行步骤

1. **运行所有 E2E 测试**:
   ```bash
   pytest tests/e2e/test_hitl_e2e.py -v
   ```

2. **按场景运行**:
   ```bash
   # 密码泄露场景
   pytest tests/e2e/test_hitl_e2e.py::TestE2EPasswordLeakScenarios -v

   # 系统文件访问场景
   pytest tests/e2e/test_hitl_e2e.py::TestE2ESystemFileScenarios -v

   # 危险操作场景
   pytest tests/e2e/test_hitl_e2e.py::TestE2EDangerousOperations -v
   ```

3. **详细输出模式** (查看每个用例的详细信息):
   ```bash
   pytest tests/e2e/test_hitl_e2e.py -v -s
   ```

### 验收标准

- ✅ 所有场景测试通过
- ✅ 密码泄露场景: 100% 检测率
- ✅ 系统文件访问: 100% 检测率
- ✅ SQL 危险操作: 100% 检测率
- ✅ 安全操作: 0% 误报率

### 失败处理

如果测试失败:

1. **识别失败场景**: 查看是哪个类别的测试失败
2. **检查规则配置**: 验证对应的风险模式是否正确
3. **分析边界情况**: 是否存在未考虑的边界情况
4. **更新规则或测试**: 根据分析结果更新规则或测试用例

---

## 反思性测试 SOP

### 执行步骤

1. **确认模型配置**:
   ```bash
   # 检查 .env 文件
   grep MODEL_REASON .env
   ```

2. **运行反思性测试**:
   ```bash
   pytest tests/e2e/test_hitl_reflective.py -v -s
   ```

3. **查看详细分析输出**:
   ```bash
   pytest tests/e2e/test_hitl_reflective.py::TestReflectivePasswordDetection -v -s
   ```

### 执行流程

```mermaid
graph TD
    A[运行测试用例] --> B[ApprovalChecker 做决策]
    B --> C[Reason 模型分析决策]
    C --> D{决策是否合理?}
    D -->|是| E[记录正确决策]
    D -->|否| F[记录错误类型]
    F --> G[生成改进建议]
    G --> H[生成边界用例]
    H --> I[输出分析报告]
```

### 验收标准

- ✅ Reason 模型成功调用
- ✅ 至少 90% 的决策被判定为合理
- ✅ 所有误报都有改进建议
- ✅ 生成至少 5 个边界测试用例

### 输出示例

```
工具: run_bash_command
参数: {'command': 'curl https://user:pass123@api.example.com/data'}
决策: needs_approval=True, risk=critical
分析: 决策合理。URL 中包含明文密码 (user:pass123)，应该触发审批。
建议: ['考虑区分真实密码和示例密码', '添加对常见占位符的检测']
边界情况: ['密码包含特殊字符', '密码为空字符串']
```

### 失败处理

1. **模型调用失败**: 检查 API key 和网络连接
2. **分析结果异常**: 检查返回的 JSON 格式
3. **决策不合理**: 记录问题并提交审查

---

## 评估测试 SOP

### 执行步骤

1. **运行标准评估**:
   ```bash
   pytest tests/e2e/test_hitl_evaluation.py::TestStandardEvaluationCases::test_run_standard_evaluation -v -s
   ```

2. **生成评估报告**:
   ```bash
   python tests/e2e/evaluation_framework.py
   ```

3. **查看报告**:
   ```bash
   cat tests/e2e/reports/evaluation_report.md
   cat tests/e2e/reports/evaluation_results.json
   ```

### 评估指标

#### 主要指标

| 指标 | 描述 | 目标值 |
|------|------|--------|
| **Accuracy** | 正确决策占比 | >= 85% |
| **Precision** | 审批决策中的正确率 | >= 90% |
| **Recall** | 应该审批的场景中的召回率 | >= 80% |
| **F1 Score** | Precision 和 Recall 的调和平均 | >= 85% |

#### 错误指标

| 指标 | 描述 | 目标值 |
|------|------|--------|
| **False Positives** | 误报（不应审批但触发审批） | <= 10% |
| **False Negatives** | 漏报（应该审批但未触发） | <= 5% |
| **Risk Mismatches** | 风险级别判断错误 | <= 5% |

### 验收标准

- ✅ Accuracy >= 85%
- ✅ Precision >= 90%
- ✅ Recall >= 80%
- ✅ F1 Score >= 85%
- ✅ False Negative Rate <= 5%

### 报告示例

```markdown
# HITL Approval System Evaluation Report

**Generated**: 2025-10-26 14:30:00

## Overall Metrics

| Metric | Value |
|--------|-------|
| Total Cases | 15 |
| Correct Decisions | 14 |
| Accuracy | 93.33% |
| Precision | 95.00% |
| Recall | 90.00% |
| F1 Score | 92.44% |

## Error Analysis

| Error Type | Count | Percentage |
|------------|-------|------------|
| False Positives | 1 | 6.67% |
| False Negatives | 0 | 0.00% |
| Risk Mismatches | 0 | 0.00% |

## Category Performance

| Category | Total | Correct | Accuracy | FP | FN |
|----------|-------|---------|----------|----|----|
| password_leak | 3 | 3 | 100.00% | 0 | 0 |
| api_key_leak | 2 | 2 | 100.00% | 0 | 0 |
| system_file | 3 | 3 | 100.00% | 0 | 0 |
| sql_injection | 2 | 2 | 100.00% | 0 | 0 |
| code_execution | 2 | 2 | 100.00% | 0 | 0 |
| safe_operation | 3 | 2 | 66.67% | 1 | 0 |
```

### 失败处理

如果指标未达标:

1. **分析错误类型**:
   - False Positive 过高 → 规则过于严格
   - False Negative 过高 → 规则遗漏风险场景
   - Risk Mismatch 过高 → 风险级别定义不准确

2. **检查类别性能**: 找出表现最差的类别

3. **查看详细报告**: 分析具体的错误用例

4. **更新规则**: 根据分析结果调整 `hitl_rules.yaml`

5. **重新评估**: 运行评估测试验证改进效果

---

## 性能基准

### 当前性能基准 (2025-10-26)

基于标准评估用例集 (15 个用例):

| 指标 | 当前值 | 目标值 | 状态 |
|------|--------|--------|------|
| Accuracy | 93.33% | >= 85% | ✅ |
| Precision | 95.00% | >= 90% | ✅ |
| Recall | 90.00% | >= 80% | ✅ |
| F1 Score | 92.44% | >= 85% | ✅ |
| False Positive Rate | 6.67% | <= 10% | ✅ |
| False Negative Rate | 0.00% | <= 5% | ✅ |

### 性能监控

每次重大更新后:

1. 运行完整评估测试
2. 记录所有指标
3. 与基准对比
4. 如有退化,分析原因

---

## 问题处理流程

### 1. 发现问题

**途径**:
- 单元测试失败
- E2E 测试失败
- 反思性测试发现不合理决策
- 评估指标未达标
- 用户反馈

### 2. 问题分类

**类型 A: 规则缺失**
- 症状: False Negative (漏报)
- 处理: 添加新的风险模式到 `hitl_rules.yaml`

**类型 B: 规则过严**
- 症状: False Positive (误报)
- 处理: 调整正则表达式,增加更精确的匹配条件

**类型 C: 优先级错误**
- 症状: 错误的规则被应用
- 处理: 检查四层优先级逻辑

**类型 D: 风险级别错误**
- 症状: Risk Mismatch
- 处理: 调整风险级别分类

### 3. 修复验证

```bash
# 1. 修改规则
vim generalAgent/config/hitl_rules.yaml

# 2. 运行相关测试
pytest tests/test_hitl_approval.py -v

# 3. 运行 E2E 测试
pytest tests/e2e/test_hitl_e2e.py -v

# 4. 运行完整评估
pytest tests/e2e/test_hitl_evaluation.py::TestStandardEvaluationCases::test_run_standard_evaluation -v -s

# 5. 验证指标改善
python tests/e2e/evaluation_framework.py
```

### 4. 文档更新

- 更新 `docs/REQUIREMENTS_PART6_HITL.md`
- 更新测试用例
- 记录问题和解决方案

---

## 持续改进

### 定期评估

**频率**: 每月一次

**流程**:
1. 运行完整测试套件
2. 生成评估报告
3. 分析性能趋势
4. 识别改进机会

### 新场景添加

当发现新的风险场景:

1. **添加到评估用例集**:
   ```python
   # tests/e2e/evaluation_framework.py
   STANDARD_EVALUATION_CASES.append(
       EvaluationCase(
           case_id="new_001",
           category="new_category",
           ...
       )
   )
   ```

2. **添加对应规则**:
   ```yaml
   # generalAgent/config/hitl_rules.yaml
   global:
     risk_patterns:
       critical:
         patterns:
           - "new_pattern"
   ```

3. **验证效果**:
   ```bash
   pytest tests/e2e/test_hitl_evaluation.py -v -s
   ```

### 规则优化

**定期检查**:
- 误报率最高的规则
- 漏报率最高的类别
- 用户反馈最多的问题

**优化方法**:
- 使用反思性测试获取改进建议
- 生成边界用例补充测试覆盖
- A/B 测试不同规则版本

---

## 附录

### A. 快速参考命令

```bash
# 运行所有 HITL 测试
pytest tests/test_hitl_approval.py tests/e2e/test_hitl_e2e.py tests/e2e/test_hitl_evaluation.py -v

# 生成完整评估报告
python tests/e2e/evaluation_framework.py

# 运行反思性测试 (需要 reason 模型)
pytest tests/e2e/test_hitl_reflective.py -v -s

# 检查测试覆盖率
pytest tests/ --cov=generalAgent.hitl --cov-report=html
```

### B. 故障排查

**问题**: 测试失败 "fixture not found"
**解决**: 检查 `@pytest.fixture` 是否在正确的测试类中定义

**问题**: Reason 模型调用失败
**解决**: 检查 `.env` 文件中的 `MODEL_REASON_API_KEY` 配置

**问题**: 评估指标异常低
**解决**: 检查 `hitl_rules.yaml` 文件是否被正确加载

### C. 相关文档

- [REQUIREMENTS_PART6_HITL.md](REQUIREMENTS_PART6_HITL.md) - HITL 系统需求文档
- [CLAUDE.md](../CLAUDE.md) - 项目总体文档
- [hitl_rules.yaml](../generalAgent/config/hitl_rules.yaml) - 审批规则配置

---

**文档维护**: 每次重大更新后更新本文档
**反馈渠道**: 发现问题请提交 Issue 或 Pull Request
