"""Document content extractors for PDF, DOCX, XLSX, PPTX.

提供各种文档类型的文本提取功能，支持预览和完整提取。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

LOGGER = logging.getLogger(__name__)

# 支持的文档类型
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx"}


def get_document_info(file_path: Path) -> Dict:
    """获取文档基本信息（页数、字符数等）"""
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return _get_pdf_info(file_path)
    elif ext == ".docx":
        return _get_docx_info(file_path)
    elif ext == ".xlsx":
        return _get_xlsx_info(file_path)
    elif ext == ".pptx":
        return _get_pptx_info(file_path)
    else:
        return {"pages": 0, "chars": 0, "type": "unknown"}


def extract_preview(file_path: Path, max_pages: int, max_chars: int) -> str:
    """提取文档预览（前N页/sheets/slides）"""
    ext = file_path.suffix.lower()

    try:
        if ext == ".pdf":
            return _extract_pdf_preview(file_path, max_pages, max_chars)
        elif ext == ".docx":
            return _extract_docx_preview(file_path, max_pages, max_chars)
        elif ext == ".xlsx":
            return _extract_xlsx_preview(file_path, max_pages, max_chars)  # max_pages = sheets
        elif ext == ".pptx":
            return _extract_pptx_preview(file_path, max_pages, max_chars)  # max_pages = slides
        else:
            return f"Error: Unsupported document type: {ext}"
    except Exception as e:
        LOGGER.error(f"Failed to extract preview from {file_path}: {e}")
        return f"Error: Failed to extract preview - {str(e)}"


def extract_full_document(file_path: Path) -> str:
    """提取文档完整内容"""
    ext = file_path.suffix.lower()

    try:
        if ext == ".pdf":
            return _extract_pdf_full(file_path)
        elif ext == ".docx":
            return _extract_docx_full(file_path)
        elif ext == ".xlsx":
            return _extract_xlsx_full(file_path)
        elif ext == ".pptx":
            return _extract_pptx_full(file_path)
        else:
            return f"Error: Unsupported document type: {ext}"
    except Exception as e:
        LOGGER.error(f"Failed to extract content from {file_path}: {e}")
        return f"Error: Failed to extract content - {str(e)}"


def chunk_document(file_path: Path) -> List[Dict]:
    """将文档分块（用于索引）

    Returns:
        List of chunks, each with:
        - id: chunk 编号
        - page: 页码/sheet编号/slide编号
        - text: 文本内容
        - offset: 字符偏移量
    """
    ext = file_path.suffix.lower()

    try:
        if ext == ".pdf":
            return _chunk_pdf(file_path)
        elif ext == ".docx":
            return _chunk_docx(file_path)
        elif ext == ".xlsx":
            return _chunk_xlsx(file_path)
        elif ext == ".pptx":
            return _chunk_pptx(file_path)
        else:
            return []
    except Exception as e:
        LOGGER.error(f"Failed to chunk document {file_path}: {e}")
        return []


# ============ PDF 处理 ============

def _get_pdf_info(file_path: Path) -> Dict:
    """获取 PDF 信息"""
    import pdfplumber

    with pdfplumber.open(file_path) as pdf:
        total_chars = sum(len(page.extract_text() or "") for page in pdf.pages)
        return {
            "pages": len(pdf.pages),
            "chars": total_chars,
            "type": "pdf"
        }


def _extract_pdf_preview(file_path: Path, max_pages: int, max_chars: int) -> str:
    """提取 PDF 前 N 页"""
    import pdfplumber

    pages_content = []
    total_chars = 0

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages], 1):
            text = page.extract_text() or ""

            # 检查是否超过字符限制
            if total_chars + len(text) > max_chars:
                # 截断当前页
                remaining = max_chars - total_chars
                if remaining > 0:
                    pages_content.append(f"=== Page {i} ===\n{text[:remaining]}...")
                break

            pages_content.append(f"=== Page {i} ===\n{text}")
            total_chars += len(text)

    return "\n\n".join(pages_content)


def _extract_pdf_full(file_path: Path) -> str:
    """提取 PDF 完整内容"""
    import pdfplumber

    pages_content = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages_content.append(f"=== Page {i} ===\n{text}")

    return "\n\n".join(pages_content)


def _chunk_pdf(file_path: Path) -> List[Dict]:
    """PDF 按页分块"""
    import pdfplumber

    chunks = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            # 提取文本
            text = page.extract_text() or ""

            # 提取表格
            tables = page.extract_tables()
            if tables:
                text += "\n\n[Tables]\n"
                for table in tables:
                    for row in table:
                        text += " | ".join(str(cell or "") for cell in row) + "\n"

            if text.strip():
                chunks.append({
                    "id": i - 1,
                    "page": i,
                    "text": text.strip(),
                    "offset": sum(len(c["text"]) for c in chunks)
                })

    return chunks


# ============ DOCX 处理 ============

def _get_docx_info(file_path: Path) -> Dict:
    """获取 DOCX 信息"""
    from docx import Document

    doc = Document(file_path)
    total_chars = sum(len(para.text) for para in doc.paragraphs)

    return {
        "pages": max(1, len(doc.paragraphs) // 10),  # 估算页数
        "chars": total_chars,
        "type": "docx"
    }


def _extract_docx_preview(file_path: Path, max_pages: int, max_chars: int) -> str:
    """提取 DOCX 前 N 段（估算为页）"""
    from docx import Document

    doc = Document(file_path)
    paragraphs = []
    total_chars = 0

    # 每页约 10 段
    max_paragraphs = max_pages * 10

    for para in doc.paragraphs[:max_paragraphs]:
        text = para.text.strip()
        if not text:
            continue

        if total_chars + len(text) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 0:
                paragraphs.append(text[:remaining] + "...")
            break

        paragraphs.append(text)
        total_chars += len(text)

    return "\n\n".join(paragraphs)


def _extract_docx_full(file_path: Path) -> str:
    """提取 DOCX 完整内容"""
    from docx import Document

    doc = Document(file_path)
    paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]

    return "\n\n".join(paragraphs)


def _chunk_docx(file_path: Path) -> List[Dict]:
    """DOCX 按段落分块（合并到 ~1000 chars）"""
    from docx import Document

    doc = Document(file_path)
    chunks = []
    current_chunk = []
    current_length = 0
    page_estimate = 1

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # 如果当前块 + 新段落 > 1000 chars，保存当前块
        if current_length + len(text) > 1000 and current_chunk:
            chunks.append({
                "id": len(chunks),
                "page": page_estimate,
                "text": "\n\n".join(current_chunk),
                "offset": sum(len(c["text"]) for c in chunks)
            })
            current_chunk = [text]
            current_length = len(text)
            page_estimate += 1
        else:
            current_chunk.append(text)
            current_length += len(text)

    # 最后一个块
    if current_chunk:
        chunks.append({
            "id": len(chunks),
            "page": page_estimate,
            "text": "\n\n".join(current_chunk),
            "offset": sum(len(c["text"]) for c in chunks)
        })

    return chunks


# ============ XLSX 处理 ============

def _get_xlsx_info(file_path: Path) -> Dict:
    """获取 XLSX 信息"""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    sheet_count = len(wb.sheetnames)

    # 估算字符数
    total_chars = 0
    for sheet_name in wb.sheetnames[:3]:  # 只统计前3个sheet
        sheet = wb[sheet_name]
        for row in sheet.iter_rows(values_only=True, max_row=100):
            total_chars += sum(len(str(cell)) for cell in row if cell is not None)

    wb.close()

    return {
        "pages": sheet_count,  # Sheet 数量作为页数
        "chars": total_chars,
        "type": "xlsx"
    }


def _extract_xlsx_preview(file_path: Path, max_sheets: int, max_chars: int) -> str:
    """提取 XLSX 前 N 个 sheet"""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    sheets_content = []
    total_chars = 0

    for sheet_name in wb.sheetnames[:max_sheets]:
        sheet = wb[sheet_name]

        rows = []
        for row in sheet.iter_rows(values_only=True, max_row=100):  # 最多100行
            row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
            if row_text.strip():
                rows.append(row_text)
                total_chars += len(row_text)

                if total_chars > max_chars:
                    break

        if rows:
            sheet_content = f"=== Sheet: {sheet_name} ===\n" + "\n".join(rows)
            sheets_content.append(sheet_content)

        if total_chars > max_chars:
            break

    wb.close()
    return "\n\n".join(sheets_content)


def _extract_xlsx_full(file_path: Path) -> str:
    """提取 XLSX 完整内容"""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    sheets_content = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]

        rows = []
        for row in sheet.iter_rows(values_only=True, max_row=1000):  # 最多1000行
            row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
            if row_text.strip():
                rows.append(row_text)

        if rows:
            sheet_content = f"=== Sheet: {sheet_name} ===\n" + "\n".join(rows)
            sheets_content.append(sheet_content)

    wb.close()
    return "\n\n".join(sheets_content)


def _chunk_xlsx(file_path: Path) -> List[Dict]:
    """XLSX 按 sheet 分块"""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    chunks = []

    for sheet_idx, sheet_name in enumerate(wb.sheetnames, 1):
        sheet = wb[sheet_name]

        rows = []
        for row in sheet.iter_rows(values_only=True, max_row=1000):
            row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
            if row_text.strip():
                rows.append(row_text)

        if rows:
            chunks.append({
                "id": sheet_idx - 1,
                "page": sheet_idx,
                "text": f"[Sheet: {sheet_name}]\n" + "\n".join(rows),
                "offset": sum(len(c["text"]) for c in chunks)
            })

    wb.close()
    return chunks


# ============ PPTX 处理 ============

def _get_pptx_info(file_path: Path) -> Dict:
    """获取 PPTX 信息"""
    from pptx import Presentation

    prs = Presentation(file_path)
    total_chars = 0

    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                total_chars += len(shape.text)

    return {
        "pages": len(prs.slides),  # Slide 数量作为页数
        "chars": total_chars,
        "type": "pptx"
    }


def _extract_pptx_preview(file_path: Path, max_slides: int, max_chars: int) -> str:
    """提取 PPTX 前 N 张幻灯片"""
    from pptx import Presentation

    prs = Presentation(file_path)
    slides_content = []
    total_chars = 0

    for slide_idx, slide in enumerate(prs.slides[:max_slides], 1):
        texts = []
        for shape in slide.shapes:
            try:
                if hasattr(shape, "text"):
                    text = shape.text.strip()
                    if text:
                        texts.append(text)
                        total_chars += len(text)
            except Exception as e:
                # Skip shapes that can't be read
                LOGGER.debug(f"Failed to read shape in slide {slide_idx}: {e}")
                continue

        if texts:
            slide_content = f"=== Slide {slide_idx} ===\n" + "\n\n".join(texts)
            slides_content.append(slide_content)

        if total_chars > max_chars:
            break

    return "\n\n".join(slides_content)


def _extract_pptx_full(file_path: Path) -> str:
    """提取 PPTX 完整内容"""
    from pptx import Presentation

    prs = Presentation(file_path)
    slides_content = []

    for slide_idx, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            try:
                if hasattr(shape, "text"):
                    text = shape.text.strip()
                    if text:
                        texts.append(text)
            except Exception as e:
                LOGGER.debug(f"Failed to read shape in slide {slide_idx}: {e}")
                continue

        if texts:
            slide_content = f"=== Slide {slide_idx} ===\n" + "\n\n".join(texts)
            slides_content.append(slide_content)

    return "\n\n".join(slides_content)


def _chunk_pptx(file_path: Path) -> List[Dict]:
    """PPTX 按幻灯片分块"""
    from pptx import Presentation

    prs = Presentation(file_path)
    chunks = []

    for slide_idx, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            try:
                if hasattr(shape, "text"):
                    text = shape.text.strip()
                    if text:
                        texts.append(text)
            except Exception as e:
                LOGGER.debug(f"Failed to read shape in slide {slide_idx}: {e}")
                continue

        if texts:
            chunks.append({
                "id": slide_idx - 1,
                "page": slide_idx,
                "text": "\n\n".join(texts),
                "offset": sum(len(c["text"]) for c in chunks)
            })

    return chunks
