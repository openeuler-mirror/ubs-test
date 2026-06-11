"""pytest configuration for all testcases.

This file imports and exposes fixtures from libs/core/fixtures.py,
making them available to all tests under testcases/ directory.

pytest fixture discovery mechanism:
  pytest searches conftest.py files from test directory upward to root.
  This top-level conftest.py makes libs/core/fixtures.py fixtures available globally.
"""

from libs.core.basecase.hcom.hcom_basecase import inject_hcom_basecase_dependencies
from libs.modules.ubse.basecase.cm_basecase import inject_cm_basecase_dependencies
from libs.modules.ubse.basecase.distributed_high_reliability_basecase import (
    inject_distributed_high_reliability_basecase_dependencies,
)
from libs.modules.ubse.basecase.mem_pooling_basecase import inject_mem_pooling_dependencies
from libs.modules.ubse.basecase.ub_pooling_basecase import inject_ub_pooling_dependencies

from libs.core.basecase.ubturbo.at_basecase import inject_at_basecase_dependencies
from libs.core.basecase.ubturbo.container_overcommit_basecase import (
    inject_container_overcommit_basecase_dependencies,
)
from libs.core.basecase.ubturbo.env_topo import inject_env_topo_dependencies
from libs.core.basecase.ubturbo.mempooling_basecase import (
    inject_mempooling_basecase_dependencies,
)

# Import pytest_configure with alias to avoid recursion
from libs.core.fixtures import (
    cleanup_stack,
    create_multibase_fixture,
    custom_params,
    node_dict,
    node_executor,
    nodes,
    pytest_addoption,
    resource,
    resource_loader,
    test_case,
    test_case_with_deps,
    test_env_config,
)
from libs.core.fixtures import pytest_configure as _fixtures_pytest_configure

# Global storage for pytest config (accessible by sub-conftest.py)
_pytest_global_config = None


import logging as _logging

import pytest as _pytest


@_pytest.hookimpl(trylast=True)
def pytest_configure(config):
    global _pytest_global_config
    _pytest_global_config = config
    _fixtures_pytest_configure(config)


def pytest_sessionstart(session):
    from libs.utils import setup_test_env

    setup_test_env()


def pytest_runtest_setup(item):
    """设置 root logger 所有 handler 的 format，确保日志始终输出时间戳和线程号。"""
    log_fmt = "%(asctime)s [TID:%(thread)d] %(levelname)s %(name)s - %(message)s"
    log_datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = _logging.Formatter(fmt=log_fmt, datefmt=log_datefmt)
    for handler in _logging.getLogger().handlers:
        handler.setFormatter(formatter)


def get_pytest_config():
    """Get pytest config for package-level fixtures."""
    return _pytest_global_config


__all__ = [
    "test_case",
    "resource",
    "nodes",
    "node_dict",
    "custom_params",
    "test_case_with_deps",
    "node_executor",
    "resource_loader",
    "cleanup_stack",
    "test_env_config",
    "create_multibase_fixture",
    "inject_cm_basecase_dependencies",
    "inject_ub_pooling_dependencies",
    "inject_mem_pooling_dependencies",
    "inject_distributed_high_reliability_basecase_dependencies",
    "inject_hcom_basecase_dependencies",
    "inject_at_basecase_dependencies",
    "inject_env_topo_dependencies",
    "inject_mempooling_basecase_dependencies",
    "inject_container_overcommit_basecase_dependencies",
    "get_pytest_config",
    "pytest_addoption",
]
