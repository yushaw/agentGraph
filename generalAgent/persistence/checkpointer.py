"""Legacy checkpointer module - deprecated.

Session persistence is now handled by session_store.py.
This file is kept for backward compatibility but returns None.
"""

from __future__ import annotations

from typing import Optional


def build_checkpointer(db_path: Optional[str] = None):
    """Return None - checkpointer is no longer used.

    Session persistence is now handled by SessionStore in main.py.
    """
    return None
