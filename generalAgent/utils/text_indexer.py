"""SQLite FTS5-based text indexer for document search.

全局索引管理器，使用 SQLite FTS5 全文搜索引擎。

特性（2025-10-27）：
- **大小写不敏感**：baseline = Baseline = BASELINE
- **英文词干提取**：baseline = baselines（Porter stemmer）
- **中文分词**：jieba 分词预处理
- **高性能**：倒排索引，O(log N) 查询复杂度
- **标准化存储**：一个 SQLite 数据库管理所有文档索引
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from generalAgent.config.project_root import get_project_root
from generalAgent.config.settings import get_settings
from generalAgent.utils.document_extractors import chunk_document

LOGGER = logging.getLogger(__name__)

# 全局索引数据库路径
INDEXES_DB = get_project_root() / "data" / "indexes.db"


def compute_file_hash(file_path: Path) -> str:
    """计算文件 MD5 哈希"""
    md5 = hashlib.md5()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)

    return md5.hexdigest()


def _get_connection() -> sqlite3.Connection:
    """获取数据库连接并初始化表结构"""
    # 确保目录存在
    INDEXES_DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(INDEXES_DB))
    conn.row_factory = sqlite3.Row  # 返回字典式行

    # 创建元数据表（记录文件信息）
    conn.execute('''
        CREATE TABLE IF NOT EXISTS file_metadata (
            file_hash TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            indexed_at TEXT NOT NULL,
            total_chunks INTEGER NOT NULL,
            full_text TEXT  -- 完整文档文本（用于 grep 搜索）
        )
    ''')

    # 迁移：为已存在的表添加 full_text 列（如果不存在）
    try:
        conn.execute('ALTER TABLE file_metadata ADD COLUMN full_text TEXT')
        conn.commit()
        LOGGER.info("Added full_text column to file_metadata table")
    except sqlite3.OperationalError:
        # 列已存在，忽略
        pass

    # 创建 FTS5 全文搜索表
    # tokenize='porter unicode61' - Porter stemmer + Unicode支持
    # remove_diacritics 2 - 移除变音符号
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            file_hash UNINDEXED,
            chunk_id UNINDEXED,
            page UNINDEXED,
            text,
            text_jieba,
            tokenize='porter unicode61 remove_diacritics 2'
        )
    ''')

    # 创建普通表存储chunk元数据
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chunks_meta (
            file_hash TEXT NOT NULL,
            chunk_id INTEGER NOT NULL,
            page INTEGER NOT NULL,
            offset INTEGER NOT NULL,
            PRIMARY KEY (file_hash, chunk_id),
            FOREIGN KEY (file_hash) REFERENCES file_metadata(file_hash) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    return conn


def index_exists(file_path: Path) -> bool:
    """检查文件是否已索引（且索引有效）"""
    file_hash = compute_file_hash(file_path)

    conn = _get_connection()
    try:
        cursor = conn.execute(
            'SELECT indexed_at FROM file_metadata WHERE file_hash = ?',
            (file_hash,)
        )
        row = cursor.fetchone()

        if not row:
            return False

        # 检查索引是否过期
        indexed_at = datetime.fromisoformat(row['indexed_at'])
        threshold_hours = get_settings().documents.index_stale_threshold_hours
        stale_threshold = datetime.now() - timedelta(hours=threshold_hours)

        if indexed_at < stale_threshold:
            LOGGER.info(f"Index for {file_path.name} is stale (> {threshold_hours}h), will rebuild")
            return False

        return True
    finally:
        conn.close()


def _preprocess_text_with_jieba(text: str) -> str:
    """使用 jieba 预处理中文文本

    将中文文本用 jieba 分词，用空格分隔，这样 FTS5 可以正确索引中文词汇。
    """
    settings = get_settings()

    if not settings.documents.use_jieba:
        return text

    try:
        import jieba
        # 禁用 jieba 的日志输出
        jieba.setLogLevel(logging.ERROR)
        # 使用搜索模式分词（会生成更多词组）
        words = jieba.cut_for_search(text)
        return ' '.join(words)
    except ImportError:
        LOGGER.warning("jieba not installed, skipping Chinese preprocessing")
        return text


def create_index(file_path: Path) -> Path:
    """为文档创建 FTS5 索引

    Returns:
        数据库文件路径（所有索引共享一个数据库）
    """
    file_hash = compute_file_hash(file_path)
    file_size = file_path.stat().st_size

    LOGGER.info(f"Creating FTS5 index for {file_path.name} (hash: {file_hash[:8]}...)")

    # 清理旧索引
    cleanup_old_indexes_for_file(file_path, keep_hash=file_hash)

    # 分块文档
    chunks = chunk_document(file_path)

    if not chunks:
        raise ValueError(f"No content extracted from {file_path.name}")

    # 合并所有 chunks 为完整文本（用于 grep 搜索）
    full_text = "\n".join(chunk['text'] for chunk in chunks)

    conn = _get_connection()
    try:
        # 插入文件元数据（包含完整文本）
        conn.execute('''
            INSERT OR REPLACE INTO file_metadata
            (file_hash, file_name, file_type, file_size, indexed_at, total_chunks, full_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            file_hash,
            file_path.name,
            file_path.suffix,
            file_size,
            datetime.now().isoformat(),
            len(chunks),
            full_text
        ))

        # 删除旧的 chunks（如果存在）
        conn.execute('DELETE FROM chunks_fts WHERE file_hash = ?', (file_hash,))
        conn.execute('DELETE FROM chunks_meta WHERE file_hash = ?', (file_hash,))

        # 插入 chunks
        for chunk in chunks:
            chunk_id = chunk['id']
            page = chunk['page']
            text = chunk['text']
            offset = chunk['offset']

            # jieba 预处理文本（用于中文搜索）
            text_jieba = _preprocess_text_with_jieba(text)

            # 插入 FTS5 表（用于全文搜索）
            conn.execute('''
                INSERT INTO chunks_fts (file_hash, chunk_id, page, text, text_jieba)
                VALUES (?, ?, ?, ?, ?)
            ''', (file_hash, chunk_id, page, text, text_jieba))

            # 插入元数据表
            conn.execute('''
                INSERT INTO chunks_meta (file_hash, chunk_id, page, offset)
                VALUES (?, ?, ?, ?)
            ''', (file_hash, chunk_id, page, offset))

        conn.commit()
        LOGGER.info(f"FTS5 index created: {len(chunks)} chunks")

    finally:
        conn.close()

    return INDEXES_DB


def _should_use_fts5(query: str, use_regex: bool) -> bool:
    """判断是否使用 FTS5（返回 False 则用 Grep）

    Args:
        query: 查询字符串
        use_regex: 用户是否明确指定正则模式

    Returns:
        True: 使用 FTS5（高效）
        False: 使用 Grep（正则支持）
    """
    import re

    # 1. 用户明确指定 use_regex=True → Grep
    if use_regex:
        return False

    # 2. 检测明确的正则语法（FTS5 不支持）
    regex_patterns = [
        r'\[.*?\]',       # 字符类 [A-Z]
        r'\{.*?\}',       # 量词 {5,10}
        r'\(',            # 分组 (pattern)
        r'\$',            # 行尾锚点
        r'\^',            # 行首锚点
        r'\\[dDwWsS]',    # 转义字符类 \d \w \s
        r'\.\*',          # 任意字符 .*
        r'\.\+',          # 至少一个 .+
        r'\.\?',          # 可选 .?
        r'(?<!")\|(?!")', # 或 | (不在引号内)
    ]

    for pattern in regex_patterns:
        if re.search(pattern, query):
            return False  # 包含复杂正则 → Grep

    # 3. FTS5 支持的模式允许通过：
    # - 引号短语: "section 4.1"
    # - 词尾通配符: base*
    # - 布尔操作: OR AND NOT
    return True  # 简单查询 → FTS5


def _search_with_grep(
    file_hash: str,
    full_text: str,
    regex_pattern: str,
    max_results: int,
    context_chars: int
) -> List[Dict]:
    """使用 Python re 在完整文本中搜索（支持完整正则）

    Args:
        file_hash: 文件哈希
        full_text: 完整文档文本
        regex_pattern: 正则表达式
        max_results: 最大结果数
        context_chars: 上下文字符数

    Returns:
        搜索结果列表 [{'chunk_id': 0, 'page': 0, 'text': '...', 'score': 100.0}, ...]
    """
    import re

    if not full_text or not regex_pattern:
        return []

    results = []

    try:
        # 编译正则（忽略大小写）
        pattern = re.compile(regex_pattern, re.IGNORECASE | re.MULTILINE)

        # 查找所有匹配
        for match_idx, match in enumerate(pattern.finditer(full_text)):
            if len(results) >= max_results:
                break

            start = match.start()
            end = match.end()

            # 提取上下文
            context_start = max(0, start - context_chars)
            context_end = min(len(full_text), end + context_chars)

            text_with_context = full_text[context_start:context_end]

            # 添加省略号
            if context_start > 0:
                text_with_context = "..." + text_with_context
            if context_end < len(full_text):
                text_with_context = text_with_context + "..."

            results.append({
                'chunk_id': match_idx,  # 使用匹配索引作为 ID
                'page': 0,  # Grep 搜索无法确定页码
                'text': text_with_context,
                'score': 100.0  # Grep 无相关度评分，固定值
            })

    except re.error as e:
        LOGGER.warning(f"Invalid regex pattern '{regex_pattern}': {e}")
        return []

    return results


def _escape_fts5_special_chars(query: str) -> str:
    """转义 FTS5 查询中的特殊字符

    FTS5 特殊字符：. , : ; ( ) [ ] { } * " '
    策略：
    - 检测数字带小数点（如 4.1），自动加引号
    - 检测带标点的短语，建议用引号

    Args:
        query: 原始查询字符串

    Returns:
        转义后的查询字符串
    """
    import re

    # 转义数字带小数点（如 4.1 -> "4.1"）
    # 只处理未被引号包裹的数字
    def quote_decimals(text):
        # 匹配不在引号内的小数
        pattern = r'(?<!")(\b\d+\.\d+\b)(?!")'
        return re.sub(pattern, r'"\1"', text)

    query = quote_decimals(query)

    return query


def _extract_keywords_from_regex(regex_pattern: str) -> str:
    """从正则表达式中提取关键词（用于 FTS5 初步搜索）

    策略：
    - 提取字母数字序列（忽略特殊字符）
    - 移除正则元字符（^$.*+?[]{}()|\）
    - 如果提取不到关键词，返回空字符串（将搜索所有chunks）

    Args:
        regex_pattern: 正则表达式模式

    Returns:
        提取的关键词（空格分隔）
    """
    import re

    # 移除正则元字符
    cleaned = re.sub(r'[\\^$.*+?[\]{}()|]', ' ', regex_pattern)

    # 提取字母数字词
    words = re.findall(r'\w+', cleaned)

    # 过滤太短的词（可能是噪音）
    keywords = [w for w in words if len(w) >= 2]

    if not keywords:
        # 无法提取关键词，返回通配符（匹配所有）
        return "*"

    # 返回 OR 组合（FTS5 语法）
    return " OR ".join(keywords)


def _filter_by_regex(
    results: List[Dict],
    regex_pattern: str,
    max_results: int
) -> List[Dict]:
    """使用正则表达式过滤搜索结果

    Args:
        results: 搜索结果列表
        regex_pattern: 正则表达式模式
        max_results: 最大结果数

    Returns:
        匹配正则的结果列表
    """
    if not results or not regex_pattern:
        return results

    import re

    try:
        # 编译正则（支持多行和大小写不敏感）
        pattern = re.compile(regex_pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        LOGGER.error(f"Invalid regex pattern '{regex_pattern}': {e}")
        return []  # 正则无效时返回空结果

    filtered_results = []
    for result in results:
        text = result['text']
        if pattern.search(text):
            # 计算匹配数（用于评分）
            matches = pattern.findall(text)
            result_copy = result.copy()
            result_copy['score'] = float(len(matches))  # 匹配次数作为得分
            filtered_results.append(result_copy)

    # 按匹配次数排序
    filtered_results.sort(key=lambda x: x['score'], reverse=True)

    return filtered_results[:max_results]


def _expand_context(
    conn: sqlite3.Connection,
    file_hash: str,
    results: List[Dict],
    context_chars: int,
    query: str
) -> List[Dict]:
    """扩展搜索结果的上下文（跨 chunk 获取）

    策略：
    1. 提取查询在 chunk 中的位置
    2. 如果当前 chunk 的上下文不够 context_chars，尝试获取相邻 chunk
    3. 优先扩展查询位置周围的文本

    Args:
        conn: 数据库连接
        file_hash: 文件哈希
        results: 搜索结果列表
        context_chars: 目标上下文字符数
        query: 搜索查询

    Returns:
        扩展上下文后的结果列表
    """
    if not results or context_chars <= 0:
        return results

    expanded_results = []

    for result in results:
        chunk_id = result['chunk_id']
        text = result['text']

        # 如果当前 chunk 的文本已经足够长，直接返回
        if len(text) >= context_chars:
            expanded_results.append(result)
            continue

        # 需要从相邻 chunk 获取更多上下文
        # 计算需要多少额外字符
        needed_chars = context_chars - len(text)
        half_needed = needed_chars // 2

        # 获取前一个 chunk（如果存在）
        prev_text = ""
        if chunk_id > 0:
            cursor = conn.execute('''
                SELECT text FROM chunks_fts
                WHERE file_hash = ? AND chunk_id = ?
            ''', (file_hash, chunk_id - 1))
            row = cursor.fetchone()
            if row:
                prev_text = row['text']
                # 只取后半部分（避免上下文过长）
                if len(prev_text) > half_needed:
                    prev_text = "..." + prev_text[-half_needed:]

        # 获取后一个 chunk（如果存在）
        next_text = ""
        cursor = conn.execute('''
            SELECT text FROM chunks_fts
            WHERE file_hash = ? AND chunk_id = ?
        ''', (file_hash, chunk_id + 1))
        row = cursor.fetchone()
        if row:
            next_text = row['text']
            # 只取前半部分（避免上下文过长）
            if len(next_text) > half_needed:
                next_text = next_text[:half_needed] + "..."

        # 组合文本
        expanded_text = prev_text + text + next_text

        # 更新结果
        expanded_result = result.copy()
        expanded_result['text'] = expanded_text
        expanded_results.append(expanded_result)

    return expanded_results


def search_in_index(
    file_path: Path,
    query: str,
    max_results: int = 5,
    context_chars: int = 100,
    use_regex: bool = False
) -> List[Dict]:
    """在索引中搜索内容（使用 FTS5）

    特性：
    - 大小写不敏感
    - 英文词干提取（baseline = baselines）
    - 中文分词支持
    - BM25 排序（FTS5 内置）
    - 跨 chunk 上下文获取
    - 正则表达式搜索（FTS5 + Python re 后处理）

    Args:
        file_path: 文档路径
        query: 搜索查询（如果 use_regex=True，则为正则表达式）
        max_results: 最大结果数
        context_chars: 上下文字符数（会尝试从相邻 chunk 获取更多上下文）
        use_regex: 是否使用正则表达式搜索（先用 FTS5 找候选，再用 re 过滤）

    Returns:
        搜索结果列表，每项包含:
        - chunk_id: chunk 编号
        - page: 页码
        - text: 文本内容（已扩展上下文）
        - score: BM25 相关性得分（对于正则搜索，score 始终为 1.0）
    """
    file_hash = compute_file_hash(file_path)

    if not index_exists(file_path):
        raise FileNotFoundError(f"No index found for {file_path.name}. Create index first.")

    # 处理空查询
    if not query or not query.strip():
        return []

    # 判断使用 FTS5 还是 Grep
    use_fts5 = _should_use_fts5(query, use_regex)

    if not use_fts5:
        # 使用 Grep 搜索完整文本
        LOGGER.info(f"Using Grep search for pattern: {query}")
        conn = _get_connection()
        try:
            # 获取完整文本
            cursor = conn.execute(
                'SELECT full_text FROM file_metadata WHERE file_hash = ?',
                (file_hash,)
            )
            row = cursor.fetchone()

            if not row or not row['full_text']:
                LOGGER.warning(f"No full_text found for {file_path.name}")
                return []

            full_text = row['full_text']
            return _search_with_grep(file_hash, full_text, query, max_results, context_chars)

        finally:
            conn.close()

    # 使用 FTS5 搜索
    LOGGER.info(f"Using FTS5 search for query: {query}")
    conn = _get_connection()
    try:
        # 正则搜索模式：提取关键词并扩大搜索范围
        if use_regex:
            # 从正则表达式中提取可能的关键词
            search_query = _extract_keywords_from_regex(query)
            # 获取更多候选（用于正则过滤）
            candidate_limit = max_results * 10
        else:
            # 转义 FTS5 特殊字符（如小数点）
            search_query = _escape_fts5_special_chars(query)
            candidate_limit = max_results

        # FTS5 搜索查询
        # - 搜索 text 列（英文，Porter stemmer 处理）
        # - 搜索 text_jieba 列（中文分词结果）
        # - 使用 bm25() 函数获取相关性得分
        # - ORDER BY rank 自动按相关性排序（rank 是 bm25 分数的负值）

        results = []

        # 为中文查询预处理（jieba 分词）
        query_jieba = _preprocess_text_with_jieba(search_query)

        # 尝试在两个字段中搜索
        search_attempts = [
            ('text', search_query),          # 英文搜索（Porter stemmer）
            ('text_jieba', query_jieba)  # 中文搜索（jieba 分词）
        ]

        for column, search_query in search_attempts:
            if not search_query or not search_query.strip():
                continue

            retry_count = 0
            max_retries = 1
            last_error = None
            cursor = None  # Initialize cursor to avoid UnboundLocalError

            while retry_count <= max_retries:
                try:
                    # FTS5 的 bm25() 函数需要使用表名作为参数
                    cursor = conn.execute(f'''
                        SELECT
                            c.chunk_id,
                            m.page,
                            c.text,
                            bm25(chunks_fts) as score
                        FROM chunks_fts c
                        JOIN chunks_meta m ON c.file_hash = m.file_hash AND c.chunk_id = m.chunk_id
                        WHERE c.file_hash = ? AND {column} MATCH ?
                        ORDER BY score
                        LIMIT ?
                    ''', (file_hash, search_query, candidate_limit))
                    break  # 成功，退出重试循环
                except Exception as e:
                    last_error = e
                    # 检测是否是语法错误
                    if "syntax error" in str(e).lower() and retry_count == 0:
                        # 第一次尝试失败，使用更激进的转义
                        LOGGER.warning(f"FTS5 syntax error, retrying with escaped query: {e}")
                        # 简单回退：移除所有布尔操作符，只保留关键词
                        import re
                        words = re.findall(r'\w+', search_query)
                        if words:
                            search_query = " OR ".join(words)
                            retry_count += 1
                        else:
                            break  # 无法提取关键词，放弃
                    else:
                        # 其他错误或第二次失败，跳过此列
                        break

            if last_error and retry_count > max_retries:
                LOGGER.warning(f"FTS5 search failed for column {column} after retries: {last_error}")
                continue

            # Skip if cursor was not successfully created
            if cursor is None:
                continue

            for row in cursor:
                results.append({
                    'chunk_id': row['chunk_id'],
                    'page': row['page'],
                    'text': row['text'],
                    'score': abs(row['score'])  # 转为正数（越大越相关）
                })

            if results:
                break  # 找到结果就停止

        # 按分数降序排序并去重
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        # 去重（可能同一chunk在两个字段都匹配）
        seen = set()
        unique_results = []
        for r in results:
            if r['chunk_id'] not in seen:
                seen.add(r['chunk_id'])
                unique_results.append(r)

        # 扩展上下文（如果需要）
        expanded_results = _expand_context(
            conn, file_hash, unique_results[:max_results], context_chars, query
        )

        # 正则表达式后处理（如果启用）
        if use_regex:
            expanded_results = _filter_by_regex(expanded_results, query, max_results)

        return expanded_results

    finally:
        conn.close()


def load_index(file_path: Path) -> Dict:
    """加载索引数据（兼容接口，返回元数据）"""
    file_hash = compute_file_hash(file_path)

    conn = _get_connection()
    try:
        cursor = conn.execute(
            'SELECT * FROM file_metadata WHERE file_hash = ?',
            (file_hash,)
        )
        row = cursor.fetchone()

        if not row:
            raise FileNotFoundError(f"No index found for {file_path.name}")

        return {
            'file_name': row['file_name'],
            'file_type': row['file_type'],
            'file_hash': row['file_hash'],
            'indexed_at': row['indexed_at'],
            'total_chunks': row['total_chunks']
        }
    finally:
        conn.close()


def cleanup_old_indexes_for_file(file_path: Path, keep_hash: str):
    """清理指定文件路径的旧索引（处理同名文件覆盖场景）"""
    # FTS5 版本：直接删除旧hash的数据即可
    # 外键 ON DELETE CASCADE 会自动清理关联数据

    conn = _get_connection()
    try:
        # 查找同名但不同hash的文件
        cursor = conn.execute('''
            SELECT file_hash FROM file_metadata
            WHERE file_name = ? AND file_hash != ?
        ''', (file_path.name, keep_hash))

        old_hashes = [row['file_hash'] for row in cursor]

        for old_hash in old_hashes:
            LOGGER.info(f"Cleaning up old index for {file_path.name} (hash: {old_hash[:8]}...)")
            conn.execute('DELETE FROM file_metadata WHERE file_hash = ?', (old_hash,))

        conn.commit()
    finally:
        conn.close()


def cleanup_old_indexes(days: int = 30, remove_orphans: bool = True):
    """清理旧索引

    Args:
        days: 清理多少天前的索引
        remove_orphans: 是否清理孤儿索引（文件已删除）
    """
    conn = _get_connection()
    try:
        threshold = datetime.now() - timedelta(days=days)

        # 清理过期索引
        cursor = conn.execute('''
            DELETE FROM file_metadata
            WHERE indexed_at < ?
        ''', (threshold.isoformat(),))

        deleted = cursor.rowcount
        LOGGER.info(f"Cleaned up {deleted} old indexes (>{days} days)")

        # 清理孤儿索引（可选）
        if remove_orphans:
            # 这个需要遍历所有索引检查文件是否存在
            # 暂时跳过，等后续需要时实现
            pass

        conn.commit()
    finally:
        conn.close()


def get_index_stats() -> Dict:
    """获取索引统计信息"""
    conn = _get_connection()
    try:
        cursor = conn.execute('SELECT COUNT(*) as total FROM file_metadata')
        total_files = cursor.fetchone()['total']

        cursor = conn.execute('SELECT COUNT(*) as total FROM chunks_fts')
        total_chunks = cursor.fetchone()['total']

        cursor = conn.execute('SELECT SUM(file_size) as total FROM file_metadata')
        total_size = cursor.fetchone()['total'] or 0

        return {
            'total_files': total_files,
            'total_chunks': total_chunks,
            'total_size_bytes': total_size,
            'database_path': str(INDEXES_DB)
        }
    finally:
        conn.close()
