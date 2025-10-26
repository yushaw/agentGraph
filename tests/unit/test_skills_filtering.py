"""Test skills filtering based on configuration."""

import asyncio
from pathlib import Path
from generalAgent.runtime.app import build_application
from generalAgent.config.project_root import resolve_project_path
from generalAgent.utils.file_processor import build_file_upload_reminder, ProcessedFile


async def test_skills_filtering():
    """Test that skills catalog only shows enabled skills."""
    print("="*60)
    print("测试 1: Skills Catalog 只显示已启用的技能")
    print("="*60)

    # Build application
    app, initial_state_factory, skill_registry, tool_registry, skill_config = await build_application()

    # Check enabled skills
    enabled_skills = skill_config.get_enabled_skills()
    print(f"\n✓ 从配置读取的已启用技能: {enabled_skills}")

    # Check all discovered skills
    all_skills = [s.id for s in skill_registry.list_meta()]
    print(f"✓ 文件系统扫描到的所有技能: {all_skills}")

    # Verify filtering works
    print(f"\n✓ 启用的技能数量: {len(enabled_skills)}")
    print(f"✓ 扫描到的技能数量: {len(all_skills)}")

    if len(enabled_skills) < len(all_skills):
        print("✓ 过滤成功: 只有部分技能被启用")
    else:
        print("⚠ 可能有问题: 所有技能都被启用了")


def test_file_upload_reminders():
    """Test dynamic file upload reminders."""
    print("\n" + "="*60)
    print("测试 2: 文件上传提示根据配置动态生成")
    print("="*60)

    from generalAgent.config.skill_config_loader import load_skill_config

    skill_config_path = resolve_project_path("generalAgent/config/skills.yaml")
    skill_config = load_skill_config(skill_config_path)

    # Test different file types
    test_files = [
        ProcessedFile(
            filename="test.pdf",
            file_type="pdf",
            size_bytes=1000,
            size_formatted="1 KB",
            workspace_path="uploads/test.pdf"
        ),
        ProcessedFile(
            filename="test.docx",
            file_type="office",  # docx is classified as "office"
            size_bytes=2000,
            size_formatted="2 KB",
            workspace_path="uploads/test.docx"
        ),
        ProcessedFile(
            filename="test.pptx",
            file_type="office",  # pptx is also "office"
            size_bytes=3000,
            size_formatted="3 KB",
            workspace_path="uploads/test.pptx"
        ),
    ]

    # Generate reminder with skill_config
    reminder = build_file_upload_reminder(test_files, skill_config)

    print("\n生成的提示内容:")
    print(reminder)

    # Check if skills are mentioned
    if "@docx" in reminder:
        print("\n✓ 找到 @docx 提示")
    if "@pptx" in reminder:
        print("✓ 找到 @pptx 提示")

    # Test without skill_config (fallback)
    reminder_fallback = build_file_upload_reminder(test_files, None)
    print("\n不使用 skill_config 的回退提示:")
    print(reminder_fallback)

    if "@pdf" in reminder_fallback and "@docx" not in reminder_fallback:
        print("\n✓ 回退模式正常: 只提示 PDF (硬编码)")


async def main():
    """Run all tests."""
    await test_skills_filtering()
    test_file_upload_reminders()

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
