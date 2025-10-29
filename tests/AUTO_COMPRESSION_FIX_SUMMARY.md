# 自动压缩功能修复总结

## 问题描述

自动压缩功能实现后，测试显示 `auto_compressed_this_request` 始终为 `False`，压缩没有执行。

## 根本原因

发现了两个关键问题：

### 1. UnboundLocalError - ContextManager 导入冲突

**症状**:
```python
UnboundLocalError: cannot access local variable 'ContextManager' where it is not associated with a value
```

**原因**:
- `ContextManager` 在函数顶部（line 103）被使用：
  ```python
  context_manager = ContextManager(settings) if settings.context.enabled else None
  ```
- 但在函数中间（line 318）又有 import 语句：
  ```python
  from generalAgent.context.manager import ContextManager
  ```
- Python 把 `ContextManager` 当作局部变量，导致前面的使用报错

**修复**: 将 import 移到文件顶部（line 13-14）：
```python
from generalAgent.context.manager import ContextManager
from generalAgent.context.token_tracker import TokenTracker
```

### 2. LangGraph State 不可变性 - 直接修改 state 无效

**症状**:
- 自动压缩逻辑执行了（看到日志 "Token usage CRITICAL"）
- 但 `auto_compressed_this_request` 仍然是 `False`
- `cumulative_prompt_tokens` 没有重置为 0

**原因**:
LangGraph 的 state 是不可变的（immutable）。原始代码直接修改了 `state` dictionary：
```python
# ❌ 错误做法：直接修改 state（无效）
state["messages"] = result.messages
state["compact_count"] = compact_count + 1
state["cumulative_prompt_tokens"] = 0
state["auto_compressed_this_request"] = True
```

这些修改不会影响实际的 graph state。后续代码继续执行并调用 LLM，然后返回新的 updates，覆盖了这些修改。

**修复**:
Auto-compression 检测到 critical 状态后，立即 `return` 更新后的 state，跳过 LLM 调用：

```python
# ✅ 正确做法：立即返回 updates
return {
    "messages": result.messages + [auto_compress_notification],
    "compact_count": compact_count + 1,
    "cumulative_prompt_tokens": 0,  # Reset token counter
    "cumulative_completion_tokens": 0,
    "auto_compressed_this_request": True,
    "new_uploaded_files": [],
    "new_mentioned_agents": [],
}
```

## 修改文件

1. **generalAgent/graph/nodes/planner.py** (lines 12-14, 308-356)
   - 移动 import 到顶部
   - 修改 auto-compression 逻辑为立即 return
   - 添加压缩通知 SystemMessage

2. **tests/manual/test_auto_compact.py** (lines 64-77, 147-157)
   - 修改测试执行至少 2 步（确保 planner 运行）
   - 添加 step 计数和详细日志

3. **tests/AUTO_COMPRESSION_TESTS.md**
   - 更新测试状态为通过
   - 添加 Manual test 结果

## 测试结果

### Unit Tests (10/10) ✅
```bash
pytest tests/unit/context/test_auto_compression_unit.py -v
# 10 passed in 0.10s
```

### Smoke Tests (4/4) ✅
```bash
pytest tests/smoke/test_auto_compression_smoke.py -v
# 4 passed in 0.14s
```

### Manual Tests (2/2) ✅
```bash
python tests/manual/test_auto_compact.py
# ✅ PASS - 自动压缩触发测试
# ✅ PASS - 低于阈值测试
# 🎉 所有测试通过!
```

## 关键设计决策

### 为什么立即 return 而不是继续执行？

1. **避免重复计算**: 压缩已经解决了 token 使用问题，不需要再调用 LLM
2. **状态一致性**: 立即返回确保压缩后的状态被正确传播
3. **性能优化**: 跳过不必要的 LLM 调用
4. **简化逻辑**: 避免复杂的状态同步问题

### 为什么添加通知 SystemMessage？

```python
auto_compress_notification = SystemMessage(content=(
    "🤖 自动压缩已执行\n\n"
    "由于 token 使用达到 95% 临界值，系统已自动压缩对话历史以避免溢出。\n"
    "对话已精简，可以继续。"
))
```

1. **用户透明度**: 让用户知道发生了自动压缩
2. **调试支持**: 在对话历史中留下压缩记录
3. **状态清晰**: 明确标记压缩的时间点

## 学习要点

1. **Python import 作用域**:
   - 函数内的 `from X import Y` 会让 Python 把 `Y` 当作局部变量
   - 如果前面已经使用了 `Y`，会报 `UnboundLocalError`
   - 解决方案：所有 import 移到文件顶部

2. **LangGraph 状态管理**:
   - State 是不可变的（immutable）
   - 必须通过 `return updates` 来更新 state
   - 直接修改 `state[key] = value` 不会生效

3. **异步函数中的 early return**:
   - 在检测到特殊条件时，可以立即 return 避免后续逻辑
   - 适用于 auto-compression、error handling 等场景

## 下一步

- [ ] 更新 E2E 测试以匹配新的实现（不需要 mock LLM）
- [ ] 添加多次自动压缩的测试
- [ ] 添加压缩失败时的错误恢复测试
- [ ] 测试模型 API 返回 context_length 错误时触发自动压缩
