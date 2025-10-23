"""Optional Postgres checkpointer factory."""

from __future__ import annotations

from typing import Optional


def build_checkpointer(dsn: Optional[str]):
    """Return a Postgres checkpointer if DSN is provided and dependency available."""

    if not dsn:
        return None

    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "缺少 postgres checkpointer 依赖。请运行 `pip install langgraph[postgres]` 后重试，"
            "或在 .env 中移除 PG_DSN 以禁用持久化。"
        ) from exc

    return PostgresSaver.from_conn_string(dsn)
