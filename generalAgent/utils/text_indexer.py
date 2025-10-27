"""Text indexer for document search.

全局索引管理器，使用 MD5 标识文件，支持索引缓存和自动更新。
索引存储在 data/indexes/ 目录下。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from generalAgent.config.project_root import get_project_root
from generalAgent.config.settings import get_settings
from generalAgent.utils.document_extractors import chunk_document

LOGGER = logging.getLogger(__name__)

# 全局索引目录
INDEXES_DIR = get_project_root() / "data" / "indexes"


def compute_file_hash(file_path: Path) -> str:
    """计算文件 MD5 哈希"""
    md5 = hashlib.md5()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)

    return md5.hexdigest()


def get_index_path(file_hash: str) -> Path:
    """获取索引文件路径（基于文件 MD5）

    Args:
        file_hash: 文件 MD5 哈希值

    Returns:
        索引文件路径: data/indexes/{hash[:2]}/{hash}.index.json
        使用两级目录避免单目录文件过多
    """
    # 两级目录：前2个字符作为子目录
    subdir = file_hash[:2]
    index_dir = INDEXES_DIR / subdir
    index_dir.mkdir(parents=True, exist_ok=True)

    return index_dir / f"{file_hash}.index.json"


def index_exists(file_path: Path) -> bool:
    """检查文件是否已索引（且索引有效）"""
    file_hash = compute_file_hash(file_path)
    index_path = get_index_path(file_hash)

    if not index_path.exists():
        return False

    # 检查索引是否过期
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)

        indexed_at = datetime.fromisoformat(index_data.get("indexed_at", ""))
        threshold_hours = get_settings().documents.index_stale_threshold_hours
        stale_threshold = datetime.now() - timedelta(hours=threshold_hours)

        # 如果索引创建时间太久远，认为过期
        if indexed_at < stale_threshold:
            LOGGER.info(f"Index for {file_path.name} is stale (>  {threshold_hours}h), will rebuild")
            return False

        return True
    except Exception as e:
        LOGGER.warning(f"Failed to validate index for {file_path.name}: {e}")
        return False


def cleanup_old_indexes_for_file(file_path: Path, keep_hash: str):
    """清理指定文件路径的旧索引（自动处理同名文件覆盖场景）

    当用户上传同名文件但内容不同时（MD5 不同），会产生孤儿索引。
    此函数在创建新索引时自动清理旧索引，保持索引目录整洁。

    Args:
        file_path: 文件路径
        keep_hash: 要保留的文件哈希（当前版本）

    Example:
        用户在同一 session 中:
        1. 上传 report.pdf (hash: abc123) → 创建索引 abc123.index.json
        2. 上传 report.pdf (hash: def456) → 创建索引 def456.index.json
        3. 自动删除 abc123.index.json（孤儿索引）
    """
    if not INDEXES_DIR.exists():
        return

    file_path_str = str(file_path)
    deleted_count = 0

    for index_file in INDEXES_DIR.rglob("*.index.json"):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            # 如果是同一文件路径，但不是当前哈希，删除旧索引
            if index_data.get("file_path") == file_path_str:
                if index_data.get("file_hash") != keep_hash:
                    index_file.unlink()
                    deleted_count += 1
                    LOGGER.debug(f"Deleted old index for {file_path.name}: {index_file.name}")
        except Exception as e:
            LOGGER.warning(f"Failed to check index {index_file.name}: {e}")

    if deleted_count > 0:
        LOGGER.info(f"Cleaned up {deleted_count} old index(es) for {file_path.name}")


def create_index(file_path: Path) -> Path:
    """创建文档搜索索引

    Args:
        file_path: 文档文件路径

    Returns:
        索引文件路径

    Raises:
        Exception: 如果索引创建失败
    """
    LOGGER.info(f"Creating search index for {file_path.name}...")

    start_time = datetime.now()

    # 计算文件哈希
    file_hash = compute_file_hash(file_path)

    # 清理该文件路径的旧索引（处理同名文件覆盖场景）
    cleanup_old_indexes_for_file(file_path, keep_hash=file_hash)

    # 分块提取文档内容
    chunks = chunk_document(file_path)

    if not chunks:
        raise ValueError(f"No content extracted from {file_path.name}")

    # 为每个 chunk 构建搜索索引
    indexed_chunks = []
    for chunk in chunks:
        indexed_chunks.append({
            "chunk_id": chunk["id"],
            "page": chunk["page"],
            "text": chunk["text"],

            # 搜索索引
            "keywords": extract_keywords(chunk["text"]),
            "bigrams": extract_ngrams(chunk["text"], n=2),
            "trigrams": extract_ngrams(chunk["text"], n=3),

            "char_count": len(chunk["text"]),
            "char_offset": chunk.get("offset", 0)
        })

    # 构建索引数据
    index_data = {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "file_type": file_path.suffix,
        "file_hash": file_hash,
        "file_size": file_path.stat().st_size,

        "indexed_at": datetime.now().isoformat(),
        "indexer_version": "1.0",

        "metadata": {
            "total_pages": len(set(c["page"] for c in chunks)),
            "total_chunks": len(chunks),
            "total_chars": sum(c["char_count"] for c in indexed_chunks),
        },

        "chunks": indexed_chunks,

        # 预留向量检索字段（v2.0）
        "vector_index_available": False,
        "vector_model": None,
        "embeddings_path": None
    }

    # 保存索引
    index_path = get_index_path(file_hash)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    elapsed = (datetime.now() - start_time).total_seconds()
    LOGGER.info(
        f"Index created for {file_path.name}: "
        f"{len(chunks)} chunks, {index_path.stat().st_size:,} bytes, "
        f"took {elapsed:.2f}s"
    )

    return index_path


def load_index(file_path: Path) -> Dict:
    """加载文档索引

    Args:
        file_path: 文档文件路径

    Returns:
        索引数据字典

    Raises:
        FileNotFoundError: 如果索引不存在
    """
    file_hash = compute_file_hash(file_path)
    index_path = get_index_path(file_hash)

    if not index_path.exists():
        raise FileNotFoundError(f"Index not found for {file_path.name}")

    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def search_in_index(
    file_path: Path,
    query: str,
    max_results: int = 5
) -> List[Dict]:
    """在索引中搜索（多策略评分）

    Args:
        file_path: 文档文件路径
        query: 搜索关键词或短语
        max_results: 最大返回结果数

    Returns:
        匹配的 chunk 列表，每个包含:
        - chunk_id: chunk 编号
        - page: 页码
        - text: 文本内容
        - score: 匹配得分
        - matched_keywords: 匹配的关键词列表
    """
    # 加载索引
    index_data = load_index(file_path)

    # 预处理查询
    query_lower = query.lower()
    query_keywords = extract_keywords(query)
    query_bigrams = extract_ngrams(query, n=2)
    query_trigrams = extract_ngrams(query, n=3)

    # 搜索所有 chunks
    matches = []

    for chunk in index_data["chunks"]:
        score = 0
        matched_keywords = []

        # 策略 1: 完整短语匹配（权重最高）
        if query_lower in chunk["text"].lower():
            score += 10
            matched_keywords.append(f"phrase:'{query}'")

        # 策略 2: 三元词组匹配
        for trigram in query_trigrams:
            if trigram in chunk.get("trigrams", []):
                score += 5
                matched_keywords.append(f"3-gram:{trigram}")

        # 策略 3: 二元词组匹配
        for bigram in query_bigrams:
            if bigram in chunk.get("bigrams", []):
                score += 3
                matched_keywords.append(f"2-gram:{bigram}")

        # 策略 4: 单关键词匹配
        chunk_keywords_set = set(chunk["keywords"])
        for kw in query_keywords:
            # 精确匹配
            if kw in chunk_keywords_set:
                score += 2
                matched_keywords.append(kw)
            # 模糊匹配（子串）
            elif any(kw in ck or ck in kw for ck in chunk_keywords_set):
                score += 1
                matched_keywords.append(f"~{kw}")

        # 策略 5: 查询词覆盖率（bonus）
        text_lower = chunk["text"].lower()
        query_words = query_lower.split()
        matched_count = sum(1 for w in query_words if w in text_lower)
        coverage = matched_count / len(query_words) if query_words else 0
        score += coverage * 2  # 最多 +2 分

        if score > 0:
            matches.append({
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "text": chunk["text"],
                "score": round(score, 2),
                "matched_keywords": list(set(matched_keywords))[:5]  # 最多显示5个
            })

    # 按得分排序，返回 Top-K
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:max_results]


def extract_keywords(text: str) -> List[str]:
    """提取关键词（简单分词 + 停用词过滤）

    Args:
        text: 文本内容

    Returns:
        关键词列表（去重）
    """
    # 分词（中英文混合）
    words = re.findall(r'[\w]+', text.lower())

    # 停用词
    stopwords = {
        # 中文
        "的", "了", "在", "是", "和", "有", "与", "及", "等", "为", "将", "对", "由", "从", "这", "那",
        # 英文
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "as", "by", "from", "this", "that", "these", "those", "it", "is", "are", "was", "were"
    }

    # 过滤：停用词 + 长度 < 2
    keywords = [w for w in words if w not in stopwords and len(w) >= 2]

    return list(set(keywords))


def extract_ngrams(text: str, n: int) -> List[str]:
    """提取 N-gram（词组）

    Args:
        text: 文本内容
        n: N-gram 大小（2=bigram, 3=trigram）

    Returns:
        N-gram 列表（去重）
    """
    words = re.findall(r'[\w]+', text.lower())
    ngrams = []

    for i in range(len(words) - n + 1):
        ngram = " ".join(words[i:i+n])
        ngrams.append(ngram)

    return list(set(ngrams))


def cleanup_old_indexes(days: int = 30, remove_orphans: bool = True):
    """清理旧索引文件

    清理策略：
    1. 删除超过 N 天未访问的索引（按访问时间）
    2. 删除孤儿索引（文件路径不存在的索引）

    Args:
        days: 删除超过 N 天未访问的索引
        remove_orphans: 是否删除孤儿索引（文件不存在的索引）
    """
    if not INDEXES_DIR.exists():
        return

    threshold = datetime.now() - timedelta(days=days)
    deleted_by_time = 0
    deleted_orphans = 0

    for index_file in INDEXES_DIR.rglob("*.index.json"):
        try:
            # 检查孤儿索引
            if remove_orphans:
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)

                file_path = Path(index_data.get("file_path", ""))

                # 如果索引指向的文件不存在，删除索引
                if not file_path.exists():
                    index_file.unlink()
                    deleted_orphans += 1
                    LOGGER.debug(f"Deleted orphan index: {index_file.name} (file not found: {file_path})")
                    continue

            # 检查最后访问时间
            last_access = datetime.fromtimestamp(index_file.stat().st_atime)

            if last_access < threshold:
                index_file.unlink()
                deleted_by_time += 1
                LOGGER.debug(f"Deleted old index: {index_file.name}")
        except Exception as e:
            LOGGER.warning(f"Failed to process index {index_file.name}: {e}")

    total_deleted = deleted_by_time + deleted_orphans
    if total_deleted > 0:
        LOGGER.info(
            f"Cleaned up {total_deleted} index file(s): "
            f"{deleted_by_time} by age (>{days}d), "
            f"{deleted_orphans} orphans"
        )


def get_index_stats() -> Dict:
    """获取索引统计信息"""
    if not INDEXES_DIR.exists():
        return {
            "total_indexes": 0,
            "total_size_bytes": 0,
            "oldest_index": None,
            "newest_index": None
        }

    index_files = list(INDEXES_DIR.rglob("*.index.json"))

    if not index_files:
        return {
            "total_indexes": 0,
            "total_size_bytes": 0,
            "oldest_index": None,
            "newest_index": None
        }

    total_size = sum(f.stat().st_size for f in index_files)
    access_times = [(f, f.stat().st_mtime) for f in index_files]
    access_times.sort(key=lambda x: x[1])

    return {
        "total_indexes": len(index_files),
        "total_size_bytes": total_size,
        "oldest_index": access_times[0][0].name if access_times else None,
        "newest_index": access_times[-1][0].name if access_times else None
    }
