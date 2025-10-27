# AgentGraph 文档

欢迎来到 AgentGraph 文档！本指南将帮助您理解、使用和扩展 AgentGraph 框架。

## 📚 文档结构

AgentGraph 文档组织为六个核心文档，每个文档专注于特定方面：

### [ARCHITECTURE.md](ARCHITECTURE.md)
**核心系统架构与设计模式**

- Part 1: 核心架构（Agent Loop、状态管理、节点系统、路由）
- Part 2: 工具系统（三层架构、发现机制、配置、TODO 工具）
- Part 3: 技能系统（知识包、注册表、依赖管理）
- Part 4: 最佳实践（路径处理、Prompt 工程、错误处理）

**何时阅读**：理解系统内部机制、实现新功能、架构决策

---

### [FEATURES.md](FEATURES.md)
**面向用户的功能特性**

- Part 1: 工作区隔离（文件操作、安全性、会话管理）
- Part 2: @Mention 系统（工具/技能/Agent 加载）
- Part 3: 文件上传系统（类型检测、处理流程）
- Part 4: 消息历史管理
- Part 5: Delegated agent 系统（任务委派、上下文隔离）
- Part 6: MCP 集成（协议支持、配置方式）
- Part 7: HITL（ask_human、工具审批）

**何时阅读**：使用 AgentGraph 功能、配置系统行为、理解工作流

---

### [DEVELOPMENT.md](DEVELOPMENT.md)
**实用开发指南**

- Part 1: 环境配置（安装、.env 配置）
- Part 2: 开发工具（创建、配置、测试）
- Part 3: 开发技能（结构、脚本、依赖）
- Part 4: 扩展系统（自定义节点、路由、服务）
- Part 5: 开发最佳实践
- Part 6: 调试与故障排查
- Part 7: 贡献指南

**何时阅读**：搭建开发环境、创建工具/技能、贡献代码

---

### [OPTIMIZATION.md](OPTIMIZATION.md)
**性能优化技术**

- Part 1: Context 管理与 KV Cache（70-90% 缓存复用率）
- Part 2: 文档搜索优化（分块策略、BM25、jieba）
- Part 3: 文本索引器（SQLite FTS5、架构设计、性能指标）
- Part 4: 其他优化（消息历史、工具可见性、Delegated agent 隔离）

**何时阅读**：提升性能、理解缓存策略、优化搜索功能

---

### [TESTING.md](TESTING.md)
**全面的测试指南**

- Part 1: 测试概述（四层测试架构）
- Part 2: Smoke 测试（快速验证）
- Part 3: Unit 测试（模块测试、Fixtures）
- Part 4: Integration 测试（@mention、工具、技能）
- Part 5: E2E 测试（业务场景、标准操作流程）
- Part 6: HITL 测试（审批、评估框架）
- Part 7: 测试开发指南
- Part 8: CI/CD 与性能测试

**何时阅读**：编写测试、运行测试套件、CI/CD 配置、质量保证

---

## 🚀 快速开始

### 新用户

1. 阅读项目根目录的 [README.md](../README.md)
2. 按照 [DEVELOPMENT.md - Part 1](DEVELOPMENT.md#part-1-environment-setup) 安装环境
3. 在 [ARCHITECTURE.md - Part 1](ARCHITECTURE.md#part-1-core-architecture) 理解核心概念
4. 在 [FEATURES.md](FEATURES.md) 探索功能特性

### 开发者

1. 搭建环境：[DEVELOPMENT.md - Part 1](DEVELOPMENT.md#part-1-environment-setup)
2. 学习工具开发：[DEVELOPMENT.md - Part 2](DEVELOPMENT.md#part-2-developing-tools)
3. 学习技能开发：[DEVELOPMENT.md - Part 3](DEVELOPMENT.md#part-3-developing-skills)
4. 编写测试：[TESTING.md](TESTING.md)

### 性能调优

1. 理解 KV Cache：[OPTIMIZATION.md - Part 1](OPTIMIZATION.md#part-1-context-management--kv-cache-optimization)
2. 优化搜索：[OPTIMIZATION.md - Part 2-3](OPTIMIZATION.md#part-2-document-search-optimization)
3. 监控指标：[OPTIMIZATION.md - Performance sections](OPTIMIZATION.md)

---

## 📖 文档维护指南

### 何时更新文档

在以下情况需要更新文档：
- 添加新功能或修改现有功能
- 修复影响已记录行为的 bug
- 改进性能或变更优化策略
- 添加新工具、技能或扩展系统
- 修改配置选项或 .env 变量

### 如何更新文档

#### 1. 识别受影响的文档

| 变更类型 | 受影响的文档 |
|---------|-------------|
| 新架构/设计模式 | ARCHITECTURE.md |
| 新功能（工作区、@mention、MCP、HITL） | FEATURES.md |
| 新工具或技能 | DEVELOPMENT.md + ARCHITECTURE.md |
| 性能改进 | OPTIMIZATION.md |
| 新测试或测试方法 | TESTING.md |
| 环境/配置变更 | DEVELOPMENT.md |

#### 2. 更新流程

**步骤 1**：更新相关文档
```bash
# 打开文档
vim docs/ARCHITECTURE.md  # 或 FEATURES.md 等

# 按照现有结构添加/修改内容
# - 保持文件路径和行号准确
# - 包含代码示例
# - 添加设计理由
# - 必要时更新目录
```

**步骤 2**：更新交叉引用
```bash
# 如果添加了新章节，需要更新以下文件的交叉引用：
# - docs/README.md（本文件）
# - 其他文档中的相关章节
# - 主 README.md
# - CLAUDE.md
```

**步骤 3**：更新 CHANGELOG
```bash
# 在 CHANGELOG.md 添加条目
vim ../CHANGELOG.md

# 包含：
# - 日期
# - 类型（Added/Changed/Fixed/Removed）
# - 简要描述
# - 相关文档章节链接
```

**步骤 4**：验证
```bash
# 检查所有链接是否有效
# 验证代码示例是否准确
# 确保文件路径正确
# 测试命令和示例
```

#### 3. 文档结构指南

**格式**：
- 使用清晰的层级标题（## Part X, ### X.Y 章节）
- 在顶部包含目录
- 在代码块中添加文件路径：`# path/to/file.py:line-numbers`
- 使用带语言标签的代码围栏：\`\`\`python, \`\`\`bash, \`\`\`yaml

**内容**：
- **What（是什么）**：描述功能/概念
- **Why（为什么）**：解释设计理由
- **How（怎么做）**：展示代码示例的实现
- **Where（在哪里）**：提供文件路径和行号
- **When（何时用）**：描述使用场景

**示例**：
```markdown
### 2.3 工具配置

**What**：工具通过 `generalAgent/config/tools.yaml` 配置

**Why**：声明式配置允许在不修改代码的情况下启用/禁用工具

**How**：
\`\`\`yaml
# generalAgent/config/tools.yaml
optional:
  my_tool:
    enabled: true
    always_available: false
    category: "utility"
\`\`\`

**Where**：
- 配置文件：`generalAgent/config/tools.yaml`
- 加载器：`generalAgent/config/tool_config_loader.py:45-67`
- 注册表：`generalAgent/tools/registry.py:89-102`

**When**：当需要在启动时控制工具可用性时使用
```

#### 4. 保持文档同步

**代码变更后**：

1. **架构变更** → 更新 ARCHITECTURE.md
   ```bash
   # 示例：修改了状态管理
   vim docs/ARCHITECTURE.md
   # 更新 Part 1: Core Architecture → 1.2 State Management
   ```

2. **新功能** → 更新 FEATURES.md + DEVELOPMENT.md
   ```bash
   # 示例：添加了新的 @mention 类型
   vim docs/FEATURES.md  # Part 2: @Mention System
   vim docs/DEVELOPMENT.md  # 如果需要开发指南
   ```

3. **性能优化** → 更新 OPTIMIZATION.md + CHANGELOG.md
   ```bash
   # 示例：改进了缓存策略
   vim docs/OPTIMIZATION.md  # Part 1: Context Management
   vim CHANGELOG.md  # 添加条目
   ```

4. **新测试方法** → 更新 TESTING.md
   ```bash
   # 示例：添加了新的测试层级
   vim docs/TESTING.md  # 更新 Part 1: Testing Overview
   ```

**定期维护**：
- 每月：检查过时信息
- 每次发布：验证所有示例有效
- 重构后：更新文件路径和行号

---

## 🔍 查找信息

### 按主题查找

| 主题 | 文档 | 章节 |
|-----|------|-----|
| Agent Loop | ARCHITECTURE.md | Part 1.1 |
| 状态管理 | ARCHITECTURE.md | Part 1.2 |
| 工具系统 | ARCHITECTURE.md | Part 2 |
| 技能系统 | ARCHITECTURE.md | Part 3 |
| TODO 工具 | ARCHITECTURE.md | Part 2.7 |
| 工作区 | FEATURES.md | Part 1 |
| @Mentions | FEATURES.md | Part 2 |
| 文件上传 | FEATURES.md | Part 3 |
| MCP | FEATURES.md | Part 6 |
| HITL | FEATURES.md | Part 7 |
| 环境配置 | DEVELOPMENT.md | Part 1 |
| 工具开发 | DEVELOPMENT.md | Part 2 |
| 技能开发 | DEVELOPMENT.md | Part 3 |
| KV Cache | OPTIMIZATION.md | Part 1 |
| 搜索优化 | OPTIMIZATION.md | Part 2-3 |
| 测试 | TESTING.md | All parts |

### 按文件路径查找

使用 grep 查找特定文件的文档：
```bash
# 查找提及特定文件的文档
grep -r "generalAgent/tools/registry.py" docs/*.md

# 查找特定函数的文档
grep -r "build_planner_node" docs/*.md
```

---

## 📊 文档统计

| 文档 | 大小 | 行数 | 最后更新 |
|-----|------|-----|---------|
| ARCHITECTURE.md | ~1500 行 | ~60 KB | 2025-10-27 |
| FEATURES.md | ~1200 行 | ~50 KB | 2025-10-27 |
| DEVELOPMENT.md | ~800 行 | ~35 KB | 2025-10-27 |
| OPTIMIZATION.md | ~1000 行 | ~65 KB | 2025-10-27 |
| TESTING.md | ~600 行 | ~25 KB | 2025-10-27 |
| **总计** | **~5100 行** | **~235 KB** | - |

---

## 🤝 贡献文档

### 文档标准

1. **准确性**：所有代码示例必须经过测试且有效
2. **完整性**：包含文件路径、行号和上下文
3. **清晰性**：为初学者和专家编写
4. **可维护性**：使用一致的格式和结构

### Pull Request 检查清单

- [ ] 更新了相关文档文件
- [ ] 添加了带文件路径的代码示例
- [ ] 如果结构变更，更新了目录
- [ ] 更新了其他文档中的交叉引用
- [ ] 在 CHANGELOG.md 添加了条目
- [ ] 验证了所有链接有效
- [ ] 测试了所有代码示例

### 审核流程

文档变更审核内容：
- 技术准确性
- 信息完整性
- 清晰度和可读性
- 与现有文档的一致性
- 正确的交叉引用

---

## 📅 最近更新

- **2025-10-27**：文档重组（14 个文档 → 6 个核心文档）
- **2025-10-27**：添加 TODO 工具文档（ARCHITECTURE.md Part 2.7）
- **2025-10-27**：添加 SQLite FTS5 文档（OPTIMIZATION.md Part 3）
- **2025-10-27**：整合测试文档（TESTING.md）

完整历史见 [CHANGELOG.md](../CHANGELOG.md)。

---

## 📞 获取帮助

- **问题**：首先使用主题索引查阅相关文档
- **Issues**：在 [GitHub Issues](https://github.com/yourusername/agentgraph/issues) 报告问题
- **讨论**：使用 GitHub Discussions 进行问答
- **文档 bug**：提交 PR 或创建带 "docs" 标签的 issue

---

**最后更新**：2025-10-27
**文档版本**：2.0（重组版）

---

## 🌏 语言版本

- [English](en/README.md) - 英文版本
- [中文](README.md) - 当前文档
