# MCP Quick Start Guide

Get started with MCP integration in 5 minutes.

## Prerequisites

```bash
# Ensure Python 3.12+
python --version

# Install MCP SDK
pip install mcp
```

## Step 1: Enable Test Server

Copy the example configuration:

```bash
cp generalAgent/config/mcp_servers.yaml.example \
   generalAgent/config/mcp_servers.yaml
```

The test server is already configured and ready to use!

## Step 2: Start AgentGraph

```bash
python main.py
```

You should see:

```
Loading MCP configuration...
  MCP servers configured: 1
  MCP tools loaded: 3
    ✓ Loaded MCP tool: mcp_echo (server: test_stdio)
    ✓ Loaded MCP tool: mcp_add (server: test_stdio)
    ✓ Loaded MCP tool: mcp_time (server: test_stdio)
```

## Step 3: Use MCP Tools

In the chat:

```
You> 使用 mcp_echo 工具发送消息 "Hello MCP!"

# First call triggers server startup
🚀 Starting MCP server: test_stdio
  ✓ MCP server started: test_stdio (mode: stdio)

A> [调用 mcp_echo...]
   Echo: Hello MCP!
```

Try other tools:

```
You> 用 mcp_add 计算 42 + 58
A> 42 + 58 = 100

You> 用 mcp_time 获取当前时间
A> Current time: 2025-10-26 10:30:45
```

## Step 4: Verify It Works

Run the quick test:

```bash
./scripts/test_mcp_quick.sh
```

Expected output:

```
================================
MCP Quick Integration Test
================================

✅ All dependencies installed

🧪 Running quick tests...

Test 1/5: Connection layer... ✓
Test 2/5: Server manager... ✓
Test 3/5: Tool wrapper... ✓
Test 4/5: Integration... ✓
Test 5/5: End-to-end... ✓

================================
✅ All quick tests passed!
================================
```

## What Just Happened?

1. **Configuration loaded**: AgentGraph read `mcp_servers.yaml`
2. **Tools registered**: 3 MCP tools added to ToolRegistry
3. **Lazy startup**: Server started on first tool call (not at startup)
4. **Tool execution**: Agent called MCP tool like any local tool
5. **Connection reused**: Subsequent calls used same server connection

## Next Steps

### Try Official Servers

Edit `mcp_servers.yaml` to enable official MCP servers:

```yaml
servers:
  # Filesystem access
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/your-username"]
    enabled: true

    tools:
      read_file:
        enabled: true
        alias: "mcp_read"
```

### Create Custom Server

See `tests/mcp_servers/test_stdio_server.py` for a complete example.

### Read Full Documentation

- **Integration Guide**: `docs/MCP_INTEGRATION.md`
- **Testing Guide**: `docs/TESTING_MCP.md`
- **Implementation Details**: `docs/MCP_IMPLEMENTATION_SUMMARY.md`

## Troubleshooting

### "MCP SDK not installed"

```bash
pip install mcp
```

### "Server won't start"

Check Python path in config:

```yaml
servers:
  test_stdio:
    command: "python"  # or "python3" on some systems
    args: ["tests/mcp_servers/test_stdio_server.py"]
```

### "Tools not appearing"

Verify configuration:

```yaml
tools:
  echo:
    enabled: true  # Must be true!
```

### Still Having Issues?

1. Check logs: `tail -f logs/app_*.log`
2. Run tests: `pytest tests/test_mcp/ -v`
3. See full troubleshooting: `docs/MCP_INTEGRATION.md`

## Summary

✅ Installed MCP SDK
✅ Configured test server
✅ Started AgentGraph with MCP
✅ Called MCP tools successfully
✅ Verified with tests

You're ready to use MCP! 🎉

## Learning Resources

- **Examples**: `tests/mcp_servers/test_stdio_server.py`
- **Configuration**: `generalAgent/config/mcp_servers.yaml.example`
- **Tests**: `tests/test_mcp/`
- **Documentation**: `docs/MCP_INTEGRATION.md`

## Common Use Cases

### File Operations

```yaml
filesystem:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
  tools:
    read_file:
      enabled: true
      alias: "fs_read"
```

### GitHub Integration

```yaml
github:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-github"]
  env:
    GITHUB_TOKEN: "${GITHUB_TOKEN}"
  tools:
    create_issue:
      enabled: true
      alias: "gh_issue"
```

### Web Search

```yaml
brave_search:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-brave-search"]
  env:
    BRAVE_API_KEY: "${BRAVE_API_KEY}"
  tools:
    search:
      enabled: true
      alias: "web_search"
```

Now go build something amazing! 🚀
