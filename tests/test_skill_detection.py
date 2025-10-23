"""Tests for skill detection (model-invoked pattern)."""

import pytest
from pathlib import Path
from unittest.mock import Mock

from langchain_core.messages import AIMessage

from agentgraph.skills import SkillRegistry
from agentgraph.graph.skill_detection import detect_skill_from_tool_calls, should_load_skill_tools


@pytest.fixture
def skill_registry(tmp_path):
    """Create a skill registry with test skills."""
    # Create weather skill
    weather_dir = tmp_path / "weather"
    weather_dir.mkdir()
    (weather_dir / "SKILL.md").write_text("""---
id: weather
name: Weather Lookup
description: Get weather info
allowed-tools:
  - get_weather
---

# Weather
""")

    # Create pptx skill
    pptx_dir = tmp_path / "pptx"
    pptx_dir.mkdir()
    (pptx_dir / "SKILL.md").write_text("""---
id: pptx
name: PowerPoint
description: Create presentations
allowed-tools:
  - draft_outline
  - generate_pptx
---

# PPTX
""")

    return SkillRegistry(tmp_path)


def test_detect_skill_from_tool_calls_weather(skill_registry):
    """Test detecting weather skill from get_weather tool call."""
    # Simulate tool call from model
    tool_calls = [{"name": "get_weather", "args": {"city": "London"}}]

    detected = detect_skill_from_tool_calls(tool_calls, skill_registry)

    assert detected == "weather"


def test_detect_skill_from_tool_calls_pptx(skill_registry):
    """Test detecting pptx skill from draft_outline tool call."""
    tool_calls = [{"name": "draft_outline", "args": {"topic": "AI"}}]

    detected = detect_skill_from_tool_calls(tool_calls, skill_registry)

    assert detected == "pptx"


def test_detect_skill_from_tool_calls_no_match(skill_registry):
    """Test no skill detected for non-skill tools."""
    tool_calls = [{"name": "calc", "args": {"expression": "2+2"}}]

    detected = detect_skill_from_tool_calls(tool_calls, skill_registry)

    assert detected is None


def test_detect_skill_from_tool_calls_empty(skill_registry):
    """Test no skill detected for empty tool calls."""
    detected = detect_skill_from_tool_calls([], skill_registry)

    assert detected is None


def test_should_load_skill_tools_new_activation(skill_registry):
    """Test loading skill tools when skill is newly detected."""
    # Create AI message with tool call
    message = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "get_weather", "args": {"city": "Paris"}}]
    )

    should_load, skill_id, allowed_tools = should_load_skill_tools(
        last_message=message,
        current_active_skill=None,
        skill_registry=skill_registry,
    )

    assert should_load is True
    assert skill_id == "weather"
    assert "get_weather" in allowed_tools


def test_should_load_skill_tools_already_active(skill_registry):
    """Test not loading skill tools when skill already active."""
    message = AIMessage(
        content="",
        tool_calls=[{"id": "call_2", "name": "get_weather", "args": {"city": "Tokyo"}}]
    )

    should_load, skill_id, allowed_tools = should_load_skill_tools(
        last_message=message,
        current_active_skill="weather",  # Already active
        skill_registry=skill_registry,
    )

    assert should_load is False  # No reload needed
    assert skill_id == "weather"
    assert allowed_tools == []


def test_should_load_skill_tools_skill_switch(skill_registry):
    """Test switching from one skill to another."""
    # Switch from weather to pptx
    message = AIMessage(
        content="",
        tool_calls=[{"id": "call_3", "name": "draft_outline", "args": {"topic": "Climate"}}]
    )

    should_load, skill_id, allowed_tools = should_load_skill_tools(
        last_message=message,
        current_active_skill="weather",  # Different skill active
        skill_registry=skill_registry,
    )

    assert should_load is True  # Should switch
    assert skill_id == "pptx"
    assert "draft_outline" in allowed_tools
    assert "generate_pptx" in allowed_tools


def test_should_load_skill_tools_no_tool_calls(skill_registry):
    """Test no loading when message has no tool calls."""
    message = AIMessage(content="Just a regular response")

    should_load, skill_id, allowed_tools = should_load_skill_tools(
        last_message=message,
        current_active_skill=None,
        skill_registry=skill_registry,
    )

    assert should_load is False
    assert skill_id is None
    assert allowed_tools == []
