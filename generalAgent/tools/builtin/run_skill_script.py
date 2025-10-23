"""Execute skill scripts in isolated workspace."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

from langchain_core.tools import tool

LOGGER = logging.getLogger(__name__)


@tool
def run_skill_script(
    skill_id: Annotated[str, "Skill ID (e.g., 'pdf')"],
    script_name: Annotated[str, "Script filename (e.g., 'fill_fillable_fields.py')"],
    arguments: Annotated[Optional[str], "JSON string of script arguments"] = None,
    timeout: Annotated[int, "Timeout in seconds"] = 30
) -> str:
    """Execute a skill's Python script in isolated workspace.

    The script will run with:
    - Working directory set to workspace root
    - Access to workspace files (uploads/, outputs/, temp/)
    - Timeout protection (default 30s)
    - Output capture (stdout/stderr)

    Examples:
        # Run PDF form filling script
        run_skill_script(
            skill_id="pdf",
            script_name="fill_fillable_fields.py",
            args='{"input_pdf": "uploads/form.pdf", "output_pdf": "outputs/filled.pdf"}'
        )

        # Run without arguments
        run_skill_script(
            skill_id="pdf",
            script_name="extract_form_field_info.py"
        )

    Args:
        skill_id: Skill identifier
        script_name: Python script filename
        args: JSON string of script arguments (optional)
        timeout: Execution timeout in seconds

    Returns:
        Script output (stdout) or error message
    """
    try:
        LOGGER.debug(f"run_skill_script called: skill_id={skill_id}, script_name={script_name}, arguments={arguments!r}, timeout={timeout}")

        # Get workspace root
        workspace_root = os.environ.get("AGENT_WORKSPACE_PATH")

        if not workspace_root:
            return "Error: No workspace configured. Cannot execute scripts."

        workspace_path = Path(workspace_root).resolve()

        # Find script in workspace/skills/{skill_id}/scripts/
        script_path = workspace_path / "skills" / skill_id / "scripts" / script_name

        if not script_path.exists():
            # Fallback: try project skills/ directory
            project_script = Path(f"skills/{skill_id}/scripts/{script_name}")
            if project_script.exists():
                script_path = project_script.resolve()
            else:
                return f"Error: Script not found: skills/{skill_id}/scripts/{script_name}"

        if not script_path.is_file():
            return f"Error: Not a file: {script_path}"

        # Parse arguments
        script_args = []
        if arguments:
            LOGGER.debug(f"Raw arguments input: {arguments!r} (type: {type(arguments)})")
            try:
                args_dict = json.loads(arguments)
                LOGGER.debug(f"Parsed args_dict: {args_dict}")
                # Convert dict to command-line arguments
                # Format: --key value (or just --key for flags)
                for key, value in args_dict.items():
                    # Handle boolean flags (action="store_true")
                    if value == "" or value is True:
                        script_args.append(f"--{key}")
                    # Skip false flags
                    elif value is False or value is None:
                        continue
                    # Regular key-value pairs
                    else:
                        script_args.extend([f"--{key}", str(value)])
            except (json.JSONDecodeError, TypeError) as e:
                return f"Error: Invalid JSON arguments: {e}"

        # Build command
        command = [sys.executable, str(script_path)] + script_args

        LOGGER.info(f"Executing script: {script_name} in {skill_id}")
        LOGGER.info(f"Script args: {script_args}")
        LOGGER.debug(f"Command: {' '.join(command)}")
        LOGGER.debug(f"Working directory: {workspace_path}")

        # Execute with timeout and workspace as cwd
        result = subprocess.run(
            command,
            cwd=workspace_path,  # Key: restrict working directory
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(Path.cwd())}  # Allow imports from project
        )

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        if result.returncode != 0:
            LOGGER.warning(f"Script exited with code {result.returncode}: {script_name}")
            return f"Script execution failed (exit code {result.returncode}):\n{output}"

        LOGGER.info(f"Script completed successfully: {script_name}")
        return output or "Script completed (no output)"

    except subprocess.TimeoutExpired:
        LOGGER.error(f"Script timeout: {script_name}")
        return f"Error: Script execution timeout ({timeout}s)"

    except Exception as e:
        LOGGER.error(f"Failed to execute script {script_name}: {e}")
        return f"Error: {str(e)}"
