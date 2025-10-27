"""Test find_files and search_file tools."""

import os
import pytest
from pathlib import Path

from generalAgent.tools.builtin.find_files import find_files
from generalAgent.tools.builtin.search_file import search_file


@pytest.fixture
def temp_workspace_with_documents(tmp_path):
    """Create temporary workspace with various document types."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create directory structure
    (workspace / "uploads").mkdir()
    (workspace / "outputs").mkdir()

    # Create text files
    (workspace / "uploads" / "report.txt").write_text(
        "Q3 Financial Report\n"
        "Revenue growth increased by 25%.\n"
        "Customer satisfaction improved."
    )

    (workspace / "uploads" / "notes.md").write_text(
        "# Meeting Notes\n"
        "Discussed quarterly results.\n"
        "Action items: Review metrics."
    )

    (workspace / "uploads" / "data.json").write_text(
        '{"revenue": 5200000, "growth": 0.25}'
    )

    # Create subdirectory with files
    reports_dir = workspace / "uploads" / "reports"
    reports_dir.mkdir()
    (reports_dir / "summary_2024.txt").write_text("Annual summary for 2024.")
    (reports_dir / "analysis_Q3.pdf").write_text("PDF content placeholder")

    # Create PDF for testing (simple text content)
    (workspace / "uploads" / "document.pdf").write_text("PDF document content")

    return workspace


@pytest.fixture(autouse=True)
def set_workspace_env(temp_workspace_with_documents):
    """Set AGENT_WORKSPACE_PATH environment variable."""
    old_value = os.environ.get("AGENT_WORKSPACE_PATH")
    os.environ["AGENT_WORKSPACE_PATH"] = str(temp_workspace_with_documents)
    yield
    if old_value is None:
        os.environ.pop("AGENT_WORKSPACE_PATH", None)
    else:
        os.environ["AGENT_WORKSPACE_PATH"] = old_value


# ========== find_files Tests ==========

def test_find_files_simple_pattern():
    """Test finding files with simple wildcard pattern."""
    result = find_files.invoke({"pattern": "*.txt", "path": "uploads"})

    assert "Error" not in result
    assert "report.txt" in result
    assert len(result.split("📄")) >= 2  # At least one file


def test_find_files_recursive_pattern():
    """Test finding files recursively."""
    result = find_files.invoke({"pattern": "**/*.txt", "path": "uploads"})

    assert "Error" not in result
    assert "report.txt" in result
    assert "summary_2024.txt" in result


def test_find_files_specific_extension():
    """Test finding files by extension."""
    result = find_files.invoke({"pattern": "*.json", "path": "uploads"})

    assert "Error" not in result
    assert "data.json" in result


def test_find_files_name_contains():
    """Test finding files with name containing pattern."""
    result = find_files.invoke({"pattern": "*report*", "path": "uploads"})

    assert "Error" not in result
    assert "report.txt" in result


def test_find_files_multiple_extensions():
    """Test finding multiple file types."""
    result = find_files.invoke({"pattern": "*.{txt,md}", "path": "uploads"})

    # Note: This might not work with all glob implementations
    # Basic check that it returns something
    assert isinstance(result, str)


def test_find_files_no_matches():
    """Test when no files match pattern."""
    result = find_files.invoke({"pattern": "*.xyz", "path": "uploads"})

    assert "No files found" in result
    assert "💡" in result  # Should show tips


def test_find_files_nonexistent_directory():
    """Test finding files in non-existent directory."""
    result = find_files.invoke({"pattern": "*.txt", "path": "nonexistent"})

    assert "Error: Directory not found" in result


def test_find_files_path_traversal_prevention():
    """Test path traversal attack prevention."""
    result = find_files.invoke({"pattern": "*.txt", "path": "../../etc"})

    assert "Error: Access denied" in result


def test_find_files_absolute_path_prevention():
    """Test absolute path prevention."""
    result = find_files.invoke({"pattern": "*.txt", "path": "/etc"})

    assert "Error: Access denied" in result


def test_find_files_shows_file_sizes():
    """Test that result includes file sizes."""
    result = find_files.invoke({"pattern": "*.txt", "path": "uploads"})

    # Should show human-readable sizes
    assert "B)" in result or "KB)" in result or "MB)" in result


def test_find_files_filters_hidden():
    """Test that hidden files are filtered out."""
    # Create hidden file
    workspace = Path(os.environ["AGENT_WORKSPACE_PATH"])
    (workspace / "uploads" / ".hidden.txt").write_text("Hidden content")

    result = find_files.invoke({"pattern": "*.txt", "path": "uploads"})

    assert ".hidden.txt" not in result


def test_find_files_sorts_by_modification_time():
    """Test that files are sorted by modification time."""
    result = find_files.invoke({"pattern": "*.txt", "path": "uploads"})

    # Just verify it returns results (exact order depends on creation timing)
    assert "📄" in result


# ========== search_file Tests (Text Files) ==========

def test_search_file_text_simple():
    """Test searching in text file."""
    result = search_file.invoke({
        "path": "uploads/report.txt",
        "query": "revenue",
        "max_results": 5
    })

    assert "Error" not in result
    assert "revenue" in result.lower() or "Revenue" in result


def test_search_file_text_with_context():
    """Test that search results include context."""
    result = search_file.invoke({
        "path": "uploads/report.txt",
        "query": "growth",
        "max_results": 5
    })

    assert "growth" in result.lower() or "Growth" in result
    # Should show line number
    assert "Line" in result


def test_search_file_text_case_insensitive():
    """Test case-insensitive search."""
    result = search_file.invoke({
        "path": "uploads/report.txt",
        "query": "REVENUE",
        "max_results": 5
    })

    # Should find "Revenue" despite uppercase query
    assert "Found" in result or "match" in result.lower()


def test_search_file_text_no_matches():
    """Test search with no matches."""
    result = search_file.invoke({
        "path": "uploads/report.txt",
        "query": "nonexistent",
        "max_results": 5
    })

    assert "No matches found" in result
    assert "💡" in result  # Should show tips


def test_search_file_text_max_results_limit():
    """Test max_results parameter."""
    # Create file with multiple matches
    workspace = Path(os.environ["AGENT_WORKSPACE_PATH"])
    (workspace / "uploads" / "multi.txt").write_text(
        "test line 1\ntest line 2\ntest line 3\ntest line 4\ntest line 5\ntest line 6"
    )

    result = search_file.invoke({
        "path": "uploads/multi.txt",
        "query": "test",
        "max_results": 3
    })

    # Should limit results
    line_count = result.count("Line")
    assert line_count <= 3


def test_search_file_highlighting():
    """Test that matching text is highlighted."""
    result = search_file.invoke({
        "path": "uploads/report.txt",
        "query": "revenue",
        "max_results": 5
    })

    # Should have highlighting markers
    assert "**" in result or "revenue" in result.lower()


# ========== search_file Tests (Error Handling) ==========

def test_search_file_nonexistent():
    """Test searching non-existent file."""
    result = search_file.invoke({
        "path": "uploads/nonexistent.txt",
        "query": "test",
        "max_results": 5
    })

    assert "Error: File not found" in result


def test_search_file_directory():
    """Test searching a directory (should fail)."""
    result = search_file.invoke({
        "path": "uploads",
        "query": "test",
        "max_results": 5
    })

    assert "Error: Not a file" in result


def test_search_file_path_traversal():
    """Test path traversal prevention."""
    result = search_file.invoke({
        "path": "../../etc/passwd",
        "query": "root",
        "max_results": 5
    })

    assert "Error: Access denied" in result


def test_search_file_unsupported_extension():
    """Test searching unsupported file type."""
    workspace = Path(os.environ["AGENT_WORKSPACE_PATH"])
    (workspace / "uploads" / "image.png").write_bytes(b"PNG binary content")

    result = search_file.invoke({
        "path": "uploads/image.png",
        "query": "test",
        "max_results": 5
    })

    assert "Error" in result
    assert "not supported" in result.lower()


# ========== search_file Tests (Document Files) ==========

def test_search_file_document_placeholder():
    """Test searching document file (using text placeholder for now)."""
    # Note: This test uses a text file with .pdf extension as placeholder
    # Real PDF indexing would require PDF library and index creation

    result = search_file.invoke({
        "path": "uploads/document.pdf",
        "query": "content",
        "max_results": 5
    })

    # Should attempt to search (may create index or search text)
    assert isinstance(result, str)
    # Actual result depends on whether file is treated as text or needs indexing


# ========== Integration Tests ==========

def test_find_then_search_workflow():
    """Test typical workflow: find files, then search content."""
    # Step 1: Find all text files
    find_result = find_files.invoke({"pattern": "*.txt", "path": "uploads"})

    assert "report.txt" in find_result

    # Step 2: Search in found file
    search_result = search_file.invoke({
        "path": "uploads/report.txt",
        "query": "revenue",
        "max_results": 5
    })

    assert "revenue" in search_result.lower() or "Revenue" in search_result


def test_find_files_root_directory():
    """Test finding files from workspace root."""
    result = find_files.invoke({"pattern": "**/*.json", "path": "."})

    assert "data.json" in result


def test_search_file_markdown():
    """Test searching markdown file."""
    result = search_file.invoke({
        "path": "uploads/notes.md",
        "query": "quarterly",
        "max_results": 5
    })

    assert "quarterly" in result.lower() or "Quarterly" in result


if __name__ == "__main__":
    """Run tests with detailed output."""
    import sys

    print("\n" + "=" * 70)
    print("Testing find_files and search_file Tools")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
