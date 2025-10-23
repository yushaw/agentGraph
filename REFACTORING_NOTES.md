# Tools & Skills 重构说明 🔧

本次重构完成了 Tools 和 Skills 系统的全面优化。

---

## 一、主要变更

### 1. 按需加载（On-Demand Loading）

**问题**：用户 @mention 未启用的工具时无法使用

**解决**：三层工具池架构
- `_discovered` - 所有扫描到的工具（包括 disabled）
- `_tools` - enabled 的工具（立即可用）
- `load_on_demand()` - 按需从 discovered 加载

**代码变更**：
- `agentgraph/tools/registry.py` - 新增 `_discovered` 池和 `load_on_demand()`
- `agentgraph/runtime/app.py` - 保留所有 discovered tools
- `agentgraph/graph/nodes/planner.py` - 使用按需加载

**效果**：
```python
# 工具 enabled: false，但可以按需加载
用户> @extract_links 提取所有链接
系统> 从 _discovered 池加载 ✅
```

### 2. 扩展 @Mention 机制

**新增功能**：支持三种类型

| 类型 | 示例 | 行为 | Reminder |
|------|------|------|----------|
| `@tool` | `@calc` | 加载工具 | "请优先使用这些工具" |
| `@skill` | `@pdf` | 不加载工具 | "请读取 SKILL.md" |
| `@agent` | `@agent` | 加载 call_subagent | "可以委派任务" |

**代码变更**：
- 新增 `agentgraph/utils/mention_classifier.py` - 分类器
- 修改 `agentgraph/graph/nodes/planner.py` - 使用分类器
- 修改 `agentgraph/graph/prompts.py` - 分类型生成 reminder

**效果**：
```
用户> @calc @pdf @agent 计算并生成报告
系统>
  ✅ 加载 calc 工具
  ✅ 加载 call_subagent 工具
  ✅ 生成三个专门的 <system_reminder>
```

### 3. 配置驱动 Metadata

**问题**：Metadata 在 `tools.yaml` 和 `app.py` 重复定义

**解决**：tools.yaml 作为单一数据源

**Before**:
```python
# app.py 硬编码
metadata = [
    ToolMeta("calc", "compute", ["compute"]),
    ...
]
```

**After**:
```yaml
# tools.yaml
core:
  calc:
    category: "compute"
    tags: ["compute", "math"]
    description: "Safe arithmetic calculator"
```

**代码变更**：
- 扩展 `agentgraph/config/tools.yaml` - 完整 metadata
- 新增 `agentgraph/tools/config_loader.py:get_all_tool_metadata()`
- 修改 `agentgraph/runtime/app.py` - 从配置读取

### 4. Skills 架构修正

**错误理解**：Skills = 工具容器（包含 allowed_tools）
**正确理解**：Skills = 文档+脚本知识包

**代码变更**：
- 修改 `agentgraph/skills/schema.py` - 移除 `allowed_tools`
- 新增 `agentgraph/skills/md_loader.py` - 简化加载
- 修改 `agentgraph/graph/prompts.py` - 更新说明
- 删除自动激活逻辑

**效果**：
- Model 通过 Read 工具读取 SKILL.md
- 根据文档指导执行操作
- 不自动加载任何工具

---

## 二、@Mention 完整流程

### 用户输入
```
@calc @pdf @agent 计算收入并生成PDF报告
```

### 1. 解析（main.py）
```python
mentions, cleaned_input = parse_mentions(user_input)
# mentions = ["calc", "pdf", "agent"]
# cleaned_input = "计算收入并生成PDF报告"
state["mentioned_agents"] = mentions
```

### 2. 分类（planner.py）
```python
classifications = classify_mentions(mentions, tool_registry, skill_registry)
grouped = {
    "tools": ["calc"],      # 工具
    "skills": ["pdf"],      # 技能
    "agents": ["agent"],    # 代理
}
```

### 3. 加载工具
```python
# @tool → 加载到 visible_tools
tool = tool_registry.load_on_demand("calc")
visible_tools.append(tool)

# @agent → 加载 call_subagent
subagent_tool = tool_registry.get_tool("call_subagent")
visible_tools.append(subagent_tool)

# @skill → 不加载工具
```

### 4. 生成 Reminder
```xml
<system_reminder>用户提到了工具：calc。请优先使用这些工具完成任务。</system_reminder>

<system_reminder>用户提到了技能：pdf。请先使用 Read 工具读取 skills/pdf/SKILL.md。</system_reminder>

<system_reminder>用户提到了代理：agent。你可以使用 call_subagent 工具委派任务。</system_reminder>
```

---

## 三、文件变更清单

### 新增文件
```
agentgraph/tools/builtin/          - 工具目录（扫描）
agentgraph/tools/config_loader.py  - 配置加载器
agentgraph/tools/scanner.py        - 工具扫描器
agentgraph/tools/subagent.py       - 子代理工具
agentgraph/tools/todo.py           - TODO 工具
agentgraph/utils/mention_classifier.py - @mention 分类器
agentgraph/skills/md_loader.py     - Skill 加载器
agentgraph/config/tools.yaml       - 工具配置
skills/pdf/SKILL.md                - PDF 技能示例
```

### 修改文件
```
agentgraph/runtime/app.py          - 按需加载支持
agentgraph/graph/nodes/planner.py  - @mention 分类处理
agentgraph/graph/prompts.py        - 分类型 reminder
agentgraph/tools/registry.py       - load_on_demand()
agentgraph/skills/schema.py        - 移除 allowed_tools
```

### 删除文件
```
agentgraph/graph/skill_detection.py - 自动激活逻辑（错误）
skills/weather/                     - 基于错误理解
skills/pptx/                        - 基于错误理解
```

---

## 四、测试

### 单元测试
- `test_registry_on_demand.py` - 按需加载 ✅
- `test_mention_types.py` - @mention 分类 ✅

### 验证
```bash
✅ Application startup
✅ 8 tools enabled
✅ 1 skill (pdf) loaded
✅ On-demand loading works
✅ @mention classification works
```

---

## 五、配置示例

### tools.yaml 格式
```yaml
core:
  calc:
    category: "compute"
    tags: ["compute", "math"]
    description: "Safe arithmetic calculator"

optional:
  extract_links:
    enabled: false            # 启动时不加载
    always_available: false
    category: "read"
    tags: ["read", "parse"]
    # 但用户 @extract_links 时会按需加载
```

### 工具行为
| Tool | enabled | 启动加载 | @mention 行为 |
|------|---------|----------|--------------|
| calc (core) | true | ✅ | 直接使用 |
| http_fetch | true | ✅ | 直接使用 |
| extract_links | false | ❌ | 按需加载 ✅ |

---

## 六、向后兼容

### tools.yaml
- ✅ 支持旧格式：`core: [now, calc]`
- ✅ 支持新格式：`core: {now: {category: "meta"}}`

### 代码接口
- ✅ `tool_registry.get_tool()` - 不变
- ✅ `skill_registry.get()` - 不变
- ✅ `build_dynamic_reminder()` - 新增参数，兼容旧参数

---

## 七、性能改进

- ✅ 启动时只加载 enabled 工具
- ✅ Skill frontmatter 延迟加载
- ✅ 未 enabled 工具不占内存（直到 @mention）
- ✅ @mention 分类缓存结果

---

## 八、总结

本次重构实现了：

1. **按需加载** - 动态加载任何已发现的工具
2. **智能分类** - @tool、@skill、@agent 三种类型
3. **配置驱动** - tools.yaml 单一数据源
4. **正确架构** - Skills = 文档+脚本，不是工具容器

系统现在能够：
- ✅ 用户 @mention 任何工具/技能/代理
- ✅ 启动快速，按需加载
- ✅ 配置简单，易于维护
- ✅ Skills 语义正确

所有测试通过，可以提交！🎉
