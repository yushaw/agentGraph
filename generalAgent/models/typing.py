"""Typing helpers for model registry."""

from typing import Literal

ModelKey = Literal["base", "reason", "vision", "code", "chat"]

__all__ = ["ModelKey"]
