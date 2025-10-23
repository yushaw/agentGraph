"""Integration tests for workspace isolation system.

Tests the complete workflow:
1. Create workspace
2. Load skills via @mention
3. Read skill documentation
4. Execute skill scripts
5. Read/write files
6. Cleanup
"""

import json
import os
from pathlib import Path

import pytest

from agentgraph.persistence.workspace import WorkspaceManager
from agentgraph.tools.builtin.file_ops import read_file, write_file, list_workspace_files
from agentgraph.tools.builtin.run_skill_script import run_skill_script


@pytest.fixture
def integration_setup(tmp_path):
    """Setup complete environment for integration testing."""
    # Create skills directory
    skills_root = tmp_path / "skills"
    skills_root.mkdir()

    # Create PDF skill
    pdf_skill = skills_root / "pdf"
    pdf_skill.mkdir()

    # Add skill documentation
    (pdf_skill / "SKILL.md").write_text("""# PDF Processing Skill

## Overview
This skill helps with PDF form filling and processing.

## Usage
1. Read this documentation: `read_file("skills/pdf/SKILL.md")`
2. Read forms guide: `read_file("skills/pdf/forms.md")`
3. Run script: `run_skill_script(skill_id="pdf", script_name="fill_form.py", args=...)`

## Scripts
- `fill_form.py` - Fill PDF forms
- `extract_info.py` - Extract form information
""")

    (pdf_skill / "forms.md").write_text("""# PDF Form Filling Guide

## Step-by-step
1. Upload PDF to workspace
2. Run fill_form.py with input/output paths
3. Download filled PDF
""")

    # Add scripts
    scripts_dir = pdf_skill / "scripts"
    scripts_dir.mkdir()

    # Fill form script
    (scripts_dir / "fill_form.py").write_text("""
import sys
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input-pdf", required=True)
parser.add_argument("--output-pdf", required=True)
parser.add_argument("--data", required=True)
args = parser.parse_args()

# Read input PDF
input_path = Path(args.input_pdf)
if not input_path.exists():
    print(f"Error: Input PDF not found: {args.input_pdf}", file=sys.stderr)
    sys.exit(1)

print(f"Reading input PDF: {args.input_pdf}")
input_content = input_path.read_text()

# Simulate filling form
print(f"Filling form with data: {args.data}")
filled_content = f"{input_content}\\n\\nFilled with: {args.data}"

# Write output
output_path = Path(args.output_pdf)
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(filled_content)

print(f"✓ Filled PDF saved to: {args.output_pdf}")
""")

    # Extract info script
    (scripts_dir / "extract_info.py").write_text("""
import sys
from pathlib import Path

input_path = Path("uploads/form.pdf")
if input_path.exists():
    print("Form structure:")
    print("- Field 1: Name (text)")
    print("- Field 2: Age (number)")
    print("- Field 3: Email (text)")
else:
    print("No PDF found in uploads/", file=sys.stderr)
    sys.exit(1)
""")

    # Create workspace root
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()

    return {
        "skills_root": skills_root,
        "workspace_root": workspace_root,
        "tmp_path": tmp_path
    }


@pytest.fixture(autouse=True)
def setup_environment(integration_setup):
    """Setup environment for each test."""
    # Change to tmp directory so skills/ path resolves correctly
    import os
    old_cwd = os.getcwd()
    os.chdir(integration_setup["tmp_path"])
    yield
    os.chdir(old_cwd)


def test_complete_pdf_workflow(integration_setup):
    """Test complete PDF form filling workflow."""
    workspace_root = integration_setup["workspace_root"]
    manager = WorkspaceManager(workspace_root)

    # ========== Step 1: Create workspace with PDF skill ==========
    print("\n[Step 1] Creating workspace with PDF skill...")
    session_id = "test-session-001"
    workspace = manager.create_session_workspace(
        session_id=session_id,
        mentioned_skills=["pdf"]
    )

    assert workspace.exists()
    assert (workspace / "skills" / "pdf").exists()
    print(f"✓ Workspace created: {workspace}")

    # Set environment variable for tools
    os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

    # ========== Step 2: Read skill documentation ==========
    print("\n[Step 2] Reading skill documentation...")

    skill_doc = read_file.invoke({"path": "skills/pdf/SKILL.md"})
    assert "PDF Processing Skill" in skill_doc
    assert "fill_form.py" in skill_doc
    print("✓ Read SKILL.md")

    forms_guide = read_file.invoke({"path": "skills/pdf/forms.md"})
    assert "PDF Form Filling Guide" in forms_guide
    print("✓ Read forms.md")

    # ========== Step 3: Upload PDF file ==========
    print("\n[Step 3] Uploading PDF file...")

    upload_result = write_file.invoke({
        "path": "uploads/form.pdf",
        "content": "PDF FORM CONTENT\n[Name] [Age] [Email]"
    })
    assert "Success" in upload_result
    print("✓ Uploaded form.pdf")

    # Verify upload
    uploaded_pdf = read_file.invoke({"path": "uploads/form.pdf"})
    assert "PDF FORM CONTENT" in uploaded_pdf

    # ========== Step 4: Extract form information ==========
    print("\n[Step 4] Extracting form information...")

    extract_result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "extract_info.py"
    })
    assert "Form structure" in extract_result
    assert "Field 1: Name" in extract_result
    print("✓ Extracted form structure")

    # ========== Step 5: Fill PDF form ==========
    print("\n[Step 5] Filling PDF form...")

    fill_result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "fill_form.py",
        "arguments": json.dumps({
            "input-pdf": "uploads/form.pdf",
            "output-pdf": "outputs/filled_form.pdf",
            "data": "Name=John Doe, Age=30, Email=john@example.com"
        })
    })
    assert "Error" not in fill_result
    assert "Filled PDF saved" in fill_result
    print("✓ Filled PDF form")

    # ========== Step 6: Verify output ==========
    print("\n[Step 6] Verifying output...")

    output_pdf = read_file.invoke({"path": "outputs/filled_form.pdf"})
    assert "PDF FORM CONTENT" in output_pdf
    assert "Filled with: Name=John Doe" in output_pdf
    print("✓ Output verified")

    # ========== Step 7: List all files ==========
    print("\n[Step 7] Listing workspace files...")

    files_list = list_workspace_files.invoke({"directory": "."})
    assert "uploads/" in files_list
    assert "outputs/" in files_list
    assert "skills/" in files_list
    print("✓ Listed files")

    # ========== Step 8: Get workspace info ==========
    print("\n[Step 8] Getting workspace info...")

    info = manager.get_workspace_info(session_id)
    assert info["exists"]
    assert info["uploads_count"] >= 1
    assert info["outputs_count"] >= 1
    assert "pdf" in info["mentioned_skills"]
    print(f"✓ Workspace info: {json.dumps(info, indent=2)}")

    print("\n✅ Complete workflow test passed!")


def test_multi_skill_workflow(integration_setup):
    """Test workflow with multiple skills."""
    workspace_root = integration_setup["workspace_root"]
    skills_root = integration_setup["skills_root"]

    # Add another skill
    excel_skill = skills_root / "excel"
    excel_skill.mkdir()
    (excel_skill / "SKILL.md").write_text("# Excel Skill\nProcessing Excel files")

    manager = WorkspaceManager(workspace_root)

    # Create workspace
    session_id = "multi-skill-session"
    workspace = manager.create_session_workspace(
        session_id=session_id,
        mentioned_skills=["pdf"]
    )

    os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

    # Read PDF skill
    pdf_doc = read_file.invoke({"path": "skills/pdf/SKILL.md"})
    assert "PDF Processing Skill" in pdf_doc

    # Add Excel skill later
    manager.create_session_workspace(
        session_id=session_id,
        mentioned_skills=["excel"]
    )

    # Now both skills should be available
    excel_doc = read_file.invoke({"path": "skills/excel/SKILL.md"})
    assert "Excel Skill" in excel_doc

    # Verify both in metadata
    info = manager.get_workspace_info(session_id)
    assert set(info["mentioned_skills"]) == {"pdf", "excel"}


def test_error_handling_workflow(integration_setup):
    """Test error handling in workflow."""
    workspace_root = integration_setup["workspace_root"]
    manager = WorkspaceManager(workspace_root)

    session_id = "error-test-session"
    workspace = manager.create_session_workspace(
        session_id=session_id,
        mentioned_skills=["pdf"]
    )

    os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

    # Try to read nonexistent file
    result = read_file.invoke({"path": "nonexistent.txt"})
    assert "Error: File not found" in result

    # Try to write to forbidden directory
    result = write_file.invoke({
        "path": "skills/pdf/malicious.txt",
        "content": "attack"
    })
    assert "Error" in result

    # Try to run nonexistent script
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "nonexistent.py"
    })
    assert "Error: Script not found" in result

    # Try path traversal
    result = read_file.invoke({"path": "../../../etc/passwd"})
    assert "Error" in result


def test_cleanup_workflow(integration_setup):
    """Test workspace cleanup."""
    workspace_root = integration_setup["workspace_root"]
    manager = WorkspaceManager(workspace_root)

    # Create multiple sessions
    for i in range(3):
        manager.create_session_workspace(f"session-{i}")

    # Verify all exist
    assert manager.get_workspace(f"session-0") is not None
    assert manager.get_workspace(f"session-1") is not None
    assert manager.get_workspace(f"session-2") is not None

    # Make session-0 old
    import time
    old_workspace = manager.get_workspace("session-0")
    metadata = json.loads((old_workspace / ".metadata.json").read_text())
    metadata["created_at"] = time.time() - (8 * 86400)  # 8 days old
    (old_workspace / ".metadata.json").write_text(json.dumps(metadata))

    # Cleanup
    cleaned = manager.cleanup_old_workspaces(days=7)
    assert cleaned == 1

    # Verify session-0 deleted, others remain
    assert manager.get_workspace("session-0") is None
    assert manager.get_workspace("session-1") is not None
    assert manager.get_workspace("session-2") is not None


def test_concurrent_operations(integration_setup):
    """Test multiple operations in same workspace."""
    workspace_root = integration_setup["workspace_root"]
    manager = WorkspaceManager(workspace_root)

    session_id = "concurrent-session"
    workspace = manager.create_session_workspace(
        session_id=session_id,
        mentioned_skills=["pdf"]
    )

    os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

    # Perform multiple operations concurrently (simulated)
    operations = []

    # Write multiple files
    for i in range(5):
        result = write_file.invoke({
            "path": f"outputs/file{i}.txt",
            "content": f"Content {i}"
        })
        operations.append(result)
        assert "Success" in result

    # Read all files
    for i in range(5):
        result = read_file.invoke({"path": f"outputs/file{i}.txt"})
        operations.append(result)
        assert f"Content {i}" in result

    # All operations should succeed
    assert len(operations) == 10


def test_skill_script_with_dependencies(integration_setup):
    """Test skill script that uses workspace files."""
    workspace_root = integration_setup["workspace_root"]
    manager = WorkspaceManager(workspace_root)

    session_id = "deps-session"
    workspace = manager.create_session_workspace(
        session_id=session_id,
        mentioned_skills=["pdf"]
    )

    os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

    # Create input file
    write_file.invoke({
        "path": "uploads/form.pdf",
        "content": "Original PDF"
    })

    # Run script that processes it
    result = run_skill_script.invoke({
        "skill_id": "pdf",
        "script_name": "fill_form.py",
        "arguments": json.dumps({
            "input-pdf": "uploads/form.pdf",
            "output-pdf": "outputs/result.pdf",
            "data": "TestData"
        })
    })

    assert "Filled PDF saved" in result

    # Verify output
    output = read_file.invoke({"path": "outputs/result.pdf"})
    assert "Original PDF" in output
    assert "Filled with: TestData" in output


if __name__ == "__main__":
    """Run integration tests with detailed output."""
    print("\n" + "=" * 70)
    print("Integration Tests: Workspace Isolation System")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
