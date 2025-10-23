"""Execute bash commands in isolated workspace."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

LOGGER = logging.getLogger(__name__)


@tool
def run_bash_command(
    command: Annotated[str, "Bash command to execute (e.g., 'ls -la', 'cat file.txt')"],
    timeout: Annotated[int, "Timeout in seconds"] = 30
) -> str:
    """Execute a bash command in the workspace directory.

    WARNING: This tool is powerful and should be used carefully.
    - Commands run in workspace directory
    - Limited to 30s timeout by default
    - No network access recommended

    Examples:
        run_bash_command("ls -la uploads/")
        run_bash_command("wc -l outputs/*.txt")
        run_bash_command("head -n 20 uploads/data.csv")

    Args:
        command: Bash command string
        timeout: Execution timeout in seconds

    Returns:
        Command output or error
    """
    try:
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured."

        workspace_path = Path(workspace_root).resolve()

        LOGGER.info(f"Executing bash command: {command}")

        # Execute in workspace
        result = subprocess.run(
            command,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,  # Allow shell commands
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        if result.returncode != 0:
            return f"Command failed (exit code {result.returncode}):\n{output}"

        return output or "Command completed (no output)"

    except subprocess.TimeoutExpired:
        return f"Error: Command timeout ({timeout}s)"

    except Exception as e:
        LOGGER.error(f"Failed to execute command: {e}")
        return f"Error: {str(e)}"
