"""Approval checker for tool execution safety."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml


@dataclass
class ApprovalDecision:
    """审批决策结果"""

    needs_approval: bool
    reason: str = ""
    risk_level: str = "low"  # low, medium, high


class ApprovalChecker:
    """工具执行审批检测器

    支持四层规则（优先级从高到低）：
    1. 工具自定义检查器（代码实现，最高优先级）
    2. 全局风险模式（跨工具检测，如敏感信息泄露）
    3. 工具配置规则（工具特定规则）
    4. 默认内置规则（兜底逻辑）
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 审批规则配置文件路径（可选）
        """
        self.config_path = config_path
        self.rules = self._load_config() if config_path else {}
        self.custom_checkers: Dict[str, Callable] = {}
        self.global_patterns = self._load_global_patterns()

    def _load_config(self) -> dict:
        """加载配置文件"""
        if not self.config_path or not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load approval config: {e}")
            return {}

    def _load_global_patterns(self) -> Dict[str, Any]:
        """加载全局风险模式"""
        global_config = self.rules.get("global", {})
        risk_patterns = global_config.get("risk_patterns", {})

        # 将配置转换为易于检查的格式
        patterns_by_level = {}
        for level, pattern_config in risk_patterns.items():
            if isinstance(pattern_config, dict):
                patterns_by_level[level] = {
                    "patterns": pattern_config.get("patterns", []),
                    "action": pattern_config.get("action", "require_approval"),
                    "reason": pattern_config.get("reason", f"匹配全局{level}风险模式"),
                }

        return patterns_by_level

    def register_checker(self, tool_name: str, checker: Callable[[dict], ApprovalDecision]):
        """注册工具自定义审批检测函数

        Args:
            tool_name: 工具名称
            checker: 检测函数，接收 args，返回 ApprovalDecision
        """
        self.custom_checkers[tool_name] = checker

    def check(self, tool_name: str, args: dict) -> ApprovalDecision:
        """检查工具调用是否需要审批

        四层检查顺序：
        1. 工具自定义检查器（最高优先级）
        2. 全局风险模式（跨工具）
        3. 工具配置规则（工具特定）
        4. 默认内置规则（兜底）

        Args:
            tool_name: 工具名称
            args: 工具参数

        Returns:
            ApprovalDecision
        """
        # 1. 工具自定义检测（优先级最高）
        if tool_name in self.custom_checkers:
            return self.custom_checkers[tool_name](args)

        # 2. 全局风险模式检查（跨工具）
        global_decision = self._check_global_patterns(args)
        if global_decision.needs_approval:
            return global_decision

        # 3. 工具配置规则
        if tool_name in self.rules.get("tools", {}):
            decision = self._check_config_rules(tool_name, args)
            if decision.needs_approval:
                return decision

        # 4. 默认内置规则
        return self._check_builtin_rules(tool_name, args)

    def _check_global_patterns(self, args: dict) -> ApprovalDecision:
        """检查全局风险模式（跨工具）

        Args:
            args: 工具参数

        Returns:
            ApprovalDecision
        """
        if not self.global_patterns:
            return ApprovalDecision(needs_approval=False)

        # 将所有参数值转为字符串
        args_str = " ".join(str(v) for v in args.values())

        # 按风险级别检查（critical > high > medium > low）
        risk_levels_order = ["critical", "high", "medium", "low"]

        for risk_level in risk_levels_order:
            if risk_level not in self.global_patterns:
                continue

            pattern_config = self.global_patterns[risk_level]
            patterns = pattern_config.get("patterns", [])
            action = pattern_config.get("action", "require_approval")
            reason = pattern_config.get("reason", f"匹配全局{risk_level}风险模式")

            for pattern in patterns:
                if re.search(pattern, args_str, re.IGNORECASE):
                    if action == "require_approval":
                        return ApprovalDecision(
                            needs_approval=True,
                            reason=reason,
                            risk_level=risk_level,
                        )

        return ApprovalDecision(needs_approval=False)

    def _check_config_rules(self, tool_name: str, args: dict) -> ApprovalDecision:
        """检查配置文件规则"""
        tool_config = self.rules["tools"][tool_name]

        if not tool_config.get("enabled", True):
            return ApprovalDecision(needs_approval=False)

        # 检查模式匹配
        patterns = tool_config.get("patterns", {})

        for risk_level, pattern_list in patterns.items():
            for pattern in pattern_list:
                if self._matches_pattern(pattern, args):
                    action = tool_config.get("actions", {}).get(
                        risk_level, "require_approval"
                    )

                    if action == "require_approval":
                        return ApprovalDecision(
                            needs_approval=True,
                            reason=f"匹配{risk_level}风险模式: {pattern}",
                            risk_level=risk_level,
                        )

        return ApprovalDecision(needs_approval=False)

    def _matches_pattern(self, pattern: str, args: dict) -> bool:
        """检查参数是否匹配模式"""
        # 将所有参数值转为字符串并检查
        args_str = " ".join(str(v) for v in args.values())
        return bool(re.search(pattern, args_str, re.IGNORECASE))

    def _check_builtin_rules(self, tool_name: str, args: dict) -> ApprovalDecision:
        """默认内置规则"""

        # run_bash_command 默认规则
        if tool_name == "run_bash_command":
            command = args.get("command", "")
            return self._check_bash_command(command)

        # http_fetch 默认规则
        if tool_name == "http_fetch":
            url = args.get("url", "")
            return self._check_http_fetch(url)

        # 默认：不需要审批
        return ApprovalDecision(needs_approval=False)

    def _check_bash_command(self, command: str) -> ApprovalDecision:
        """检查 bash 命令安全性"""
        # 高风险操作
        high_risk_patterns = [
            r"\brm\s+-rf\b",
            r"\bsudo\b",
            r"\bchmod\s+777\b",
            r"\bmkfs\b",
            r"\bdd\b.*\bif=/dev/",
            r"\b>\s*/dev/",
        ]

        for pattern in high_risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return ApprovalDecision(
                    needs_approval=True,
                    reason=f"检测到高风险操作",
                    risk_level="high",
                )

        # 中等风险操作
        medium_risk_patterns = [
            r"\bcurl\b",
            r"\bwget\b",
            r"\bgit\s+clone\b",
            r"\bpip\s+install\b",
            r"\bnpm\s+install\b",
        ]

        for pattern in medium_risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return ApprovalDecision(
                    needs_approval=True,
                    reason=f"检测到网络/安装操作",
                    risk_level="medium",
                )

        return ApprovalDecision(needs_approval=False)

    def _check_http_fetch(self, url: str) -> ApprovalDecision:
        """检查 HTTP 请求安全性"""
        # 检查本地/内网地址
        local_patterns = [
            r"localhost",
            r"127\.0\.0\.1",
            r"192\.168\.",
            r"10\.",
            r"172\.(1[6-9]|2[0-9]|3[0-1])\.",
        ]

        for pattern in local_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return ApprovalDecision(
                    needs_approval=True,
                    reason=f"访问本地/内网地址",
                    risk_level="medium",
                )

        return ApprovalDecision(needs_approval=False)
