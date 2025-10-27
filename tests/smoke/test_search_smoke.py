"""Smoke tests for document search system (quick validation)."""

import pytest
from pathlib import Path

from generalAgent.utils.text_indexer import create_index, search_in_index, index_exists
from generalAgent.utils.document_extractors import chunk_document, extract_preview


@pytest.fixture
def quick_pdf(tmp_path):
    """Create a minimal PDF for smoke testing."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    pdf_path = tmp_path / "smoke.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(100, 750, "Smoke test document")
    c.drawString(100, 730, "Contains test@example.com")
    c.drawString(100, 710, "Version 1.0 released 2025-01-01")
    c.save()
    return pdf_path


def test_smoke_index_creation(quick_pdf):
    """Smoke: Can create index."""
    create_index(quick_pdf)
    assert index_exists(quick_pdf)


def test_smoke_fts5_search(quick_pdf):
    """Smoke: FTS5 search works."""
    create_index(quick_pdf)
    results = search_in_index(quick_pdf, 'test', max_results=1)
    assert len(results) > 0


def test_smoke_grep_search(quick_pdf):
    """Smoke: Grep search works."""
    create_index(quick_pdf)
    results = search_in_index(quick_pdf, r'\d+', max_results=1, use_regex=True)
    assert len(results) > 0


def test_smoke_document_extraction(quick_pdf):
    """Smoke: Document extraction works."""
    chunks = chunk_document(quick_pdf)
    assert len(chunks) > 0
    assert 'text' in chunks[0]


def test_smoke_preview_extraction(quick_pdf):
    """Smoke: Preview extraction works."""
    preview = extract_preview(quick_pdf, max_pages=1, max_chars=500)
    assert len(preview) > 0
    assert 'Smoke test' in preview
