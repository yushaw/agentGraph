"""Globally available, read-only tools."""

from __future__ import annotations

import ast
import json
import operator as op
from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def now() -> str:
    """Return current UTC datetime."""

    return datetime.now(timezone.utc).isoformat()


@tool
def calc(expression: str) -> str:
    """Evaluate a safe arithmetic expression."""

    allowed_ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
    }

    def _eval(node: ast.AST):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("disallowed expression")

    try:
        node = ast.parse(expression, mode="eval").body
        return str(_eval(node))
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"calc failed: {exc}"}, ensure_ascii=False)


@tool
def format_json(text: str) -> str:
    """Best-effort JSON pretty printer."""

    try:
        obj = json.loads(text)
    except Exception:
        obj = json.loads(text.strip().rstrip("`"))
    return json.dumps(obj, ensure_ascii=False, indent=2)


@tool
def start_decomposition(reason: str = "") -> str:
    """Request the agent to create a plan and delegate via the decomposition workflow."""

    return json.dumps({"ok": True, "reason": reason}, ensure_ascii=False)
