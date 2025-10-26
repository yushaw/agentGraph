# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (2025-10-27) - E2E Testing Expansion

**New Test Suites**: Added 13 comprehensive E2E test scenarios (+92.9% test coverage)

**Test Categories**:

1. **Advanced Multi-Turn Scenarios** (2 tests):
   - `test_progressive_task_refinement`: Simulates gradual requirement clarification
   - `test_context_switch_and_recall`: Tests memory across topic changes

2. **Subagent Delegation** (2 tests):
   - `test_complex_task_delegation`: Multi-step task delegation workflow
   - `test_subagent_error_handling`: Error handling in delegated tasks

3. **Tool Chaining Scenarios** (2 tests):
   - `test_conditional_tool_chain`: Conditional branching logic
   - `test_iterative_refinement_loop`: Iterative file modification workflow

4. **Error Recovery** (2 tests):
   - `test_file_not_found_recovery`: Fallback strategy testing
   - `test_retry_on_tool_failure`: Graceful failure handling

5. **Stateful Workflows** (2 tests):
   - `test_todo_list_workflow`: Task tracking across turns
   - `test_session_state_accumulation`: Multi-turn information accumulation

6. **Edge Cases** (3 tests):
   - `test_empty_file_handling`: Empty file processing
   - `test_large_message_history_trimming`: Message history limits
   - `test_concurrent_file_operations`: Multiple file operations

**Test Results**: All 13 new tests passing (total: 27 E2E tests, up from 14)

**Files Modified**:
- `tests/e2e/test_agent_workflows.py` (+410 lines)

### Added (2025-10-27) - Testing Infrastructure Reorganization

**New Structure**:
- Created four-tier testing hierarchy: smoke, unit, integration, e2e
- Added comprehensive testing documentation (TESTING_GUIDE.md, E2E_TESTING_SOP.md, HITL_TESTING_SOP.md)
- Implemented `tests/run_tests.py` for organized test execution
- Added pytest fixtures and shared test infrastructure in `tests/conftest.py`

**Files Added**:
- `tests/README.md` - Testing overview and quick start
- `tests/run_tests.py` - Test runner with tier support
- `tests/conftest.py` - Shared pytest fixtures
- `tests/smoke/` - Critical path smoke tests
- `tests/unit/` - Unit tests (reorganized from root)
- `tests/integration/` - Integration tests
- `tests/fixtures/` - Test fixtures and mock MCP servers
- `docs/TESTING_GUIDE.md` - Comprehensive testing guide
- `docs/E2E_TESTING_SOP.md` - E2E testing procedures
- `docs/HITL_TESTING_SOP.md` - HITL testing procedures

**Files Removed** (reorganized into new structure):
- Old test files from `tests/` root (moved to appropriate tiers)
- Duplicate MCP test directories merged into `tests/fixtures/`

### Fixed (2025-10-27) - Settings Configuration Optimization

**Problem**: Reflective HITL tests were always skipped because environment variables from `.env` were not being loaded correctly into settings, even though the API keys existed in the file.

**Root Cause**:
- `ModelRoutingSettings`, `GovernanceSettings`, and `ObservabilitySettings` were using `BaseModel` instead of `BaseSettings`
- Pydantic's `BaseModel` does not automatically load from environment variables
- This required manual fallback patterns in business code (`or _env()` workarounds)

**Changes**:

1. **Settings Architecture** (`generalAgent/config/settings.py`):
   - Changed `ModelRoutingSettings` from `BaseModel` to `BaseSettings`
   - Changed `GovernanceSettings` from `BaseModel` to `BaseSettings`
   - Changed `ObservabilitySettings` from `BaseModel` to `BaseSettings`
   - Added `model_config = SettingsConfigDict(env_file=".env", ...)` to all three classes
   - Settings now properly load from environment variables via Pydantic's built-in mechanism

2. **Model Resolver Cleanup** (`generalAgent/runtime/model_resolver.py`):
   - Removed `_env()` fallback helper function (no longer needed)
   - Simplified `resolve_model_configs()` by removing `or _env()` patterns
   - Added documentation explaining that settings now load correctly without fallbacks
   - Code is cleaner and more maintainable

3. **Test Code Fixes** (`tests/unit/test_hitl_reflective.py`):
   - Fixed `ReflectiveTestRunner.__init__()` to use `build_model_resolver()` instead of `build_default_registry()`
   - Changed from getting `ModelSpec` (metadata) to actual `ChatOpenAI` instances
   - Simplified `@pytest.mark.skipif` conditions (removed complex env var checks)
   - All 5 reflective HITL tests now pass correctly

**Impact**:
- ✅ Environment variables now load correctly from `.env` file
- ✅ All 5 reflective HITL tests pass (previously skipped)
- ✅ Removed workaround code (`or _env()` fallbacks)
- ✅ Cleaner, more maintainable codebase
- ✅ Proper separation of concerns (settings vs business logic)

**Test Results**:
- Before: 138 passed, 5 skipped, 2 failed
- After: 143+ passed, 0 failed, 0 skipped (reflective tests take ~409s)

**Files Modified**:
- `generalAgent/config/settings.py` (lines 16-127)
- `generalAgent/runtime/model_resolver.py` (lines 20-94)
- `tests/unit/test_hitl_reflective.py` (lines 14-336)

**Documentation Updated**:
- Added "Settings Architecture" section to `CLAUDE.md`
- Expanded "Configuration" section in `README.md` with detailed structure and examples

**Verification**:
```bash
# Verify settings load correctly
python -c "from generalAgent.config.settings import get_settings; s = get_settings(); print('API Key loaded:', bool(s.models.reason_api_key))"
# Expected: API Key loaded: True

# Run reflective HITL tests
pytest tests/unit/test_hitl_reflective.py -v
# Expected: 5 passed
```

---

## Previous Changes

For changes before 2025-10-27, see the "更新日志" section in [README.md](README.md#更新日志).
