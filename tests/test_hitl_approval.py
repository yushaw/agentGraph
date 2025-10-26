"""Tests for HITL approval system with global risk patterns."""

import pytest
from pathlib import Path
import tempfile
import yaml

from generalAgent.hitl.approval_checker import ApprovalChecker, ApprovalDecision


class TestGlobalRiskPatterns:
    """测试全局风险模式检测"""

    @pytest.fixture
    def config_with_global_patterns(self):
        """创建包含全局风险模式的配置"""
        config = {
            "global": {
                "enabled": True,
                "risk_patterns": {
                    "critical": {
                        "patterns": [
                            r"password\s*[=:]\s*['\"]?[\w.-]+",  # key=value format
                            r":\s*password\w+",                   # URL format (user:password)
                            r"api[_-]?key\s*[=:]\s*['\"]?[\w-]+",
                            r"secret\s*[=:]\s*['\"]?[\w.-]+",
                        ],
                        "action": "require_approval",
                        "reason": "检测到敏感信息（密码/密钥/令牌）",
                    },
                    "high": {
                        "patterns": [
                            r"/etc/passwd",
                            r"/etc/shadow",
                            r"DROP\s+(TABLE|DATABASE)",
                        ],
                        "action": "require_approval",
                        "reason": "检测到高风险操作（系统文件/数据库删除）",
                    },
                    "medium": {
                        "patterns": [
                            r"https?://[^/]*\d+\.\d+\.\d+\.\d+",  # IP address
                            r"\bexec\s*\(",
                            r"\beval\s*\(",
                        ],
                        "action": "require_approval",
                        "reason": "检测到可疑模式（代码执行/IP地址）",
                    },
                },
            },
            "tools": {},
        }

        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)

    @pytest.fixture
    def checker_with_global_patterns(self, config_with_global_patterns):
        """创建带全局模式的 ApprovalChecker"""
        return ApprovalChecker(config_path=config_with_global_patterns)

    def test_critical_password_detection(self, checker_with_global_patterns):
        """测试密码泄露检测"""
        # Test various password formats
        test_cases = [
            {"command": "curl -u user:password123 http://api.com"},
            {"url": "http://api.com?password=secret123"},
            {"config": "password='mypassword'"},
            {"data": "password: hunter2"},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval, f"Should detect password in {args}"
            assert decision.risk_level == "critical"
            assert "敏感信息" in decision.reason

    def test_critical_api_key_detection(self, checker_with_global_patterns):
        """测试 API Key 泄露检测"""
        test_cases = [
            {"command": "export API_KEY=sk-1234567890"},
            {"config": "api-key: abc123def456"},
            {"data": "apikey=myapikey123"},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval
            assert decision.risk_level == "critical"

    def test_critical_secret_detection(self, checker_with_global_patterns):
        """测试 Secret 泄露检测"""
        test_cases = [
            {"command": "docker run -e SECRET=mysecret app"},
            {"config": "secret: 'topsecret123'"},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval
            assert decision.risk_level == "critical"

    def test_high_system_files(self, checker_with_global_patterns):
        """测试系统敏感文件检测"""
        test_cases = [
            {"path": "/etc/passwd"},
            {"file": "/etc/shadow"},
            {"command": "cat /etc/passwd"},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval
            assert decision.risk_level == "high"
            assert "高风险操作" in decision.reason

    def test_high_sql_operations(self, checker_with_global_patterns):
        """测试 SQL 危险操作检测"""
        test_cases = [
            {"query": "DROP TABLE users"},
            {"sql": "DROP DATABASE production"},
            {"command": "mysql -e 'DROP TABLE sessions'"},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval
            assert decision.risk_level == "high"

    def test_medium_ip_address_url(self, checker_with_global_patterns):
        """测试 IP 地址 URL 检测"""
        test_cases = [
            {"url": "http://192.168.1.1/api"},
            {"endpoint": "https://10.0.0.5:8080/data"},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval
            assert decision.risk_level == "medium"

    def test_medium_code_execution(self, checker_with_global_patterns):
        """测试代码执行模式检测"""
        test_cases = [
            {"code": "exec('print(hello)')"},
            {"command": "python -c \"eval('1+1')\""},
        ]

        for args in test_cases:
            decision = checker_with_global_patterns.check("any_tool", args)
            assert decision.needs_approval
            assert decision.risk_level == "medium"

    def test_safe_operations_pass(self, checker_with_global_patterns):
        """测试安全操作不触发审批"""
        safe_test_cases = [
            {"command": "ls -la"},
            {"url": "https://api.example.com/data"},
            {"query": "SELECT * FROM users"},
            {"data": "normal text without sensitive info"},
        ]

        for args in safe_test_cases:
            decision = checker_with_global_patterns.check("safe_tool", args)
            assert not decision.needs_approval, f"Should not flag safe operation: {args}"


class TestPriorityLevels:
    """测试四层审批规则的优先级"""

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

    def test_custom_checker_highest_priority(self, full_config):
        """测试自定义检查器优先级最高"""
        checker = ApprovalChecker(config_path=full_config)

        # 注册自定义检查器
        def custom_checker(args):
            # 自定义逻辑：总是允许
            return ApprovalDecision(needs_approval=False)

        checker.register_checker("run_bash_command", custom_checker)

        # 即使命令包含密码和 rm -rf，自定义检查器也会允许
        decision = checker.check("run_bash_command", {"command": "rm -rf /tmp password=123"})
        assert not decision.needs_approval, "Custom checker should override all rules"

    def test_global_patterns_before_tool_rules(self, full_config):
        """测试全局模式优先于工具规则"""
        checker = ApprovalChecker(config_path=full_config)

        # 包含密码的 ls 命令（ls 不在工具规则中）
        decision = checker.check("run_bash_command", {"command": "ls -la password=secret"})

        # 应该被全局模式拦截
        assert decision.needs_approval
        assert "全局检测到密码" in decision.reason
        assert decision.risk_level == "critical"

    def test_tool_rules_before_builtin(self, full_config):
        """测试工具规则优先于内置规则"""
        checker = ApprovalChecker(config_path=full_config)

        # rm -rf 命令（在工具规则中）
        decision = checker.check("run_bash_command", {"command": "rm -rf /tmp"})

        # 应该被工具规则拦截
        assert decision.needs_approval
        assert decision.risk_level == "high_risk"  # 来自工具配置


class TestCrossToolDetection:
    """测试全局模式的跨工具检测能力"""

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
                        ],
                        "action": "require_approval",
                        "reason": "检测到敏感信息",
                    },
                    "high": {
                        "patterns": [
                            r"/etc/passwd",
                            r"/etc/shadow",
                        ],
                        "action": "require_approval",
                        "reason": "检测到系统文件",
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

    def test_password_in_different_tools(self, checker):
        """测试密码检测在不同工具中都生效"""
        tools_and_args = [
            ("http_fetch", {"url": "http://api.com?password=secret"}),
            ("write_file", {"content": "config: password=hunter2"}),
            ("custom_tool", {"data": "password: topsecret"}),
            ("any_tool", {"config": "password='mypass'"}),
        ]

        for tool_name, args in tools_and_args:
            decision = checker.check(tool_name, args)
            assert decision.needs_approval, f"Should detect password in {tool_name}"
            # 全局模式应该检测到密码
            assert "密码" in decision.reason or "敏感" in decision.reason, f"Wrong reason: {decision.reason}"

    def test_system_files_in_different_tools(self, checker):
        """测试系统文件检测在不同工具中都生效"""
        tools_and_args = [
            ("run_bash_command", {"command": "cat /etc/passwd"}),
            ("read_file", {"path": "/etc/shadow"}),
            ("write_file", {"path": "/etc/passwd", "content": "data"}),
        ]

        for tool_name, args in tools_and_args:
            decision = checker.check(tool_name, args)
            assert decision.needs_approval, f"Should detect system file in {tool_name}"
            assert decision.risk_level == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
