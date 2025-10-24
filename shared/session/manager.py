"""Session manager - encapsulates SessionStore + WorkspaceManager."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Callable, Tuple

from shared.session.store import SessionStore
from shared.workspace.manager import WorkspaceManager

LOGGER = logging.getLogger(__name__)


class SessionManager:
    """Manage session lifecycle and state persistence.

    Responsibilities:
    - Create new sessions (generate ID, workspace, initial state)
    - Load/save sessions from persistent storage
    - Track current active session
    - Manage session-workspace coordination
    """

    def __init__(
        self,
        session_store: SessionStore,
        workspace_manager: WorkspaceManager,
        initial_state_factory: Callable[[], dict]
    ):
        """Initialize session manager.

        Args:
            session_store: Persistent session storage
            workspace_manager: Workspace file manager
            initial_state_factory: Factory function that creates initial state dict
        """
        self.session_store = session_store
        self.workspace_manager = workspace_manager
        self.initial_state_factory = initial_state_factory

        # Current active session
        self.current_session_id: Optional[str] = None
        self.current_state: Optional[dict] = None

        LOGGER.info("SessionManager initialized")

    def create_session(self, mentioned_skills: List[str] = None) -> Tuple[str, dict]:
        """Create a new session with fresh state and workspace.

        Args:
            mentioned_skills: Skills to preload in workspace

        Returns:
            (session_id, state): New session ID and initial state
        """
        session_id = str(uuid.uuid4())
        state = self.initial_state_factory()
        state["thread_id"] = session_id

        # Create workspace
        workspace_path = self.workspace_manager.create_session_workspace(
            session_id=session_id,
            mentioned_skills=mentioned_skills or []
        )
        state["workspace_path"] = str(workspace_path)

        self.current_session_id = session_id
        self.current_state = state

        LOGGER.info(f"Created new session: {session_id[:16]}...")
        return session_id, state

    def reset_session(self) -> Tuple[str, dict]:
        """Reset to a new session (discard current session without saving).

        Returns:
            (session_id, state): New session ID and initial state
        """
        LOGGER.info(f"Resetting session (old: {self.current_session_id[:16] if self.current_session_id else 'none'})")
        return self.create_session()

    def load_session(self, session_id_prefix: str) -> bool:
        """Load a saved session by ID prefix.

        Args:
            session_id_prefix: Prefix of session ID to load (e.g., "abc123")

        Returns:
            True if session loaded successfully, False otherwise
        """
        # Find matching sessions
        sessions = self.session_store.list_sessions()
        matching = [s for s in sessions if s[0].startswith(session_id_prefix)]

        if len(matching) == 0:
            LOGGER.warning(f"No sessions found matching prefix: {session_id_prefix}")
            return False

        if len(matching) > 1:
            LOGGER.warning(f"Multiple sessions match prefix {session_id_prefix}: {len(matching)} found")
            return False

        # Load the unique match
        session_id = matching[0][0]
        state = self.session_store.load(session_id)

        if not state:
            LOGGER.error(f"Failed to load session state: {session_id}")
            return False

        # Restore or create workspace if needed
        if "workspace_path" not in state or not state["workspace_path"]:
            LOGGER.info(f"Session {session_id[:16]} missing workspace, creating...")
            workspace_path = self.workspace_manager.create_session_workspace(
                session_id=session_id,
                mentioned_skills=[]
            )
            state["workspace_path"] = str(workspace_path)

        self.current_session_id = session_id
        self.current_state = state

        msg_count = len(state.get("messages", []))
        LOGGER.info(f"Loaded session {session_id[:16]}... with {msg_count} messages")
        return True

    def save_current_session(self):
        """Save current session to persistent storage.

        Note: Set environment variable DISABLE_SESSION_PERSISTENCE=true in tests
        to skip persistence (should only be used in automated tests).
        """
        # Skip if persistence is disabled (for testing only)
        if os.getenv("DISABLE_SESSION_PERSISTENCE", "").lower() == "true":
            LOGGER.debug("Session persistence disabled (test mode), skipping save")
            return

        if not self.current_state or not self.current_session_id:
            LOGGER.warning("No active session to save")
            return

        self.session_store.save(self.current_session_id, self.current_state)
        LOGGER.debug(f"Saved session: {self.current_session_id[:16]}...")

    def list_sessions(self) -> List[Tuple[str, str, str, int]]:
        """List all saved sessions.

        Returns:
            List of (thread_id, created_at, updated_at, message_count) tuples
        """
        return self.session_store.list_sessions()

    def get_current_session_info(self) -> Dict[str, any]:
        """Get information about current active session.

        Returns:
            Dict with session info, or empty dict if no active session
        """
        if not self.current_state or not self.current_session_id:
            return {"active": False}

        msg_count = len(self.current_state.get("messages", []))
        workspace_path = self.current_state.get("workspace_path")

        return {
            "active": True,
            "session_id": self.current_session_id,
            "session_id_short": self.current_session_id[:16],
            "message_count": msg_count,
            "workspace_path": workspace_path,
            "active_skill": self.current_state.get("active_skill"),
            "mentioned_agents": self.current_state.get("mentioned_agents", []),
            "todos": self.current_state.get("todos", []),
        }

    def update_workspace_skills(self, skill_ids: List[str]):
        """Add skills to current session's workspace.

        Args:
            skill_ids: List of skill IDs to add
        """
        if not self.current_session_id:
            LOGGER.warning("No active session, cannot update workspace skills")
            return

        workspace = self.workspace_manager.get_workspace(self.current_session_id)
        if workspace:
            self.workspace_manager._add_skills_to_workspace(workspace, skill_ids)
            LOGGER.info(f"Added skills to workspace: {skill_ids}")


__all__ = ["SessionManager"]
