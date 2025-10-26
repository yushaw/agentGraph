"""End-to-end tests for HITL approval system.

Tests the complete workflow from tool call to approval decision,
including integration with the agent loop and session persistence.
"""

import pytest
from pathlib import Path
import tempfile
import yaml

from generalAgent.hitl.approval_checker import ApprovalChecker, ApprovalDecision
from generalAgent.models.registry import ModelRegistry
from generalAgent.config.settings import get_settings


class TestE2EPasswordLeakScenarios:
    """端到端测试：密码泄露场景"""

    @pytest.fixture
    def config_with_global_patterns(self):
        """创建包含全局风险模式的配置"""
        config = {
            "global": {
                "enabled": True,
                "risk_patterns": {
                    "critical": {
                        "patterns": [
                            r"password\s*[=:]\s*['\"]?[\w.-]+",
                            r":\s*password\w+",
                            r"api[_-]?key\s*[=:]\s*['\"]?[\w-]+",
                        ],
                        "action": "require_approval",
                        "reason": "检测到敏感信息（密码/密钥/令牌）",
                    },
                },
            },
            "tools": {},
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)

    @pytest.fixture
    def checker(self, config_with_global_patterns):
        return ApprovalChecker(config_path=config_with_global_patterns)

    def test_scenario_curl_with_credentials(self, checker):
        """场景：curl 命令包含明文密码"""
        # 模拟用户意图：调用 API
        tool_name = "run_bash_command"
        args = {"command": "curl -u admin:P@ssw0rd123 https://api.example.com/data"}

        # 执行审批检查
        decision = checker.check(tool_name, args)

        # 验证结果
        assert decision.needs_approval, "应该拦截包含密码的 curl 命令"
        assert decision.risk_level == "critical", "密码泄露应该是 critical 级别"
        assert "敏感信息" in decision.reason or "密码" in decision.reason

    def test_scenario_env_file_with_secrets(self, checker):
        """场景：写入包含密钥的 .env 文件"""
        tool_name = "write_file"
        args = {
            "path": "outputs/.env",
            "content": "API_KEY=sk-1234567890abcdef\nSECRET_TOKEN=my-secret-token",
        }

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截包含 API Key 的文件写入"
        assert decision.risk_level == "critical"

    def test_scenario_git_config_with_credentials(self, checker):
        """场景：配置 git remote 包含密码"""
        tool_name = "run_bash_command"
        args = {
            "command": "git remote add origin https://user:mypassword@github.com/user/repo.git"
        }

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截包含密码的 git remote URL"
        assert decision.risk_level == "critical"

    def test_scenario_database_connection_string(self, checker):
        """场景：数据库连接字符串包含密码"""
        tool_name = "write_file"
        args = {
            "path": "outputs/config.yaml",
            "content": "database_url: postgresql://user:password123@localhost/db",
        }

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截包含密码的数据库连接串"


class TestE2ESystemFileScenarios:
    """端到端测试：系统文件访问场景"""

    @pytest.fixture
    def config_with_global_patterns(self):
        """创建包含全局风险模式的配置"""
        config = {
            "global": {
                "enabled": True,
                "risk_patterns": {
                    "high": {
                        "patterns": [
                            r"/etc/passwd",
                            r"/etc/shadow",
                            r"~/.ssh/id_rsa",
                        ],
                        "action": "require_approval",
                        "reason": "检测到系统敏感文件",
                    },
                },
            },
            "tools": {},
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)

    @pytest.fixture
    def checker(self, config_with_global_patterns):
        return ApprovalChecker(config_path=config_with_global_patterns)

    def test_scenario_read_passwd_file(self, checker):
        """场景：尝试读取 /etc/passwd"""
        tool_name = "read_file"
        args = {"path": "/etc/passwd"}

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截读取 /etc/passwd"
        assert decision.risk_level == "high"

    def test_scenario_backup_ssh_keys(self, checker):
        """场景：备份 SSH 私钥"""
        tool_name = "run_bash_command"
        args = {"command": "cp ~/.ssh/id_rsa backup/id_rsa.bak"}

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截 SSH 私钥操作"
        assert decision.risk_level == "high"


class TestE2EDangerousOperations:
    """端到端测试：危险操作场景"""

    @pytest.fixture
    def config_with_global_patterns(self):
        """创建包含全局风险模式的配置"""
        config = {
            "global": {
                "enabled": True,
                "risk_patterns": {
                    "high": {
                        "patterns": [
                            r"DROP\s+(TABLE|DATABASE)",
                            r"DELETE\s+FROM.*WHERE\s+1=1",
                            r"TRUNCATE\s+TABLE",
                        ],
                        "action": "require_approval",
                        "reason": "检测到危险的数据库操作",
                    },
                    "medium": {
                        "patterns": [
                            r"\bexec\s*\(",
                            r"\beval\s*\(",
                        ],
                        "action": "require_approval",
                        "reason": "检测到代码执行操作",
                    },
                },
            },
            "tools": {},
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)

    @pytest.fixture
    def checker(self, config_with_global_patterns):
        return ApprovalChecker(config_path=config_with_global_patterns)

    def test_scenario_drop_production_database(self, checker):
        """场景：删除生产数据库"""
        tool_name = "run_bash_command"
        args = {"command": "mysql -u root -p -e 'DROP DATABASE production'"}

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截删除数据库操作"
        assert decision.risk_level == "high"

    def test_scenario_sql_delete_all(self, checker):
        """场景：删除表中所有数据"""
        tool_name = "run_bash_command"
        args = {"command": "psql -c 'DELETE FROM users WHERE 1=1'"}

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截删除所有记录操作"
        assert decision.risk_level == "high"

    def test_scenario_python_exec_injection(self, checker):
        """场景：Python 代码注入"""
        tool_name = "write_file"
        args = {
            "path": "outputs/script.py",
            "content": "user_input = input('Enter code: ')\nexec(user_input)",
        }

        decision = checker.check(tool_name, args)

        assert decision.needs_approval, "应该拦截包含 exec() 的代码"
        assert decision.risk_level == "medium"


class TestE2ECrossToolDetection:
    """端到端测试：跨工具检测能力"""

    @pytest.fixture
    def config_with_global_patterns(self):
        """创建包含全局风险模式的配置"""
        config = {
            "global": {
                "enabled": True,
                "risk_patterns": {
                    "critical": {
                        "patterns": [
                            r"password\s*[=:]\s*['\"]?[\w.-]+",
                        ],
                        "action": "require_approval",
                        "reason": "检测到密码信息",
                    },
                },
            },
            "tools": {},
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)

    @pytest.fixture
    def checker(self, config_with_global_patterns):
        return ApprovalChecker(config_path=config_with_global_patterns)

    def test_password_detected_across_multiple_tools(self, checker):
        """验证密码检测在不同工具中都生效"""
        test_scenarios = [
            # Bash 命令
            ("run_bash_command", {"command": "export DB_PASSWORD=secret123"}),
            # 写文件
            ("write_file", {"path": "config.yaml", "content": "password: hunter2"}),
            # HTTP 请求
            ("http_fetch", {"url": "http://api.com?password=admin123"}),
            # 自定义工具
            ("custom_tool", {"config": "password='mypass'"}),
        ]

        for tool_name, args in test_scenarios:
            decision = checker.check(tool_name, args)
            assert decision.needs_approval, f"应该在 {tool_name} 中检测到密码"
            assert decision.risk_level == "critical"
            assert "密码" in decision.reason or "敏感" in decision.reason or "password" in decision.reason.lower()


class TestE2EPriorityInteractions:
    """端到端测试：多层优先级交互"""

    @pytest.fixture
    def full_config(self):
        """创建包含全局模式和工具规则的完整配置"""
        config = {
            "global": {
                "risk_patterns": {
                    "critical": {
                        "patterns": [r"password\s*="],
                        "action": "require_approval",
                        "reason": "全局检测到密码",
                    },
                },
            },
            "tools": {
                "run_bash_command": {
                    "enabled": True,
                    "patterns": {
                        "high_risk": [r"rm\s+-rf"],
                    },
                    "actions": {
                        "high_risk": "require_approval",
                    },
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)

    def test_custom_checker_overrides_all(self, full_config):
        """场景：自定义检查器覆盖所有其他规则"""
        checker = ApprovalChecker(config_path=full_config)

        # 注册自定义检查器，总是允许
        def always_allow(args):
            return ApprovalDecision(needs_approval=False)

        checker.register_checker("run_bash_command", always_allow)

        # 即使命令包含密码和 rm -rf，自定义检查器也会允许
        decision = checker.check("run_bash_command", {"command": "rm -rf /tmp password=secret"})
        assert not decision.needs_approval, "自定义检查器应该覆盖所有规则"

    def test_global_patterns_before_tool_rules(self, full_config):
        """场景：全局模式优先于工具规则"""
        checker = ApprovalChecker(config_path=full_config)

        # 包含密码但不包含 rm -rf
        decision = checker.check("run_bash_command", {"command": "ls -la password=secret"})

        # 应该被全局模式拦截
        assert decision.needs_approval
        assert "全局" in decision.reason
        assert decision.risk_level == "critical"

    def test_tool_rules_after_global(self, full_config):
        """场景：工具规则在全局模式之后检查"""
        checker = ApprovalChecker(config_path=full_config)

        # 包含 rm -rf 但不包含密码
        decision = checker.check("run_bash_command", {"command": "rm -rf /tmp/old_files"})

        # 应该被工具规则拦截
        assert decision.needs_approval
        assert decision.risk_level == "high_risk"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
