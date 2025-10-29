# 自动压缩测试套件

## 测试架构

自动压缩功能的测试分为三个层级：

### 1. Unit Tests（单元测试）
**位置**: `tests/unit/context/test_auto_compression_unit.py`

**测试范围**:
- Token tracker 正确识别 critical 状态（≥95%）
- ContextManager 压缩逻辑
- State 更新逻辑
- 防重复压缩标志
- Max_tokens 限制（1440 tokens = 2000 chars + 20% buffer）
- 降级策略（emergency truncation）

**特点**:
- 不依赖完整的 LangGraph
- Mock LLM 调用
- 执行快（< 1秒）

**运行**:
```bash
pytest tests/unit/context/test_auto_compression_unit.py -v
```

**结果**: ✅ 10/10 tests passed

---

### 2. Smoke Tests（冒烟测试）
**位置**: `tests/smoke/test_auto_compression_smoke.py`

**测试范围**:
- Critical 阈值检测（96% 触发，80% 不触发）
- 压缩基本功能
- 防止重复压缩
- Max_tokens 限制验证

**特点**:
- 快速验证关键路径（< 10秒）
- 适合 pre-commit 检查
- 轻量级 mock

**运行**:
```bash
pytest tests/smoke/test_auto_compression_smoke.py -v
```

**结果**: ✅ 4/4 tests passed

---

### 3. E2E Tests（端到端测试）
**位置**: `tests/e2e/test_auto_compression_e2e.py`

**测试范围**:
- 真实对话场景触发自动压缩
- 低于阈值不触发压缩
- 多次自动压缩场景

**特点**:
- 使用真实的 LangGraph app
- Mock LLM 调用（避免 API 费用）
- 测试完整业务流程
- 执行慢（可能需要 30-60秒）

**运行**:
```bash
pytest tests/e2e/test_auto_compression_e2e.py -v -s
```

**注意**: E2E 测试需要完整的应用环境

---

## 测试用例清单

### Unit Tests (10个)

#### TokenTracker Critical Detection (3个)
- [x] `test_detect_critical_threshold` - 检测 critical 阈值（96%）
- [x] `test_detect_warning_not_critical` - Warning 级别不触发（90%）
- [x] `test_detect_info_not_critical` - Info 级别不触发（80%）

#### ContextManager Compression (3个)
- [x] `test_compress_reduces_message_count` - 压缩减少消息数
- [x] `test_compress_resets_tokens` - 压缩减少 token 估算
- [x] `test_compress_preserves_system_messages` - 保留 SystemMessage

#### State Update (2个)
- [x] `test_state_update_after_compression` - State 正确更新
- [x] `test_prevent_duplicate_compression_flag` - 防重复压缩标志

#### Max Tokens & Fallback (2个)
- [x] `test_compression_uses_max_tokens_limit` - 使用 max_tokens=1440
- [x] `test_fallback_to_truncation_on_error` - 降级到 emergency_truncate

---

### Smoke Tests (4个)
- [x] `test_critical_threshold_detection_smoke` - Critical 检测
- [x] `test_compression_basic_functionality_smoke` - 基本压缩功能
- [x] `test_duplicate_compression_prevention_smoke` - 防重复压缩
- [x] `test_compression_with_max_tokens_smoke` - Max_tokens 验证

---

### E2E Tests (3个)
- [x] `test_auto_compress_triggered_in_real_conversation` - 真实对话触发压缩 (Manual test passed)
- [x] `test_no_auto_compress_below_threshold_e2e` - 低于阈值不触发 (Manual test passed)
- [ ] `test_multiple_auto_compressions_e2e` - 多次自动压缩 (Pending)

**注意**: Manual tests 已经通过，E2E 测试需要更新以匹配新的实现（planner 立即返回压缩后的 state）。

---

## 运行所有测试

```bash
# 运行 unit + smoke（快速验证）
pytest tests/unit/context/test_auto_compression_unit.py tests/smoke/test_auto_compression_smoke.py -v

# 运行完整测试套件
pytest tests/unit/context/test_auto_compression_unit.py \
       tests/smoke/test_auto_compression_smoke.py \
       tests/e2e/test_auto_compression_e2e.py -v -s
```

---

## 测试覆盖的功能点

### ✅ 已覆盖
1. Critical 阈值检测（95%）
2. Token 使用率计算
3. 压缩逻辑（compact 策略）
4. Message 数量减少
5. Token 估算减少
6. SystemMessage 保留
7. State 更新（messages, compact_count, cumulative_tokens）
8. 防重复压缩标志（auto_compressed_this_request）
9. Max_tokens 限制（1440）
10. 降级策略（emergency_truncate）

### ⚠️ 需要进一步测试
1. Planner node 中自动压缩的触发时机
2. 与完整 LangGraph 流程的集成
3. 错误恢复机制（模型 API 报错时）
4. 多次压缩的累积效果

---

## 测试结果总结

| 测试类型 | 文件 | 通过 | 失败 | 跳过 |
|---------|------|-----|-----|-----|
| Unit | test_auto_compression_unit.py | 10 | 0 | 0 |
| Smoke | test_auto_compression_smoke.py | 4 | 0 | 0 |
| Manual | test_auto_compact.py | 2 | 0 | 0 |
| E2E | test_auto_compression_e2e.py | - | - | - |
| **总计** | | **16** | **0** | **0** |

**状态**: ✅ Unit、Smoke 和 Manual 测试全部通过

---

## 下一步

1. ✅ **自动压缩实现完成**: Planner node 正确触发自动压缩并立即返回压缩后的 state
2. **更新 E2E 测试**: 修改 E2E 测试以匹配新的实现（不再需要 mock LLM）
3. **添加错误恢复测试**: 测试模型 API 返回 context_length 错误时的自动压缩
4. **性能测试**: 测试自动压缩的性能开销
5. **压力测试**: 测试极端情况（超大对话、多次压缩）

---

## 相关文档

- [FEATURES.md](../docs/FEATURES.md) - 上下文压缩功能说明
- [test_context_compression.py](./unit/context/test_context_compression.py) - 原有的压缩测试
- [TESTING.md](../docs/TESTING.md) - 测试指南
