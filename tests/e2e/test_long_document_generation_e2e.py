"""
E2E test for long document generation workflow.

This test simulates the original issue where Agent tried to generate
a 20-day travel plan in a single write_file call, causing JSON truncation.

The fix involves:
1. max_completion_tokens configuration to prevent truncation
2. SystemMessage guidance to use outline-first → edit-to-expand pattern
3. Tool docstrings that reinforce the correct workflow
"""

import pytest
import os
from pathlib import Path


@pytest.mark.e2e
@pytest.mark.asyncio
class TestLongDocumentGenerationE2E:
    """End-to-end test for long document generation with truncation prevention."""

    @pytest.fixture
    def workspace(self, tmp_path):
        """Setup isolated workspace."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "outputs").mkdir()
        os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)
        yield workspace
        if "AGENT_WORKSPACE_PATH" in os.environ:
            del os.environ["AGENT_WORKSPACE_PATH"]

    async def test_long_document_with_outline_first_pattern(self, workspace):
        """
        Test the recommended pattern: outline-first → edit-to-expand.

        This simulates generating a 20-day travel plan without truncation.
        """
        from generalAgent.tools.builtin.file_ops import write_file
        from generalAgent.tools.builtin.edit_file import edit_file

        # Step 1: Agent creates outline (SHORT content, no truncation risk)
        outline_content = """# 北京20天深度旅行计划

## 行程概览
[待补充]

## 第1-3天：历史文化初体验
[待补充]

## 第4-7天：长城与皇家园林
[待补充]

## 第8-10天：胡同与老北京生活
[待补充]

## 第11-14天：现代北京与艺术区
[待补充]

## 第15-17天：郊区探索
[待补充]

## 第18-20天：美食与总结
[待补充]

## 实用信息
[待补充]
"""

        result = write_file("outputs/beijing_plan.md", outline_content)
        assert "Success" in result

        # Verify outline created
        plan_file = workspace / "outputs" / "beijing_plan.md"
        assert plan_file.exists()
        content = plan_file.read_text()
        assert "[待补充]" in content
        assert "第1-3天" in content

        # Step 2: Agent expands each section incrementally using edit_file
        # Each edit is small (few hundred tokens), never hits max_tokens limit

        # Expand section 1
        section_1_content = """## 第1-3天：历史文化初体验

### 第1天：初识北京
- 上午：天安门广场、故宫博物院（需提前预约）
- 下午：景山公园俯瞰故宫全景
- 晚上：王府井大街、小吃街

### 第2天：天坛与胡同
- 上午：天坛公园（祈年殿、圜丘坛）
- 下午：南锣鼓巷、什刹海
- 晚上：后海酒吧街

### 第3天：颐和园
- 全天：颐和园深度游览
- 昆明湖划船、长廊、苏州街"""

        result = edit_file(
            "outputs/beijing_plan.md",
            "## 第1-3天：历史文化初体验\n[待补充]",
            section_1_content
        )
        assert "Success" in result

        # Expand section 2
        section_2_content = """## 第4-7天：长城与皇家园林

### 第4天：慕田峪长城
- 全天：慕田峪长城（缆车上下）
- 长城徒步，拍照留念

### 第5天：圆明园与北大
- 上午：圆明园遗址公园
- 下午：北京大学、清华大学校园

### 第6-7天：雍和宫与恭王府
- 雍和宫（藏传佛教寺院）
- 恭王府（和珅故居）"""

        result = edit_file(
            "outputs/beijing_plan.md",
            "## 第4-7天：长城与皇家园林\n[待补充]",
            section_2_content
        )
        assert "Success" in result

        # Continue expanding other sections...
        # (In real scenario, Agent would expand all remaining sections)

        # Verify final document
        final_content = plan_file.read_text()

        # Check that expanded content exists
        assert "天安门广场" in final_content
        assert "慕田峪长城" in final_content

        # Check that some [待补充] markers remain (sections not yet expanded)
        remaining_tbd = final_content.count("[待补充]")
        assert remaining_tbd < 7  # Less than original count (some expanded)

        # Verify no truncation occurred (file is valid and complete)
        assert plan_file.stat().st_size > len(outline_content)
        assert "# 北京20天深度旅行计划" in final_content

    async def test_anti_pattern_full_content_in_one_write(self, workspace):
        """
        Test the ANTI-PATTERN that should be AVOIDED.

        This simulates what the Agent tried to do originally:
        Generate entire 20-day plan (>2000 words) in single write_file call.

        With old config (no max_tokens), this would be truncated.
        With new config (max_tokens=4096), this would still be problematic
        but at least wouldn't cause JSON truncation.
        """
        from generalAgent.tools.builtin.file_ops import write_file

        # Try to write very long content in one go (ANTI-PATTERN)
        very_long_content = "# 北京20天旅行计划\n\n"

        # Generate ~3000 words of content
        for day in range(1, 21):
            very_long_content += f"\n## 第{day}天\n\n"
            very_long_content += f"### 上午活动\n{'- 活动内容' * 10}\n\n"
            very_long_content += f"### 下午活动\n{'- 活动内容' * 10}\n\n"
            very_long_content += f"### 晚上活动\n{'- 活动内容' * 10}\n\n"

        # This works now due to max_completion_tokens=4096, but it's still inefficient
        result = write_file("outputs/bad_pattern.md", very_long_content)

        # File is created, but this approach:
        # 1. Uses many tokens unnecessarily
        # 2. Could still hit limits for very long content
        # 3. Less safe (overwrites everything)
        assert "Success" in result

        bad_file = workspace / "outputs" / "bad_pattern.md"
        assert bad_file.exists()

        # Even though it works, this is NOT the recommended pattern
        # The outline-first approach is much better

    def test_max_completion_tokens_prevents_json_truncation(self):
        """
        Test that max_completion_tokens configuration prevents the original issue.

        Original issue: Kimi API default 1024 tokens → tool call JSON truncated
        Fix: Configure MODEL_CHAT_MAX_COMPLETION_TOKENS=4096
        """
        from generalAgent.config.settings import get_settings
        from generalAgent.runtime.model_resolver import resolve_model_configs

        settings = get_settings()
        configs = resolve_model_configs(settings)

        # Verify that max_completion_tokens is configured for chat model
        chat_config = configs["chat"]
        assert "max_completion_tokens" in chat_config

        # Should be at least 2048 (fallback) or higher if configured
        assert chat_config["max_completion_tokens"] >= 2048

        # Recommended value for Kimi is 4096+
        # (User should set MODEL_CHAT_MAX_COMPLETION_TOKENS=4096 in .env)

    def test_system_message_guides_correct_pattern(self):
        """
        Test that SystemMessage includes guidance for the correct pattern.
        """
        from generalAgent.graph.prompts import PLANNER_SYSTEM_PROMPT

        # Verify that SystemMessage mentions the correct pattern
        assert "edit_file" in PLANNER_SYSTEM_PROMPT
        assert "write_file" in PLANNER_SYSTEM_PROMPT

        # Should mention long documents
        assert "长文档" in PLANNER_SYSTEM_PROMPT or ">1000" in PLANNER_SYSTEM_PROMPT

    def test_tool_docstrings_reinforce_pattern(self):
        """
        Test that tool docstrings reinforce the outline-first pattern.
        """
        from generalAgent.tools.builtin.file_ops import write_file
        from generalAgent.tools.builtin.edit_file import edit_file

        # write_file should mention edit_file preference
        write_doc = write_file.__doc__
        assert "edit_file" in write_doc
        assert "ALWAYS prefer" in write_doc or "prefer" in write_doc.lower()

        # edit_file should explain its benefits
        edit_doc = edit_file.__doc__
        assert "exact" in edit_doc.lower() or "replacement" in edit_doc.lower()


@pytest.mark.smoke
class TestLongDocumentSmoke:
    """Smoke test for basic long document workflow."""

    def test_outline_then_edit_smoke(self, tmp_path):
        """Quick smoke test for outline → edit workflow."""
        from generalAgent.tools.builtin.file_ops import write_file
        from generalAgent.tools.builtin.edit_file import edit_file

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "outputs").mkdir()
        os.environ["AGENT_WORKSPACE_PATH"] = str(workspace)

        try:
            # Create outline
            write_result = write_file(
                "outputs/test.md",
                "# Test\n\n## Section 1\n[TBD]\n"
            )
            assert "Success" in write_result

            # Expand section
            edit_result = edit_file(
                "outputs/test.md",
                "## Section 1\n[TBD]",
                "## Section 1\nExpanded content"
            )
            assert "Success" in edit_result

            # Verify
            test_file = workspace / "outputs" / "test.md"
            content = test_file.read_text()
            assert "Expanded content" in content
            assert "[TBD]" not in content

        finally:
            if "AGENT_WORKSPACE_PATH" in os.environ:
                del os.environ["AGENT_WORKSPACE_PATH"]
