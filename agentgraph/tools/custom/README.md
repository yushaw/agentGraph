# Custom Tools Directory

This directory is for user-defined tools.

## How to add a custom tool

1. Create a `.py` file in this directory
2. Define your tool using LangChain's `@tool` decorator
3. The scanner will automatically discover it at startup

## Example

```python
# my_tool.py
from langchain_core.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """Description of what this tool does."""
    # Your implementation
    return f"Processed: {query}"
```

## Configuration

Tools in this directory will override builtin tools with the same name.

To enable/disable your tool, add it to `agentgraph/config/tools.yaml`:

```yaml
optional:
  my_custom_tool:
    enabled: true
    always_available: false
    category: "custom"
    tags: ["custom"]
    description: "My custom tool"
```

## MCP Tools

MCP (Model Context Protocol) tools can also be added here. Follow MCP integration guidelines.
