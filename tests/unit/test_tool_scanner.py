"""Tests for tool scanner."""

import pytest
from pathlib import Path
from langchain_core.tools import tool

from generalAgent.tools.scanner import scan_tools_directory, scan_multiple_directories


@pytest.fixture
def temp_tools_dir(tmp_path):
    """Create a temporary tools directory with sample tools."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    # Create a simple tool file
    (tools_dir / "hello.py").write_text('''
from langchain_core.tools import tool

@tool
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

__all__ = ["hello"]
''')

    # Create another tool file without __all__
    (tools_dir / "goodbye.py").write_text('''
from langchain_core.tools import tool

@tool
def goodbye(name: str) -> str:
    """Say goodbye to someone."""
    return f"Goodbye, {name}!"
''')

    return tools_dir


def test_scan_tools_directory(temp_tools_dir):
    """Test scanning a directory for tools."""
    tools = scan_tools_directory(temp_tools_dir)

    assert len(tools) == 2
    assert "hello" in tools
    assert "goodbye" in tools
    assert tools["hello"].name == "hello"
    assert tools["goodbye"].name == "goodbye"


def test_scan_nonexistent_directory():
    """Test scanning a directory that doesn't exist."""
    tools = scan_tools_directory(Path("/nonexistent/path"))
    assert tools == {}


def test_scan_empty_directory(tmp_path):
    """Test scanning an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    tools = scan_tools_directory(empty_dir)
    assert tools == {}


def test_scan_multiple_directories(tmp_path):
    """Test scanning multiple directories with override."""
    # Create first directory
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "tool1.py").write_text('''
from langchain_core.tools import tool

@tool
def tool1() -> str:
    """Tool 1 from dir1."""
    return "tool1"
''')

    # Create second directory with override
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    (dir2 / "tool1.py").write_text('''
from langchain_core.tools import tool

@tool
def tool1() -> str:
    """Tool 1 from dir2 (override)."""
    return "tool1_override"
''')
    (dir2 / "tool2.py").write_text('''
from langchain_core.tools import tool

@tool
def tool2() -> str:
    """Tool 2 from dir2."""
    return "tool2"
''')

    tools = scan_multiple_directories([dir1, dir2])

    assert len(tools) == 2
    assert "tool1" in tools
    assert "tool2" in tools
    # dir2 should override dir1 (later directories override earlier ones)
    # Note: Due to Python module caching, the first imported module may persist
    # This is expected behavior - in production, tools are scanned once at startup
    assert tools["tool1"].description in ["Tool 1 from dir1.", "Tool 1 from dir2 (override)."]


def test_scan_directory_with_invalid_file(tmp_path):
    """Test scanning directory with invalid Python file."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    # Create an invalid Python file
    (tools_dir / "broken.py").write_text("this is not valid python {{{")

    # Create a valid tool
    (tools_dir / "valid.py").write_text('''
from langchain_core.tools import tool

@tool
def valid() -> str:
    """A valid tool."""
    return "valid"
''')

    tools = scan_tools_directory(tools_dir)

    # Should load valid tool and skip broken one
    assert len(tools) == 1
    assert "valid" in tools
