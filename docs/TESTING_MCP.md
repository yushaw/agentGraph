# Testing MCP Integration

Guide for testing MCP integration in AgentGraph.

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-asyncio mcp

# Run all MCP tests
pytest tests/test_mcp/ -v

# Run with output (see print statements)
pytest tests/test_mcp/ -v -s
```

## Test Categories

### Unit Tests

Test individual components in isolation:

```bash
# Connection layer
pytest tests/test_mcp/test_connection.py -v

# Server manager
pytest tests/test_mcp/test_manager.py -v

# Tool wrapper
pytest tests/test_mcp/test_wrapper.py -v

# Config loader
pytest tests/test_mcp/test_loader.py -v
```

### Integration Tests

Test component interactions:

```bash
pytest tests/test_mcp/test_integration.py -v
```

### End-to-End Tests

Test complete workflows:

```bash
pytest tests/test_mcp/test_e2e.py -v -s
```

## Key Test Scenarios

### 1. Lazy Startup

Verify servers start on first tool call:

```bash
pytest tests/test_mcp/test_manager.py::test_lazy_server_startup -v -s
```

Expected output:
```
🚀 Starting MCP server: test_stdio
✓ Server started on first call
```

### 2. Tool Invocation

Test actual tool calls:

```bash
pytest tests/test_mcp/test_connection.py::test_call_echo_tool -v
```

### 3. Error Recovery

Verify error handling:

```bash
pytest tests/test_mcp/test_e2e.py::test_mcp_error_scenarios -v -s
```

### 4. Performance

Measure startup and call times:

```bash
pytest tests/test_mcp/test_e2e.py::test_performance_metrics -v -s
```

Expected output:
```
First call (with startup): 2.345s
Subsequent call: 0.234s
Speedup: 10.0x
```

### 5. Complete Workflow

Test full agent workflow:

```bash
pytest tests/test_mcp/test_e2e.py::test_complete_agent_workflow -v -s
```

This runs through:
1. MCP initialization
2. Application building
3. Lazy server startup
4. Multiple tool calls
5. Concurrent operations
6. Cleanup

## Test Development

### Creating New Tests

1. **Create test file**:
   ```bash
   touch tests/test_mcp/test_my_feature.py
   ```

2. **Write test**:
   ```python
   import pytest

   @pytest.mark.asyncio
   async def test_my_feature(mcp_manager, mcp_tools):
       """Test my MCP feature."""
       # Use fixtures
       tool = next(t for t in mcp_tools if t.name == "mcp_echo")

       # Call tool
       result = await tool._arun(message="test")

       # Assert
       assert "Echo: test" in result
   ```

3. **Run test**:
   ```bash
   pytest tests/test_mcp/test_my_feature.py -v
   ```

### Using Fixtures

Available fixtures from `conftest.py`:

```python
@pytest.mark.asyncio
async def test_with_fixtures(
    test_server_path,      # Path to test server
    test_mcp_config,       # MCP configuration dict
    mcp_manager,           # MCPServerManager instance
    mcp_tools              # List of MCP tools
):
    # Your test code
    pass
```

### Testing Async Operations

Always use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### Testing Errors

Use `pytest.raises`:

```python
@pytest.mark.asyncio
async def test_error():
    with pytest.raises(ValueError, match="error message"):
        await function_that_raises()
```

## Debugging Tests

### Run Single Test

```bash
pytest tests/test_mcp/test_connection.py::test_stdio_connection_lifecycle -v
```

### Show Print Statements

```bash
pytest tests/test_mcp/ -v -s
```

### Drop into Debugger

```bash
# Break on failure
pytest tests/test_mcp/ --pdb

# Break on first failure
pytest tests/test_mcp/ -x --pdb
```

### Enable Debug Logging

```python
import logging

@pytest.mark.asyncio
async def test_with_logging(mcp_manager):
    logging.basicConfig(level=logging.DEBUG)
    # Debug output will show
```

### Check Coverage

```bash
pip install pytest-cov
pytest tests/test_mcp/ --cov=generalAgent.tools.mcp --cov-report=html
open htmlcov/index.html
```

## Common Issues

### Tests Hang

**Symptom**: Test never completes

**Solution**: Check for orphaned server processes
```bash
ps aux | grep test_stdio_server
kill <pid>
```

### Import Errors

**Symptom**: `ModuleNotFoundError`

**Solution**: Add project root to Python path
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/test_mcp/ -v
```

### Connection Timeouts

**Symptom**: `asyncio.TimeoutError`

**Solution**: Increase timeout in config
```python
# In conftest.py
@pytest.fixture
def test_mcp_config():
    return {
        "settings": {
            "startup_timeout": 60  # Increase from 30
        }
    }
```

### MCP SDK Not Found

**Symptom**: `ImportError: No module named 'mcp'`

**Solution**: Install MCP SDK
```bash
pip install mcp
```

## CI/CD Integration

### GitHub Actions

```yaml
name: MCP Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-asyncio mcp

      - name: Run MCP tests
        run: pytest tests/test_mcp/ -v --tb=short
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
echo "Running MCP tests..."
pytest tests/test_mcp/ -q || {
    echo "MCP tests failed!"
    exit 1
}
```

## Performance Testing

Run performance benchmarks:

```bash
pytest tests/test_mcp/test_e2e.py::test_performance_metrics -v -s
```

Expected metrics:
- **First call**: 2-3s (includes server startup)
- **Subsequent calls**: 0.1-0.3s
- **Speedup**: ~10x

## Test Coverage Goals

Target coverage for MCP module:

- Connection layer: 95%+
- Server manager: 95%+
- Tool wrapper: 90%+
- Config loader: 95%+
- Integration: 80%+

Check current coverage:

```bash
pytest tests/test_mcp/ \
  --cov=generalAgent.tools.mcp \
  --cov-report=term-missing
```

## Best Practices

1. **Always use async/await**
   ```python
   @pytest.mark.asyncio
   async def test_feature():
       await async_operation()
   ```

2. **Clean up resources**
   ```python
   async def test_with_cleanup(mcp_manager):
       try:
           # Test code
           pass
       finally:
           await mcp_manager.shutdown()
   ```

3. **Use descriptive names**
   ```python
   def test_lazy_startup_triggers_on_first_call():
       pass  # Clear what's being tested
   ```

4. **Test one thing at a time**
   ```python
   def test_server_starts():
       # Only test server start
       pass

   def test_server_accepts_connections():
       # Only test connections
       pass
   ```

5. **Use fixtures for reusable setup**
   ```python
   @pytest.fixture
   async def started_server(mcp_manager):
       await mcp_manager.get_server("test_stdio")
       yield mcp_manager
       await mcp_manager.shutdown()
   ```

## Next Steps

1. Run complete test suite
2. Check coverage report
3. Add tests for custom MCP servers
4. Integrate into CI/CD
5. Set up pre-commit hooks

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Test Directory](../tests/test_mcp/)
