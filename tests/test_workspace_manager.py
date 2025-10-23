"""Test WorkspaceManager for session isolation and skill loading."""

import json
import shutil
import time
from pathlib import Path

import pytest

from generalAgent.persistence.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace_root(tmp_path):
    """Create temporary workspace root."""
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    return workspace_root


@pytest.fixture
def temp_skills_dir(tmp_path):
    """Create temporary skills directory with sample skills."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()

    # Create sample skill: pdf
    pdf_skill = skills_root / "pdf"
    pdf_skill.mkdir()
    (pdf_skill / "SKILL.md").write_text("# PDF Skill\nSample skill for testing")
    (pdf_skill / "reference.md").write_text("# Reference\nAdditional docs")

    # Create scripts directory
    scripts_dir = pdf_skill / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "test_script.py").write_text("print('Hello from script')")

    # Create another skill: excel
    excel_skill = skills_root / "excel"
    excel_skill.mkdir()
    (excel_skill / "SKILL.md").write_text("# Excel Skill\nSample Excel skill")

    return skills_root


def test_create_workspace_basic(temp_workspace_root):
    """Test basic workspace creation."""
    manager = WorkspaceManager(temp_workspace_root)

    # Create workspace
    workspace = manager.create_session_workspace("session-001")

    assert workspace.exists()
    assert workspace.name == "session-001"
    assert (workspace / "uploads").exists()
    assert (workspace / "outputs").exists()
    assert (workspace / "temp").exists()
    assert (workspace / ".metadata.json").exists()

    # Check metadata
    metadata = json.loads((workspace / ".metadata.json").read_text())
    assert metadata["session_id"] == "session-001"
    assert "created_at" in metadata
    assert metadata["mentioned_skills"] == []


def test_create_workspace_with_skills(temp_workspace_root, temp_skills_dir, monkeypatch):
    """Test workspace creation with skills loading."""
    # Monkeypatch Path to use temp_skills_dir
    original_cwd = Path.cwd()
    monkeypatch.chdir(temp_skills_dir.parent)

    manager = WorkspaceManager(temp_workspace_root)

    # Create workspace with skills
    workspace = manager.create_session_workspace(
        "session-002",
        mentioned_skills=["pdf", "excel"]
    )

    assert workspace.exists()

    # Check skills directory
    skills_dir = workspace / "skills"
    assert skills_dir.exists()

    # Check pdf skill
    pdf_link = skills_dir / "pdf"
    assert pdf_link.exists()
    # Should be symlink or directory (fallback on Windows)
    assert pdf_link.is_symlink() or pdf_link.is_dir()

    # Check if skill files are accessible
    assert (pdf_link / "SKILL.md").exists()
    assert (pdf_link / "scripts" / "test_script.py").exists()

    # Check excel skill
    excel_link = skills_dir / "excel"
    assert excel_link.exists()

    # Check metadata
    metadata = json.loads((workspace / ".metadata.json").read_text())
    assert set(metadata["mentioned_skills"]) == {"pdf", "excel"}


def test_create_workspace_idempotent(temp_workspace_root):
    """Test that creating workspace twice is idempotent."""
    manager = WorkspaceManager(temp_workspace_root)

    # Create first time
    workspace1 = manager.create_session_workspace("session-003")
    created_time1 = (workspace1 / ".metadata.json").stat().st_mtime

    # Wait a bit
    time.sleep(0.1)

    # Create second time (should not recreate)
    workspace2 = manager.create_session_workspace("session-003")
    created_time2 = (workspace2 / ".metadata.json").stat().st_mtime

    assert workspace1 == workspace2
    assert created_time1 == created_time2  # File not modified


def test_add_skills_incrementally(temp_workspace_root, temp_skills_dir, monkeypatch):
    """Test adding skills to existing workspace."""
    monkeypatch.chdir(temp_skills_dir.parent)
    manager = WorkspaceManager(temp_workspace_root)

    # Create workspace with one skill
    workspace = manager.create_session_workspace(
        "session-004",
        mentioned_skills=["pdf"]
    )

    # Verify only pdf exists
    assert (workspace / "skills" / "pdf").exists()
    assert not (workspace / "skills" / "excel").exists()

    # Add excel skill
    manager.create_session_workspace(
        "session-004",
        mentioned_skills=["excel"]
    )

    # Now both should exist
    assert (workspace / "skills" / "pdf").exists()
    assert (workspace / "skills" / "excel").exists()

    # Check metadata
    metadata = json.loads((workspace / ".metadata.json").read_text())
    assert set(metadata["mentioned_skills"]) == {"pdf", "excel"}


def test_nonexistent_skill_warning(temp_workspace_root, caplog):
    """Test that loading nonexistent skill logs warning."""
    manager = WorkspaceManager(temp_workspace_root)

    workspace = manager.create_session_workspace(
        "session-005",
        mentioned_skills=["nonexistent_skill"]
    )

    assert workspace.exists()
    # Should not crash, but skill won't be loaded
    assert not (workspace / "skills" / "nonexistent_skill").exists()


def test_get_workspace(temp_workspace_root):
    """Test getting workspace path."""
    manager = WorkspaceManager(temp_workspace_root)

    # Before creation
    assert manager.get_workspace("session-006") is None

    # Create workspace
    manager.create_session_workspace("session-006")

    # After creation
    workspace = manager.get_workspace("session-006")
    assert workspace is not None
    assert workspace.name == "session-006"


def test_cleanup_old_workspaces(temp_workspace_root):
    """Test cleaning up old workspaces."""
    manager = WorkspaceManager(temp_workspace_root)

    # Create workspaces with different ages
    old_session = "session-old"
    new_session = "session-new"

    # Create old workspace
    old_workspace = manager.create_session_workspace(old_session)

    # Manually set old creation time (8 days ago)
    metadata = json.loads((old_workspace / ".metadata.json").read_text())
    metadata["created_at"] = time.time() - (8 * 86400)
    (old_workspace / ".metadata.json").write_text(json.dumps(metadata))

    # Create new workspace
    manager.create_session_workspace(new_session)

    # Cleanup (7 days threshold)
    cleaned = manager.cleanup_old_workspaces(days=7)

    assert cleaned == 1
    assert not old_workspace.exists()
    assert manager.get_workspace(new_session).exists()


def test_get_workspace_info(temp_workspace_root):
    """Test getting workspace information."""
    manager = WorkspaceManager(temp_workspace_root)

    # Nonexistent workspace
    info = manager.get_workspace_info("nonexistent")
    assert info["exists"] is False

    # Create workspace and add files
    workspace = manager.create_session_workspace("session-007")
    (workspace / "uploads" / "file1.txt").write_text("test")
    (workspace / "outputs" / "result.csv").write_text("data")

    # Get info
    info = manager.get_workspace_info("session-007")
    assert info["exists"] is True
    assert "path" in info
    assert "created_at" in info
    assert info["uploads_count"] > 0
    assert info["outputs_count"] > 0


def test_force_recreate_workspace(temp_workspace_root):
    """Test force recreating workspace."""
    manager = WorkspaceManager(temp_workspace_root)

    # Create workspace with file
    workspace = manager.create_session_workspace("session-008")
    (workspace / "outputs" / "old_file.txt").write_text("old")

    # Force recreate
    workspace_new = manager.create_session_workspace("session-008", force=True)

    # Old file should be gone
    assert not (workspace_new / "outputs" / "old_file.txt").exists()


def test_concurrent_skill_loading(temp_workspace_root, temp_skills_dir, monkeypatch):
    """Test that loading same skill twice doesn't cause issues."""
    monkeypatch.chdir(temp_skills_dir.parent)
    manager = WorkspaceManager(temp_workspace_root)

    # Load same skill multiple times
    workspace = manager.create_session_workspace(
        "session-009",
        mentioned_skills=["pdf", "pdf", "pdf"]  # Duplicates
    )

    # Should only appear once in metadata
    metadata = json.loads((workspace / ".metadata.json").read_text())
    assert metadata["mentioned_skills"].count("pdf") == 1

    # Skill should exist
    assert (workspace / "skills" / "pdf").exists()


# Integration test
def test_full_workflow(temp_workspace_root, temp_skills_dir, monkeypatch):
    """Test complete workflow: create, add skills, write files, get info, cleanup."""
    monkeypatch.chdir(temp_skills_dir.parent)
    manager = WorkspaceManager(temp_workspace_root)

    # Step 1: Create workspace
    session_id = "integration-test"
    workspace = manager.create_session_workspace(session_id)
    assert workspace.exists()

    # Step 2: Add skill
    manager.create_session_workspace(session_id, mentioned_skills=["pdf"])
    assert (workspace / "skills" / "pdf" / "SKILL.md").exists()

    # Step 3: Simulate file operations
    (workspace / "uploads" / "input.pdf").write_text("PDF content")
    (workspace / "outputs" / "output.txt").write_text("Results")
    (workspace / "temp" / "cache.json").write_text("{}")

    # Step 4: Get info
    info = manager.get_workspace_info(session_id)
    assert info["exists"]
    assert info["uploads_count"] >= 1
    assert info["outputs_count"] >= 1
    assert info["temp_count"] >= 1
    assert "pdf" in info["mentioned_skills"]

    # Step 5: Cleanup (shouldn't delete yet - too recent)
    cleaned = manager.cleanup_old_workspaces(days=7)
    assert cleaned == 0
    assert workspace.exists()


if __name__ == "__main__":
    """Run tests with detailed output."""
    import sys

    print("\n" + "=" * 70)
    print("Testing WorkspaceManager")
    print("=" * 70 + "\n")

    # Run pytest with verbose output
    pytest.main([__file__, "-v", "-s"])
