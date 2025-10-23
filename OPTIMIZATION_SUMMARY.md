# AgentGraph Optimization Summary

## ✅ 已完成的优化 (Just Completed)

### 1. 清理无用代码
- ✅ 删除 `guard.py` 和 `verify.py` 节点文件
- ✅ 更新 `nodes/__init__.py` 移除相关 imports
- ✅ `builder.py` 已经不使用这些节点（之前就完成了）

### 2. Token 使用优化
- ✅ **Planner**: 20 轮 → 10 轮 (`keep_recent=10`)
- ✅ **Step Executor**: 6 轮 → 3 轮 (`keep_recent=3`)
- ✅ **Finalize**: 20 轮 → 10 轮 (`keep_recent=10`)

所有改动都使用 `truncate_messages_safely()` 确保消息对完整性。

### 3. Charlie 品牌身份（之前已完成）
`prompts.py` 已经有完整的 Charlie 身份定义：
- 身份说明："一个高效、友好的 AI 助手"
- 回复风格：简洁直接、专业但不生硬
- 工作方式：简单任务直接完成，复杂任务先规划再执行

### 4. @Mention 机制（之前已完成）
- ✅ 解析 `@weather` / `@get_weather` / `@pptx` 等
- ✅ 自动加载对应的 skills/tools
- ✅ 作为常驻工具在整个对话中可用
- ✅ Agent/Skill/Tool 对用户透明

### 5. 日志系统（之前已完成）
- ✅ 所有 node 的入口/出口日志
- ✅ State 快照记录
- ✅ 工具可见性跟踪
- ✅ Routing 决策记录
- ✅ Prompt 完整记录

---

## ⚠️ 还需要实现的功能

### 1. 流式输出 (Streaming) - 优先级 P0

**当前状态：**
- 使用 `app.invoke()` 阻塞式调用
- 用户体验：等待 5-10 秒 → 一次性返回完整答案

**需要实现：**
```python
# 改为 async 流式调用
async for chunk in app.astream(state, config=config):
    # 实时输出每个 chunk
    print(chunk)
```

**涉及的文件：**
- `main.py` - 改为 async main
- `agentgraph/agents/factory.py` - invoke_planner/invoke_subagent 改为 ainvoke
- 前端对接：SSE (Server-Sent Events) 或 WebSocket

**预计工作量：** 3-4 小时

**关键点：**
- LangGraph 支持 `.astream()` 和 `.astream_events()`
- 需要将所有 `invoke()` 改为 `ainvoke()`
- Node 函数改为 async def
- Message streaming 需要前端配合

---

### 2. 统一错误处理 - 优先级 P0

**当前状态：**
- 有零散的 `try-except`
- 错误被静默吞掉，用户不知道发生了什么

**需要实现：**

#### a) 创建错误处理装饰器
```python
# agentgraph/utils/error_handler.py

def with_error_boundary(node_name: str):
    def decorator(func):
        async def wrapper(state: AppState):
            try:
                return await func(state)
            except TimeoutError as e:
                logger.error(f"{node_name} timeout: {e}")
                return {
                    "messages": [SystemMessage(
                        content=f"抱歉，{node_name} 响应超时，请稍后重试。"
                    )]
                }
            except RateLimitError as e:
                return {
                    "messages": [SystemMessage(
                        content="请求过于频繁，请 1 分钟后再试。"
                    )]
                }
            except Exception as e:
                logger.exception(f"{node_name} error", exc_info=e)
                return {
                    "messages": [SystemMessage(
                        content=f"执行出错：{str(e)}，请重试或联系支持。"
                    )]
                }
        return wrapper
    return decorator
```

#### b) 应用到所有 node
```python
@with_error_boundary("planner")
async def planner_node(state: AppState):
    # ...
```

#### c) 工具调用失败处理
```python
# tools.py 中的每个工具
@tool
def get_weather(city: str) -> str:
    try:
        # API call
        return result
    except Timeout:
        return json.dumps({
            "ok": False,
            "error": "天气服务响应超时，请稍后重试"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "ok": False,
            "error": f"查询失败：{str(e)}"
        }, ensure_ascii=False)
```

**预计工作量：** 2-3 小时

---

### 3. 多模态输入自动检测 - 优先级 P1

**当前状态：**
- `planner.py` 有 `_detect_multimodal_input()` 函数
- 检测图片和代码块
- 自动选择对应模型

**需要增强：**
- 检测更多类型（音频、视频、文件）
- 更智能的模型选择

**当前实现已经不错，可以暂时不改。**

---

### 4. 会话持久化完善 - 优先级 P1

**当前状态：**
- 有 PostgreSQL checkpointer
- `main.py` 使用 thread_id
- 基本可用

**需要增强：**
- 跨设备同步（通过 user_id）
- 会话列表查询
- 会话历史加载

**建议：** 先保持现状，等有实际需求再优化

---

### 5. 多 Agent 协作 - 优先级 P1

**当前状态：**
- 有 `call_external_agent` 工具
- 可以通过 @mention 调用

**实现计划：**
```python
# 用户输入
"@code_agent 帮我写一段 Python 代码"

# 系统处理
mentioned_agents = ["code_agent"]
→ 加载 call_external_agent 工具
→ LLM 决定调用
→ call_external_agent(
    agent_url="https://api.code-agent.com",
    task="写一段 Python 代码"
  )
```

**当前实现已经基本满足需求。**

---

## 📋 实施优先级

### 立即执行 (本周)
1. ✅ 清理 Guard/Verify - **已完成**
2. ✅ Token 优化 - **已完成**
3. ⏳ 流式输出 - **进行中**
4. ⏳ 错误处理 - **进行中**

### 下周执行
5. 会话持久化增强
6. 多模态检测优化

### 后续迭代
7. 用户个性化
8. 成本分析仪表盘
9. A/B 测试框架

---

## 🚀 下一步行动

**建议先完成流式输出，因为：**
1. 对 C 端用户体验影响最大
2. 技术难度适中
3. 可以先在本地 CLI 验证，再接入前端

**或者先完成错误处理，因为：**
1. 提升系统稳定性
2. 改动较小，风险低
3. 对后续开发有帮助

**你想先做哪个？**
