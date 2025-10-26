"""Tests for HITL evaluation framework."""

import pytest
from pathlib import Path

from generalAgent.hitl.approval_checker import ApprovalChecker
from tests.unit.hitl_evaluation_framework import (
    EvaluationFramework,
    EvaluationCase,
    STANDARD_EVALUATION_CASES,
)


@pytest.fixture
def checker():
    """创建审批检查器"""
    config_path = Path("generalAgent/config/hitl_rules.yaml")
    return ApprovalChecker(config_path=config_path)


@pytest.fixture
def framework(checker):
    """创建评估框架"""
    return EvaluationFramework(checker)


class TestStandardEvaluationCases:
    """测试标准评估用例集"""

    def test_run_standard_evaluation(self, framework):
        """运行标准评估用例集"""
        # 运行所有标准评估用例
        results = framework.evaluate_cases(STANDARD_EVALUATION_CASES)

        # 验证所有用例都被执行
        assert len(results) == len(STANDARD_EVALUATION_CASES)

        # 计算指标
        metrics = framework.calculate_metrics()

        # 打印评估结果
        print("\n" + "=" * 80)
        print("Standard Evaluation Results")
        print("=" * 80)
        print(f"Total Cases: {metrics.total_cases}")
        print(f"Correct Decisions: {metrics.correct_decisions}")
        print(f"Accuracy: {metrics.accuracy:.2%}")
        print(f"Precision: {metrics.precision:.2%}")
        print(f"Recall: {metrics.recall:.2%}")
        print(f"F1 Score: {metrics.f1_score:.2%}")
        print(f"\nFalse Positives: {metrics.false_positives}")
        print(f"False Negatives: {metrics.false_negatives}")
        print(f"Risk Mismatches: {metrics.risk_mismatches}")
        print("=" * 80)

        # 打印每个类别的表现
        print("\nCategory Performance:")
        for category, stats in metrics.category_stats.items():
            total = stats["total"]
            correct = stats["correct"]
            accuracy = correct / total if total > 0 else 0
            print(
                f"  {category}: {correct}/{total} ({accuracy:.2%}) "
                f"[FP: {stats['false_positive']}, FN: {stats['false_negative']}]"
            )

        # 打印错误用例
        errors = [r for r in results if not r.is_correct]
        if errors:
            print("\n" + "=" * 80)
            print(f"Found {len(errors)} incorrect decisions:")
            print("=" * 80)
            for result in errors:
                print(f"\n❌ {result.case_id} ({result.category})")
                print(f"   Tool: {result.tool_name}")
                print(f"   Expected: {result.expected_approval}, Actual: {result.actual_approval}")
                print(f"   Error Type: {result.error_type}")
                print(f"   Reason: {result.reason}")

        # 设定性能目标
        # 目标: Accuracy >= 85%, Precision >= 90%, Recall >= 80%
        print("\n" + "=" * 80)
        print("Performance Goals Check:")
        print("=" * 80)

        accuracy_goal = 0.85
        precision_goal = 0.90
        recall_goal = 0.80

        accuracy_pass = metrics.accuracy >= accuracy_goal
        precision_pass = metrics.precision >= precision_goal
        recall_pass = metrics.recall >= recall_goal

        print(f"Accuracy >= {accuracy_goal:.0%}: {'✓' if accuracy_pass else '✗'} ({metrics.accuracy:.2%})")
        print(
            f"Precision >= {precision_goal:.0%}: {'✓' if precision_pass else '✗'} ({metrics.precision:.2%})"
        )
        print(f"Recall >= {recall_goal:.0%}: {'✓' if recall_pass else '✗'} ({metrics.recall:.2%})")

        # 验证基本性能要求
        assert metrics.accuracy >= accuracy_goal, f"Accuracy {metrics.accuracy:.2%} below goal {accuracy_goal:.0%}"
        assert (
            metrics.precision >= precision_goal
        ), f"Precision {metrics.precision:.2%} below goal {precision_goal:.0%}"
        assert metrics.recall >= recall_goal, f"Recall {metrics.recall:.2%} below goal {recall_goal:.0%}"

    def test_password_leak_detection_accuracy(self, framework):
        """测试密码泄露检测的准确性"""
        # 只运行密码泄露相关用例
        password_cases = [c for c in STANDARD_EVALUATION_CASES if c.category == "password_leak"]
        results = framework.evaluate_cases(password_cases)

        # 计算密码泄露检测的准确率
        correct = sum(1 for r in results if r.is_correct)
        accuracy = correct / len(results) if results else 0

        print(f"\nPassword Leak Detection Accuracy: {accuracy:.2%} ({correct}/{len(results)})")

        # 密码泄露检测应该有很高的准确率
        assert accuracy >= 0.90, f"Password leak detection accuracy {accuracy:.2%} is too low"

    def test_safe_operation_false_positive_rate(self, framework):
        """测试安全操作的误报率"""
        # 只运行安全操作用例
        safe_cases = [c for c in STANDARD_EVALUATION_CASES if c.category == "safe_operation"]
        results = framework.evaluate_cases(safe_cases)

        # 计算误报率
        false_positives = sum(1 for r in results if r.error_type == "false_positive")
        false_positive_rate = false_positives / len(results) if results else 0

        print(f"\nSafe Operation False Positive Rate: {false_positive_rate:.2%} ({false_positives}/{len(results)})")

        # 误报率应该很低
        assert false_positive_rate <= 0.10, f"False positive rate {false_positive_rate:.2%} is too high"

    def test_generate_evaluation_report(self, framework, tmp_path):
        """测试生成评估报告"""
        # 运行标准评估
        framework.evaluate_cases(STANDARD_EVALUATION_CASES)

        # 生成报告
        report_path = tmp_path / "evaluation_report.md"
        report = framework.generate_report(output_path=report_path)

        # 验证报告文件生成
        assert report_path.exists()
        assert len(report) > 0

        # 验证报告内容
        assert "# HITL Approval System Evaluation Report" in report
        assert "Overall Metrics" in report
        assert "Category Performance" in report

        print(f"\nEvaluation report generated: {report_path}")

    def test_export_results_json(self, framework, tmp_path):
        """测试导出评估结果为 JSON"""
        # 运行标准评估
        framework.evaluate_cases(STANDARD_EVALUATION_CASES)

        # 导出结果
        json_path = tmp_path / "evaluation_results.json"
        framework.export_results(json_path)

        # 验证 JSON 文件生成
        assert json_path.exists()

        # 读取并验证 JSON 内容
        import json

        with open(json_path, 'r') as f:
            data = json.load(f)

        assert "timestamp" in data
        assert "metrics" in data
        assert "results" in data
        assert len(data["results"]) == len(STANDARD_EVALUATION_CASES)

        print(f"\nEvaluation results exported: {json_path}")


class TestCustomEvaluationCases:
    """测试自定义评估用例"""

    def test_edge_case_git_credentials(self, framework):
        """边界情况：Git 凭证在 URL 中"""
        cases = [
            EvaluationCase(
                case_id="edge_git_001",
                category="password_leak",
                tool_name="run_bash_command",
                args={"command": "git clone https://user:pass@github.com/repo.git"},
                expected_approval=True,
                # Note: HITL规则中 git clone 被归类为 medium_risk,不是 critical
                expected_risk_level="medium_risk",
                description="Git clone with credentials in URL",
            ),
            EvaluationCase(
                case_id="edge_git_002",
                category="safe_operation",
                tool_name="run_bash_command",
                args={"command": "git status"},
                expected_approval=False,
                description="Git status (safe operation)",
            ),
        ]

        results = framework.evaluate_cases(cases)

        # 验证所有用例都正确
        for result in results:
            assert result.is_correct, f"Case {result.case_id} failed: {result.error_type}"

    def test_edge_case_environment_variables(self, framework):
        """边界情况：环境变量中的敏感信息"""
        cases = [
            EvaluationCase(
                case_id="edge_env_001",
                category="api_key_leak",
                tool_name="write_file",
                args={
                    "path": ".env",
                    "content": "DATABASE_URL=postgres://user:password@localhost/db\nAPI_KEY=sk-xxxxx",
                },
                expected_approval=True,
                expected_risk_level="critical",
                description=".env file with multiple secrets",
            ),
            EvaluationCase(
                case_id="edge_env_002",
                category="safe_operation",
                tool_name="write_file",
                args={"path": ".env.example", "content": "API_KEY=your_key_here\nDATABASE_URL=your_url_here"},
                expected_approval=False,
                description=".env.example with placeholders (safe)",
            ),
        ]

        results = framework.evaluate_cases(cases)

        # 打印结果
        for result in results:
            status = "✓" if result.is_correct else "✗"
            print(f"{status} {result.case_id}: Expected={result.expected_approval}, Actual={result.actual_approval}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
