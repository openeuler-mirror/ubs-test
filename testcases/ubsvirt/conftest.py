"""pytest configuration for all testcases.

This file imports and exposes fixtures from libs/core/fixtures.py,
making them available to all tests under testcases/ directory.

pytest fixture discovery mechanism:
  pytest searches conftest.py files from test directory upward to root.
  This top-level conftest.py makes libs/core/fixtures.py fixtures available globally.
"""
import importlib
import logging
from pathlib import Path
from typing import Any, Dict, Set

import pytest

from libs.modules.ubsvirt.basecase.openstack_basecase import inject_openstack_basecase_dependencies as inject_virtualization_openstack_basecase_dependencies
from libs.modules.ubsvirt.basecase.vmxml_basecase import inject_vmxml_basecase_dependencies


logger = logging.getLogger(__name__)

_hooks_collected: Set[str] = set()
_hooks_executed: Dict[str, Any] = {}

TOPO_BASE_PATH = Path(__file__).parent.parent.parent / "resource" / "ubsvirt" / "topo"
XML_BASE_PATH = Path(__file__).parent.parent.parent / "resource" / "ubsvirt" / "xml"


@pytest.fixture
def topo_dir():
    """Provide base directory path for topo files.

    Returns:
        Path: Path to resource/ubsvirt/topo directory
    """
    return TOPO_BASE_PATH


@pytest.fixture
def xml_base_path():
    """Provide base directory path for XML files.

    Returns:
        Path: Path to resource/ubsvirt/xml directory
    """
    return XML_BASE_PATH


@pytest.fixture
def get_topo_path(topo_dir):
    """Factory fixture to get topo file path for a specific test case.

    Usage:
        topo_path = get_topo_path("test_vm_fragment_009")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_test_vm_fragment_009")))

    Returns:
        callable: Function that takes topo_name (str) and returns Path
    """
    def _get_topo_path(topo_name: str) -> Path:
        if not topo_name.endswith("_topo.json"):
            topo_name = topo_name + "_topo.json"
        return topo_dir / topo_name
    return _get_topo_path


def pytest_collection_modifyitems(config, items):
    """Collect all hook markers from test cases.

    Called by pytest after test collection is complete.
    Gathers all unique hook paths from test class markers.
    """
    global _hooks_collected

    for item in items:
        # Get hook marker from test class or test function
        hook_marker = item.get_closest_marker("hook")
        if hook_marker and hook_marker.args:
            hook_path = hook_marker.args[0]
            _hooks_collected.add(hook_path)

    if _hooks_collected:
        logger.info(f"[UBSE_VIRT_HOOK] Collected hooks from test cases: {_hooks_collected}")


@pytest.hookimpl(wrapper=True)
def pytest_runtestloop(session):
    """Execute all collected hooks before tests start.

    This hook wrapper runs before the test loop starts.
    - Loads and initializes each hook
    - Calls beforePreTestSet() for each hook (only once)
    - Executes tests
    - Calls afterPostTestSet() for each hook after tests complete
    """
    global _hooks_executed, _hooks_collected

    config = session.config

    # Skip if no hooks collected
    if not _hooks_collected:
        logger.info("[UBSE_VIRT_HOOK] No hooks to execute")
        yield
        return

    # Import helper functions from hook_runner
    from libs.core.hook_runner import _build_ssh_hosts, _read_custom_params

    # Get nodes and params from config
    nodes = _build_ssh_hosts(config)
    custom_params = _read_custom_params(config)

    if not nodes:
        logger.warning("[UBSE_VIRT_HOOK] No nodes available, skipping hook execution")
        yield
        return

    # Execute each hook's beforePreTestSet (only once)
    for hook_path in _hooks_collected:
        if hook_path in _hooks_executed:
            continue

        try:
            module_path, class_name = hook_path.rsplit(".", 1)
            mod = importlib.import_module(module_path)
            hook_class = getattr(mod, class_name)
            hook = hook_class()

            if hasattr(hook, "_init_from_fixture"):
                hook._init_from_fixture(nodes, custom_params)

            logger.info(f"[UBSE_VIRT_HOOK] === {hook_path}.beforePreTestSet() ===")
            hook.beforePreTestSet()
            logger.info(f"[UBSE_VIRT_HOOK] === {hook_path} beforePreTestSet completed ===")

            _hooks_executed[hook_path] = hook
        except Exception as exc:
            logger.error(f"[UBSE_VIRT_HOOK] Failed to execute hook '{hook_path}': {exc}")

    # Run tests
    yield

    # Cleanup: execute each hook's afterPostTestSet
    for hook_path, hook in _hooks_executed.items():
        try:
            logger.info(f"[UBSE_VIRT_HOOK] === {hook_path}.afterPostTestSet() ===")
            hook.afterPostTestSet()
            logger.info(f"[UBSE_VIRT_HOOK] === {hook_path} afterPostTestSet completed ===")
        except Exception as exc:
            logger.error(f"[UBSE_VIRT_HOOK] Failed to cleanup hook '{hook_path}': {exc}")

    # Clear executed hooks for next test run (if running multiple packages)
    _hooks_executed.clear()