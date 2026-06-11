"""UBS Test Library - Common building blocks for testing.

This library provides shared utilities, core functionality, and helper functions
for testing UB ServiceCore components across multiple integration and feature tests.
"""

__version__ = "0.1.0"
__author__ = "Jinhui Tong"
__license__ = "MulanPSL2"

from libs.core import TestCase
from libs.utils import setup_test_env, cleanup_test_env, get_test_config

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "TestCase",
    "setup_test_env",
    "cleanup_test_env",
    "get_test_config",
]
