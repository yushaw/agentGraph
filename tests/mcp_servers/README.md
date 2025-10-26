# Test MCP Servers

This directory contains test MCP servers for development and testing.

## Available Servers

### test_stdio_server.py

A simple stdio-mode MCP server with 3 tools:

- **echo**: Echo back a message
- **add**: Add two numbers
- **get_time**: Get current server time

### Usage

#### Standalone Testing

```bash
# Run server directly (for debugging)
python tests/mcp_servers/test_stdio_server.py

# Test with MCP SDK
python -c "
from mcp import ClientSession
from mcp.client.stdio import stdio_client
import asyncio

async def test():
    async with stdio_client('python', ['tests/mcp_servers/test_stdio_server.py']) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f'Tools: {[t.name for t in tools.tools]}')
            result = await session.call_tool('echo', {'message': 'Hello!'})
            print(f'Result: {result.content[0].text}')

asyncio.run(test())
"
```

#### Integration Testing

Add to `generalAgent/config/mcp_servers.yaml`:

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
      add:
        enabled: true
        alias: "mcp_add"
      get_time:
        enabled: true
        alias: "mcp_time"
```

Then run AgentGraph:

```bash
python main.py
```

## Creating New Test Servers

1. Copy `test_stdio_server.py` as a template
2. Modify tools in `list_tools()` and `call_tool()`
3. Add configuration to `mcp_servers.yaml`
4. Test standalone first, then integrate

## Dependencies

```bash
pip install mcp
```

## Troubleshooting

### Server doesn't start

Check Python path and file permissions:
```bash
python --version
ls -la tests/mcp_servers/test_stdio_server.py
```

### Tools not appearing

Verify server lists tools correctly:
```bash
python tests/mcp_servers/test_stdio_server.py
# Should not error, runs as server
```

Check configuration has tools enabled.
