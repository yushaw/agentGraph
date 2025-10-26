"""Integration test for skills configuration and file upload."""

import asyncio
from pathlib import Path
from generalAgent.runtime.app import build_application
from generalAgent.config.project_root import resolve_project_path
from generalAgent.utils.file_processor import build_file_upload_reminder, ProcessedFile


async def test_skills_catalog_in_prompt():
    """Test that only enabled skills appear in system prompt."""
    print("=" * 60)
    print("测试 1: SystemPrompt 中的 Skills Catalog")
    print("=" * 60)

    # Build application
    app, initial_state_factory, skill_registry, tool_registry, skill_config = await build_application()

    # Get enabled skills from config
    enabled_skills = skill_config.get_enabled_skills()
    print(f"\n✓ 配置中启用的技能: {enabled_skills}")

    # Build skills catalog (as done in planner.py)
    from generalAgent.graph.prompts import build_skills_catalog
    catalog = build_skills_catalog(skill_registry, skill_config)

    print(f"\n✓ 生成的 Skills Catalog:\n{catalog}\n")

    # Verify only enabled skills in catalog
    for skill_id in enabled_skills:
        if f"#{skill_id}" in catalog:
            print(f"  ✓ 找到已启用技能: {skill_id}")
        else:
            print(f"  ✗ 未找到已启用技能: {skill_id}")

    # Verify disabled skills NOT in catalog
    all_skills = [s.id for s in skill_registry.list_meta()]
    disabled_skills = set(all_skills) - set(enabled_skills)
    for skill_id in disabled_skills:
        if f"#{skill_id}" in catalog:
            print(f"  ✗ 错误: 禁用技能出现在 catalog: {skill_id}")
        else:
            print(f"  ✓ 禁用技能未出现在 catalog: {skill_id}")


async def test_file_upload_hints():
    """Test dynamic file upload hints based on skills.yaml."""
    print("\n" + "=" * 60)
    print("测试 2: 文件上传动态提示")
    print("=" * 60)

    # Build application
    app, initial_state_factory, skill_registry, tool_registry, skill_config = await build_application()

    # Test various file types
    test_files = [
        ProcessedFile(
            filename="report.pdf",
            file_type="pdf",
            size_bytes=1500000,
            size_formatted="1.5 MB",
            workspace_path="uploads/report.pdf"
        ),
        ProcessedFile(
            filename="data.xlsx",
            file_type="office",  # Generic type
            size_bytes=500000,
            size_formatted="500 KB",
            workspace_path="uploads/data.xlsx"
        ),
        ProcessedFile(
            filename="summary.docx",
            file_type="office",  # Generic type
            size_bytes=300000,
            size_formatted="300 KB",
            workspace_path="uploads/summary.docx"
        ),
        ProcessedFile(
            filename="slides.pptx",
            file_type="office",  # Generic type
            size_bytes=2000000,
            size_formatted="2 MB",
            workspace_path="uploads/slides.pptx"
        ),
    ]

    # Generate reminder
    reminder = build_file_upload_reminder(test_files, skill_config)

    print("\n生成的文件上传提示:")
    print(reminder)

    # Check hints
    print("\n✓ 检查提示内容:")
    checks = [
        ("@pdf" in reminder, "PDF 文件提示 @pdf"),
        ("@xlsx" in reminder, "XLSX 文件提示 @xlsx"),
        ("@docx" in reminder, "DOCX 文件提示 @docx"),
        ("@pptx" in reminder, "PPTX 文件提示 @pptx"),
    ]

    for passed, description in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {description}")


async def test_mention_classification():
    """Test @mention classification for skills."""
    print("\n" + "=" * 60)
    print("测试 3: @Mention 分类")
    print("=" * 60)

    # Build application
    app, initial_state_factory, skill_registry, tool_registry, skill_config = await build_application()

    # Test mentions
    from generalAgent.utils.mention_classifier import classify_mentions

    test_cases = [
        ("pdf", "skill"),
        ("docx", "skill"),
        ("xlsx", "skill"),
        ("read_file", "tool"),
        ("write_file", "tool"),
        ("unknown_mention", "unknown"),
    ]

    print("\n✓ 测试分类结果:")
    for mention, expected in test_cases:
        # classify_mentions takes a list of mention names (without @)
        result = classify_mentions([mention], tool_registry, skill_registry)

        # Get the first classification result
        if result:
            actual = result[0].type
        else:
            actual = None

        status = "✓" if actual == expected else "✗"
        print(f"  {status} @{mention} → {actual} (expected: {expected})")


async def main():
    """Run all integration tests."""
    await test_skills_catalog_in_prompt()
    await test_file_upload_hints()
    await test_mention_classification()

    print("\n" + "=" * 60)
    print("集成测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
