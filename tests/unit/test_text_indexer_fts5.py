"""Unit tests for FTS5 text indexer with Grep fallback."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

from generalAgent.utils.text_indexer import (
    compute_file_hash,
    index_exists,
    create_index,
    search_in_index,
    _should_use_fts5,
    cleanup_old_indexes,
    INDEXES_DB
)


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a sample PDF for testing."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    pdf_path = tmp_path / "test.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)

    # Page 1
    c.drawString(100, 750, "Research Paper 2025")
    c.drawString(100, 730, "Baseline experiment results: 98.5%")
    c.drawString(100, 710, "Error code: 404 not found")
    c.drawString(100, 690, "Contact: researcher@university.edu")
    c.showPage()

    # Page 2
    c.drawString(100, 750, "Version 1.2.3 released on 2025-01-15")
    c.drawString(100, 730, "Temperature: 25.5C, Humidity: 60%")
    c.drawString(100, 710, "Pattern: ABC-123-XYZ")
    c.showPage()

    c.save()
    return pdf_path


# ========== Basic Functionality Tests ==========

def test_compute_file_hash(sample_pdf):
    """Test MD5 hash computation."""
    hash1 = compute_file_hash(sample_pdf)
    hash2 = compute_file_hash(sample_pdf)

    assert hash1 == hash2
    assert len(hash1) == 32  # MD5 is 32 hex chars


def test_create_index_saves_full_text(sample_pdf):
    """Test that create_index saves full_text to database."""
    import sqlite3

    create_index(sample_pdf)
    file_hash = compute_file_hash(sample_pdf)

    conn = sqlite3.connect(str(INDEXES_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        'SELECT full_text FROM file_metadata WHERE file_hash = ?',
        (file_hash,)
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row['full_text'] is not None
    assert len(row['full_text']) > 0
    assert 'Baseline' in row['full_text']


# ========== Routing Logic Tests ==========

def test_should_use_fts5_simple_word():
    """Simple word should use FTS5."""
    assert _should_use_fts5('baseline', False) == True


def test_should_use_fts5_boolean():
    """Boolean query should use FTS5."""
    assert _should_use_fts5('baseline OR experiment', False) == True


def test_should_use_fts5_regex_flag():
    """use_regex=True should trigger Grep."""
    assert _should_use_fts5('anything', True) == False


def test_should_use_fts5_digit_class():
    """Digit class should use Grep."""
    assert _should_use_fts5(r'\d+', False) == False


def test_should_use_fts5_dot_star():
    """Dot-star pattern should use Grep."""
    assert _should_use_fts5(r'error.*message', False) == False


# ========== FTS5 Search Tests ==========

def test_fts5_search_simple_word(sample_pdf):
    """Test FTS5 search for simple word."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, 'baseline', max_results=5)
    assert len(results) > 0
    assert 'Baseline' in results[0]['text']


def test_fts5_search_no_match(sample_pdf):
    """Test FTS5 returns empty for no match."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, 'nonexistent_word_xyz', max_results=5)
    assert len(results) == 0


# ========== Grep Search Tests ==========

def test_grep_search_digit_pattern(sample_pdf):
    """Test Grep search for digit pattern."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, r'\d+', max_results=5, use_regex=True)
    assert len(results) > 0


def test_grep_search_email_pattern(sample_pdf):
    """Test Grep search for email pattern."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, r'\w+@\w+\.\w+', max_results=5, use_regex=True)
    assert len(results) > 0
    assert 'researcher@university.edu' in results[0]['text']


def test_grep_search_date_pattern(sample_pdf):
    """Test Grep search for date pattern."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, r'\d{4}-\d{2}-\d{2}', max_results=5, use_regex=True)
    assert len(results) > 0
    assert '2025-01-15' in results[0]['text']


def test_grep_search_invalid_regex(sample_pdf):
    """Test Grep handles invalid regex gracefully."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, r'(invalid', max_results=5, use_regex=True)
    assert results == []


# ========== Integration Tests ==========

def test_auto_routing_regex_to_grep(sample_pdf):
    """Test automatic routing of regex pattern to Grep."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, r'\d+', max_results=5)
    assert len(results) > 0


def test_max_results_limit(sample_pdf):
    """Test max_results parameter limits output."""
    create_index(sample_pdf)
    results = search_in_index(sample_pdf, r'\d+', max_results=2, use_regex=True)
    assert len(results) <= 2
