# MCP Integration Tests

Comprehensive test suite for MCP (Model Context Protocol) integration in AgentGraph.

## Test Structure

```
tests/test_mcp/
├── conftest.py              # Pytest fixtures
├── test_connection.py       # Connection layer tests
├── test_manager.py          # Server manager tests
├── test_wrapper.py          # Tool wrapper tests
├── test_loader.py           # Configuration loader tests
├── test_integration.py      # Integration tests
└── test_e2e.py             # End-to-end scenario tests
```

## Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Install MCP SDK
pip install mcp
```

## Running Tests

### Run All MCP Tests

```bash
pytest tests/test_mcp/ -v
```

### Run Specific Test File

```bash
# Connection tests
pytest tests/test_mcp/test_connection.py -v

# Manager tests
pytest tests/test_mcp/test_manager.py -v

# Integration tests
pytest tests/test_mcp/test_integration.py -v

# E2E tests
pytest tests/test_mcp/test_e2e.py -v
```

### Run Specific Test

```bash
pytest tests/test_mcp/test_connection.py::test_stdio_connection_lifecycle -v
```

### Run with Output

```bash
# Show print statements
pytest tests/test_mcp/ -v -s

# Show detailed E2E output
pytest tests/test_mcp/test_e2e.py -v -s
```

### Skip Slow Tests

```bash
# Skip tests marked as slow
pytest tests/test_mcp/ -v -m "not slow"
```

## Test Coverage

### 1. Connection Layer (test_connection.py)

Tests the low-level MCP connection:

- ✅ Server lifecycle (start/stop)
- ✅ Tool listing
- ✅ Tool invocation (echo, add, get_time)
- ✅ Error handling
- ✅ Tool information retrieval

```bash
pytest tests/test_mcp/test_connection.py -v
```

Expected: 6 tests pass

### 2. Server Manager (test_manager.py)

Tests server lifecycle management:

- ✅ Manager initialization
- ✅ Lazy server startup
- ✅ Server connection pooling
- ✅ Graceful shutdown
- ✅ Error scenarios

```bash
pytest tests/test_mcp/test_manager.py -v
```

Expected: 5 tests pass

### 3. Tool Wrapper (test_wrapper.py)

Tests LangChain BaseTool integration:

- ✅ Wrapper creation
- ✅ Async/sync tool calls
- ✅ Lazy server startup trigger
- ✅ Tool metadata
- ✅ Error handling

```bash
pytest tests/test_mcp/test_wrapper.py -v
```

Expected: 7 tests pass

### 4. Configuration Loader (test_loader.py)

Tests configuration loading:

- ✅ YAML config loading
- ✅ Tool filtering (enabled/disabled)
- ✅ Naming strategies (alias/prefix)
- ✅ Server filtering

```bash
pytest tests/test_mcp/test_loader.py -v
```

Expected: 7 tests pass

### 5. Integration Tests (test_integration.py)

Tests component integration:

- ✅ Full integration flow
- ✅ ToolRegistry integration
- ✅ Always-available tools
- ✅ Concurrent tool calls
- ✅ Error recovery
- ✅ Server restart
- ✅ Multiple sessions
- ✅ Application integration

```bash
pytest tests/test_mcp/test_integration.py -v
```

Expected: 8 tests pass

### 6. End-to-End Tests (test_e2e.py)

Tests real-world scenarios:

- ✅ Complete agent workflow
- ✅ Session lifecycle
- ✅ Tool discovery
- ✅ Error scenarios
- ✅ Performance metrics

```bash
pytest tests/test_mcp/test_e2e.py -v -s
```

Expected: 5 tests pass

## Test Fixtures

### Key Fixtures (conftest.py)

- `test_server_path`: Path to test stdio server
- `test_mcp_config`: Test MCP configuration
- `mcp_manager`: Initialized MCP manager with cleanup
- `mcp_tools`: Loaded MCP tools

### Using Fixtures

```python
@pytest.mark.asyncio
async def test_my_feature(mcp_manager, mcp_tools):
    # Use fixtures
    echo_tool = next(t for t in mcp_tools if t.name == "mcp_echo")
    result = await echo_tool._arun(message="test")
    assert "Echo: test" in result
```

## Writing New Tests

### Basic Structure

```python
import pytest

@pytest.mark.asyncio
async def test_my_mcp_feature(mcp_manager, mcp_tools):
    """Test description."""
    # Arrange
    tool = next(t for t in mcp_tools if t.name == "mcp_echo")

    # Act
    result = await tool._arun(message="test")

    # Assert
    assert "expected" in result
```

### Testing Async Code

All MCP operations are async, use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

### Testing Error Scenarios

```python
@pytest.mark.asyncio
async def test_error_handling():
    with pytest.raises(ValueError, match="expected error"):
        await operation_that_fails()
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run MCP Tests
  run: |
    pip install pytest pytest-asyncio mcp
    pytest tests/test_mcp/ -v --tb=short
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/test_mcp/ -q || exit 1
```

## Debugging Tests

### Run with Debugger

```bash
# Use pdb
pytest tests/test_mcp/ --pdb

# Break on first failure
pytest tests/test_mcp/ -x --pdb
```

### Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

@pytest.mark.asyncio
async def test_with_logging(mcp_manager):
    # Debug output will show
    result = await mcp_manager.get_server("test_stdio")
```

## Performance Testing

Run performance tests separately:

```bash
pytest tests/test_mcp/test_e2e.py::test_performance_metrics -v -s
```

Expected output shows timing comparisons:
- First call (with startup): ~2-3s
- Subsequent call: ~0.1-0.3s
- Speedup: ~10x

## Troubleshooting

### Tests Hang

Check if server processes are orphaned:

```bash
ps aux | grep test_stdio_server
kill <pid>
```

### Import Errors

Ensure project root in path:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/test_mcp/ -v
```

### MCP SDK Not Found

```bash
pip install mcp
```

### Connection Timeouts

Increase timeout in conftest.py:

```python
@pytest.fixture
def test_mcp_config():
    return {
        "settings": {
            "startup_timeout": 60  # Increase from 30
        }
    }
```

## Test Markers

```python
@pytest.mark.asyncio      # Async test
@pytest.mark.slow         # Slow test (skip with -m "not slow")
@pytest.mark.integration  # Integration test
```

## Coverage Report

```bash
# Generate coverage report
pip install pytest-cov
pytest tests/test_mcp/ --cov=generalAgent.tools.mcp --cov-report=html

# View report
open htmlcov/index.html
```

## Next Steps

1. Run all tests to verify setup
2. Check test coverage
3. Add custom tests for your MCP servers
4. Integrate into CI/CD pipeline

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
