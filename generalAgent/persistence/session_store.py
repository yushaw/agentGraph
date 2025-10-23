"""Simple SQLite-based session storage."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any


class SessionStore:
    """Simple SQLite store for saving and loading conversation sessions."""

    def __init__(self, db_path: str = "data/sessions.db"):
        """Initialize the session store.

        Args:
            db_path: Path to SQLite database file
        """
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    thread_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, thread_id: str, state: Dict[str, Any]):
        """Save a session state to database.

        Args:
            thread_id: Unique session identifier
            state: The session state dictionary
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Serialize state to JSON (need to handle non-serializable objects)
            state_json = self._serialize_state(state)

            message_count = len(state.get("messages", []))
            now = datetime.utcnow().isoformat()

            # Check if session exists
            cursor = conn.execute(
                "SELECT created_at FROM sessions WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()

            if row:
                # Update existing session
                conn.execute(
                    """UPDATE sessions
                       SET state_json = ?, updated_at = ?, message_count = ?
                       WHERE thread_id = ?""",
                    (state_json, now, message_count, thread_id)
                )
            else:
                # Insert new session
                conn.execute(
                    """INSERT INTO sessions (thread_id, state_json, created_at, updated_at, message_count)
                       VALUES (?, ?, ?, ?, ?)""",
                    (thread_id, state_json, now, now, message_count)
                )

            conn.commit()
        finally:
            conn.close()

    def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Load a session state from database.

        Args:
            thread_id: Unique session identifier

        Returns:
            The session state dictionary, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT state_json FROM sessions WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()

            if row:
                state_json = row[0]
                return self._deserialize_state(state_json)
            return None
        finally:
            conn.close()

    def list_sessions(self) -> List[tuple]:
        """List all saved sessions.

        Returns:
            List of (thread_id, created_at, updated_at, message_count) tuples
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """SELECT thread_id, created_at, updated_at, message_count
                   FROM sessions
                   ORDER BY updated_at DESC"""
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def delete(self, thread_id: str):
        """Delete a session from database.

        Args:
            thread_id: Unique session identifier
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
            conn.commit()
        finally:
            conn.close()

    def _serialize_state(self, state: Dict[str, Any]) -> str:
        """Serialize state to JSON string.

        Handles LangChain messages by converting them to dicts.
        """
        from langchain_core.messages import BaseMessage

        def serialize_obj(obj):
            if isinstance(obj, BaseMessage):
                # Convert message to dict
                msg_dict = {
                    "__type__": "message",
                    "type": obj.type,
                    "content": obj.content,
                    "id": getattr(obj, "id", None),
                    "name": getattr(obj, "name", None),
                    "tool_calls": getattr(obj, "tool_calls", None),
                }
                # For ToolMessage, also save tool_call_id
                if obj.type == "tool":
                    msg_dict["tool_call_id"] = getattr(obj, "tool_call_id", None)
                return msg_dict
            elif isinstance(obj, dict):
                return {k: serialize_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_obj(item) for item in obj]
            else:
                return obj

        serializable = serialize_obj(state)
        return json.dumps(serializable, ensure_ascii=False)

    def _deserialize_state(self, state_json: str) -> Dict[str, Any]:
        """Deserialize JSON string to state.

        Reconstructs LangChain messages from dicts.
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

        def deserialize_obj(obj):
            if isinstance(obj, dict):
                # Check if it's a serialized message
                if obj.get("__type__") == "message":
                    msg_type = obj.get("type")
                    content = obj.get("content")

                    if msg_type == "human":
                        return HumanMessage(content=content, id=obj.get("id"))
                    elif msg_type == "ai":
                        msg = AIMessage(content=content, id=obj.get("id"))
                        if obj.get("tool_calls"):
                            msg.tool_calls = obj["tool_calls"]
                        return msg
                    elif msg_type == "system":
                        return SystemMessage(content=content, id=obj.get("id"))
                    elif msg_type == "tool":
                        # Ensure tool_call_id is never empty
                        tool_call_id = obj.get("tool_call_id") or obj.get("id") or "unknown"
                        return ToolMessage(
                            content=content,
                            tool_call_id=tool_call_id,
                            name=obj.get("name", "")
                        )
                    else:
                        # Unknown message type, return as dict
                        return obj
                else:
                    return {k: deserialize_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [deserialize_obj(item) for item in obj]
            else:
                return obj

        data = json.loads(state_json)
        return deserialize_obj(data)
