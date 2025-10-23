"""Test script execution tools (run_skill_script, run_bash_command)."""

import json
import os
import sys
from pathlib import Path

import pytest

from generalAgent.tools.builtin.run_skill_script import run_skill_script
from generalAgent.tools.builtin.run_bash_command import run_bash_command


@pytest.fixture
def temp_workspace_with_skills(tmp_path):
    """Create temporary workspace with skill scripts."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create skills directory
    skills_dir = workspace / "skills"
    skills_dir.mkdir()

    # Create pdf skill with scripts
    pdf_skill = skills_dir / "pdf"
    pdf_skill.mkdir()

    scripts_dir = pdf_skill / "scripts"
    scripts_dir.mkdir()

    # Simple hello script
    hello_script = scripts_dir / "hello.py"
    hello_script.write_text("""
import sys
print("Hello from skill script!")
print(f"Python version: {sys.version}")
""")

    # Script with arguments
    args_script = scripts_dir / "process_args.py"
    args_script.write_text("""
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

print(f"Input: {args.input}")
print(f"Output: {args.output}")
""")

    # Script that reads and writes files
    file_script = scripts_dir / "process_file.py"
    file_script.write_text("""
import sys
from pathlib import Path

# Read from uploads/
input_path = Path("uploads/input.txt")
if input_path.exists():
    content = input_path.read_text()
    print(f"Read: {content}")

    # Write to outputs/
    output_path = Path("outputs/result.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content.upper())
    print("Wrote to outputs/result.txt")
else:
    print("Input file not found", file=sys.stderr)
    sys.exit(1)
""")

    # Script that takes time (for timeout test)
    slow_script = scripts_dir / "slow.py"
    slow_script.write_text("""
import time
print("Starting...")
time.sleep(5)
print("Done!")
""")

    # Script with error
    error_script = scripts_dir / "error.py"
    error_script.write_text("""
import sys
print("Before error")
raise ValueError("Intentional error for testing")
print("After error")  # This won't execute
""")

    # Create workspace directories
    (workspace / "uploads").mkdir()
    (workspace / "outputs").mkdir()
    (workspace / "temp").mkdir()

    # Add test input file
    (workspace / "uploads" / "input.txt").write_text("test data")

    return workspace


@pytest.fixture(autouse=True)
def set_workspace_env(temp_workspace_with_skills):
    """Set AGENT_WORKSPACE_PATH environment variable."""
    old_value = os.environ.get("AGENT_WORKSPACE_PATH")
    os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace_with_skills)
    yield
    if old_value is None:
        os.environ.pop("AGENT_WORKSPACE_PATH", None)
    else:
        os.environ["AGENT_WORKSPACE_PATH"] = old_value


# ========== run_skill_script tests ==========

def test_run_simple_script(temp_workspace_with_skills):
    """Test running simple script without arguments."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "hello.py"
    })

    assert "Error" not in result
    assert "Hello from skill script!" in result
    assert "Python version:" in result


def test_run_script_with_arguments(temp_workspace_with_skills):
    """Test running script with arguments."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "process_args.py",
        "arguments": json.dumps({
            "input": "test_input.pdf",
            "output": "test_output.pdf"
        })
    })

    assert "Error" not in result
    assert "Input: test_input.pdf" in result
    assert "Output: test_output.pdf" in result


def test_run_script_file_operations(temp_workspace_with_skills):
    """Test script that reads and writes files in workspace."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "process_file.py"
    })

    assert "Error" not in result
    assert "Read: test data" in result
    assert "Wrote to outputs/result.txt" in result

    # Verify output file was created
    output_file = temp_workspace_with_skills / "outputs" / "result.txt"
    assert output_file.exists()
    assert output_file.read_text() == "TEST DATA"


def test_run_script_nonexistent_script(temp_workspace_with_skills):
    """Test running nonexistent script."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "nonexistent.py"
    })

    assert "Error: Script not found" in result


def test_run_script_nonexistent_skill(temp_workspace_with_skills):
    """Test running script from nonexistent skill."""
    result = run_skill_script.invoke({
        "skill_id": "nonexistent_skill",
        "script_name": "hello.py"
    })

    assert "Error: Script not found" in result


def test_run_script_with_error(temp_workspace_with_skills):
    """Test running script that raises error."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "error.py"
    })

    assert "Script execution failed" in result
    assert "Before error" in result
    assert "ValueError: Intentional error" in result or "Traceback" in result


def test_run_script_timeout(temp_workspace_with_skills):
    """Test script execution timeout."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "slow.py",
        "timeout": 2  # 2 seconds timeout
    })

    assert "Error: Script execution timeout" in result


def test_run_script_invalid_json_args(temp_workspace_with_skills):
    """Test with invalid JSON arguments."""
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "hello.py",
        "arguments": "invalid json"
    })

    assert "Error: Invalid JSON arguments" in result


def test_run_script_without_workspace_env(monkeypatch):
    """Test run_skill_script without AGENT_WORKSPACE_PATH set."""
    monkeypatch.delenv("AGENT_WORKSPACE_PATH", raising=False)

    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "hello.py"
    })

    assert "Error: No workspace configured" in result


def test_run_script_working_directory(temp_workspace_with_skills):
    """Test that script runs with workspace as cwd."""
    # Create script that checks cwd
    cwd_script = temp_workspace_with_skills / "skills" / "pdf" / "scripts" / "check_cwd.py"
    cwd_script.write_text("""
import os
from pathlib import Path

cwd = Path.cwd()
print(f"CWD: {cwd}")

# Check if we can see workspace directories
print(f"uploads/ exists: {(cwd / 'uploads').exists()}")
print(f"outputs/ exists: {(cwd / 'outputs').exists()}")
""")

    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "check_cwd.py"
    })

    assert "uploads/ exists: True" in result
    assert "outputs/ exists: True" in result


# ========== run_bash_command tests ==========

def test_run_bash_simple_command(temp_workspace_with_skills):
    """Test running simple bash command."""
    result = run_bash_command.invoke({
        "command": "echo 'Hello from bash'"
    })

    assert "Error" not in result
    assert "Hello from bash" in result


def test_run_bash_list_files(temp_workspace_with_skills):
    """Test listing files with bash."""
    result = run_bash_command.invoke({
        "command": "ls -la"
    })

    assert "Error" not in result
    assert "uploads" in result
    assert "outputs" in result
    assert "skills" in result


def test_run_bash_count_lines(temp_workspace_with_skills):
    """Test counting lines in file."""
    result = run_bash_command.invoke({
        "command": "wc -l uploads/input.txt"
    })

    assert "Error" not in result
    assert "uploads/input.txt" in result


def test_run_bash_pipe_commands(temp_workspace_with_skills):
    """Test piping bash commands."""
    result = run_bash_command.invoke({
        "command": "ls uploads/ | wc -l"
    })

    assert "Error" not in result
    # Should count files in uploads/


def test_run_bash_create_file(temp_workspace_with_skills):
    """Test creating file with bash."""
    result = run_bash_command.invoke({
        "command": "echo 'Created by bash' > outputs/bash_test.txt"
    })

    assert "Error" not in result or result.strip() == ""

    # Verify file created
    output_file = temp_workspace_with_skills / "outputs" / "bash_test.txt"
    assert output_file.exists()
    assert "Created by bash" in output_file.read_text()


def test_run_bash_timeout(temp_workspace_with_skills):
    """Test bash command timeout."""
    result = run_bash_command.invoke({
        "command": "sleep 20",
        "timeout": 1
    })

    assert "Error: Command timeout" in result


def test_run_bash_command_error(temp_workspace_with_skills):
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


def test_run_bash_working_directory(temp_workspace_with_skills):
    """Test that bash runs in workspace directory."""
    result = run_bash_command.invoke({
        "command": "pwd"
    })

    assert str(temp_workspace_with_skills) in result


# ========== Integration tests ==========

def test_script_and_bash_integration(temp_workspace_with_skills):
    """Test using script and bash together."""
    # Step 1: Run script to create output
    script_result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "process_file.py"
    })
    assert "Error" not in script_result

    # Step 2: Use bash to verify output
    bash_result = run_bash_command.invoke({
        "command": "cat outputs/result.txt"
    })
    assert "TEST DATA" in bash_result


def test_script_with_multiple_args(temp_workspace_with_skills):
    """Test script with various argument types."""
    # Create script that handles different types
    multi_args_script = temp_workspace_with_skills / "skills" / "pdf" / "scripts" / "multi_args.py"
    multi_args_script.write_text("""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--count", type=int, required=True)
parser.add_argument("--enable", action="store_true")
args = parser.parse_args()

print(f"Name: {args.name}")
print(f"Count: {args.count}")
print(f"Enabled: {args.enable}")
""")

    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "multi_args.py",
        "arguments": json.dumps({
            "name": "test",
            "count": "42",
            "enable": ""
        })
    })

    assert "Name: test" in result
    assert "Count: 42" in result


if __name__ == "__main__":
    """Run tests with detailed output."""
    print("\n" + "=" * 70)
    print("Testing Script Execution Tools")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
