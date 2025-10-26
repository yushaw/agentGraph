# MCP Integration Guide

AgentGraph now supports the Model Context Protocol (MCP), allowing you to connect external tools and services to your agent.

## Overview

MCP integration enables:
- **External tool connectivity**: Connect to filesystem, GitHub, databases, etc.
- **Lazy startup**: Servers only start when tools are first used
- **Manual control**: Explicitly configure which tools are available
- **Multiple protocols**: Support for stdio and SSE connection modes
- **Automatic cleanup**: Servers shut down gracefully on exit

## Quick Start

### 1. Install MCP SDK

```bash
pip install mcp
```

### 2. Create Configuration

Copy the example configuration:

```bash
cp generalAgent/config/mcp_servers.yaml.example generalAgent/config/mcp_servers.yaml
```

### 3. Test with Built-in Server

The test stdio server is included for development. Edit `mcp_servers.yaml`:

```yaml
servers:
  test_stdio:
    command: "python"
    args: ["tests/mcp_servers/test_stdio_server.py"]
    enabled: true

    tools:
      echo:
        enabled: true
        alias: "mcp_echo"
        description: "Echo back a message"
```

### 4. Run AgentGraph

```bash
python main.py
```

You should see:

```
Loading MCP configuration...
  MCP servers configured: 1
  MCP tools loaded: 3
    ✓ Loaded MCP tool: mcp_echo (server: test_stdio)
```

### 5. Use MCP Tools

```
You> 使用 mcp_echo 工具发送消息 "Hello MCP!"

# First call triggers lazy server startup
🚀 Starting MCP server: test_stdio
  ✓ MCP server started: test_stdio (mode: stdio)

A> [调用 mcp_echo...]
   Echo: Hello MCP!
```

## Configuration Reference

### Server Configuration

```yaml
servers:
  <server_id>:
    command: "python"              # Command to start server
    args: ["path/to/server.py"]    # Command arguments
    enabled: true                  # Enable/disable server
    env:                           # Environment variables
      API_KEY: "${API_KEY}"        # Use ${VAR} for env references
    connection_mode: "stdio"       # "stdio" or "sse"
    url: "http://localhost:8000"   # For SSE mode only

    tools:
      <tool_name>:
        enabled: true               # Enable/disable tool
        always_available: false     # Always in agent context
        alias: "custom_name"        # Custom tool name
        description: "..."          # Tool description
```

### Global Settings

```yaml
settings:
  lazy_start: true              # Lazy vs immediate startup
  namespace_strategy: "alias"   # "alias" or "prefix"
  startup_timeout: 30           # Server startup timeout (seconds)
  default_connection_mode: "stdio"  # Default mode for servers
```

## Connection Modes

### Stdio Mode (Default)

Standard input/output communication. Works with most MCP servers.

```yaml
servers:
  my_server:
    command: "python"
    args: ["server.py"]
    connection_mode: "stdio"  # or omit (default)
```

### SSE Mode

Server-Sent Events over HTTP. For web-based MCP servers.

```yaml
servers:
  my_web_server:
    command: "node"
    args: ["server.js"]
    connection_mode: "sse"
    url: "http://localhost:8000/sse"
```

## Official MCP Servers

### Filesystem Server

```yaml
servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"]
    enabled: true

    tools:
      read_file:
        enabled: true
        alias: "mcp_read"
      write_file:
        enabled: true
        alias: "mcp_write"
```

### GitHub Server

```yaml
servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    enabled: true
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"

    tools:
      create_issue:
        enabled: true
        alias: "gh_issue"
```

### More Servers

See official MCP servers: https://github.com/modelcontextprotocol

## Tool Naming Strategies

### Alias Strategy (Recommended)

Use custom aliases for clean names:

```yaml
settings:
  namespace_strategy: "alias"

servers:
  filesystem:
    tools:
      read_file:
        alias: "fs_read"  # Tool name: fs_read
```

### Prefix Strategy

Automatic namespacing to prevent conflicts:

```yaml
settings:
  namespace_strategy: "prefix"

servers:
  filesystem:
    tools:
      read_file:
        # No alias needed
        # Tool name: mcp__filesystem__read_file
```

## Lazy Startup

Servers start only when tools are first called:

```yaml
settings:
  lazy_start: true  # Recommended
```

**Benefits:**
- Fast application startup
- Lower resource usage
- Only start what you need

**Flow:**
1. Application starts → MCP tools registered, servers NOT started
2. Agent calls `mcp_echo` → Triggers filesystem server startup
3. Subsequent calls → Use existing connection

## Always Available Tools

Mark frequently used tools as always available:

```yaml
tools:
  search:
    enabled: true
    always_available: true  # Always in agent context
```

**When to use:**
- Core functionality tools
- Tools used in 90%+ of conversations
- Tools with low latency

**Trade-off:** More tokens per request (tool schemas in prompt)

## Lifecycle Management

MCP servers are automatically managed:

1. **Startup**: Lazy (on first use) or immediate
2. **Usage**: Reuse connection for all calls
3. **Shutdown**: Graceful cleanup on exit or timeout

### Graceful Shutdown

```python
# Automatic on Ctrl+C
^C
Cleaning up MCP servers...
  ✓ Closed: test_stdio
✅ MCP cleanup completed
```

### Timeout Handling

Servers shut down after session timeout (configurable).

## Troubleshooting

### Server Won't Start

Check logs for errors:
```bash
tail -f logs/app_*.log
```

Common issues:
- Command not found: Verify `command` and `args`
- Port already in use: Change SSE `url`
- Permission denied: Check file permissions

### Tool Not Found

Verify configuration:
```yaml
tools:
  my_tool:
    enabled: true  # Must be true
```

Check if tool exists on server:
```bash
# Test server directly
python tests/mcp_servers/test_stdio_server.py
```

### Import Errors

Install MCP SDK:
```bash
pip install mcp
```

For SSE mode:
```bash
pip install aiohttp
```

## Creating Custom MCP Servers

See `tests/mcp_servers/test_stdio_server.py` for a complete example.

### Basic Structure

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("my-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [Tool(name="my_tool", description="...", inputSchema={...})]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name == "my_tool":
        result = do_something(arguments)
        return [TextContent(type="text", text=result)]

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Architecture

```
AgentGraph
    ↓
ToolRegistry (unified interface)
    ↓
MCPToolWrapper (LangChain BaseTool)
    ↓
MCPServerManager (lifecycle)
    ↓
MCPConnection (stdio/SSE)
    ↓
MCP Server Process
```

## Best Practices

1. **Use lazy startup**: Keeps application fast
2. **Limit always_available tools**: Reduces token usage
3. **Use aliases**: Clean, descriptive names
4. **Test servers independently**: Debug issues faster
5. **Monitor logs**: Track startup and errors
6. **Graceful shutdown**: Let cleanup complete

## Next Steps

- Explore official MCP servers
- Create custom servers for your needs
- Integrate with your favorite APIs
- Share your MCP servers with the community

## Resources

- MCP Documentation: https://modelcontextprotocol.io
- Official Servers: https://github.com/modelcontextprotocol
- SDK Repository: https://github.com/modelcontextprotocol/python-sdk
