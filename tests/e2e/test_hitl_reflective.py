"""Reflective testing for HITL approval system using reasoning model.

Uses the "reason" model to analyze approval decisions and identify edge cases,
false positives, and potential improvements.
"""

import pytest
from pathlib import Path
import tempfile
import yaml
import json
from typing import List, Dict, Any

from generalAgent.hitl.approval_checker import ApprovalChecker, ApprovalDecision
from generalAgent.models.registry import ModelRegistry
from generalAgent.config.settings import get_settings


class ReflectiveTestRunner:
    """使用 reasoning 模型进行反思性测试的运行器"""

    def __init__(self):
        self.settings = get_settings()
        self.registry = ModelRegistry(self.settings.models)
        self.reason_model = self.registry.get("reason")

    def analyze_decision(
        self, tool_name: str, args: dict, decision: ApprovalDecision, expected_approval: bool
    ) -> Dict[str, Any]:
        """使用 reason 模型分析审批决策的合理性"""

        prompt = f"""你是一个安全审计专家。请分析以下工具调用的审批决策是否合理。

**工具调用**:
- 工具名称: {tool_name}
- 参数: {json.dumps(args, ensure_ascii=False, indent=2)}

**审批决策**:
- 需要审批: {decision.needs_approval}
- 风险级别: {decision.risk_level}
- 原因: {decision.reason}

**预期结果**: {"需要审批" if expected_approval else "不需要审批"}

请分析:
1. 这个决策是否合理？为什么？
2. 是否存在误判（false positive 或 false negative）？
3. 如果是误判，应该如何改进规则？
4. 是否存在边界情况或特殊场景需要考虑？

请以 JSON 格式返回分析结果:
{{
    "is_reasonable": true/false,
    "is_correct": true/false,
    "error_type": "false_positive" / "false_negative" / null,
    "analysis": "详细分析",
    "suggestions": ["改进建议1", "改进建议2"],
    "edge_cases": ["边界情况1", "边界情况2"]
}}
"""

        try:
            response = self.reason_model.invoke(prompt)
            # 尝试从响应中提取 JSON
            content = response.content if hasattr(response, 'content') else str(response)

            # 查找 JSON 块
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
            else:
                # 如果无法解析 JSON，返回原始分析
                result = {
                    "is_reasonable": True,
                    "is_correct": decision.needs_approval == expected_approval,
                    "error_type": None,
                    "analysis": content,
                    "suggestions": [],
                    "edge_cases": [],
                }
        except Exception as e:
            # 如果调用失败，返回基本分析
            result = {
                "is_reasonable": True,
                "is_correct": decision.needs_approval == expected_approval,
                "error_type": None,
                "analysis": f"模型调用失败: {e}",
                "suggestions": [],
                "edge_cases": [],
            }

        return result

    def generate_edge_cases(self, risk_category: str) -> List[Dict[str, Any]]:
        """使用 reason 模型生成边界测试用例"""

        prompt = f"""你是一个安全测试专家。请为以下风险类别生成边界测试用例。

**风险类别**: {risk_category}

请生成 5-10 个边界测试用例，包括:
1. 应该触发审批的典型场景
2. 应该触发审批的边界场景（容易误判的）
3. 不应该触发审批但容易误判的场景
4. 绕过检测的尝试场景

请以 JSON 格式返回:
{{
    "test_cases": [
        {{
            "tool_name": "工具名",
            "args": {{"参数": "值"}},
            "should_approve": true/false,
            "description": "用例描述",
            "rationale": "为什么这个用例重要"
        }}
    ]
}}
"""

        try:
            response = self.reason_model.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # 查找 JSON 块
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                return result.get("test_cases", [])
            else:
                return []
        except Exception as e:
            print(f"生成边界用例失败: {e}")
            return []


@pytest.fixture
def reflective_runner():
    """创建反思性测试运行器"""
    return ReflectiveTestRunner()


@pytest.fixture
def checker_with_global_patterns():
    """创建包含全局风险模式的审批检查器"""
    config = {
        "global": {
            "enabled": True,
            "risk_patterns": {
                "critical": {
                    "patterns": [
                        r"password\s*[=:]\s*['\"]?[\w.-]+",
                        r":\s*password\w+",
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
                        r"https?://[^/]*\d+\.\d+\.\d+\.\d+",
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

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = Path(f.name)

    return ApprovalChecker(config_path=config_path)


class TestReflectivePasswordDetection:
    """使用 reason 模型反思密码检测规则"""

    @pytest.mark.skipif(
        not get_settings().models.reason_api_key,
        reason="需要配置 reason 模型 API key",
    )
    def test_analyze_password_in_url(self, reflective_runner, checker_with_global_patterns):
        """反思分析：URL 中的密码检测"""
        tool_name = "run_bash_command"
        args = {"command": "curl https://user:pass123@api.example.com/data"}

        decision = checker_with_global_patterns.check(tool_name, args)
        analysis = reflective_runner.analyze_decision(tool_name, args, decision, expected_approval=True)

        # 记录分析结果
        print("\n" + "=" * 80)
        print(f"工具: {tool_name}")
        print(f"参数: {args}")
        print(f"决策: needs_approval={decision.needs_approval}, risk={decision.risk_level}")
        print(f"分析: {analysis['analysis']}")
        if analysis['suggestions']:
            print(f"建议: {analysis['suggestions']}")
        if analysis['edge_cases']:
            print(f"边界情况: {analysis['edge_cases']}")
        print("=" * 80)

        # 验证决策正确性
        assert analysis['is_correct'], f"决策错误: {analysis['analysis']}"

    @pytest.mark.skipif(
        not get_settings().models.reason_api_key,
        reason="需要配置 reason 模型 API key",
    )
    def test_analyze_false_positive_password_in_text(
        self, reflective_runner, checker_with_global_patterns
    ):
        """反思分析：误报场景 - 文本中提到 password 但不是真实密码"""
        tool_name = "write_file"
        args = {
            "path": "outputs/docs.md",
            "content": "Please set your password using the password field in the settings.",
        }

        decision = checker_with_global_patterns.check(tool_name, args)
        analysis = reflective_runner.analyze_decision(tool_name, args, decision, expected_approval=False)

        # 记录分析结果
        print("\n" + "=" * 80)
        print(f"工具: {tool_name}")
        print(f"参数: {args}")
        print(f"决策: needs_approval={decision.needs_approval}, risk={decision.risk_level}")
        print(f"分析: {analysis['analysis']}")
        if analysis['suggestions']:
            print(f"改进建议: {analysis['suggestions']}")
        print("=" * 80)

        # 如果存在误报，记录建议
        if analysis['error_type'] == 'false_positive':
            print(f"\n⚠️  检测到误报，建议改进规则")


class TestReflectiveEdgeCaseGeneration:
    """使用 reason 模型生成边界测试用例"""

    @pytest.mark.skipif(
        not get_settings().models.reason_api_key,
        reason="需要配置 reason 模型 API key",
    )
    def test_generate_password_edge_cases(self, reflective_runner, checker_with_global_patterns):
        """生成密码检测的边界用例"""
        edge_cases = reflective_runner.generate_edge_cases("密码泄露检测")

        print("\n" + "=" * 80)
        print("生成的边界测试用例:")
        print("=" * 80)

        for i, case in enumerate(edge_cases, 1):
            print(f"\n用例 {i}: {case.get('description', 'N/A')}")
            print(f"工具: {case.get('tool_name', 'N/A')}")
            print(f"参数: {case.get('args', {})}")
            print(f"预期: {'需要审批' if case.get('should_approve') else '不需要审批'}")
            print(f"理由: {case.get('rationale', 'N/A')}")

            # 运行生成的测试用例
            if case.get('tool_name') and case.get('args'):
                decision = checker_with_global_patterns.check(
                    case['tool_name'], case['args']
                )
                is_correct = decision.needs_approval == case.get('should_approve', False)
                status = "✓" if is_correct else "✗"
                print(f"结果: {status} (needs_approval={decision.needs_approval})")

                if not is_correct:
                    print(f"⚠️  不符合预期! 风险级别: {decision.risk_level}, 原因: {decision.reason}")

        print("=" * 80)

        # 验证至少生成了一些用例
        assert len(edge_cases) > 0, "应该生成至少一个边界用例"

    @pytest.mark.skipif(
        not get_settings().models.reason_api_key,
        reason="需要配置 reason 模型 API key",
    )
    def test_generate_sql_injection_edge_cases(self, reflective_runner, checker_with_global_patterns):
        """生成 SQL 危险操作的边界用例"""
        edge_cases = reflective_runner.generate_edge_cases("SQL 危险操作检测")

        print("\n" + "=" * 80)
        print("SQL 操作边界测试用例:")
        print("=" * 80)

        for i, case in enumerate(edge_cases, 1):
            print(f"\n用例 {i}: {case.get('description', 'N/A')}")
            print(f"工具: {case.get('tool_name', 'N/A')}")
            print(f"参数: {case.get('args', {})}")
            print(f"预期: {'需要审批' if case.get('should_approve') else '不需要审批'}")

            # 运行生成的测试用例
            if case.get('tool_name') and case.get('args'):
                decision = checker_with_global_patterns.check(
                    case['tool_name'], case['args']
                )
                is_correct = decision.needs_approval == case.get('should_approve', False)
                status = "✓" if is_correct else "✗"
                print(f"结果: {status} (needs_approval={decision.needs_approval})")

        print("=" * 80)

        assert len(edge_cases) > 0, "应该生成至少一个边界用例"


class TestReflectiveFalsePositiveAnalysis:
    """使用 reason 模型分析误报场景"""

    @pytest.mark.skipif(
        not get_settings().models.reason_api_key,
        reason="需要配置 reason 模型 API key",
    )
    def test_analyze_common_false_positives(self, reflective_runner, checker_with_global_patterns):
        """分析常见的误报场景"""

        # 定义可能误报的场景
        potential_false_positives = [
            {
                "tool_name": "write_file",
                "args": {"path": "docs/auth.md", "content": "Change your password regularly"},
                "expected": False,
                "description": "文档中提到 password 关键词",
            },
            {
                "tool_name": "run_bash_command",
                "args": {"command": "man passwd"},
                "expected": False,
                "description": "查看 passwd 命令手册",
            },
            {
                "tool_name": "read_file",
                "args": {"path": "config/api_keys.example.txt"},
                "expected": False,
                "description": "读取示例配置文件（不含真实密钥）",
            },
        ]

        false_positive_count = 0
        analysis_results = []

        for scenario in potential_false_positives:
            decision = checker_with_global_patterns.check(
                scenario['tool_name'], scenario['args']
            )
            analysis = reflective_runner.analyze_decision(
                scenario['tool_name'],
                scenario['args'],
                decision,
                scenario['expected'],
            )

            if analysis['error_type'] == 'false_positive':
                false_positive_count += 1

            analysis_results.append({
                'scenario': scenario['description'],
                'decision': decision,
                'analysis': analysis,
            })

        # 输出分析报告
        print("\n" + "=" * 80)
        print("误报分析报告")
        print("=" * 80)
        print(f"总测试场景: {len(potential_false_positives)}")
        print(f"检测到误报: {false_positive_count}")
        print("=" * 80)

        for result in analysis_results:
            if result['analysis']['error_type'] == 'false_positive':
                print(f"\n⚠️  误报场景: {result['scenario']}")
                print(f"决策: needs_approval={result['decision'].needs_approval}")
                print(f"分析: {result['analysis']['analysis']}")
                if result['analysis']['suggestions']:
                    print(f"改进建议:")
                    for suggestion in result['analysis']['suggestions']:
                        print(f"  - {suggestion}")

        print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
