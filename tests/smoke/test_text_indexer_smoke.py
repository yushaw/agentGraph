"""Smoke tests for text indexer FTS5.

快速验证核心功能（< 5s），用于 CI/CD 前置检查。

测试覆盖：
1. 基本索引创建和搜索
2. 大小写不敏感（baseline = BASELINE）
3. 英文词干提取（baseline = baselines）
"""

import pytest
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from generalAgent.utils.text_indexer import (
    create_index,
    search_in_index,
    index_exists,
    INDEXES_DB,
)


@pytest.fixture
def quick_test_pdf(tmp_path):
    """快速生成包含核心测试内容的 PDF"""
    pdf_path = tmp_path / "smoke_test.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)

    # 核心测试内容：大小写 + 词干
    c.drawString(100, 750, "Machine Learning Baselines and Performance Metrics")
    c.drawString(100, 730, "We compared our model against three baseline systems.")
    c.drawString(100, 710, "The BASELINE accuracy was 85%, while our model achieved 92%.")
    c.drawString(100, 690, "Multiple baselines were tested across different datasets.")

    c.showPage()
    c.save()
    return pdf_path


@pytest.fixture
def cleanup_db():
    """清理测试数据库"""
    yield
    if INDEXES_DB.exists():
        INDEXES_DB.unlink()


def test_smoke_basic_indexing_and_search(quick_test_pdf, cleanup_db):
    """冒烟测试：基本索引创建和搜索"""
    # 创建索引
    db_path = create_index(quick_test_pdf)
    assert db_path.exists()
    assert index_exists(quick_test_pdf)

    # 搜索测试
    results = search_in_index(quick_test_pdf, "baseline", max_results=5)
    assert len(results) > 0, "Should find 'baseline'"

    # 验证结果包含相关内容
    assert any("baseline" in r['text'].lower() for r in results)


def test_smoke_case_insensitivity(quick_test_pdf, cleanup_db):
    """冒烟测试：大小写不敏感（核心需求验证）"""
    create_index(quick_test_pdf)

    # 小写搜索应该匹配大写
    results_lower = search_in_index(quick_test_pdf, "baseline", max_results=5)
    results_upper = search_in_index(quick_test_pdf, "BASELINE", max_results=5)

    assert len(results_lower) > 0, "Lowercase search should find results"
    assert len(results_upper) > 0, "Uppercase search should find results"

    # 两者应该找到相同的内容
    assert len(results_lower) == len(results_upper), "Case insensitive search should return same count"


def test_smoke_stemming(quick_test_pdf, cleanup_db):
    """冒烟测试：英文词干提取（核心需求验证）"""
    create_index(quick_test_pdf)

    # 单数搜索应该匹配复数
    results_singular = search_in_index(quick_test_pdf, "baseline", max_results=10)
    results_plural = search_in_index(quick_test_pdf, "baselines", max_results=10)

    assert len(results_singular) > 0, "Singular 'baseline' should find results"
    assert len(results_plural) > 0, "Plural 'baselines' should find results"

    # 验证能找到包含 baselines 的内容
    text_combined = " ".join(r['text'].lower() for r in results_plural)
    assert "baselines" in text_combined or "baseline" in text_combined
