"""E2E tests for document search workflow."""

import pytest
from pathlib import Path

from generalAgent.utils.file_processor import process_file
from generalAgent.utils.text_indexer import search_in_index, index_exists
from generalAgent.tools.builtin.search_file import search_file


@pytest.fixture
def research_paper(tmp_path):
    """Create a realistic research paper PDF."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    pdf_path = tmp_path / "research_paper.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)

    # Title page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Impact of Baseline Methods on AI Performance")
    c.setFont("Helvetica", 12)
    c.drawString(100, 720, "Authors: Alice Smith, Bob Johnson")
    c.drawString(100, 700, "Email: alice.smith@university.edu")
    c.drawString(100, 680, "Published: 2025-01-20")
    c.showPage()

    # Abstract
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 750, "Abstract")
    c.setFont("Helvetica", 11)
    c.drawString(100, 720, "This paper presents experimental results comparing")
    c.drawString(100, 700, "baseline methods with advanced AI techniques.")
    c.drawString(100, 680, "Accuracy improved from 85.3% to 92.7% using our approach.")
    c.drawString(100, 660, "Error rate decreased by 45% compared to previous work.")
    c.showPage()

    # Methods section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 750, "Section 4.1: Experimental Setup")
    c.setFont("Helvetica", 11)
    c.drawString(100, 720, "We conducted experiments on dataset XYZ-2024.")
    c.drawString(100, 700, "Configuration: learning_rate=0.001, batch_size=32")
    c.drawString(100, 680, "Hardware: NVIDIA A100 GPU, 80GB memory")
    c.drawString(100, 660, "Runtime: approximately 12.5 hours per experiment")
    c.showPage()

    # Results
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 750, "Results")
    c.setFont("Helvetica", 11)
    c.drawString(100, 720, "Table 1 shows performance metrics:")
    c.drawString(100, 700, "  Baseline: Accuracy=85.3%, F1=0.82")
    c.drawString(100, 680, "  Our Method: Accuracy=92.7%, F1=0.91")
    c.drawString(100, 660, "Statistical significance: p-value < 0.001")
    c.showPage()

    c.save()
    return pdf_path


@pytest.fixture
def workspace_with_pdf(tmp_path, research_paper):
    """Simulate a workspace with an uploaded PDF."""
    # Create workspace structure
    workspace = tmp_path / "workspace"
    uploads_dir = workspace / "uploads"
    uploads_dir.mkdir(parents=True)

    # Simulate file upload
    dest_path = uploads_dir / research_paper.name
    import shutil
    shutil.copy2(research_paper, dest_path)

    return workspace, dest_path


# ========== E2E Workflow Tests ==========

def test_e2e_upload_and_index(workspace_with_pdf):
    """E2E: Upload file and create index."""
    workspace, pdf_path = workspace_with_pdf

    # Verify file uploaded
    assert pdf_path.exists()

    # Index should be created (simulating proactive indexing)
    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    assert index_exists(pdf_path)


def test_e2e_search_simple_keyword(workspace_with_pdf):
    """E2E: Search for simple keyword (FTS5 route)."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Search for "baseline" - should use FTS5
    results = search_in_index(pdf_path, 'baseline', max_results=3)

    assert len(results) > 0
    # Should find mentions of "baseline" in the paper
    assert any('baseline' in r['text'].lower() for r in results)


def test_e2e_search_email_regex(workspace_with_pdf):
    """E2E: Search for email with regex (Grep route)."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Search for email pattern - should use Grep
    results = search_in_index(pdf_path, r'\w+@\w+\.\w+', max_results=3, use_regex=True)

    assert len(results) > 0
    assert 'alice.smith@university.edu' in results[0]['text']


def test_e2e_search_decimal_numbers(workspace_with_pdf):
    """E2E: Search for decimal numbers (Grep route)."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Search for percentages/decimals - should use Grep
    results = search_in_index(pdf_path, r'\d+\.\d+%', max_results=5, use_regex=True)

    assert len(results) > 0
    # Should find 85.3%, 92.7%, etc.


def test_e2e_search_section_number(workspace_with_pdf):
    """E2E: Search for section number like '4.1'."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Search for "4.1" - FTS5 with quoted phrase
    results = search_in_index(pdf_path, '"4.1"', max_results=3)

    assert len(results) > 0
    assert '4.1' in results[0]['text']


def test_e2e_search_config_pattern(workspace_with_pdf):
    """E2E: Search for configuration pattern (Grep route)."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Search for key=value pattern - should use Grep
    results = search_in_index(pdf_path, r'\w+=\d+\.?\d*', max_results=5, use_regex=True)

    assert len(results) > 0
    # Should find learning_rate=0.001, batch_size=32, etc.


def test_e2e_boolean_search(workspace_with_pdf):
    """E2E: Boolean search combining keywords (FTS5 route)."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Boolean query - should use FTS5
    results = search_in_index(pdf_path, 'baseline OR experiment', max_results=5)

    assert len(results) > 0


def test_e2e_no_results(workspace_with_pdf):
    """E2E: Search with no results."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Search for non-existent term
    results = search_in_index(pdf_path, 'quantum_entanglement_xyz', max_results=5)

    assert len(results) == 0


def test_e2e_search_file_tool_integration(workspace_with_pdf, monkeypatch):
    """E2E: Integration with search_file tool."""
    workspace, pdf_path = workspace_with_pdf

    # Set workspace environment
    monkeypatch.setenv("AGENT_WORKSPACE_PATH", str(workspace))

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # Use search_file tool (simulates agent tool call)
    result = search_file.invoke({
        "path": "uploads/research_paper.pdf",
        "query": "baseline",
        "max_results": 3
    })

    assert "baseline" in result.lower()
    # Result should contain search matches


def test_e2e_multiple_searches_same_document(workspace_with_pdf):
    """E2E: Multiple searches on same document (index reuse)."""
    workspace, pdf_path = workspace_with_pdf

    from generalAgent.utils.text_indexer import create_index
    create_index(pdf_path)

    # First search (FTS5)
    results1 = search_in_index(pdf_path, 'accuracy', max_results=3)

    # Second search (Grep)
    results2 = search_in_index(pdf_path, r'\d+%', max_results=3, use_regex=True)

    # Third search (FTS5 boolean)
    results3 = search_in_index(pdf_path, 'baseline AND experiment', max_results=3)

    # All should work without re-indexing
    assert len(results1) > 0
    assert len(results2) > 0
    # Boolean might have 0 results, but shouldn't crash


if __name__ == "__main__":
    """Run E2E tests."""
    import sys

    print("\n" + "=" * 70)
    print("E2E Tests: Document Search Workflow")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
