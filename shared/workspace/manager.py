"""Workspace management for session-isolated file operations."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import List, Optional

LOGGER = logging.getLogger(__name__)


class WorkspaceManager:
    """Manage per-session isolated workspaces.

    Each session gets an isolated workspace directory where:
    - Skills are symlinked for quick access
    - User uploads are stored
    - Agent outputs are written
    - Temporary files are created

    Architecture inspired by:
    - OpenAI Code Interpreter (/home/sandbox + /mnt/data)
    - E2B (per-session VM isolation)
    - Jupyter Notebook (structured data directories)
    """

    def __init__(self, root_dir: Path | str = "data/workspace", skill_registry=None):
        """Initialize workspace manager.

        Args:
            root_dir: Root directory for all workspaces
            skill_registry: SkillRegistry for dependency management (optional)
        """
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.skill_registry = skill_registry
        LOGGER.info(f"WorkspaceManager initialized: {self.root.resolve()}")

    def create_session_workspace(
        self,
        session_id: str,
        mentioned_skills: Optional[List[str]] = None,
        force: bool = False
    ) -> Path:
        """Create or update isolated workspace for a session.

        Directory structure:
            workspace/{session_id}/
                ├── skills/          # Symlinked skills (read-only)
                │   └── pdf/
                │       ├── SKILL.md
                │       └── scripts/
                ├── uploads/         # User-uploaded files
                ├── outputs/         # Agent-generated files
                ├── temp/            # Temporary files
                └── .metadata.json   # Session metadata

        Args:
            session_id: Session/thread ID
            mentioned_skills: Skills to load (e.g., ["pdf", "pptx"])
            force: Force recreate workspace if exists

        Returns:
            Path to workspace root
        """
        workspace = self.root / session_id

        # Force recreate: delete existing workspace
        if workspace.exists() and force:
            LOGGER.info(f"Force recreating workspace: {session_id}")
            shutil.rmtree(workspace)

        # Check if already exists
        if workspace.exists() and not force:
            LOGGER.debug(f"Workspace already exists: {workspace}")

            # Add newly mentioned skills if any
            if mentioned_skills:
                self._add_skills_to_workspace(workspace, mentioned_skills)

            return workspace

        # Create fresh workspace
        LOGGER.info(f"Creating workspace for session: {session_id}")
        workspace.mkdir(parents=True, exist_ok=True)

        # Create standard directories
        (workspace / "uploads").mkdir(exist_ok=True)
        (workspace / "outputs").mkdir(exist_ok=True)
        (workspace / "temp").mkdir(exist_ok=True)

        # Load mentioned skills (deduplicate)
        unique_skills = list(set(mentioned_skills)) if mentioned_skills else []
        if unique_skills:
            self._add_skills_to_workspace(workspace, unique_skills)

        # Write metadata
        metadata = {
            "session_id": session_id,
            "created_at": time.time(),
            "mentioned_skills": unique_skills,
        }
        (workspace / ".metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8"
        )

        LOGGER.info(f"Workspace created: {workspace}")
        return workspace

    def _add_skills_to_workspace(self, workspace: Path, skill_ids: List[str]):
        """Add skills to workspace via symlink.

        Args:
            workspace: Workspace directory
            skill_ids: List of skill IDs to add
        """
        skills_dir = workspace / "skills"
        skills_dir.mkdir(exist_ok=True)

        # Load metadata to track skills
        metadata_file = workspace / ".metadata.json"
        metadata = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        existing_skills = set(metadata.get("mentioned_skills", []))

        for skill_id in skill_ids:
            if skill_id in existing_skills:
                continue  # Already loaded

            # Find skill source directory
            # Try multiple possible locations
            possible_paths = [
                Path(f"skills/{skill_id}"),
                Path(f"generalAgent/skills/{skill_id}"),
            ]

            src = None
            for path in possible_paths:
                if path.exists():
                    src = path.resolve()
                    break

            if not src:
                LOGGER.warning(f"Skill not found: {skill_id}")
                continue

            dst = skills_dir / skill_id

            # Install dependencies if needed
            if self.skill_registry:
                success, msg = self.skill_registry.ensure_dependencies(skill_id)
                if not success:
                    LOGGER.warning(f"  ⚠ Dependency installation failed for {skill_id}: {msg}")
                    # Continue anyway, script execution will show detailed error
                elif "installed successfully" in msg:
                    LOGGER.info(f"  ✓ Dependencies installed for {skill_id}")

            # Use symlink for fast, read-only access
            try:
                if dst.exists():
                    # Remove old symlink/directory
                    if dst.is_symlink():
                        dst.unlink()
                    else:
                        shutil.rmtree(dst)

                dst.symlink_to(src, target_is_directory=True)
                existing_skills.add(skill_id)
                LOGGER.info(f"  ✓ Linked skill: {skill_id} -> {src}")

            except OSError as e:
                # Symlink failed (maybe Windows without admin), fallback to copy
                LOGGER.warning(f"Symlink failed for {skill_id}, copying instead: {e}")
                shutil.copytree(src, dst, dirs_exist_ok=True)
                existing_skills.add(skill_id)
                LOGGER.info(f"  ✓ Copied skill: {skill_id}")

        # Update metadata
        metadata["mentioned_skills"] = list(existing_skills)
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def get_workspace(self, session_id: str) -> Optional[Path]:
        """Get workspace path for a session.

        Args:
            session_id: Session ID

        Returns:
            Workspace path if exists, None otherwise
        """
        workspace = self.root / session_id
        return workspace if workspace.exists() else None

    def cleanup_old_workspaces(self, days: int = 7):
        """Delete workspaces older than N days.

        Args:
            days: Age threshold in days
        """
        cutoff = time.time() - (days * 86400)
        cleaned = 0

        for workspace in self.root.iterdir():
            if not workspace.is_dir():
                continue

            metadata_file = workspace / ".metadata.json"
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    created_at = metadata.get("created_at", 0)

                    if created_at < cutoff:
                        LOGGER.info(f"Cleaning old workspace: {workspace.name}")
                        shutil.rmtree(workspace)
                        cleaned += 1
                except Exception as e:
                    LOGGER.warning(f"Failed to clean workspace {workspace.name}: {e}")

        if cleaned > 0:
            LOGGER.info(f"Cleaned {cleaned} old workspaces (older than {days} days)")

        return cleaned

    def get_workspace_info(self, session_id: str) -> dict:
        """Get workspace information.

        Args:
            session_id: Session ID

        Returns:
            Workspace info dict
        """
        workspace = self.get_workspace(session_id)
        if not workspace:
            return {"exists": False}

        metadata_file = workspace / ".metadata.json"
        metadata = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        # Count files
        def count_files(path: Path) -> int:
            return len(list(path.rglob("*"))) if path.exists() else 0

        return {
            "exists": True,
            "path": str(workspace),
            "created_at": metadata.get("created_at"),
            "mentioned_skills": metadata.get("mentioned_skills", []),
            "uploads_count": count_files(workspace / "uploads"),
            "outputs_count": count_files(workspace / "outputs"),
            "temp_count": count_files(workspace / "temp"),
        }
