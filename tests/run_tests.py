#!/usr/bin/env python
"""Unified test runner for GeneralAgent.

Provides standardized entry points for different test types:
- smoke: Quick validation tests (< 30s)
- unit: Unit tests for individual modules
- integration: Integration tests for module interactions
- e2e: End-to-end business workflow tests
- all: Run all tests

Usage:
    python tests/run_tests.py smoke
    python tests/run_tests.py unit
    python tests/run_tests.py integration
    python tests/run_tests.py e2e
    python tests/run_tests.py all
"""

import sys
import subprocess
import os
from pathlib import Path
from typing import List, Optional


class TestRunner:
    """统一测试运行器"""

    def __init__(self):
        self.tests_dir = Path(__file__).parent
        self.project_root = self.tests_dir.parent

        # 确保项目根目录在 PYTHONPATH 中
        project_root_str = str(self.project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        # 设置环境变量供子进程使用
        pythonpath = os.environ.get("PYTHONPATH", "")
        if project_root_str not in pythonpath:
            os.environ["PYTHONPATH"] = f"{project_root_str}:{pythonpath}" if pythonpath else project_root_str

    def run_smoke_tests(self) -> int:
        """运行冒烟测试 (快速验证)"""
        print("=" * 80)
        print("🔥 Running Smoke Tests (Quick Validation)")
        print("=" * 80)
        print("Purpose: Fast critical-path tests to catch obvious breakage")
        print("Expected time: < 30 seconds")
        print()

        return subprocess.call([
            "pytest",
            str(self.tests_dir / "smoke"),
            "-v",
            "--tb=short",
            "-m", "not slow"
        ])

    def run_unit_tests(self) -> int:
        """运行单元测试"""
        print("=" * 80)
        print("🧪 Running Unit Tests")
        print("=" * 80)
        print("Purpose: Test individual modules in isolation")
        print("Coverage: HITL, MCP, Tools, Skills, Workspace, etc.")
        print()

        return subprocess.call([
            "pytest",
            str(self.tests_dir / "unit"),
            "-v",
            "--tb=short"
        ])

    def run_integration_tests(self) -> int:
        """运行集成测试"""
        print("=" * 80)
        print("🔗 Running Integration Tests")
        print("=" * 80)
        print("Purpose: Test interactions between modules")
        print("Coverage: @Mention system, Tool registry, Subagent, etc.")
        print()

        return subprocess.call([
            "pytest",
            str(self.tests_dir / "integration"),
            "-v",
            "--tb=short"
        ])

    def run_e2e_tests(self) -> int:
        """运行端到端测试"""
        print("=" * 80)
        print("🚀 Running E2E Tests (Business Workflows)")
        print("=" * 80)
        print("Purpose: Test complete user scenarios end-to-end")
        print("Coverage: Full agent loop, multi-turn conversations, file ops, etc.")
        print()

        return subprocess.call([
            "pytest",
            str(self.tests_dir / "e2e"),
            "-v",
            "--tb=short",
            "-s"  # Show print statements for better visibility
        ])

    def run_all_tests(self) -> int:
        """运行所有测试"""
        print("=" * 80)
        print("🎯 Running ALL Tests")
        print("=" * 80)
        print()

        results = {
            "smoke": self.run_smoke_tests(),
            "unit": self.run_unit_tests(),
            "integration": self.run_integration_tests(),
            "e2e": self.run_e2e_tests(),
        }

        print("\n" + "=" * 80)
        print("📊 Test Results Summary")
        print("=" * 80)

        total_failed = 0
        for test_type, exit_code in results.items():
            status = "✅ PASSED" if exit_code == 0 else "❌ FAILED"
            print(f"{test_type:12} {status}")
            if exit_code != 0:
                total_failed += 1

        print("=" * 80)

        if total_failed == 0:
            print("🎉 All test suites passed!")
            return 0
        else:
            print(f"⚠️  {total_failed}/{len(results)} test suite(s) failed")
            return 1

    def run_with_coverage(self, test_type: Optional[str] = None) -> int:
        """运行测试并生成覆盖率报告"""
        print("=" * 80)
        print("📈 Running Tests with Coverage Report")
        print("=" * 80)
        print()

        test_path = str(self.tests_dir)
        if test_type and test_type != "all":
            test_path = str(self.tests_dir / test_type)

        return subprocess.call([
            "pytest",
            test_path,
            "-v",
            "--cov=generalAgent",
            "--cov-report=html",
            "--cov-report=term"
        ])


def main():
    """主入口"""
    runner = TestRunner()

    if len(sys.argv) < 2:
        print("Usage: python tests/run_tests.py [smoke|unit|integration|e2e|all|coverage]")
        print()
        print("Test Types:")
        print("  smoke       - Quick validation tests (< 30s)")
        print("  unit        - Unit tests for individual modules")
        print("  integration - Integration tests for module interactions")
        print("  e2e         - End-to-end business workflow tests")
        print("  all         - Run all test types")
        print("  coverage    - Run all tests with coverage report")
        print()
        print("Examples:")
        print("  python tests/run_tests.py smoke")
        print("  python tests/run_tests.py unit")
        print("  python tests/run_tests.py all")
        print("  python tests/run_tests.py coverage")
        sys.exit(1)

    test_type = sys.argv[1].lower()

    if test_type == "smoke":
        exit_code = runner.run_smoke_tests()
    elif test_type == "unit":
        exit_code = runner.run_unit_tests()
    elif test_type == "integration":
        exit_code = runner.run_integration_tests()
    elif test_type == "e2e":
        exit_code = runner.run_e2e_tests()
    elif test_type == "all":
        exit_code = runner.run_all_tests()
    elif test_type == "coverage":
        exit_code = runner.run_with_coverage()
    else:
        print(f"❌ Unknown test type: {test_type}")
        print("Valid types: smoke, unit, integration, e2e, all, coverage")
        sys.exit(1)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
