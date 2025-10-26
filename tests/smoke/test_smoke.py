"""Smoke tests for quick validation.

Smoke tests are fast, critical-path tests that verify the system's basic functionality.
Run these before commits to catch obvious breakage.

Typical run time: < 30 seconds
"""

import pytest
from pathlib import Path


class TestBasicSetup:
    """验证基础设置和配置"""

    def test_settings_load(self):
        """测试配置加载"""
        from generalAgent.config.settings import get_settings

        settings = get_settings()
        assert settings is not None
        assert settings.models is not None

    def test_project_paths_accessible(self):
        """测试项目路径可访问"""
        from generalAgent.config.project_root import get_project_root

        project_root = get_project_root()
        assert project_root.exists()
        assert project_root.is_dir()


class TestConfigFiles:
    """验证配置文件存在"""

    def test_tools_config_exists(self):
        """测试工具配置文件存在"""
        config_path = Path("generalAgent/config/tools.yaml")
        assert config_path.exists(), "tools.yaml 应该存在"
        assert config_path.is_file()

    def test_hitl_config_exists(self):
        """测试 HITL 配置文件存在"""
        config_path = Path("generalAgent/config/hitl_rules.yaml")
        assert config_path.exists(), "hitl_rules.yaml 应该存在"
        assert config_path.is_file()


class TestDirectoryStructure:
    """验证项目目录结构完整性"""

    def test_core_directories_exist(self):
        """测试核心目录存在"""
        required_dirs = [
            "generalAgent",
            "generalAgent/tools",
            "generalAgent/skills",
            "generalAgent/config",
            "generalAgent/graph",
            "generalAgent/models",
            "tests",
        ]

        for dir_path in required_dirs:
            path = Path(dir_path)
            assert path.exists(), f"{dir_path} 应该存在"
            assert path.is_dir(), f"{dir_path} 应该是目录"

    def test_skills_directory_has_content(self):
        """测试技能目录包含内容"""
        skills_dir = Path("generalAgent/skills")
        assert skills_dir.exists()

        # 至少应该有一些技能目录
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        # 如果没有技能也不报错,只是警告
        if len(skill_dirs) == 0:
            pytest.skip("No skills found, but this is not an error")


class TestImports:
    """验证关键模块可以导入"""

    def test_import_config(self):
        """测试导入配置模块"""
        from generalAgent.config import settings

        assert settings is not None

    def test_import_models(self):
        """测试导入模型模块"""
        from generalAgent.models import registry

        assert registry is not None

    def test_import_tools(self):
        """测试导入工具模块"""
        from generalAgent.tools import registry

        assert registry is not None

    def test_import_skills(self):
        """测试导入技能模块"""
        from generalAgent.skills import registry

        assert registry is not None

    def test_import_graph(self):
        """测试导入图模块"""
        from generalAgent import graph

        assert graph is not None

    def test_import_hitl(self):
        """测试导入 HITL 模块"""
        from generalAgent.hitl import approval_checker

        assert approval_checker is not None


class TestToolSystem:
    """验证工具系统基本功能"""

    def test_tool_config_loader(self):
        """测试工具配置加载"""
        from generalAgent.tools.config_loader import load_tool_config

        tool_config = load_tool_config()
        assert tool_config is not None
        # ToolConfig 对象有 config 属性
        assert hasattr(tool_config, 'config')
        assert hasattr(tool_config, 'get_core_tools')

    def test_tool_scanner_import(self):
        """测试工具扫描器可导入"""
        from generalAgent.tools.scanner import scan_multiple_directories

        assert scan_multiple_directories is not None


class TestHITLSystem:
    """验证 HITL 系统基本功能"""

    def test_approval_checker_init(self):
        """测试审批检查器初始化"""
        from generalAgent.hitl.approval_checker import ApprovalChecker
        from pathlib import Path

        config_path = Path("generalAgent/config/hitl_rules.yaml")
        if not config_path.exists():
            pytest.skip("hitl_rules.yaml not found")

        checker = ApprovalChecker(config_path=config_path)
        assert checker is not None

    def test_approval_decision_dataclass(self):
        """测试审批决策数据类"""
        from generalAgent.hitl.approval_checker import ApprovalDecision

        decision = ApprovalDecision(needs_approval=False)
        assert decision is not None
        assert not decision.needs_approval


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
