"""Test script execution tool (run_bash_command)."""

import os
from pathlib import Path

import pytest

from generalAgent.tools.builtin.run_bash_command import run_bash_command


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create workspace directories
    (workspace / "uploads").mkdir()
    (workspace / "outputs").mkdir()
    (workspace / "temp").mkdir()

    # Add test input file
    (workspace / "uploads" / "input.txt").write_text("test data")

    return workspace


@pytest.fixture(autouse=True)
def set_workspace_env(temp_workspace):
    """Set AGENT_WORKSPACE_PATH environment variable."""
    old_value = os.environ.get("AGENT_WORKSPACE_PATH")
    os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace)
    yield
    if old_value is None:
        os.environ.pop("AGENT_WORKSPACE_PATH", None)
    else:
        os.environ["AGENT_WORKSPACE_PATH"] = old_value


# ========== run_bash_command tests ==========

def test_run_bash_simple_command(temp_workspace):
    """Test running simple bash command."""
    result = run_bash_command.invoke({
        "command": "echo 'Hello from bash'"
    })

    assert "Error" not in result
    assert "Hello from bash" in result


def test_run_bash_list_files(temp_workspace):
    """Test listing files with bash."""
    result = run_bash_command.invoke({
        "command": "ls -la"
    })

    assert "Error" not in result
    assert "uploads" in result
    assert "outputs" in result


def test_run_bash_count_lines(temp_workspace):
    """Test counting lines in file."""
    result = run_bash_command.invoke({
        "command": "wc -l uploads/input.txt"
    })

    assert "Error" not in result
    assert "uploads/input.txt" in result


def test_run_bash_pipe_commands(temp_workspace):
    """Test piping bash commands."""
    result = run_bash_command.invoke({
        "command": "ls uploads/ | wc -l"
    })

    assert "Error" not in result
    # Should count files in uploads/


def test_run_bash_create_file(temp_workspace):
    """Test creating file with bash."""
    result = run_bash_command.invoke({
        "command": "echo 'Created by bash' > outputs/bash_test.txt"
    })

    assert "Error" not in result or result.strip() == ""

    # Verify file created
    output_file = temp_workspace / "outputs" / "bash_test.txt"
    assert output_file.exists()
    assert "Created by bash" in output_file.read_text()


def test_run_bash_timeout(temp_workspace):
    """Test bash command timeout."""
    result = run_bash_command.invoke({
        "command": "sleep 20",
        "timeout": 1
    })

    assert "Error: Command timeout" in result


def test_run_bash_command_error(temp_workspace):
    """Test bash command that fails."""
    result = run_bash_command.invoke({
        "command": "ls nonexistent_directory"
    })

    assert "Command failed" in result or "No such file" in result


def test_run_bash_without_workspace_env(monkeypatch):
    """Test run_bash_command without AGENT_WORKSPACE_PATH set."""
    monkeypatch.delenv("AGENT_WORKSPACE_PATH", raising=False)

    result = run_bash_command.invoke({
        "command": "echo 'test'"
    })

    assert "Error: No workspace configured" in result


def test_run_bash_working_directory(temp_workspace):
    """Test that bash runs in workspace directory."""
    result = run_bash_command.invoke({
        "command": "pwd"
    })

    assert str(temp_workspace) in result


def test_run_bash_python_script(temp_workspace):
    """Test running Python script via bash command."""
    # Create a test script
    script_path = temp_workspace / "outputs" / "test_script.py"
    script_path.write_text("""
import sys
print("Hello from Python script!")
print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}")
""")

    # Note: macOS 上 python 命令可能不存在,需要用 python3 或 sys.executable
    import sys
    python_cmd = sys.executable  # 使用当前 Python 解释器

    result = run_bash_command.invoke({
        "command": f"{python_cmd} {script_path}"
    })

    assert "Error" not in result, f"Unexpected error: {result}"
    assert "Hello from Python script!" in result


if __name__ == "__main__":
    """Run tests with detailed output."""
    print("\n" + "=" * 70)
    print("Testing run_bash_command Tool")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
