"""Test file operation tools (read_file, write_file, list_workspace_files)."""

import os
from pathlib import Path

import pytest

from generalAgent.tools.builtin.file_ops import read_file, write_file, list_workspace_files


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with sample files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create directory structure
    (workspace / "skills").mkdir()
    (workspace / "uploads").mkdir()
    (workspace / "outputs").mkdir()
    (workspace / "temp").mkdir()

    # Add sample skills
    pdf_skill = workspace / "skills" / "pdf"
    pdf_skill.mkdir(parents=True)
    (pdf_skill / "SKILL.md").write_text("# PDF Skill\nTest documentation")
    (pdf_skill / "forms.md").write_text("# Forms Guide\nHow to fill forms")

    # Add sample uploads
    (workspace / "uploads" / "document.txt").write_text("User uploaded file")

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


# ========== read_file tests ==========

def test_read_file_skill_documentation(temp_workspace):
    """Test reading skill documentation."""
    result = read_file.invoke({"path": "skills/pdf/SKILL.md"})

    assert "Error" not in result
    assert "PDF Skill" in result
    assert "Test documentation" in result


def test_read_file_skill_subdoc(temp_workspace):
    """Test reading skill subdocumentation."""
    result = read_file.invoke({"path": "skills/pdf/forms.md"})

    assert "Error" not in result
    assert "Forms Guide" in result


def test_read_file_uploaded_file(temp_workspace):
    """Test reading user-uploaded file."""
    result = read_file.invoke({"path": "uploads/document.txt"})

    assert "Error" not in result
    assert "User uploaded file" in result


def test_read_file_nonexistent(temp_workspace):
    """Test reading nonexistent file."""
    result = read_file.invoke({"path": "uploads/nonexistent.txt"})

    assert "Error: File not found" in result


def test_read_file_directory(temp_workspace):
    """Test reading directory (should fail)."""
    result = read_file.invoke({"path": "uploads"})

    assert "Error" in result
    assert "Not a file" in result


def test_read_file_path_traversal_attack(temp_workspace):
    """Test path traversal attack prevention."""
    # Try to escape workspace
    result = read_file.invoke({"path": "../../etc/passwd"})

    assert "Error: Access denied" in result or "Error: File not found" in result


def test_read_file_absolute_path_attack(temp_workspace):
    """Test absolute path attack prevention."""
    result = read_file.invoke({"path": "/etc/passwd"})

    assert "Error" in result


def test_read_file_binary_content(temp_workspace):
    """Test reading binary file."""
    # Create binary file
    binary_file = temp_workspace / "uploads" / "image.bin"
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    result = read_file.invoke({"path": "uploads/image.bin"})

    assert "Error" in result
    assert "binary content detected" in result.lower() or "not a text file" in result.lower()


def test_read_file_empty_file(temp_workspace):
    """Test reading empty file."""
    (temp_workspace / "uploads" / "empty.txt").write_text("")

    result = read_file.invoke({"path": "uploads/empty.txt"})

    assert "Error" not in result
    assert result == ""


def test_read_file_large_file(temp_workspace):
    """Test reading large file."""
    # Create 1MB file
    large_content = "x" * (1024 * 1024)
    (temp_workspace / "uploads" / "large.txt").write_text(large_content)

    result = read_file.invoke({"path": "uploads/large.txt"})

    assert "Error" not in result
    assert len(result) == 1024 * 1024


def test_read_file_without_workspace_env(monkeypatch):
    """Test read_file without AGENT_WORKSPACE_PATH set."""
    # Remove environment variable
    monkeypatch.delenv("AGENT_WORKSPACE_PATH", raising=False)

    # Should fall back to project skills/
    result = read_file.invoke({"path": "skills/pdf/SKILL.md"})

    # Will try to read from project skills/ (may exist or not)
    # Just verify it doesn't crash
    assert isinstance(result, str)


# ========== write_file tests ==========

def test_write_file_to_outputs(temp_workspace):
    """Test writing file to outputs directory."""
    result = write_file.invoke({
        "path": "outputs/result.txt",
        "content": "Analysis complete"
    })

    assert "Success" in result
    assert "outputs/result.txt" in result

    # Verify file exists
    output_file = temp_workspace / "outputs" / "result.txt"
    assert output_file.exists()
    assert output_file.read_text() == "Analysis complete"


def test_write_file_to_temp(temp_workspace):
    """Test writing file to temp directory."""
    result = write_file.invoke({
        "path": "temp/cache.json",
        "content": '{"key": "value"}'
    })

    assert "Success" in result

    temp_file = temp_workspace / "temp" / "cache.json"
    assert temp_file.exists()
    assert temp_file.read_text() == '{"key": "value"}'


def test_write_file_to_uploads(temp_workspace):
    """Test writing file to uploads directory."""
    result = write_file.invoke({
        "path": "uploads/new_upload.txt",
        "content": "Uploaded content"
    })

    assert "Success" in result

    upload_file = temp_workspace / "uploads" / "new_upload.txt"
    assert upload_file.exists()


def test_write_file_create_subdirectory(temp_workspace):
    """Test that parent directories are created automatically."""
    result = write_file.invoke({
        "path": "outputs/reports/2024/analysis.txt",
        "content": "Report data"
    })

    assert "Success" in result

    output_file = temp_workspace / "outputs" / "reports" / "2024" / "analysis.txt"
    assert output_file.exists()
    assert output_file.read_text() == "Report data"


def test_write_file_to_skills_forbidden(temp_workspace):
    """Test that writing to skills/ is forbidden."""
    result = write_file.invoke({
        "path": "skills/pdf/malicious.txt",
        "content": "Should not work"
    })

    assert "Error" in result
    assert "Can only write to" in result

    # Verify file was NOT created
    malicious_file = temp_workspace / "skills" / "pdf" / "malicious.txt"
    assert not malicious_file.exists()


def test_write_file_path_traversal_attack(temp_workspace):
    """Test path traversal attack prevention."""
    result = write_file.invoke({
        "path": "outputs/../../etc/malicious.txt",
        "content": "Attack"
    })

    assert "Error: Access denied" in result


def test_write_file_absolute_path_attack(temp_workspace):
    """Test absolute path attack prevention."""
    result = write_file.invoke({
        "path": "/tmp/malicious.txt",
        "content": "Attack"
    })

    assert "Error" in result


def test_write_file_overwrite_existing(temp_workspace):
    """Test overwriting existing file."""
    # Create initial file
    (temp_workspace / "outputs" / "data.txt").write_text("Old content")

    # Overwrite
    result = write_file.invoke({
        "path": "outputs/data.txt",
        "content": "New content"
    })

    assert "Success" in result

    # Verify overwritten
    data_file = temp_workspace / "outputs" / "data.txt"
    assert data_file.read_text() == "New content"


def test_write_file_empty_content(temp_workspace):
    """Test writing empty file."""
    result = write_file.invoke({
        "path": "outputs/empty.txt",
        "content": ""
    })

    assert "Success" in result

    empty_file = temp_workspace / "outputs" / "empty.txt"
    assert empty_file.exists()
    assert empty_file.read_text() == ""


def test_write_file_unicode_content(temp_workspace):
    """Test writing Unicode content."""
    result = write_file.invoke({
        "path": "outputs/unicode.txt",
        "content": "Hello 世界 🌍"
    })

    assert "Success" in result

    unicode_file = temp_workspace / "outputs" / "unicode.txt"
    assert unicode_file.read_text(encoding="utf-8") == "Hello 世界 🌍"


def test_write_file_without_workspace_env(monkeypatch):
    """Test write_file without AGENT_WORKSPACE_PATH set."""
    monkeypatch.delenv("AGENT_WORKSPACE_PATH", raising=False)

    result = write_file.invoke({
        "path": "outputs/test.txt",
        "content": "Data"
    })

    assert "Error: No workspace configured" in result


# ========== list_workspace_files tests ==========

def test_list_workspace_files_root(temp_workspace):
    """Test listing root workspace directory."""
    result = list_workspace_files.invoke({"directory": "."})

    assert "Error" not in result
    assert "skills/" in result
    assert "uploads/" in result
    assert "outputs/" in result
    assert "temp/" in result


def test_list_workspace_files_specific_dir(temp_workspace):
    """Test listing specific directory."""
    result = list_workspace_files.invoke({"directory": "uploads"})

    assert "Error" not in result
    assert "document.txt" in result


def test_list_workspace_files_nested_dir(temp_workspace):
    """Test listing nested directory."""
    result = list_workspace_files.invoke({"directory": "skills/pdf"})

    assert "Error" not in result
    assert "SKILL.md" in result
    assert "forms.md" in result


def test_list_workspace_files_empty_dir(temp_workspace):
    """Test listing empty directory."""
    result = list_workspace_files.invoke({"directory": "temp"})

    assert "Directory is empty" in result


def test_list_workspace_files_nonexistent(temp_workspace):
    """Test listing nonexistent directory."""
    result = list_workspace_files.invoke({"directory": "nonexistent"})

    assert "Error: Directory not found" in result


def test_list_workspace_files_file_not_dir(temp_workspace):
    """Test listing a file (not directory)."""
    result = list_workspace_files.invoke({"directory": "uploads/document.txt"})

    assert "Error: Not a directory" in result


def test_list_workspace_files_path_traversal(temp_workspace):
    """Test path traversal prevention in list."""
    result = list_workspace_files.invoke({"directory": "../../../etc"})

    assert "Error: Access denied" in result


def test_list_workspace_files_with_files(temp_workspace):
    """Test listing directory with multiple files."""
    # Add more files
    (temp_workspace / "outputs" / "file1.txt").write_text("1")
    (temp_workspace / "outputs" / "file2.csv").write_text("2")
    (temp_workspace / "outputs" / "subdir").mkdir()

    result = list_workspace_files.invoke({"directory": "outputs"})

    assert "file1.txt" in result
    assert "file2.csv" in result
    assert "subdir/" in result
    assert "bytes" in result


if __name__ == "__main__":
    """Run tests with detailed output."""
    import sys

    print("\n" + "=" * 70)
    print("Testing File Operation Tools")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
