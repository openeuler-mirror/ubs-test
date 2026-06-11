"""pytest configuration for HCOM service tests.

This file imports only HCOM-specific fixtures, avoiding dependency on
ubturbo modules (which require pandas).
"""

# Import HCOM-specific fixture
from libs.core.basecase.hcom.hcom_basecase import inject_hcom_basecase_dependencies

# Import base fixtures from parent conftest
# We need to manually import them to avoid the full conftest chain
from libs.core.fixtures import (
    custom_params,
    node_dict,
    nodes,
    resource,
    test_case,
)

__all__ = [
    "test_case",
    "resource",
    "nodes",
    "node_dict",
    "custom_params",
    "inject_hcom_basecase_dependencies",
]
