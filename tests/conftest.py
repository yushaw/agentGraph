"""Pytest configuration and fixtures for all tests.

This file is automatically loaded by pytest and ensures proper test environment setup.
"""

import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH for imports to work
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
