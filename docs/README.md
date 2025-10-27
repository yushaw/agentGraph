# GeneralAgent 详细需求文档

本目录包含 GeneralAgent 项目的详细需求文档，包括架构设计、实现细节和最佳实践。

## 文档结构

### Part 1: 核心架构与工具系统
**文件**: `REQUIREMENTS_PART1_ARCHITECTURE.md`

包含内容：
- **核心架构需求**
  - Agent Loop 架构
  - 状态管理
  - 节点系统
  - 路由系统
- **工具系统需求**
  - 三层工具加载架构（discovered/registered/visible）
  - 工具扫描与发现
  - 工具配置系统
  - 工具元数据系统
  - 持久化工具
  - 工具可见性构建
- **技能系统需求**
  - 技能定义（Knowledge Package）
  - 技能注册系统
  - 技能依赖管理
  - 技能目录生成
  - 技能脚本执行

### Part 2: 工作区隔离与会话管理
**文件**: `REQUIREMENTS_PART2_WORKSPACE.md`

包含内容：
- **工作区隔离需求**
  - 工作区目录结构
  - 路径隔离与安全
  - 技能符号链接
  - 文件上传处理
  - 工作区清理
- **会话管理需求**
  - 会话持久化（SQLite）
  - 会话生命周期
  - 会话自动保存
- **模型路由需求**
  - 多模型插槽系统
  - 模型注册表
  - 动态模型解析

### Part 3: @提及系统与消息管理
**文件**: `REQUIREMENTS_PART3_MENTIONS.md`

包含内容：
- **@提及系统需求**
  - 三类提及分类（tool/skill/agent）
  - 提及解析
  - 工具按需加载
  - 技能加载
  - 代理委派
  - 动态系统提醒
- **消息历史管理需求**
  - 消息历史限制
  - 消息清理策略（Clean vs Truncate）
  - 消息角色定义
  - System Prompt 管理
- **子代理委派需求**
  - 子代理架构
  - call_subagent 工具
  - 上下文隔离
  - 子代理系统提示
  - 子代理使用场景
- **文件上传需求**
  - 文件类型检测
  - 文件上传流程
  - 文件引用注入
  - 自动技能推荐
  - 多文件上传支持

### Part 4: 实现技巧与设计模式
**文件**: `REQUIREMENTS_PART4_TRICKS.md`

包含 50+ 实现技巧，分为 10 个类别：

- **分类 A: 路径处理技巧**（4 个）
  - A1. 工作区相对路径 vs 绝对路径
  - A2. 两步路径验证（防止路径遍历）
  - A3. 符号链接路径处理（不 resolve）
  - A4. 项目根目录自动识别

- **分类 B: 工具系统技巧**（5 个）
  - B1. 三层工具架构（discovered/registered/visible）
  - B2. 多工具文件支持（__all__ 导出）
  - B3. 工具元数据与配置分离
  - B4. 动态工具可见性构建
  - B5. 环境变量传递工作区路径

- **分类 C: Prompt 工程技巧**（4 个）
  - C1. 动态系统提醒（Context-Aware）
  - C2. 技能目录动态生成
  - C3. 主 Agent vs 子 Agent 提示差异
  - C4. 当前时间注入

- **分类 D: 配置管理技巧**（3 个）
  - D1. Pydantic Settings 加载 .env
  - D2. 模型别名支持（Provider-Specific）
  - D3. YAML 配置热加载

- **分类 E: 消息管理技巧**（3 个）
  - E1. Clean 策略（保留完整轮次）
  - E2. 消息角色管理
  - E3. 消息历史限制配置

- **分类 F: 会话持久化技巧**（3 个）
  - F1. LangGraph Checkpointer 集成
  - F2. 会话元数据管理
  - F3. 会话 ID 生成策略

- **分类 G: 技能系统技巧**（3 个）
  - G1. Skills as Knowledge Packages（非工具容器）
  - G2. 技能脚本依赖自动安装
  - G3. 技能脚本接口规范

- **分类 H: 环境变量技巧**（2 个）
  - H1. 环境变量作为上下文传递
  - H2. 子进程环境变量继承

- **分类 I: 日志与调试技巧**（3 个）
  - I1. 结构化日志记录
  - I2. Prompt 截断日志
  - I3. 工具调用日志

- **分类 J: 错误处理技巧**（3 个）
  - J1. 工具错误边界装饰器
  - J2. 优雅降级（Graceful Degradation）
  - J3. 循环限制与死锁检测

### Part 5: MCP (Model Context Protocol) 集成
**文件**: `REQUIREMENTS_PART5_MCP.md`

包含内容：
- **核心架构**
  - MCP 分层架构（Connection → Manager → Wrapper）
  - 延迟启动机制
  - 双协议支持（stdio/SSE）
- **配置系统**
  - mcp_servers.yaml 配置详解
  - 环境变量替换
  - 工具命名策略（alias/prefix）
- **实现细节**
  - 启动流程
  - 工具注册流程
  - 优雅关闭机制
- **使用指南**
  - 快速开始
  - 添加官方 MCP 服务器
  - 高级配置
- **测试与验证**
  - 测试基础设施
  - 运行测试
  - 验证清单

### Part 6: HITL (Human-in-the-Loop) 机制
**文件**: `REQUIREMENTS_PART6_HITL.md`

包含内容：
- **两种 HITL 模式**
  - ask_human 工具（Agent 主动交互）
  - Tool Approval Framework（系统级安全）
- **核心架构**
  - LangGraph interrupt() 机制
  - ApprovalToolNode 包装器
  - 三层审批规则系统
- **实现细节**
  - ask_human 工具实现
  - ApprovalChecker 规则系统
  - Graph 集成方式
  - 极简版 UI 提示
- **使用指南**
  - ask_human 使用示例
  - Tool Approval 配置示例
  - 自定义检查器
- **配置与扩展**
  - hitl_rules.yaml 配置
  - 扩展 ask_human（choice/multi_choice）
  - 审批日志

## 文档特点

每个需求都包含：
- **详细说明**：需求的背景和目标
- **技术实现**：完整的代码示例和文件位置
- **设计考量**：实现背后的设计思考和权衡

每个实现技巧都包含：
- ❓ **问题描述**：解决的具体问题
- 📍 **实现位置**：代码文件和行号
- 💻 **代码示例**：完整的实现代码
- 💡 **设计考量**：设计背后的思考和最佳实践

## 如何使用

1. **了解架构**：从 Part 1 开始，理解核心架构和工具/技能系统
2. **深入细节**：阅读 Part 2-3，了解工作区、会话、消息管理等实现
3. **学习技巧**：查阅 Part 4，学习 50+ 实现技巧和设计模式
4. **代码映射**：每个需求都标注了文件位置，方便查找对应代码

## 其他文档

### 文档读取与搜索功能
AgentGraph 支持读取和搜索多种文档格式（PDF、DOCX、XLSX、PPTX）。

**核心功能**：
- **find_files**: 快速文件名模式匹配（glob支持）
- **read_file**: 自动格式检测的文件读取（支持文档预览）
- **search_file**: 智能内容搜索（文本实时扫描 + 文档索引搜索）

**实现细节**：
- `generalAgent/utils/document_extractors.py` - 文档内容提取（PDF/DOCX/XLSX/PPTX）
- `generalAgent/utils/text_indexer.py` - MD5-based 全局索引系统
- `generalAgent/tools/builtin/find_files.py` - 文件查找工具
- `generalAgent/tools/builtin/search_file.py` - 内容搜索工具
- `generalAgent/config/settings.py` - DocumentSettings 配置

**索引策略**：
- 全局两级目录结构（`data/indexes/{hash[:2]}/{hash}.index.json`）
- MD5 去重，避免重复索引
- 自动孤儿索引清理（同名文件覆盖时）
- 24小时过期检测

详见: `../CLAUDE.md` - File Operation Tools 章节

### 技能配置管理
**文件**: `SKILLS_CONFIGURATION.md`

说明技能系统的配置方式，包括：
- skills.yaml 配置详解
- 技能启用/禁用策略
- 文件类型自动加载
- 技能目录过滤

### 测试指南
**文件**: `TESTING_GUIDE.md`

包含测试框架使用指南：
- 四层测试架构（smoke/unit/integration/e2e）
- 测试运行方式
- 测试编写规范

**相关文档**:
- `E2E_TESTING_SOP.md` - E2E 测试标准操作流程
- `HITL_TESTING_SOP.md` - HITL 功能测试流程

### 上下文管理优化
**文件**: `CONTEXT_MANAGEMENT.md`

详细说明 KV Cache 优化策略：
- 固定 SystemMessage 设计
- 分钟级时间戳
- 动态 Reminder 移至最后消息
- 70-90% KV Cache 复用率

## 文档维护

- **版本**: 2025-10-27
- **生成方式**: 基于实际代码和设计文档生成
- **更新频率**: 重大架构变更时更新
- **最近更新**:
  - 2025-10-27: 新增文档读取与搜索功能说明
  - 2025-10-26: 新增 Part 5 (MCP 集成) 和 Part 6 (HITL 机制)
  - 2025-01-24: 初始版本 (Part 1-4)

## 相关文档

- 项目 README: `../README.md`
- 重构笔记: `../REFACTORING_NOTES.md`
- 配置模板: `../.env.example`
- 工具配置: `../generalAgent/config/tools.yaml`
