"""Unit tests for enhanced edit_file and write_file tools."""

import os
import pytest
from pathlib import Path
from generalAgent.tools.builtin.edit_file import edit_file
from generalAgent.tools.builtin.file_ops import write_file


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "outputs").mkdir()
    (workspace / "temp").mkdir()
    (workspace / "uploads").mkdir()

    # Set workspace env
    os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

    yield workspace

    # Cleanup
    if "AGENT_WORKSPACE_PATH" in os.environ:
        del os.environ["AGENT_WORKSPACE_PATH"]


class TestEditFileTool:
    """Test edit_file tool behavior."""

    def test_basic_string_replacement(self, temp_workspace):
        """Test basic exact string replacement."""
        # Create a test file
        test_file = temp_workspace / "outputs" / "test.txt"
        test_file.write_text("Hello World\nThis is a test\n")

        # Perform edit
        result = edit_file(
            path="outputs/test.txt",
            old_string="Hello World",
            new_string="Hello Python"
        )

        assert "Success" in result
        assert test_file.read_text() == "Hello Python\nThis is a test\n"

    def test_fails_if_old_string_not_found(self, temp_workspace):
        """Test that edit fails if old_string doesn't exist."""
        test_file = temp_workspace / "outputs" / "test.txt"
        test_file.write_text("Hello World\n")

        result = edit_file(
            path="outputs/test.txt",
            old_string="NonExistent",
            new_string="Something"
        )

        assert "Error" in result
        assert "not found" in result

    def test_fails_if_old_string_not_unique(self, temp_workspace):
        """Test that edit fails if old_string appears multiple times without replace_all."""
        test_file = temp_workspace / "outputs" / "test.txt"
        test_file.write_text("foo\nfoo\nfoo\n")

        result = edit_file(
            path="outputs/test.txt",
            old_string="foo",
            new_string="bar",
            replace_all=False
        )

        assert "Error" in result
        assert "occurrences" in result

    def test_replace_all_mode(self, temp_workspace):
        """Test replace_all mode for renaming variables."""
        test_file = temp_workspace / "outputs" / "script.py"
        test_file.write_text("old_name = 1\nprint(old_name)\nreturn old_name\n")

        result = edit_file(
            path="outputs/script.py",
            old_string="old_name",
            new_string="new_name",
            replace_all=True
        )

        assert "Success" in result
        content = test_file.read_text()
        assert "new_name = 1" in content
        assert "print(new_name)" in content
        assert "return new_name" in content
        assert "old_name" not in content

    def test_preserves_whitespace_and_indentation(self, temp_workspace):
        """Test that whitespace and indentation are preserved exactly."""
        test_file = temp_workspace / "outputs" / "code.py"
        test_file.write_text("def func():\n    return 42\n")

        result = edit_file(
            path="outputs/code.py",
            old_string="    return 42",
            new_string="    return 100"
        )

        assert "Success" in result
        assert test_file.read_text() == "def func():\n    return 100\n"

    def test_fails_if_file_not_in_allowed_dirs(self, temp_workspace):
        """Test that editing files outside allowed directories fails."""
        # Try to edit a file in skills/ (not allowed)
        result = edit_file(
            path="skills/test.txt",
            old_string="old",
            new_string="new"
        )

        assert "Error" in result
        assert "only edit files in" in result.lower()

    def test_fails_if_path_traversal_attempt(self, temp_workspace):
        """Test that path traversal attempts are blocked."""
        result = edit_file(
            path="../../../etc/passwd",
            old_string="old",
            new_string="new"
        )

        assert "Error" in result
        assert "Access denied" in result


class TestWriteFileTool:
    """Test write_file tool behavior."""

    def test_create_new_file(self, temp_workspace):
        """Test creating a new file."""
        result = write_file(
            path="outputs/new.txt",
            content="Hello World"
        )

        assert "Success" in result
        test_file = temp_workspace / "outputs" / "new.txt"
        assert test_file.exists()
        assert test_file.read_text() == "Hello World"

    def test_overwrite_existing_file(self, temp_workspace):
        """Test overwriting an existing file."""
        test_file = temp_workspace / "outputs" / "existing.txt"
        test_file.write_text("Old content")

        result = write_file(
            path="outputs/existing.txt",
            content="New content"
        )

        assert "Success" in result
        assert test_file.read_text() == "New content"

    def test_create_parent_directories(self, temp_workspace):
        """Test that parent directories are created automatically."""
        result = write_file(
            path="outputs/subdir/nested/file.txt",
            content="Nested content"
        )

        assert "Success" in result
        test_file = temp_workspace / "outputs" / "subdir" / "nested" / "file.txt"
        assert test_file.exists()
        assert test_file.read_text() == "Nested content"

    def test_fails_if_not_in_allowed_dirs(self, temp_workspace):
        """Test that writing outside allowed directories fails."""
        result = write_file(
            path="skills/test.txt",
            content="content"
        )

        assert "Error" in result
        assert "Can only write to" in result

    def test_fails_if_path_traversal_attempt(self, temp_workspace):
        """Test that path traversal attempts are blocked."""
        result = write_file(
            path="../../../tmp/bad.txt",
            content="malicious"
        )

        assert "Error" in result
        assert "Access denied" in result


class TestEditWriteWorkflow:
    """Test the outline-first → edit-to-expand workflow."""

    def test_outline_first_then_expand(self, temp_workspace):
        """Test the recommended workflow: create outline with write_file, expand with edit_file."""
        # Step 1: Create outline
        write_result = write_file(
            path="outputs/plan.md",
            content="# Plan\n\n## Phase 1\n[TBD]\n\n## Phase 2\n[TBD]\n"
        )
        assert "Success" in write_result

        # Step 2: Expand Phase 1
        edit_result_1 = edit_file(
            path="outputs/plan.md",
            old_string="## Phase 1\n[TBD]",
            new_string="## Phase 1\n- Task 1: Setup\n- Task 2: Configuration"
        )
        assert "Success" in edit_result_1

        # Step 3: Expand Phase 2
        edit_result_2 = edit_file(
            path="outputs/plan.md",
            old_string="## Phase 2\n[TBD]",
            new_string="## Phase 2\n- Task 3: Testing\n- Task 4: Deployment"
        )
        assert "Success" in edit_result_2

        # Verify final content
        test_file = temp_workspace / "outputs" / "plan.md"
        final_content = test_file.read_text()

        assert "## Phase 1" in final_content
        assert "- Task 1: Setup" in final_content
        assert "## Phase 2" in final_content
        assert "- Task 3: Testing" in final_content
        assert "[TBD]" not in final_content

    def test_multiple_section_expansion(self, temp_workspace):
        """Test expanding multiple sections independently."""
        # Create outline with multiple [TBD] markers
        write_file(
            path="outputs/document.md",
            content="# Document\n\n## Section A\n[TBD]\n\n## Section B\n[TBD]\n\n## Section C\n[TBD]\n"
        )

        # Expand each section one by one
        sections = [
            ("## Section A\n[TBD]", "## Section A\nContent A"),
            ("## Section B\n[TBD]", "## Section B\nContent B"),
            ("## Section C\n[TBD]", "## Section C\nContent C"),
        ]

        for old, new in sections:
            result = edit_file(
                path="outputs/document.md",
                old_string=old,
                new_string=new
            )
            assert "Success" in result

        # Verify all sections expanded
        test_file = temp_workspace / "outputs" / "document.md"
        final_content = test_file.read_text()

        assert "Content A" in final_content
        assert "Content B" in final_content
        assert "Content C" in final_content
        assert "[TBD]" not in final_content
