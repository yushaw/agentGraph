# Development Guide

> **Note**: Practical guide for developing with and extending AgentGraph

## Table of Contents

- [Part 1: Environment Setup](#part-1-environment-setup)
  - [1.1 Prerequisites](#11-prerequisites)
  - [1.2 Installation](#12-installation)
  - [1.3 Environment Configuration (.env)](#13-environment-configuration-env)
  - [1.4 Pydantic Settings](#14-pydantic-settings)
  - [1.5 Model Configuration](#15-model-configuration)
- [Part 2: Developing Tools](#part-2-developing-tools)
  - [2.1 Tool Basics](#21-tool-basics)
  - [2.2 Creating a New Tool](#22-creating-a-new-tool)
  - [2.3 Tool Configuration (tools.yaml)](#23-tool-configuration-toolsyaml)
  - [2.4 Tool Metadata](#24-tool-metadata)
  - [2.5 Multi-Tool Files (\_\_all\_\_ export)](#25-multi-tool-files-__all__-export)
  - [2.6 Testing Tools](#26-testing-tools)
  - [2.7 Best Practices](#27-best-practices)
- [Part 3: Developing Skills](#part-3-developing-skills)
  - [3.1 Skill Structure](#31-skill-structure)
  - [3.2 Creating a Skill Package](#32-creating-a-skill-package)
  - [3.3 SKILL.md Documentation](#33-skillmd-documentation)
  - [3.4 Skill Scripts](#34-skill-scripts)
  - [3.5 Dependency Management (requirements.txt)](#35-dependency-management-requirementstxt)
  - [3.6 Skill Configuration (skills.yaml)](#36-skill-configuration-skillsyaml)
  - [3.7 Testing Skills](#37-testing-skills)
- [Part 4: Extending the System](#part-4-extending-the-system)
  - [4.1 Adding Custom Nodes](#41-adding-custom-nodes)
  - [4.2 Custom Routing Logic](#42-custom-routing-logic)
  - [4.3 Integrating Third-Party Services](#43-integrating-third-party-services)
  - [4.4 Custom Model Resolvers](#44-custom-model-resolvers)
  - [4.5 Delegated agent Catalogs](#45-delegated agent-catalogs)
- [Part 5: Development Best Practices](#part-5-development-best-practices)
  - [5.1 Code Organization](#51-code-organization)
  - [5.2 Naming Conventions](#52-naming-conventions)
  - [5.3 Error Handling Patterns](#53-error-handling-patterns)
  - [5.4 Logging Guidelines](#54-logging-guidelines)
  - [5.5 Configuration Management](#55-configuration-management)
  - [5.6 Path Handling](#56-path-handling)
- [Part 6: Debugging and Troubleshooting](#part-6-debugging-and-troubleshooting)
  - [6.1 Logging and Tracing](#61-logging-and-tracing)
  - [6.2 LangSmith Integration](#62-langsmith-integration)
  - [6.3 Common Issues](#63-common-issues)
  - [6.4 Debug Tools](#64-debug-tools)
- [Part 7: Contributing](#part-7-contributing)
  - [7.1 Code Style](#71-code-style)
  - [7.2 Testing Requirements](#72-testing-requirements)
  - [7.3 Documentation](#73-documentation)
  - [7.4 Pull Request Process](#74-pull-request-process)

---

## Part 1: Environment Setup

### 1.1 Prerequisites

**Required**:
- Python 3.12 or higher
- uv (recommended) or pip
- Git

**Optional**:
- Docker (for containerized development)
- PostgreSQL (for persistent checkpointing)

### 1.2 Installation

#### Method 1: Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/agentGraph.git
cd agentGraph

# Install dependencies with uv
uv sync

# Verify installation
python -c "import generalAgent; print('OK')"
```

#### Method 2: Using pip

```bash
# Clone the repository
git clone https://github.com/your-org/agentGraph.git
cd agentGraph

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .

# Verify installation
python -c "import generalAgent; print('OK')"
```

#### Method 3: Development Mode

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Or with uv
uv sync --all-extras
```

### 1.3 Environment Configuration (.env)

Create a `.env` file in the project root:

```bash
# Copy the template
cp .env.example .env

# Edit with your settings
vim .env
```

**Complete .env template** (based on actual `.env.example`):

```bash
#=============================================================================
# MODEL CONFIGURATION (Required)
#=============================================================================

# Five model slots, each with 4 fields: ID, API_KEY, BASE_URL, CONTEXT_WINDOW
# Supports multiple aliases (e.g., MODEL_BASIC_* and MODEL_BASE_* both work)

# ===== Base Model (general chat/analysis) =====
MODEL_BASIC_API_KEY=                               # Or: MODEL_BASE_API_KEY
MODEL_BASIC_BASE_URL=https://api.deepseek.com      # Or: MODEL_BASE_BASE_URL
MODEL_BASIC_ID=deepseek-chat                       # Or: MODEL_BASE_ID
MODEL_BASIC_CONTEXT_WINDOW=128000                  # Or: MODEL_BASE_CONTEXT_WINDOW (total capacity: input+output)
MODEL_BASIC_MAX_COMPLETION_TOKENS=4096             # Or: MODEL_BASE_MAX_COMPLETION_TOKENS (max output tokens, prevents tool call truncation, default 2048)

# ===== Reasoning Model (reasoning / deep thinking) =====
MODEL_REASONING_API_KEY=                           # Or: MODEL_REASON_API_KEY
MODEL_REASONING_BASE_URL=https://api.deepseek.com  # Or: MODEL_REASON_BASE_URL
MODEL_REASONING_ID=deepseek-reasoner               # Or: MODEL_REASON_ID
MODEL_REASONING_CONTEXT_WINDOW=128000              # Or: MODEL_REASON_CONTEXT_WINDOW (total capacity: input+output)
MODEL_REASONING_MAX_COMPLETION_TOKENS=8192         # Or: MODEL_REASON_MAX_COMPLETION_TOKENS (reasoning models need higher output limits, default 2048)

# ===== Multimodal Model (vision understanding) =====
MODEL_MULTIMODAL_API_KEY=                                    # Or: MODEL_VISION_API_KEY
MODEL_MULTIMODAL_BASE_URL=https://open.bigmodel.cn/api/paas/v4  # Or: MODEL_VISION_BASE_URL
MODEL_MULTIMODAL_ID=glm-4.5v                                 # Or: MODEL_VISION_ID
MODEL_MULTIMODAL_CONTEXT_WINDOW=64000                        # Or: MODEL_VISION_CONTEXT_WINDOW (total capacity: input+output)
MODEL_MULTIMODAL_MAX_COMPLETION_TOKENS=4096                  # Or: MODEL_VISION_MAX_COMPLETION_TOKENS (max output tokens, default 2048)

# ===== Code Model (code understanding & generation) =====
MODEL_CODE_API_KEY=
MODEL_CODE_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_CODE_ID=glm-4.6
MODEL_CODE_CONTEXT_WINDOW=200000                             # Total capacity: input+output
MODEL_CODE_MAX_COMPLETION_TOKENS=8192                        # Code generation needs higher output limits (default 2048)

# ===== Chat Model (main conversation) =====
MODEL_CHAT_API_KEY=
MODEL_CHAT_BASE_URL=https://api.moonshot.cn/v1
MODEL_CHAT_ID=kimi-k2-0905-preview
MODEL_CHAT_CONTEXT_WINDOW=256000                             # Total capacity: input+output
MODEL_CHAT_MAX_COMPLETION_TOKENS=4096                        # Max output tokens (Kimi default 1024 is too low, recommend 4096+, default 2048)

#=============================================================================
# Jina AI Configuration (for web fetching and search)
#=============================================================================

JINA_API_KEY=
JINA_STRIP_IMAGES=true           # Filter out image links in Markdown to save bandwidth (true/false, default true)
JINA_REMOVE_SELECTORS=nav,footer,header,.sidebar,.navigation,.menu,aside  # CSS selectors to remove (comma-separated)
JINA_CONTENT_CLEANING=true       # Use LLM to clean content and remove noise (true/false, default true)
JINA_CLEANING_MIN_LENGTH=2000    # Minimum content length to trigger cleaning (chars, default 2000)

#=============================================================================
# LangSmith Configuration (Optional)
#=============================================================================

LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=                # Or: LANGCHAIN_API_KEY

#=============================================================================
# Runtime Controls (Optional, commented means using default values)
#=============================================================================

# MAX_MESSAGE_HISTORY=40          # Max message history to retain (10-100, default 40)
# MAX_LOOPS=100                   # Max loop iterations (1-500, default 100)

#=============================================================================
# Logging Configuration (Optional)
#=============================================================================

# LOG_PROMPT_MAX_LENGTH=500       # Max prompt display length in logs (100-5000, default 500)
```

**Important Notes**:

1. **Model Configuration Aliases**:
   - `MODEL_BASIC_*` = `MODEL_BASE_*`
   - `MODEL_REASONING_*` = `MODEL_REASON_*`
   - `MODEL_MULTIMODAL_*` = `MODEL_VISION_*`
   - Both naming styles work, system auto-detects

2. **CONTEXT_WINDOW vs MAX_COMPLETION_TOKENS**:
   - **CONTEXT_WINDOW** (Context Window): Total model capacity limit (input tokens + output tokens)
     - Used for KV Cache optimization and message history management
     - Example: Kimi k2's CONTEXT_WINDOW=256000 means input+output combined cannot exceed 256K tokens

   - **MAX_COMPLETION_TOKENS** (Max Completion Tokens): Maximum tokens for a single output (controls output only)
     - **Key Purpose**: Prevents tool call truncation (incomplete tool call JSON causes parsing failures)
     - Default: 2048 (if not configured)
     - **Recommended Values**:
       - Base/Multimodal models: 4096
       - Reasoning/Code models: 8192 (need longer outputs)
       - Kimi API defaults to only 1024, **strongly recommend 4096+**
     - **Backward Compatibility**: Also supports old naming `MODEL_*_MAX_TOKENS`

3. **Jina AI Configuration**:
   - Powers `fetch_web` and `web_search` tools
   - Supports content cleaning, image filtering, selector removal

4. **Document Processing Settings**:
   - Not configured in .env, uses code defaults
   - To customize, modify `DocumentSettings` class in `generalAgent/config/settings.py`

**Environment Variables Precedence**:

1. **Values in .env file** - Highest priority
2. **System environment variables** - Second priority
3. **Pydantic Field defaults** - Fallback defaults

### 1.4 Pydantic Settings

AgentGraph uses **Pydantic BaseSettings** for automatic environment variable loading with type validation.

**Settings Architecture** (`generalAgent/config/settings.py`):

```python
Settings
├── ModelRoutingSettings     # Model IDs and credentials
├── GovernanceSettings       # Runtime controls (auto_approve, max_loops)
├── ObservabilitySettings    # Tracing, logging, persistence
└── DocumentSettings         # Document processing parameters
```

**Key Features**:

1. **Automatic .env loading** - All settings classes inherit from `BaseSettings`
2. **Multiple aliases** - `AliasChoices` support provider-specific names
3. **Type validation** - Pydantic validates types, ranges (e.g., `max_loops: int = Field(ge=1, le=500)`)
4. **No fallbacks needed** - Settings are loaded directly from environment

**Usage Example**:

```python
from generalAgent.config.settings import get_settings

# Get singleton instance (cached)
settings = get_settings()

# Access settings (automatically loaded from .env)
api_key = settings.models.reason_api_key
max_loops = settings.governance.max_loops
db_path = settings.observability.session_db_path
```

**Adding New Settings**:

1. Add to settings class:

```python
# generalAgent/config/settings.py
class GovernanceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_loops: int = Field(default=100, ge=1, le=500)
    max_retries: int = Field(default=3, ge=1, le=10)  # NEW
```

2. Add to `.env`:

```bash
MAX_RETRIES=5
```

3. Use in code:

```python
settings = get_settings()
retries = settings.governance.max_retries
```

### 1.5 Model Configuration

**Supported Model Slots**:

1. **base** - General-purpose model (default for most tasks)
2. **reasoning** - Complex reasoning tasks
3. **vision** - Image processing tasks
4. **code** - Code generation/analysis
5. **chat** - Conversational tasks

**Provider Examples**:

#### DeepSeek

```bash
MODEL_BASIC_API_KEY=sk-xxx
MODEL_BASIC_BASE_URL=https://api.deepseek.com
MODEL_BASIC_ID=deepseek-chat

MODEL_REASONING_API_KEY=sk-xxx
MODEL_REASONING_BASE_URL=https://api.deepseek.com
MODEL_REASONING_ID=deepseek-reasoner
```

#### GLM (Zhipu AI)

```bash
MODEL_MULTIMODAL_API_KEY=xxx
MODEL_MULTIMODAL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_MULTIMODAL_ID=glm-4.5v
```

#### Moonshot (Kimi)

```bash
MODEL_CHAT_API_KEY=xxx
MODEL_CHAT_BASE_URL=https://api.moonshot.cn/v1
MODEL_CHAT_ID=kimi-k2-0905-preview
```

#### OpenAI

```bash
MODEL_BASE_API_KEY=sk-xxx
MODEL_BASE_BASE_URL=https://api.openai.com/v1
MODEL_BASE_ID=gpt-4-turbo-preview
```

**Model Resolution Flow**:

```python
# generalAgent/runtime/model_resolver.py
def resolve(self, state: AppState, node_name: str) -> str:
    """Resolve model with fallback"""

    # Prefer vision model for images
    if state.get("images") and "vision" in self.configs:
        return "vision"

    # Prefer reasoning model for complex tasks
    if node_name == "decompose" and "reasoning" in self.configs:
        return "reasoning"

    # Fallback to base model
    if "base" in self.configs:
        return "base"

    # Ultimate fallback: first available
    return list(self.configs.keys())[0]
```

---

## Part 2: Developing Tools

### 2.1 Tool Basics

**What are Tools?**

Tools are Python functions that the agent can call to perform specific actions:
- Read/write files
- Make HTTP requests
- Execute commands
- Search documents
- Call external APIs

**Tool Architecture**:

```
Tool System
├── Discovery Layer (_discovered)     # All scanned tools (including disabled)
├── Registry Layer (_tools)            # Enabled tools (immediately available)
└── Visibility Layer                   # Dynamic visibility per context
```

**Tool Types**:

1. **Core tools** - Always enabled (e.g., `now`, `todo_write`, `read_file`)
2. **Optional tools** - Can be enabled/disabled (e.g., `http_fetch`, `run_bash_command`)
3. **On-demand tools** - Loaded when @mentioned (e.g., `@extract_links`)

### 2.2 Creating a New Tool

#### Step 1: Create Tool File

Create a new file in `generalAgent/tools/builtin/` or `generalAgent/tools/custom/`:

```python
# generalAgent/tools/custom/my_calculator.py
from langchain_core.tools import tool
import logging

LOGGER = logging.getLogger(__name__)

@tool
def calculate_sum(numbers: list[float]) -> float:
    """Calculate the sum of a list of numbers.

    Args:
        numbers: List of numbers to sum

    Returns:
        The sum of all numbers
    """
    try:
        result = sum(numbers)
        LOGGER.info(f"Calculated sum: {result}")
        return result
    except Exception as e:
        LOGGER.error(f"Calculation failed: {e}")
        return f"Error: {e}"

@tool
def calculate_average(numbers: list[float]) -> float:
    """Calculate the average of a list of numbers.

    Args:
        numbers: List of numbers to average

    Returns:
        The average of all numbers
    """
    try:
        if not numbers:
            return 0.0
        result = sum(numbers) / len(numbers)
        LOGGER.info(f"Calculated average: {result}")
        return result
    except Exception as e:
        LOGGER.error(f"Calculation failed: {e}")
        return f"Error: {e}"

# Export tools explicitly
__all__ = ["calculate_sum", "calculate_average"]
```

**Key Points**:

1. Use `@tool` decorator from `langchain_core.tools`
2. Provide clear docstring (used in tool description)
3. Add type hints for parameters and return value
4. Handle errors gracefully
5. Return string results (agent sees tool output as text)
6. Use `__all__` to export multiple tools

#### Step 2: Add Tool Configuration

Edit `generalAgent/config/tools.yaml`:

```yaml
optional:
  calculate_sum:
    enabled: true                      # Load at startup
    always_available: false            # Not globally visible (default)
    category: "compute"                # Tool category
    tags: ["math", "calculation"]      # Searchable tags
    description: "Sum a list of numbers"

  calculate_average:
    enabled: true
    always_available: false
    category: "compute"
    tags: ["math", "calculation", "statistics"]
    description: "Calculate average of numbers"
```

#### Step 3: Test Your Tool

```bash
# Run the application
python main.py

# Test in CLI
You> @calculate_sum 帮我计算 [1, 2, 3, 4, 5] 的和
Agent> [calls calculate_sum([1, 2, 3, 4, 5])]
       总和是 15。
```

### 2.3 Tool Configuration (tools.yaml)

**Configuration Structure**:

```yaml
# Core tools - Always loaded
core:
  now:
    category: "meta"
    tags: ["meta", "time"]
    description: "Get current UTC time"

  todo_write:
    category: "meta"
    tags: ["meta", "task"]
    description: "Write task list"

# Optional tools - Can be enabled/disabled
optional:
  http_fetch:
    enabled: true                      # Load at startup
    always_available: false            # Not globally visible
    category: "network"
    tags: ["network", "read"]
    description: "Fetch web page content"

  run_bash_command:
    enabled: false                     # Not loaded at startup
    always_available: false
    category: "system"
    tags: ["system", "dangerous"]
    description: "Execute bash commands"
```

**Configuration Options**:

- `enabled: true/false` - Whether to load at startup
- `always_available: true/false` - Whether globally visible (use sparingly)
- `category` - Tool category for organization
- `tags` - Searchable tags
- `description` - Human-readable description

**Loading Behavior**:

| Setting | Behavior |
|---------|----------|
| `core: tool` | Always loaded, always visible |
| `enabled: true` | Loaded at startup, visible by default |
| `enabled: false` | Not loaded, but available via @mention |
| `always_available: true` | Added to all agent contexts (use sparingly) |

### 2.4 Tool Metadata

**ToolMeta Structure** (`generalAgent/tools/registry.py`):

```python
@dataclass
class ToolMeta:
    name: str                           # Tool name (e.g., "read_file")
    category: str                       # Category (e.g., "file", "network")
    tags: list[str]                     # Tags (e.g., ["read", "file"])
    description: str                    # Human-readable description
    always_available: bool = False      # Global visibility flag
```

**Usage**:

```python
from generalAgent.tools.registry import ToolRegistry

registry = ToolRegistry()

# Register tool with metadata
registry.register_tool(read_file_tool)
registry.add_metadata(ToolMeta(
    name="read_file",
    category="file",
    tags=["read", "file", "workspace"],
    description="Read file from workspace",
    always_available=False,
))

# Query metadata
meta = registry.get_metadata("read_file")
print(f"Category: {meta.category}")
print(f"Tags: {meta.tags}")
```

### 2.5 Multi-Tool Files (\_\_all\_\_ export)

**Problem**: How to export multiple tools from a single file?

**Solution**: Use `__all__` to explicitly declare exports.

**Example** (`generalAgent/tools/builtin/file_ops.py`):

```python
from langchain_core.tools import tool

@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""
    pass

@tool
def write_file(file_path: str, content: str) -> str:
    """Write file to workspace"""
    pass

@tool
def list_workspace_files(directory: str = ".") -> str:
    """List files in directory"""
    pass

# Export all tools explicitly
__all__ = ["read_file", "write_file", "list_workspace_files"]
```

**Tool Scanner** (`generalAgent/tools/scanner.py`):

```python
def _extract_tools_from_module(file_path: Path) -> Dict[str, Any]:
    """Extract ALL tools from a module"""

    tools = {}

    # Method 1: Use __all__ if defined (recommended)
    if hasattr(module, "__all__"):
        tool_names = module.__all__
        for name in tool_names:
            obj = getattr(module, name)
            if isinstance(obj, BaseTool):
                tools[obj.name] = obj

    # Method 2: Introspect all attributes (fallback)
    else:
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool) and not name.startswith("_"):
                tools[obj.name] = obj

    return tools
```

**Best Practices**:

1. Always use `__all__` for explicit control
2. Group related tools in one file (e.g., all file operations)
3. Avoid exporting private tools (prefix with `_`)

### 2.6 Testing Tools

#### Unit Test Example

```python
# tests/unit/test_calculator_tools.py
import pytest
from generalAgent.tools.custom.my_calculator import calculate_sum, calculate_average

def test_calculate_sum():
    """Test sum calculation"""
    result = calculate_sum.invoke({"numbers": [1, 2, 3, 4, 5]})
    assert result == 15.0

def test_calculate_sum_empty():
    """Test sum with empty list"""
    result = calculate_sum.invoke({"numbers": []})
    assert result == 0.0

def test_calculate_average():
    """Test average calculation"""
    result = calculate_average.invoke({"numbers": [2, 4, 6, 8, 10]})
    assert result == 6.0

def test_calculate_average_error():
    """Test error handling"""
    result = calculate_average.invoke({"numbers": []})
    assert result == 0.0
```

#### Integration Test Example

```python
# tests/integration/test_calculator_integration.py
import pytest
from generalAgent.tools.registry import ToolRegistry
from generalAgent.tools.config_loader import load_tool_config

def test_calculator_tools_loaded():
    """Test that calculator tools are loaded by registry"""

    # Load configuration
    config = load_tool_config()

    # Create registry
    registry = ToolRegistry()

    # Load tools
    from generalAgent.tools.scanner import scan_tools_directory
    tools_dir = Path("generalAgent/tools/custom")
    discovered = scan_tools_directory(tools_dir)

    for tool in discovered:
        if config.is_enabled(tool.name):
            registry.register_tool(tool)

    # Verify tools are loaded
    assert registry.get_tool("calculate_sum") is not None
    assert registry.get_tool("calculate_average") is not None
```

### 2.7 Best Practices

#### Error Handling

Always return friendly error messages instead of raising exceptions:

```python
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""
    try:
        workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
        abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        LOGGER.error(f"Failed to read file: {e}", exc_info=True)
        return f"Error: Failed to read file: {e}"
```

#### Using Error Boundary Decorator

```python
# generalAgent/tools/decorators.py
from functools import wraps
import logging

LOGGER = logging.getLogger(__name__)

def with_error_boundary(func):
    """Decorator to catch and format tool errors"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except FileNotFoundError as e:
            error_msg = f"File not found: {e.filename}"
            LOGGER.error(f"Tool '{func.__name__}' failed: {error_msg}")
            return f"Error: {error_msg}"

        except PermissionError as e:
            error_msg = f"Permission denied: {e}"
            LOGGER.error(f"Tool '{func.__name__}' failed: {error_msg}")
            return f"Error: {error_msg}"

        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {e}"
            LOGGER.error(f"Tool '{func.__name__}' failed: {error_msg}", exc_info=True)
            return f"Error: {error_msg}"

    return wrapper

# Usage
@tool
@with_error_boundary
def read_file(file_path: str) -> str:
    """Read file from workspace"""
    # No try-except needed, decorator handles it
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

#### Logging

Use structured logging for debugging:

```python
import logging

LOGGER = logging.getLogger(__name__)

@tool
def my_tool(param: str) -> str:
    """My tool description"""

    LOGGER.info(f"Tool called with param: {param}")

    try:
        result = process(param)
        LOGGER.info(f"✓ Tool succeeded: {result}")
        return result

    except Exception as e:
        LOGGER.error(f"✗ Tool failed: {e}", exc_info=True)
        return f"Error: {e}"
```

#### Path Security

Always validate paths to prevent directory traversal:

```python
from generalAgent.utils.file_processor import resolve_workspace_path

@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""

    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # Validates path is within workspace
    abs_path = resolve_workspace_path(
        file_path,
        workspace_root,
        must_exist=True,        # Check file exists
        allow_write=False,      # Read-only operation
    )

    with open(abs_path, "r") as f:
        return f.read()
```

#### Environment Variables

Use environment variables for context:

```python
import os
from pathlib import Path

@tool
def my_tool() -> str:
    """My tool description"""

    # Get workspace path
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))

    # Get session ID
    session_id = os.environ.get("AGENT_CONTEXT_ID")

    # Get user ID
    user_id = os.environ.get("AGENT_USER_ID", "anonymous")

    # Use context...
```

---

## Part 3: Developing Skills

### 3.1 Skill Structure

**What are Skills?**

Skills are **knowledge packages** (documentation + scripts), NOT tool containers. They provide:
- **SKILL.md** - Main documentation with usage guide
- **scripts/** - Python scripts for specific tasks
- **Reference docs** - Additional documentation
- **requirements.txt** - Python dependencies (optional)

**Directory Structure**:

```
skills/<skill_id>/
├── SKILL.md           # Main skill documentation (required)
├── requirements.txt   # Python dependencies (optional)
├── reference.md       # Additional reference (optional)
├── forms.md           # Specific guides (optional)
└── scripts/           # Python scripts (optional)
    ├── script1.py
    └── script2.py
```

**Important**: Skills do NOT have `allowed_tools` - they are documentation packages that guide the agent.

### 3.2 Creating a Skill Package

#### Step 1: Create Skill Directory

```bash
mkdir -p generalAgent/skills/my-skill/scripts
cd generalAgent/skills/my-skill
```

#### Step 2: Write SKILL.md

```markdown
# My Skill

> Brief description of what this skill does

## Overview

This skill provides capabilities for [describe capabilities].

## Usage

### Basic Usage

1. Read the input file using `read_file` tool
2. Process the data using the provided scripts
3. Write the output using `write_file` tool

### Example

User: @my-skill 处理文件 uploads/data.txt

Agent workflow:
1. Read the SKILL.md (this file)
2. Read the input file: `read_file("uploads/data.txt")`
3. Execute processing script: `run_bash_command("python skills/my-skill/scripts/process.py")`
4. Write output: `write_file("outputs/result.txt", content)`

## Scripts

### process.py

Process input data and generate output.

**Usage**:
```bash
python skills/my-skill/scripts/process.py
```

**Input**: Reads from stdin (JSON format)
```json
{
  "input_file": "uploads/data.txt",
  "output_file": "outputs/result.txt",
  "options": {
    "format": "json"
  }
}
```

**Output**: Prints to stdout (JSON format)
```json
{
  "status": "success",
  "output_file": "outputs/result.txt",
  "records_processed": 100
}
```

## Dependencies

This skill requires the following Python packages:
- pandas>=2.0.0
- numpy>=1.24.0

Install with: `pip install -r requirements.txt`

## Error Handling

Common errors and solutions:

1. **Missing input file**
   - Error: "File not found: uploads/data.txt"
   - Solution: Ensure file is uploaded to workspace

2. **Invalid format**
   - Error: "Unsupported format: xyz"
   - Solution: Use supported formats (csv, json, xlsx)

## References

- [External Documentation](https://example.com/docs)
- [API Reference](https://example.com/api)
```

#### Step 3: Create Script

```python
# scripts/process.py
import json
import sys
import os
from pathlib import Path

def main():
    # 1. Read workspace path from environment
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")
    if not workspace:
        print(json.dumps({"error": "AGENT_WORKSPACE_PATH not set"}))
        sys.exit(1)

    workspace_path = Path(workspace)

    # 2. Read arguments from stdin (JSON)
    try:
        args = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    # 3. Validate required arguments
    required = ["input_file", "output_file"]
    missing = [k for k in required if k not in args]
    if missing:
        print(json.dumps({"error": f"Missing arguments: {missing}"}))
        sys.exit(1)

    # 4. Execute logic
    input_path = workspace_path / args["input_file"]
    output_path = workspace_path / args["output_file"]

    try:
        # Read input
        with open(input_path, "r") as f:
            data = f.read()

        # Process (your logic here)
        result = process_data(data, args.get("options", {}))

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result)

        # 5. Print result to stdout (JSON)
        print(json.dumps({
            "status": "success",
            "output_file": str(args["output_file"]),
            "records_processed": len(result.split("\n")),
        }))

    except Exception as e:
        # 6. Print error (JSON)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

def process_data(data: str, options: dict) -> str:
    """Process input data"""
    # Your processing logic here
    return data.upper()  # Example: convert to uppercase

if __name__ == "__main__":
    main()
```

**Script Interface Requirements**:

1. Read workspace path from `AGENT_WORKSPACE_PATH` environment variable
2. Read arguments from stdin (JSON format)
3. Validate required arguments
4. Execute logic using workspace-relative paths
5. Print result to stdout (JSON format)
6. Print errors to stdout (JSON format) and exit with non-zero code

#### Step 4: Add Dependencies

```txt
# requirements.txt
pandas>=2.0.0
numpy>=1.24.0
```

#### Step 5: Configure Skill

Edit `generalAgent/config/skills.yaml`:

```yaml
optional:
  my-skill:
    enabled: true                           # Show in catalog
    always_available: false
    description: "My custom skill for data processing"
    auto_load_on_file_types: ["txt", "csv"]  # Auto-load for these file types
```

### 3.3 SKILL.md Documentation

**Best Practices**:

1. **Clear Overview** - Describe what the skill does
2. **Step-by-Step Usage** - Provide workflow examples
3. **Script Documentation** - Document each script's usage
4. **Example Workflow** - Show complete agent workflow
5. **Error Handling** - List common errors and solutions
6. **Dependencies** - Document required packages
7. **References** - Link to external resources

**Template**:

```markdown
# [Skill Name]

> One-line description

## Overview

[Detailed description of capabilities]

## Usage

### Basic Usage

[Step-by-step guide]

### Example

[Complete workflow example]

## Scripts

### [script_name.py]

[Script description]

**Usage**:
```bash
[Command example]
```

**Input**:
```json
[Input format]
```

**Output**:
```json
[Output format]
```

## Dependencies

[List of dependencies]

## Error Handling

[Common errors and solutions]

## References

[External links]
```

### 3.4 Skill Scripts

**Script Design Principles**:

1. **Stdin/Stdout Communication** - Standard I/O for data exchange
2. **JSON Format** - Structured input/output
3. **Environment Variables** - Context from `AGENT_WORKSPACE_PATH`
4. **Error Handling** - Return JSON errors, exit with non-zero
5. **Workspace-Relative Paths** - All paths relative to workspace

**Complete Example**:

```python
#!/usr/bin/env python
"""
PDF Form Filling Script

Reads form data from JSON and fills a PDF form.
"""
import json
import sys
import os
from pathlib import Path

# Import dependencies
try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    print(json.dumps({
        "error": "Missing dependency: pypdf2",
        "solution": "Install with: pip install pypdf2"
    }))
    sys.exit(1)

def main():
    # Read workspace path
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")
    if not workspace:
        print(json.dumps({"error": "AGENT_WORKSPACE_PATH not set"}))
        sys.exit(1)

    workspace_path = Path(workspace)

    # Read arguments from stdin
    try:
        args = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    # Validate arguments
    required = ["input_pdf", "output_pdf", "fields"]
    missing = [k for k in required if k not in args]
    if missing:
        print(json.dumps({"error": f"Missing: {missing}"}))
        sys.exit(1)

    # Build paths
    input_path = workspace_path / args["input_pdf"]
    output_path = workspace_path / args["output_pdf"]

    # Validate input
    if not input_path.exists():
        print(json.dumps({"error": f"Input not found: {args['input_pdf']}"}))
        sys.exit(1)

    try:
        # Fill PDF form
        result = fill_pdf_form(
            str(input_path),
            str(output_path),
            args["fields"]
        )

        # Return success
        print(json.dumps({
            "status": "success",
            "output_file": args["output_pdf"],
            "fields_filled": result["fields_filled"],
        }))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

def fill_pdf_form(input_pdf: str, output_pdf: str, fields: dict) -> dict:
    """Fill PDF form fields"""
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    # Copy pages
    for page in reader.pages:
        writer.add_page(page)

    # Fill fields
    if "/AcroForm" in reader.trailer["/Root"]:
        writer.update_page_form_field_values(writer.pages[0], fields)

    # Write output
    Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)

    return {"fields_filled": len(fields)}

if __name__ == "__main__":
    main()
```

**Script Invocation** (by agent using `run_bash_command` tool):

```python
# Agent calls:
run_bash_command(
    command='python skills/my-skill/scripts/fill_form.py',
    input_json={
        "input_pdf": "uploads/form.pdf",
        "output_pdf": "outputs/filled.pdf",
        "fields": {
            "name": "John Doe",
            "date": "2025-01-24"
        }
    }
)
```

### 3.5 Dependency Management (requirements.txt)

**Automatic Installation**:

Dependencies are installed automatically when user first @mentions the skill.

**How it works**:

1. User types `@my-skill` or uploads matching file
2. WorkspaceManager links skill to workspace
3. WorkspaceManager checks for `requirements.txt`
4. If found, runs `pip install -r requirements.txt`
5. Marks dependencies as installed (cached)

**Code** (`shared/workspace/manager.py`):

```python
def _link_skill(self, skill_id: str, skill_path: Path):
    """Link skill to workspace and install dependencies"""

    target_dir = self.workspace_path / "skills" / skill_id

    # Create symlink
    if not target_dir.exists():
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        target_dir.symlink_to(skill_path, target_is_directory=True)

    # Check for requirements.txt
    requirements = skill_path / "requirements.txt"
    if requirements.exists() and not self._is_dependencies_installed(skill_id):
        self._install_skill_dependencies(skill_id, requirements)

def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    """Install dependencies using pip"""

    try:
        LOGGER.info(f"Installing dependencies for skill '{skill_id}'...")

        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True,
            timeout=120,  # 2 minutes timeout
        )

        # Mark as installed
        self._skill_registry.mark_dependencies_installed(skill_id)

        LOGGER.info(f"✓ Dependencies installed for '{skill_id}'")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        LOGGER.warning(f"Failed to install dependencies: {error_msg}")
        # Don't fail the whole session, just warn

    except subprocess.TimeoutExpired:
        LOGGER.warning(f"Dependency installation timeout for '{skill_id}'")
```

**Error Handling**:

If installation fails, agent receives friendly error:

```python
# generalAgent/tools/builtin/run_bash_command.py
except ImportError as e:
    missing_module = str(e).split("'")[1] if "'" in str(e) else "unknown"
    return f"""Script execution failed: Missing dependency

错误: 缺少 Python 模块 '{missing_module}'

建议操作:
1. 检查 skills/{skill_id}/requirements.txt 是否包含此依赖
2. 手动安装: pip install {missing_module}
3. 或联系技能维护者添加依赖声明
"""
```

### 3.6 Skill Configuration (skills.yaml)

**Configuration File**: `generalAgent/config/skills.yaml`

```yaml
# Global settings
global:
  enabled: true                    # Enable/disable entire skills system
  auto_load_on_file_upload: true  # Auto-load skills when matching files uploaded

# Core skills - Always loaded at startup
core: []  # Empty by default

# Optional skills - Load on demand
optional:
  pdf:
    enabled: false                           # Show in catalog?
    always_available: false                  # Keep loaded across all sessions?
    description: "PDF processing and form filling"
    auto_load_on_file_types: ["pdf"]        # Auto-load when .pdf uploaded

  my-skill:
    enabled: true
    always_available: false
    description: "My custom skill"
    auto_load_on_file_types: ["txt", "csv"]

# Skills directories
directories:
  builtin: "generalAgent/skills"
```

**Configuration Options**:

- `enabled: true` - Show in catalog and load at startup
- `enabled: false` - Hide from catalog, only load via @mention or file upload
- `always_available: true` - Keep loaded across all sessions (not recommended)
- `auto_load_on_file_types` - File extensions that trigger auto-load

**Behavior**:

| Setting | Catalog | Startup | @mention | File Upload |
|---------|---------|---------|----------|-------------|
| `enabled: true` | ✓ Visible | ✓ Loaded | ✓ Works | ✓ Auto-loads |
| `enabled: false` | ✗ Hidden | ✗ Not loaded | ✓ Works | ✓ Auto-loads |

**Use Cases**:

1. **Hide experimental skills**: Set `enabled: false`
2. **Default skills**: Set `enabled: true`
3. **Progressive disclosure**: Start with `enabled: false`, auto-load on file upload

### 3.7 Testing Skills

#### Manual Testing

```bash
# Start CLI
python main.py

# Test skill loading
You> @my-skill 处理文件 uploads/data.txt

# Check logs
tail -f logs/agentgraph_*.log | grep "my-skill"
```

#### Unit Test (Script)

```python
# tests/unit/test_my_skill_script.py
import json
import subprocess
import sys
from pathlib import Path

def test_process_script():
    """Test process.py script"""

    script_path = Path("generalAgent/skills/my-skill/scripts/process.py")

    # Prepare input
    input_data = {
        "input_file": "uploads/test.txt",
        "output_file": "outputs/result.txt",
        "options": {"format": "json"}
    }

    # Run script
    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env={"AGENT_WORKSPACE_PATH": "/tmp/test_workspace"},
    )

    # Check result
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["status"] == "success"
    assert "output_file" in output
```

#### Integration Test

```python
# tests/integration/test_my_skill_integration.py
import pytest
from pathlib import Path
from generalAgent.skills.registry import SkillRegistry

def test_skill_loading():
    """Test skill loads correctly"""

    registry = SkillRegistry(skills_root=Path("generalAgent/skills"))

    # Check skill exists
    skill = registry.get_skill("my-skill")
    assert skill is not None
    assert skill.id == "my-skill"
    assert skill.name == "My Skill"

    # Check SKILL.md exists
    skill_md = skill.path / "SKILL.md"
    assert skill_md.exists()

    # Check scripts exist
    scripts_dir = skill.path / "scripts"
    assert scripts_dir.exists()
    assert (scripts_dir / "process.py").exists()
```

---

## Part 4: Extending the System

### 4.1 Adding Custom Nodes

Custom nodes allow you to add new logic points in the LangGraph flow.

**Example: Add a "validation" node**:

```python
# generalAgent/graph/nodes/validation.py
from typing import Any
from langchain_core.messages import AIMessage
import logging

LOGGER = logging.getLogger(__name__)

def validation_node(state: dict[str, Any]) -> dict[str, Any]:
    """Validate agent output before finalizing"""

    messages = state["messages"]
    last_message = messages[-1]

    # Check if output meets criteria
    if isinstance(last_message, AIMessage):
        content = last_message.content

        # Example validation: Check minimum length
        if len(content) < 10:
            LOGGER.warning("Output too short, requesting more detail")

            # Add validation message
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(
                content="请提供更详细的回答（至少10个字符）。"
            ))

            return {
                "messages": messages,
                "needs_replan": True,  # Trigger replanning
            }

    # Validation passed
    LOGGER.info("✓ Output validation passed")
    return {"needs_replan": False}
```

**Integrate into graph**:

```python
# generalAgent/graph/builder.py
from generalAgent.graph.nodes.validation import validation_node

def build_state_graph(...):
    workflow = StateGraph(AppState)

    # Add nodes
    workflow.add_node("plan", planner_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("validation", validation_node)  # NEW
    workflow.add_node("finalize", finalize_node)

    # Add edges
    workflow.add_edge("plan", "tools")
    workflow.add_edge("tools", "validation")  # NEW

    # Add conditional edge
    workflow.add_conditional_edges(
        "validation",
        lambda state: "plan" if state.get("needs_replan") else "finalize",
        {"plan": "plan", "finalize": "finalize"}
    )

    return workflow.compile()
```

### 4.2 Custom Routing Logic

**Example: Add image detection routing**:

```python
# generalAgent/graph/routing.py
from typing import Literal
from generalAgent.graph.state import AppState

def agent_route(state: AppState) -> Literal["tools", "vision", "finalize"]:
    """Route agent based on content"""

    messages = state["messages"]
    last = messages[-1]

    # Check loop limit
    if state["loops"] >= state["max_loops"]:
        return "finalize"

    # Check for images in state
    if state.get("images"):
        return "vision"  # Route to vision node

    # LLM wants to call tools
    if last.tool_calls:
        return "tools"

    # LLM finished
    return "finalize"
```

**Add vision node**:

```python
# generalAgent/graph/nodes/vision.py
from generalAgent.models.registry import ModelRegistry
from langchain_core.messages import HumanMessage

def vision_node(state: dict) -> dict:
    """Process images with vision model"""

    model_registry = ModelRegistry.get_instance()
    vision_model = model_registry.get_model("vision")

    # Prepare messages with images
    messages = state["messages"]
    images = state.get("images", [])

    # Add images to last message
    last_message = messages[-1]
    content = [
        {"type": "text", "text": last_message.content},
        *[{"type": "image_url", "image_url": {"url": img}} for img in images]
    ]

    # Invoke vision model
    result = vision_model.invoke([HumanMessage(content=content)])

    return {
        "messages": [result],
        "images": [],  # Clear images after processing
    }
```

### 4.3 Integrating Third-Party Services

**Example: Add a weather service**:

```python
# generalAgent/services/weather.py
import requests
from typing import Optional

class WeatherService:
    """Weather data service"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.weather.com/v1"

    def get_weather(self, city: str) -> Optional[dict]:
        """Get weather for city"""

        try:
            response = requests.get(
                f"{self.base_url}/weather",
                params={"city": city, "apikey": self.api_key},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            LOGGER.error(f"Weather API failed: {e}")
            return None
```

**Create tool that uses service**:

```python
# generalAgent/tools/builtin/weather.py
from langchain_core.tools import tool
from generalAgent.services.weather import WeatherService
import os

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city.

    Args:
        city: City name (e.g., "Beijing", "Shanghai")

    Returns:
        Weather description
    """
    api_key = os.environ.get("WEATHER_API_KEY")
    if not api_key:
        return "Error: WEATHER_API_KEY not configured"

    service = WeatherService(api_key)
    weather = service.get_weather(city)

    if not weather:
        return f"Error: Could not fetch weather for {city}"

    return f"Weather in {city}: {weather['description']}, {weather['temp']}°C"
```

**Add to .env**:

```bash
WEATHER_API_KEY=your-api-key-here
```

### 4.4 Custom Model Resolvers

**Example: Add a custom resolver for specialized tasks**:

```python
# generalAgent/runtime/custom_model_resolver.py
from typing import Dict, Optional
from generalAgent.graph.state import AppState

class CustomModelResolver:
    """Custom model resolver with task-specific logic"""

    def __init__(self, configs: Dict[str, dict]):
        self.configs = configs

    def resolve(self, state: AppState, node_name: str) -> str:
        """Resolve model based on task complexity and content"""

        # Analyze task complexity
        complexity = self._analyze_complexity(state)

        # Route based on complexity
        if complexity == "high":
            # Use reasoning model for complex tasks
            if "reasoning" in self.configs:
                return "reasoning"

        # Route based on content type
        if state.get("images"):
            if "vision" in self.configs:
                return "vision"

        # Check if task involves code
        if self._is_code_task(state):
            if "code" in self.configs:
                return "code"

        # Default to base model
        if "base" in self.configs:
            return "base"

        # Fallback to first available
        return list(self.configs.keys())[0]

    def _analyze_complexity(self, state: AppState) -> str:
        """Analyze task complexity"""

        messages = state.get("messages", [])
        if not messages:
            return "low"

        last_message = messages[-1]
        content = last_message.content if hasattr(last_message, "content") else ""

        # Simple heuristic: longer messages = more complex
        if len(content) > 1000:
            return "high"
        elif len(content) > 500:
            return "medium"
        else:
            return "low"

    def _is_code_task(self, state: AppState) -> bool:
        """Check if task involves code"""

        messages = state.get("messages", [])
        if not messages:
            return False

        last_message = messages[-1]
        content = last_message.content if hasattr(last_message, "content") else ""

        # Look for code-related keywords
        code_keywords = ["代码", "函数", "class", "def", "import", "编程"]
        return any(keyword in content.lower() for keyword in code_keywords)
```

**Use custom resolver**:

```python
# main.py
from generalAgent.runtime.app import build_application
from generalAgent.runtime.custom_model_resolver import CustomModelResolver

# Build application with custom resolver
app, state_factory, skill_registry, tool_registry = build_application()

# Replace default resolver
custom_resolver = CustomModelResolver(configs=app.model_configs)
app.model_resolver = custom_resolver
```

### 4.5 Delegated agent Catalogs

**Example: Add a specialized delegated agent**:

```python
# generalAgent/agents/data_analysis_agent.py
from typing import Dict, Any
from langchain_core.messages import SystemMessage

class DataAnalysisAgent:
    """Specialized agent for data analysis tasks"""

    def __init__(self, model, tools):
        self.model = model
        self.tools = tools
        self.system_prompt = """你是数据分析专家。

核心能力：
- 数据清洗和预处理
- 统计分析
- 可视化生成
- 趋势预测

工作流程：
1. 理解数据结构
2. 进行数据分析
3. 生成可视化报告
4. 提供分析结论
"""

    def invoke(self, task: str, context: Dict[str, Any]) -> str:
        """Execute data analysis task"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=task)
        ]

        result = self.model.invoke(messages, tools=self.tools)
        return result.content
```

**Register in delegated agent catalog**:

```python
# generalAgent/runtime/app.py
def build_application():
    # ... existing code ...

    # Create delegated agent catalog
    delegated agent_catalog = {
        "data-analyst": {
            "name": "数据分析师",
            "description": "专门负责数据分析、统计和可视化",
            "capabilities": ["数据清洗", "统计分析", "可视化", "趋势预测"],
            "allowed_tools": ["read_file", "write_file", "run_python_script"],
        },
        # ... other delegated agents ...
    }

    # Register agent factory
    def create_delegated agent(agent_type: str):
        if agent_type == "data-analyst":
            from generalAgent.agents.data_analysis_agent import DataAnalysisAgent
            model = model_registry.get_model("base")
            tools = [tool_registry.get_tool(t) for t in ["read_file", "write_file"]]
            return DataAnalysisAgent(model, tools)
        # ... other agents ...

    return app, state_factory, skill_registry, tool_registry, create_delegated agent
```

---

## Part 5: Development Best Practices

### 5.1 Code Organization

**Project Structure Best Practices**:

1. **Shared Infrastructure** (`shared/`) - Reusable components
2. **Agent-Specific Logic** (`generalAgent/`) - Business logic
3. **Clear Separation** - Infrastructure vs business logic

**Module Organization**:

```
generalAgent/
├── agents/           # Agent factories
├── config/           # Settings and configuration
├── graph/            # State, nodes, routing
│   ├── nodes/        # Individual node implementations
│   ├── prompts.py    # Prompt templates
│   ├── routing.py    # Routing logic
│   ├── state.py      # State definition
│   └── builder.py    # Graph assembly
├── models/           # Model registry and routing
├── runtime/          # Application assembly
├── skills/           # Skill packages
├── tools/            # Tool system
│   ├── builtin/      # Built-in tools
│   ├── custom/       # Custom tools
│   ├── registry.py   # Tool registry
│   └── scanner.py    # Tool discovery
└── utils/            # Utility functions
```

**Best Practices**:

1. **One responsibility per module** - Each file should have a clear purpose
2. **Avoid circular imports** - Use dependency injection
3. **Group related functionality** - Tools, nodes, utilities
4. **Clear naming** - Module names reflect their purpose

### 5.2 Naming Conventions

**Files**:
- `snake_case.py` - Python modules
- `PascalCase` - Classes
- `UPPER_CASE.md` - Documentation files

**Functions and Variables**:
```python
# ✓ Good
def build_skills_catalog(skill_registry: SkillRegistry) -> str:
    enabled_skills = skill_registry.get_enabled_skills()
    return format_catalog(enabled_skills)

# ✗ Bad
def BuildSkillsCatalog(sr):
    es = sr.GetEnabledSkills()
    return FormatCatalog(es)
```

**Classes**:
```python
# ✓ Good
class ToolRegistry:
    def register_tool(self, tool: BaseTool) -> None:
        pass

# ✗ Bad
class tool_registry:
    def RegisterTool(self, t):
        pass
```

**Constants**:
```python
# ✓ Good
MAX_LOOPS = 100
DEFAULT_TIMEOUT = 30
SKILL_CONFIG_PATH = "generalAgent/config/skills.yaml"

# ✗ Bad
maxLoops = 100
default_timeout = 30
skillConfigPath = "generalAgent/config/skills.yaml"
```

**Environment Variables**:
```python
# ✓ Good
MODEL_BASE_API_KEY
MODEL_REASON_BASE_URL
AGENT_WORKSPACE_PATH

# ✗ Bad
modelBaseApiKey
model_reason_url
agentWorkspace
```

### 5.3 Error Handling Patterns

**Pattern 1: Return Error Messages (Tools)**

Tools should return error messages instead of raising exceptions:

```python
# ✓ Good
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""
    try:
        workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
        abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        LOGGER.error(f"Failed to read file: {e}", exc_info=True)
        return f"Error: {e}"

# ✗ Bad
@tool
def read_file(file_path: str) -> str:
    """Read file from workspace"""
    # Raises exception - agent can't handle it
    workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
    abs_path = resolve_workspace_path(file_path, workspace_root, must_exist=True)

    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()
```

**Pattern 2: Graceful Degradation (Services)**

Services should degrade gracefully when features are unavailable:

```python
# ✓ Good
def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    try:
        subprocess.run([...], check=True, timeout=120)
        self._skill_registry.mark_dependencies_installed(skill_id)

    except subprocess.CalledProcessError as e:
        # Don't fail the whole session, just warn
        LOGGER.warning(f"Failed to install dependencies for '{skill_id}': {e}")
        LOGGER.warning("Skill scripts may not work. Manual installation required.")

    except subprocess.TimeoutExpired:
        LOGGER.warning(f"Dependency installation timeout for '{skill_id}'")

# ✗ Bad
def _install_skill_dependencies(self, skill_id: str, requirements_file: Path):
    # Raises exception - whole session fails
    subprocess.run([...], check=True, timeout=120)
    self._skill_registry.mark_dependencies_installed(skill_id)
```

**Pattern 3: Error Boundary Decorator**

Use decorators to centralize error handling:

```python
# ✓ Good
from generalAgent.tools.decorators import with_error_boundary

@tool
@with_error_boundary
def my_tool(param: str) -> str:
    """My tool"""
    # No try-except needed
    return process(param)

# ✗ Bad
@tool
def my_tool(param: str) -> str:
    """My tool"""
    try:
        return process(param)
    except Exception as e:
        # Duplicated error handling in every tool
        return f"Error: {e}"
```

### 5.4 Logging Guidelines

**Logging Levels**:

- `DEBUG` - Detailed information for debugging
- `INFO` - General information about execution
- `WARNING` - Something unexpected but not critical
- `ERROR` - Errors that should be investigated

**Setup Logging**:

```python
# generalAgent/__init__.py
import logging

def setup_logging(level=logging.INFO):
    """Setup structured logging"""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("logs/app.log"),
            logging.StreamHandler(),
        ],
    )
```

**Use Module Logger**:

```python
import logging

LOGGER = logging.getLogger(__name__)  # Use module name

def my_function():
    LOGGER.info("Function called")
    LOGGER.debug(f"Param value: {param}")
    LOGGER.warning("Unexpected condition")
    LOGGER.error("Operation failed", exc_info=True)
```

**Logging Best Practices**:

```python
# ✓ Good - Structured and informative
LOGGER.info(f"Loading tool on-demand: {tool_name}")
LOGGER.info(f"✓ Tool loaded: {tool_name}")
LOGGER.warning(f"✗ Tool not found: {tool_name}")
LOGGER.error(f"Failed to load tool '{tool_name}': {e}", exc_info=True)

# ✗ Bad - Vague and inconsistent
LOGGER.info("Loading tool")
LOGGER.info("Done")
LOGGER.warning("Not found")
LOGGER.error("Error")
```

**Log Prompt Truncation**:

```python
# For long prompts
max_length = 500
if len(system_prompt) > max_length:
    preview = system_prompt[:max_length] + f"... ({len(system_prompt)} chars)"
else:
    preview = system_prompt

LOGGER.debug(f"System prompt:\n{preview}")
```

### 5.5 Configuration Management

**Use Pydantic Settings**:

```python
# ✓ Good - Type-safe, validated, auto-loaded
from generalAgent.config.settings import get_settings

settings = get_settings()
max_loops = settings.governance.max_loops  # From .env, validated

# ✗ Bad - Manual parsing, no validation
import os

max_loops = int(os.getenv("MAX_LOOPS", "100"))  # Error-prone
```

**Configuration Hierarchy**:

1. **Environment variables** (.env file)
2. **Default values** (Pydantic Field defaults)
3. **Runtime overrides** (function parameters)

**YAML Configuration**:

```python
# ✓ Good - Centralized configuration
# generalAgent/config/tools.yaml
optional:
  http_fetch:
    enabled: true
    category: "network"
    tags: ["network", "read"]

# Load with type-safe loader
from generalAgent.tools.config_loader import load_tool_config
config = load_tool_config()
enabled_tools = config.get_all_enabled_tools()

# ✗ Bad - Hardcoded in Python
ENABLED_TOOLS = {"http_fetch", "extract_links"}  # Hard to maintain
```

### 5.6 Path Handling

**Always Use Path Objects**:

```python
from pathlib import Path

# ✓ Good
workspace_root = Path(os.environ.get("AGENT_WORKSPACE_PATH"))
file_path = workspace_root / "uploads" / "data.txt"

if file_path.exists():
    content = file_path.read_text()

# ✗ Bad
workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")
file_path = os.path.join(workspace_root, "uploads", "data.txt")

if os.path.exists(file_path):
    with open(file_path, "r") as f:
        content = f.read()
```

**Security: Validate Paths**:

```python
from generalAgent.utils.file_processor import resolve_workspace_path

# ✓ Good - Validates path is within workspace
abs_path = resolve_workspace_path(
    file_path,
    workspace_root,
    must_exist=True,
    allow_write=False,
)

# ✗ Bad - No validation, path traversal vulnerability
abs_path = workspace_root / file_path  # Allows ../../../etc/passwd
```

**Project Root Resolution**:

```python
from generalAgent.config.project_root import resolve_project_path

# ✓ Good - Works from any directory
skills_root = resolve_project_path("generalAgent/skills")
config_path = resolve_project_path("generalAgent/config/tools.yaml")

# ✗ Bad - Breaks when running from different directory
skills_root = Path("generalAgent/skills")  # Only works from project root
```

---

## Part 6: Debugging and Troubleshooting

### 6.1 Logging and Tracing

**Enable Debug Logging**:

```bash
# In .env
LOG_LEVEL=DEBUG

# Or at runtime
export LOG_LEVEL=DEBUG
python main.py
```

**Check Logs**:

```bash
# View latest log
tail -f logs/agentgraph_*.log

# Search for errors
grep "ERROR" logs/agentgraph_*.log

# Search for specific tool
grep "read_file" logs/agentgraph_*.log
```

**Log Files Location**:

```
logs/
├── agentgraph_20250124.log      # Daily log files
├── agentgraph_20250125.log
└── error.log                     # Error-only log (if configured)
```

### 6.2 LangSmith Integration

**Enable LangSmith Tracing**:

```bash
# In .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=my-project
LANGCHAIN_API_KEY=your-api-key
```

**View Traces**:

1. Go to https://smith.langchain.com
2. Select your project
3. View traces for each conversation turn

**Trace Information**:

- Input/output for each node
- Tool calls and results
- Token usage
- Latency
- Errors

**Debug with LangSmith**:

```python
# Add custom metadata to traces
from langchain_core.tracers import ConsoleCallbackHandler

# In your code
result = agent.invoke(
    input_data,
    config={
        "callbacks": [ConsoleCallbackHandler()],
        "metadata": {
            "session_id": session_id,
            "user_id": user_id,
        }
    }
)
```

### 6.3 Common Issues

#### Issue 1: Tools Not Loading

**Symptoms**:
- Tool not available when @mentioned
- "Tool not found" error

**Debug**:

```bash
# Check tool configuration
cat generalAgent/config/tools.yaml | grep my_tool

# Check tool file exists
ls generalAgent/tools/builtin/my_tool.py

# Check logs
grep "Scanning tools" logs/agentgraph_*.log
grep "my_tool" logs/agentgraph_*.log
```

**Solutions**:

1. **Check tool is enabled** in `tools.yaml`:
   ```yaml
   optional:
     my_tool:
       enabled: true  # Must be true for startup loading
   ```

2. **Check __all__ export**:
   ```python
   __all__ = ["my_tool"]  # Must be exported
   ```

3. **Check tool decorator**:
   ```python
   @tool  # Must have decorator
   def my_tool(...):
       pass
   ```

#### Issue 2: Skills Not Auto-Loading

**Symptoms**:
- Skill doesn't load when file uploaded
- No file upload hints shown

**Debug**:

```bash
# Check skill configuration
cat generalAgent/config/skills.yaml | grep my-skill

# Check file type configuration
grep "auto_load_on_file_types" generalAgent/config/skills.yaml

# Check logs
grep "auto-load" logs/agentgraph_*.log
grep "my-skill" logs/agentgraph_*.log
```

**Solutions**:

1. **Check auto-load is enabled**:
   ```yaml
   global:
     auto_load_on_file_upload: true
   ```

2. **Check file type matches**:
   ```yaml
   optional:
     my-skill:
       auto_load_on_file_types: ["txt", "csv"]  # Must match file extension
   ```

3. **Check file extension parsing** in logs:
   ```
   [INFO] File uploaded: data.txt (extension: txt)
   [INFO] Auto-loading skill: my-skill
   ```

#### Issue 3: Model API Errors

**Symptoms**:
- "API key not found" error
- "Connection refused" error
- "Model not found" error

**Debug**:

```bash
# Check environment variables
echo $MODEL_BASE_API_KEY
echo $MODEL_BASE_BASE_URL

# Check .env file
cat .env | grep MODEL_BASE

# Check logs
grep "MODEL" logs/agentgraph_*.log
grep "API" logs/agentgraph_*.log
```

**Solutions**:

1. **Verify API key** in `.env`:
   ```bash
   MODEL_BASE_API_KEY=sk-xxx  # Must be valid key
   ```

2. **Verify base URL**:
   ```bash
   MODEL_BASE_BASE_URL=https://api.deepseek.com  # Must be correct endpoint
   ```

3. **Test API manually**:
   ```bash
   curl -X POST https://api.deepseek.com/v1/chat/completions \
     -H "Authorization: Bearer $MODEL_BASE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'
   ```

#### Issue 4: Workspace Permission Errors

**Symptoms**:
- "Permission denied" error
- "Cannot write to skills/" error

**Debug**:

```bash
# Check workspace permissions
ls -la data/workspace/session_123/

# Check logs
grep "Permission" logs/agentgraph_*.log
grep "write" logs/agentgraph_*.log
```

**Solutions**:

1. **Check write directory**:
   ```python
   # ✓ Can write to these
   "outputs/result.txt"
   "temp/cache.json"
   "uploads/data.txt"

   # ✗ Cannot write to these
   "skills/pdf/SKILL.md"  # Read-only
   "../../../etc/passwd"  # Outside workspace
   ```

2. **Use resolve_workspace_path**:
   ```python
   abs_path = resolve_workspace_path(
       file_path,
       workspace_root,
       allow_write=True,  # Check write permission
   )
   ```

### 6.4 Debug Tools

#### Interactive Python Shell

```bash
# Start Python shell with project imports
python -i -c "from generalAgent.config.settings import get_settings; settings = get_settings()"

# Now you can inspect settings
>>> settings.governance.max_loops
100
>>> settings.models.base_api_key
'sk-xxx'
```

#### Tool Testing Script

```python
# test_tool.py
from generalAgent.tools.registry import ToolRegistry
from generalAgent.tools.scanner import scan_tools_directory
from pathlib import Path

# Setup
registry = ToolRegistry()
tools_dir = Path("generalAgent/tools/builtin")
tools = scan_tools_directory(tools_dir)

for tool in tools:
    registry.register_tool(tool)

# Test tool
my_tool = registry.get_tool("read_file")
result = my_tool.invoke({"file_path": "test.txt"})
print(result)
```

#### Skill Testing Script

```python
# test_skill.py
from generalAgent.skills.registry import SkillRegistry
from pathlib import Path

# Setup
registry = SkillRegistry(skills_root=Path("generalAgent/skills"))

# Test skill
skill = registry.get_skill("pdf")
print(f"Skill: {skill.name}")
print(f"Path: {skill.path}")
print(f"SKILL.md exists: {(skill.path / 'SKILL.md').exists()}")
```

---

## Part 7: Contributing

### 7.1 Code Style

**Python Style Guide**:

- Follow PEP 8
- Use Black for formatting (line length: 88)
- Use isort for import sorting
- Use type hints

**Formatting Tools**:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Format code with Black
black generalAgent/ tests/

# Sort imports
isort generalAgent/ tests/

# Check with flake8
flake8 generalAgent/ tests/
```

**Pre-commit Hook** (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

**Install pre-commit**:

```bash
pip install pre-commit
pre-commit install
```

### 7.2 Testing Requirements

**Test Coverage**:

- Minimum 80% coverage for new code
- All critical paths must have tests
- Integration tests for user-facing features

**Run Tests**:

```bash
# Quick smoke tests
python tests/run_tests.py smoke

# Full test suite
python tests/run_tests.py all

# Coverage report
python tests/run_tests.py coverage
```

**Test Pyramid**:

```
        E2E Tests (Few)
       ╱              ╲
      ╱  Integration  ╲
     ╱                ╲
    ╱   Unit Tests    ╲
   ╱     (Many)       ╲
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

**Required Tests**:

1. **Unit tests** - For all new functions/classes
2. **Integration tests** - For feature workflows
3. **E2E tests** - For critical user journeys (optional)

### 7.3 Documentation

**Required Documentation**:

1. **Docstrings** - For all public functions/classes
2. **CHANGELOG.md** - For all changes
3. **Code comments** - For complex logic
4. **README updates** - For new features

**Docstring Format**:

```python
def my_function(param1: str, param2: int) -> str:
    """One-line summary of function.

    Detailed description of what the function does.
    Can be multiple paragraphs.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is invalid
        FileNotFoundError: When file not found

    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        'test-42'
    """
    pass
```

### 7.4 Pull Request Process

**Before Submitting PR**:

1. **Run tests**: `python tests/run_tests.py all`
2. **Format code**: `black generalAgent/ tests/`
3. **Check style**: `flake8 generalAgent/ tests/`
4. **Update CHANGELOG.md**
5. **Update documentation**

**PR Template**:

```markdown
## Description

Brief description of changes.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing locally

## Checklist

- [ ] Code follows project style
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No breaking changes (or documented)
- [ ] Tests added/updated
- [ ] All tests pass

## Related Issues

Fixes #123
Related to #456
```

**Review Process**:

1. **Automated checks** - CI/CD runs tests
2. **Code review** - Maintainer reviews code
3. **Feedback** - Address review comments
4. **Approval** - At least one approval required
5. **Merge** - Squash and merge

---

## Summary

This development guide covers:

1. **Environment Setup** - Installation, configuration, model setup
2. **Developing Tools** - Creating, configuring, testing tools
3. **Developing Skills** - Skill structure, scripts, configuration
4. **Extending the System** - Custom nodes, routing, services
5. **Best Practices** - Code organization, error handling, logging
6. **Debugging** - Logging, tracing, common issues
7. **Contributing** - Code style, testing, documentation, PRs

For more details, see:
- [CLAUDE.md](CLAUDE.md) - Project overview and architecture
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Comprehensive testing guide
- [REQUIREMENTS_PART4_TRICKS.md](REQUIREMENTS_PART4_TRICKS.md) - Implementation tricks
- [SKILLS_CONFIGURATION.md](SKILLS_CONFIGURATION.md) - Skills configuration guide
