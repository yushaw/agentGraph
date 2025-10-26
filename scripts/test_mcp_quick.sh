#!/bin/bash
# Quick MCP integration test script

set -e

echo "=================================="
echo "MCP Quick Integration Test"
echo "=================================="
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
python -c "import pytest" 2>/dev/null || {
    echo "❌ pytest not installed"
    echo "   Run: pip install pytest pytest-asyncio"
    exit 1
}

python -c "import mcp" 2>/dev/null || {
    echo "❌ MCP SDK not installed"
    echo "   Run: pip install mcp"
    exit 1
}

echo "✅ All dependencies installed"
echo ""

# Run quick tests
echo "🧪 Running quick tests..."
echo ""

# Test 1: Connection layer
echo "Test 1/5: Connection layer..."
pytest tests/test_mcp/test_connection.py::test_stdio_connection_lifecycle -v -q || exit 1

# Test 2: Manager
echo ""
echo "Test 2/5: Server manager..."
pytest tests/test_mcp/test_manager.py::test_lazy_server_startup -v -q || exit 1

# Test 3: Wrapper
echo ""
echo "Test 3/5: Tool wrapper..."
pytest tests/test_mcp/test_wrapper.py::test_wrapper_async_call -v -q || exit 1

# Test 4: Integration
echo ""
echo "Test 4/5: Integration..."
pytest tests/test_mcp/test_integration.py::test_full_integration_flow -v -q || exit 1

# Test 5: E2E
echo ""
echo "Test 5/5: End-to-end..."
pytest tests/test_mcp/test_e2e.py::test_complete_agent_workflow -v -s || exit 1

echo ""
echo "=================================="
echo "✅ All quick tests passed!"
echo "=================================="
echo ""
echo "To run full test suite:"
echo "  pytest tests/test_mcp/ -v"
echo ""
