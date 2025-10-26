"""Human-in-the-Loop (HITL) module for generalAgent.

Provides approval mechanisms and user interaction capabilities.
"""

from .approval_checker import ApprovalChecker, ApprovalDecision
from .approval_node import ApprovalToolNode

__all__ = [
    "ApprovalChecker",
    "ApprovalDecision",
    "ApprovalToolNode",
]
