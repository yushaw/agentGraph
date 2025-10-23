"""Tests for SKILL.md Markdown + frontmatter loader."""

import pytest
from pathlib import Path

from agentgraph.skills.md_loader import (
    parse_skill_md,
    load_skill_from_md,
    read_skill_content,
    load_skills_directory_md,
)


@pytest.fixture
def sample_skill_md(tmp_path):
    """Create a sample SKILL.md file."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Test Skill
description: A test skill for unit testing
version: 1.0.0
allowed-tools:
  - tool_a
  - tool_b
---

# Test Skill

This is the markdown body content.

## Instructions

1. Do something
2. Do something else

## Examples

Example usage here.
""")
    return skill_file


@pytest.fixture
def minimal_skill_md(tmp_path):
    """Create a minimal SKILL.md with only required fields."""
    skill_dir = tmp_path / "minimal_skill"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Minimal Skill
description: Only required fields
---

# Minimal Content
""")
    return skill_file


def test_parse_skill_md_success():
    """Test parsing valid SKILL.md content."""
    content = """---
name: Test
description: A test
---

# Body content
"""
    frontmatter, body = parse_skill_md(content)

    assert frontmatter["name"] == "Test"
    assert frontmatter["description"] == "A test"
    assert body == "# Body content"


def test_parse_skill_md_missing_frontmatter():
    """Test parsing fails without frontmatter."""
    content = "# Just markdown\n\nNo frontmatter here."

    with pytest.raises(ValueError, match="must start with YAML frontmatter"):
        parse_skill_md(content)


def test_parse_skill_md_invalid_yaml():
    """Test parsing fails with invalid YAML."""
    content = """---
name: Test
bad yaml: [unclosed
---

# Body
"""
    with pytest.raises(ValueError, match="Invalid YAML frontmatter"):
        parse_skill_md(content)


def test_load_skill_from_md(sample_skill_md):
    """Test loading SKILL.md into SkillMeta."""
    meta = load_skill_from_md(sample_skill_md)

    assert meta.name == "Test Skill"
    assert meta.description == "A test skill for unit testing"
    assert meta.version == "1.0.0"
    assert meta.allowed_tools == ["tool_a", "tool_b"]
    assert meta.id == "test_skill"  # Defaults to directory name
    assert meta.path == sample_skill_md.parent


def test_load_skill_from_md_minimal(minimal_skill_md):
    """Test loading minimal SKILL.md with only required fields."""
    meta = load_skill_from_md(minimal_skill_md)

    assert meta.name == "Minimal Skill"
    assert meta.description == "Only required fields"
    assert meta.version == "0.1.0"  # Default
    assert meta.allowed_tools is None
    assert meta.id == "minimal_skill"


def test_load_skill_from_md_missing_required_field(tmp_path):
    """Test loading fails when required field is missing."""
    skill_dir = tmp_path / "bad_skill"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Only Name
---

# Missing description
""")

    with pytest.raises(ValueError, match="missing required field 'description'"):
        load_skill_from_md(skill_file)


def test_read_skill_content(sample_skill_md):
    """Test reading markdown body content (progressive loading)."""
    content = read_skill_content(sample_skill_md.parent)

    assert "# Test Skill" in content
    assert "## Instructions" in content
    assert "## Examples" in content
    assert "---" not in content  # Frontmatter removed


def test_load_skills_directory_md(tmp_path):
    """Test loading multiple SKILL.md files from directory."""
    # Create skill 1
    skill1 = tmp_path / "skill_one"
    skill1.mkdir()
    (skill1 / "SKILL.md").write_text("""---
name: Skill One
description: First skill
---

# Content
""")

    # Create skill 2
    skill2 = tmp_path / "skill_two"
    skill2.mkdir()
    (skill2 / "SKILL.md").write_text("""---
name: Skill Two
description: Second skill
---

# Content
""")

    # Create invalid skill (should be skipped)
    skill3 = tmp_path / "skill_bad"
    skill3.mkdir()
    (skill3 / "SKILL.md").write_text("Bad content")

    # Load all skills
    registry = load_skills_directory_md(tmp_path)

    assert len(registry) == 2
    assert "skill_one" in registry
    assert "skill_two" in registry
    assert "skill_bad" not in registry

    assert registry["skill_one"].name == "Skill One"
    assert registry["skill_two"].name == "Skill Two"


def test_load_skills_directory_md_nonexistent(tmp_path):
    """Test loading from nonexistent directory returns empty dict."""
    registry = load_skills_directory_md(tmp_path / "nonexistent")

    assert registry == {}


def test_skill_md_with_custom_id(tmp_path):
    """Test SKILL.md with explicit id field."""
    skill_dir = tmp_path / "my_directory"
    skill_dir.mkdir()

    (skill_dir / "SKILL.md").write_text("""---
id: custom_id
name: Custom ID Skill
description: Skill with explicit ID
---

# Content
""")

    meta = load_skill_from_md(skill_dir / "SKILL.md")
    assert meta.id == "custom_id"  # Uses explicit ID, not directory name
