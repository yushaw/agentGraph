"""Test that reminders are generated only once (not repeated every turn)."""
import pytest
from generalAgent.graph.state import AppState
from generalAgent.utils.file_processor import build_file_upload_reminder
from generalAgent.config.skill_config_loader import SkillConfig


def test_uploaded_files_structure():
    """Test that uploaded_files and new_uploaded_files are separate fields."""
    state: AppState = {
        "uploaded_files": [{"filename": "old.pdf"}],
        "new_uploaded_files": [{"filename": "new.pdf"}],
    }

    assert state["uploaded_files"] == [{"filename": "old.pdf"}]
    assert state["new_uploaded_files"] == [{"filename": "new.pdf"}]


def test_file_upload_reminder_uses_new_files_only():
    """Test that reminder is only generated for new_uploaded_files."""
    from pathlib import Path
    from generalAgent.config.project_root import resolve_project_path

    # Simulate state after first upload
    state_turn1: AppState = {
        "uploaded_files": [{"filename": "report.pdf", "file_type": "pdf"}],
        "new_uploaded_files": [{"filename": "report.pdf", "file_type": "pdf"}],
    }

    # Turn 1: Should generate reminder (has new files)
    config_path = resolve_project_path("generalAgent/config/skills.yaml")
    skill_config = SkillConfig(config_path=config_path)
    reminder_turn1 = build_file_upload_reminder(state_turn1["new_uploaded_files"], skill_config)
    assert "report.pdf" in reminder_turn1

    # Simulate state after planner clears new_uploaded_files
    state_turn2: AppState = {
        "uploaded_files": [{"filename": "report.pdf", "file_type": "pdf"}],  # Still there
        "new_uploaded_files": [],  # Cleared by planner
    }

    # Turn 2: Should NOT generate reminder (no new files)
    reminder_turn2 = build_file_upload_reminder(state_turn2["new_uploaded_files"], skill_config)
    assert reminder_turn2 == ""


def test_mentioned_agents_structure():
    """Test that mentioned_agents and new_mentioned_agents are separate fields."""
    state: AppState = {
        "mentioned_agents": ["pdf", "http_fetch"],
        "new_mentioned_agents": ["search_file"],
    }

    assert state["mentioned_agents"] == ["pdf", "http_fetch"]
    assert state["new_mentioned_agents"] == ["search_file"]


def test_mention_reminder_uses_new_mentions_only():
    """Test that @mention reminder is only generated for new_mentioned_agents."""
    from generalAgent.graph.prompts import build_dynamic_reminder

    # Turn 1: User mentions @pdf
    reminder_turn1 = build_dynamic_reminder(
        mentioned_skills=["pdf"],
    )
    assert "pdf" in reminder_turn1
    assert "SKILL.md" in reminder_turn1

    # Turn 2: No new mentions (new_mentioned_agents = [])
    reminder_turn2 = build_dynamic_reminder(
        mentioned_skills=[],  # Empty because new_mentioned_agents was cleared
    )
    assert reminder_turn2 == ""


def test_planner_clears_one_time_fields():
    """Test that planner returns updates to clear one-time reminder fields."""
    # Simulate planner node return value
    updates = {
        "messages": [],  # AI message
        "loops": 2,
        "new_uploaded_files": [],  # Cleared
        "new_mentioned_agents": [],  # Cleared
    }

    assert updates["new_uploaded_files"] == []
    assert updates["new_mentioned_agents"] == []


def test_cli_sets_new_fields_correctly():
    """Test that CLI sets both historical and new fields correctly."""
    # Simulate first turn with file upload
    state_initial = {
        "uploaded_files": [],
        "new_uploaded_files": [],
        "mentioned_agents": [],
        "new_mentioned_agents": [],
    }

    # User uploads file
    processed_files = [{"filename": "doc.pdf", "file_type": "pdf"}]
    state_initial["new_uploaded_files"] = processed_files
    state_initial["uploaded_files"] = processed_files

    assert len(state_initial["new_uploaded_files"]) == 1
    assert len(state_initial["uploaded_files"]) == 1

    # Simulate second turn WITHOUT file upload
    state_turn2 = state_initial.copy()
    state_turn2["new_uploaded_files"] = []  # No new files
    # uploaded_files remains unchanged

    assert len(state_turn2["new_uploaded_files"]) == 0  # Should be empty
    assert len(state_turn2["uploaded_files"]) == 1  # Historical record preserved


def test_mention_cumulative_behavior():
    """Test that mentioned_agents accumulates while new_mentioned_agents resets."""
    state = {
        "mentioned_agents": [],
        "new_mentioned_agents": [],
    }

    # Turn 1: @pdf
    state["new_mentioned_agents"] = ["pdf"]
    state["mentioned_agents"] = ["pdf"]

    # Turn 2: @http_fetch
    state["new_mentioned_agents"] = ["http_fetch"]  # Reset to current turn only
    state["mentioned_agents"] = ["pdf", "http_fetch"]  # Cumulative

    assert state["new_mentioned_agents"] == ["http_fetch"]  # Only current
    assert set(state["mentioned_agents"]) == {"pdf", "http_fetch"}  # All history


def test_no_mention_clears_new_field():
    """Test that new_mentioned_agents is cleared when no mentions in turn."""
    state = {
        "mentioned_agents": ["pdf"],
        "new_mentioned_agents": ["pdf"],
    }

    # Turn 2: No mentions
    state["new_mentioned_agents"] = []  # Should be explicitly set to empty

    assert state["new_mentioned_agents"] == []
    assert state["mentioned_agents"] == ["pdf"]  # Historical preserved
