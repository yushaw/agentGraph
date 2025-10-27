"""Test text indexer and search functionality."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from generalAgent.utils.text_indexer import (
    compute_file_hash,
    get_index_path,
    index_exists,
    create_index,
    load_index,
    search_in_index,
    extract_keywords,
    extract_ngrams,
    cleanup_old_indexes,
    get_index_stats,
    INDEXES_DIR
)


@pytest.fixture
def sample_pdf_for_indexing(tmp_path):
    """Create a sample PDF with searchable content."""
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "searchable.pdf"
    c = canvas.Canvas(str(pdf_path))

    # Page 1 - Financial Report
    c.drawString(100, 750, "Q3 Financial Report 2024")
    c.drawString(100, 730, "Revenue growth increased by 25% this quarter.")
    c.drawString(100, 710, "Total revenue: $5.2 million")
    c.showPage()

    # Page 2 - Customer Analysis
    c.drawString(100, 750, "Customer Analysis")
    c.drawString(100, 730, "Customer churn rate decreased to 3.5%.")
    c.drawString(100, 710, "New customer acquisitions: 1,200 accounts")
    c.showPage()

    c.save()

    return pdf_path


@pytest.fixture
def cleanup_test_indexes():
    """Clean up test indexes after tests."""
    yield
    # Cleanup code if needed
    # Note: Tests use tmp_path which auto-cleans


# ========== File Hashing Tests ==========

def test_compute_file_hash(tmp_path):
    """Test MD5 file hashing."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    hash1 = compute_file_hash(test_file)

    assert len(hash1) == 32  # MD5 is 32 hex chars
    assert hash1.isalnum()

    # Same content = same hash
    test_file2 = tmp_path / "test2.txt"
    test_file2.write_text("Hello World")

    hash2 = compute_file_hash(test_file2)
    assert hash1 == hash2


def test_compute_file_hash_different_content(tmp_path):
    """Test that different content produces different hashes."""
    file1 = tmp_path / "file1.txt"
    file1.write_text("Content A")

    file2 = tmp_path / "file2.txt"
    file2.write_text("Content B")

    hash1 = compute_file_hash(file1)
    hash2 = compute_file_hash(file2)

    assert hash1 != hash2


# ========== Index Path Tests ==========

def test_get_index_path():
    """Test index path generation."""
    test_hash = "abcdef1234567890"

    index_path = get_index_path(test_hash)

    # Should use two-level directory structure
    assert "ab" in str(index_path)  # First 2 chars as subdir
    assert f"{test_hash}.index.json" in str(index_path)
    assert "data/indexes" in str(index_path)


def test_get_index_path_creates_directory(tmp_path, monkeypatch):
    """Test that get_index_path creates directories."""
    # Mock INDEXES_DIR to use tmp_path
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    test_hash = "xyz123"
    index_path = get_index_path(test_hash)

    # Directory should be created
    assert index_path.parent.exists()
    assert index_path.parent.name == "xy"  # First 2 chars


# ========== Keyword Extraction Tests ==========

def test_extract_keywords_english():
    """Test keyword extraction from English text."""
    text = "The quick brown fox jumps over the lazy dog"

    keywords = extract_keywords(text)

    assert "quick" in keywords
    assert "brown" in keywords
    assert "fox" in keywords
    assert "jumps" in keywords

    # Stopwords should be removed
    assert "the" not in keywords
    # "over" might or might not be in stopwords, just check common ones are removed


def test_extract_keywords_chinese():
    """Test keyword extraction from Chinese text."""
    text = "营收增长了25%，客户满意度提升"

    keywords = extract_keywords(text)

    # Basic regex tokenization splits differently for Chinese
    # Just verify some keywords are extracted
    assert len(keywords) > 0
    # The regex [\w]+ will extract multi-char sequences
    assert any("营收" in kw or "增长" in kw or "客户" in kw for kw in keywords)

    # Stopwords should be removed
    assert "了" not in keywords


def test_extract_keywords_mixed():
    """Test keyword extraction from mixed language text."""
    text = "Q3 revenue 营收 increased by 25%"

    keywords = extract_keywords(text)

    assert "q3" in keywords or "revenue" in keywords
    assert "increased" in keywords
    assert "25" in keywords


def test_extract_keywords_removes_short_words():
    """Test that single-character words are removed."""
    text = "A B test data x y result"

    keywords = extract_keywords(text)

    # Single chars should be removed
    assert "a" not in keywords
    assert "b" not in keywords
    assert "x" not in keywords

    # Multi-char words kept
    assert "test" in keywords
    assert "data" in keywords


# ========== N-gram Extraction Tests ==========

def test_extract_bigrams():
    """Test bigram extraction."""
    text = "revenue growth customer churn"

    bigrams = extract_ngrams(text, n=2)

    assert "revenue growth" in bigrams
    assert "growth customer" in bigrams
    assert "customer churn" in bigrams


def test_extract_trigrams():
    """Test trigram extraction."""
    text = "customer acquisition cost analysis"

    trigrams = extract_ngrams(text, n=3)

    assert "customer acquisition cost" in trigrams
    assert "acquisition cost analysis" in trigrams


def test_extract_ngrams_deduplication():
    """Test that n-grams are deduplicated."""
    text = "test test test"

    bigrams = extract_ngrams(text, n=2)

    # Should only have one "test test" entry
    assert bigrams.count("test test") == 1


# ========== Index Creation Tests ==========

def test_create_index_pdf(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test creating index for PDF document."""
    # Mock INDEXES_DIR
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    index_path = create_index(sample_pdf_for_indexing)

    # Index file should exist
    assert index_path.exists()
    assert index_path.suffix == ".json"

    # Load and verify structure
    with open(index_path, "r") as f:
        index_data = json.load(f)

    assert index_data['file_name'] == "searchable.pdf"
    assert index_data['file_type'] == ".pdf"
    assert 'file_hash' in index_data
    assert 'indexed_at' in index_data
    assert 'chunks' in index_data
    assert len(index_data['chunks']) > 0

    # Check chunk structure
    chunk = index_data['chunks'][0]
    assert 'chunk_id' in chunk
    assert 'page' in chunk
    assert 'text' in chunk
    assert 'keywords' in chunk
    assert 'bigrams' in chunk
    assert 'trigrams' in chunk


def test_create_index_metadata(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test that index contains correct metadata."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    index_path = create_index(sample_pdf_for_indexing)

    with open(index_path, "r") as f:
        index_data = json.load(f)

    # Check metadata
    metadata = index_data['metadata']
    assert metadata['total_pages'] >= 1
    assert metadata['total_chunks'] >= 1
    assert metadata['total_chars'] > 0

    # Check vector index fields (reserved for v2.0)
    assert index_data['vector_index_available'] == False
    assert index_data['vector_model'] is None


# ========== Index Existence Tests ==========

def test_index_exists_false_when_not_created(tmp_path):
    """Test index_exists returns False for non-indexed file."""
    test_file = tmp_path / "new_file.txt"
    test_file.write_text("Not indexed yet")

    assert index_exists(test_file) == False


def test_index_exists_true_after_creation(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test index_exists returns True after index is created."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    assert index_exists(sample_pdf_for_indexing) == False

    create_index(sample_pdf_for_indexing)

    assert index_exists(sample_pdf_for_indexing) == True


def test_index_exists_stale_detection(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test that stale indexes are detected."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    # Create index
    index_path = create_index(sample_pdf_for_indexing)

    # Manually modify indexed_at to be old
    with open(index_path, "r") as f:
        index_data = json.load(f)

    old_time = datetime.now() - timedelta(hours=25)  # Stale threshold is 24h
    index_data['indexed_at'] = old_time.isoformat()

    with open(index_path, "w") as f:
        json.dump(index_data, f)

    # Should detect as stale
    assert index_exists(sample_pdf_for_indexing) == False


# ========== Load Index Tests ==========

def test_load_index(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test loading index data."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    index_data = load_index(sample_pdf_for_indexing)

    assert 'chunks' in index_data
    assert len(index_data['chunks']) > 0


def test_load_index_nonexistent_raises(tmp_path):
    """Test loading non-existent index raises error."""
    test_file = tmp_path / "nonexistent.txt"
    test_file.write_text("Test")

    with pytest.raises(FileNotFoundError):
        load_index(test_file)


# ========== Search Tests ==========

def test_search_in_index_phrase_match(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test phrase matching in search."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    results = search_in_index(sample_pdf_for_indexing, "revenue growth", max_results=5)

    assert len(results) > 0
    assert results[0]['score'] > 0
    assert 'text' in results[0]
    assert 'page' in results[0]

    # Should find the phrase
    assert any("revenue" in r['text'].lower() and "growth" in r['text'].lower()
               for r in results)


def test_search_in_index_keyword_match(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test keyword matching in search."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    results = search_in_index(sample_pdf_for_indexing, "customer churn", max_results=5)

    assert len(results) > 0
    assert any("customer" in r['text'].lower() or "churn" in r['text'].lower()
               for r in results)


def test_search_in_index_no_matches(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test search with no matches."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    results = search_in_index(sample_pdf_for_indexing, "nonexistent query xyz", max_results=5)

    assert len(results) == 0


def test_search_in_index_returns_top_k(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test that search returns max_results items."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    # Search for common word
    results = search_in_index(sample_pdf_for_indexing, "customer revenue", max_results=2)

    assert len(results) <= 2


def test_search_scoring_phrase_higher_than_keyword(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test that phrase matches score higher than keyword matches."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    # "revenue growth" appears as exact phrase on page 1
    results = search_in_index(sample_pdf_for_indexing, "revenue growth", max_results=5)

    # Top result should have high score due to phrase match
    if len(results) > 0:
        assert results[0]['score'] >= 10  # Phrase match gives +10


# ========== Cleanup Tests ==========

def test_cleanup_old_indexes(tmp_path, monkeypatch):
    """Test cleanup of old index files."""
    test_indexes = tmp_path / "indexes"
    test_indexes.mkdir(parents=True)
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    # Create old index file
    old_index = test_indexes / "ab" / "old.index.json"
    old_index.parent.mkdir(parents=True)
    old_index.write_text('{"test": "data"}')

    # Set old access time (31 days ago)
    old_time = (datetime.now() - timedelta(days=31)).timestamp()
    old_index.touch()
    import os
    os.utime(old_index, (old_time, old_time))

    # Cleanup indexes older than 30 days
    cleanup_old_indexes(days=30)

    # Old index should be deleted
    assert not old_index.exists()


def test_get_index_stats_empty(tmp_path, monkeypatch):
    """Test index stats when no indexes exist."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    stats = get_index_stats()

    assert stats['total_indexes'] == 0
    assert stats['total_size_bytes'] == 0
    assert stats['oldest_index'] is None
    assert stats['newest_index'] is None


def test_get_index_stats_with_indexes(sample_pdf_for_indexing, tmp_path, monkeypatch):
    """Test index stats with existing indexes."""
    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    create_index(sample_pdf_for_indexing)

    stats = get_index_stats()

    assert stats['total_indexes'] == 1
    assert stats['total_size_bytes'] > 0
    assert stats['oldest_index'] is not None
    assert stats['newest_index'] is not None


# ========== Orphan Index Cleanup Tests ==========

def test_cleanup_old_indexes_for_file_same_name_different_content(tmp_path, monkeypatch):
    """Test cleanup when same-name file is replaced with different content."""
    from reportlab.pdfgen import canvas
    from generalAgent.utils.text_indexer import cleanup_old_indexes_for_file

    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    # Create first version of file
    pdf_path = tmp_path / "report.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Version 1 content")
    c.showPage()
    c.save()

    # Create index for version 1
    index_path_v1 = create_index(pdf_path)
    hash_v1 = compute_file_hash(pdf_path)

    assert index_path_v1.exists()

    # Replace with version 2 (different content)
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Version 2 content - DIFFERENT")
    c.showPage()
    c.save()

    hash_v2 = compute_file_hash(pdf_path)
    assert hash_v1 != hash_v2  # Content changed

    # Create index for version 2 (should auto-cleanup v1)
    index_path_v2 = create_index(pdf_path)

    # Version 1 index should be deleted
    assert not index_path_v1.exists()
    # Version 2 index should exist
    assert index_path_v2.exists()


def test_cleanup_old_indexes_removes_orphans(tmp_path, monkeypatch):
    """Test that cleanup_old_indexes removes orphan indexes."""
    from reportlab.pdfgen import canvas

    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    # Create file and index
    pdf_path = tmp_path / "document.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Test content")
    c.showPage()
    c.save()

    index_path = create_index(pdf_path)
    assert index_path.exists()

    # Delete the file (index becomes orphan)
    pdf_path.unlink()
    assert not pdf_path.exists()

    # Cleanup should remove orphan index
    cleanup_old_indexes(days=9999, remove_orphans=True)

    # Index should be deleted
    assert not index_path.exists()


def test_cleanup_old_indexes_keeps_valid_indexes(tmp_path, monkeypatch):
    """Test that cleanup_old_indexes keeps valid indexes."""
    from reportlab.pdfgen import canvas

    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    # Create file and index
    pdf_path = tmp_path / "valid_document.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "Valid content")
    c.showPage()
    c.save()

    index_path = create_index(pdf_path)
    assert index_path.exists()

    # Cleanup orphans (but file still exists)
    cleanup_old_indexes(days=9999, remove_orphans=True)

    # Index should still exist (not orphan)
    assert index_path.exists()


def test_multiple_file_versions_across_sessions(tmp_path, monkeypatch):
    """Test handling multiple versions of same file across sessions."""
    from reportlab.pdfgen import canvas

    test_indexes = tmp_path / "indexes"
    monkeypatch.setattr("generalAgent.utils.text_indexer.INDEXES_DIR", test_indexes)

    workspace1 = tmp_path / "session1"
    workspace1.mkdir()
    workspace2 = tmp_path / "session2"
    workspace2.mkdir()

    # Session 1: Upload report.pdf (version 1)
    pdf1 = workspace1 / "uploads" / "report.pdf"
    pdf1.parent.mkdir(parents=True)
    c = canvas.Canvas(str(pdf1))
    c.drawString(100, 750, "Session 1 content")
    c.showPage()
    c.save()

    index1 = create_index(pdf1)
    hash1 = compute_file_hash(pdf1)

    # Session 2: Upload report.pdf (same name, different content)
    pdf2 = workspace2 / "uploads" / "report.pdf"
    pdf2.parent.mkdir(parents=True)
    c = canvas.Canvas(str(pdf2))
    c.drawString(100, 750, "Session 2 content - DIFFERENT")
    c.showPage()
    c.save()

    hash2 = compute_file_hash(pdf2)
    assert hash1 != hash2  # Different content

    # Create index for session 2
    index2 = create_index(pdf2)

    # Both indexes should exist (different file paths)
    assert index1.exists()
    assert index2.exists()

    # Different hashes
    assert index1 != index2


if __name__ == "__main__":
    """Run tests with detailed output."""
    import sys

    print("\n" + "=" * 70)
    print("Testing Text Indexer and Search")
    print("=" * 70 + "\n")

    pytest.main([__file__, "-v", "-s"])
