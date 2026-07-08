"""pytest configuration for ubse test package.

Hook Management Strategy:
- Collects hook markers from all test cases during pytest collection phase
- Executes each unique hook only ONCE before tests start (pytest_runtestloop)
- Cleans up all hooks after tests complete

Usage:
- Mark test class with @pytest.mark.hook("path.to.HookClass")
- Hook class must implement:
    - _init_from_fixture(nodes, custom_params)
    - beforePreTestSet()
    - afterPostTestSet()

Example:
    @pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
    class TestMyCase(MEM_Pooling_BaseCase):
        ...
"""
import importlib
import logging
from typing import Any, Dict, Set

import pytest

logger = logging.getLogger(__name__)

# Global storage for collected hooks and executed hooks
_hooks_collected: Set[str] = set()
_hooks_executed: Dict[str, Any] = {}


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
        logger.info(f"[UBSE_HOOK] Collected hooks from test cases: {_hooks_collected}")


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
        logger.info("[UBSE_HOOK] No hooks to execute")
        yield
        return
    
    # Import helper functions from hook_runner
    from libs.core.hook_runner import _build_ssh_hosts, _read_custom_params
    
    # Get nodes and params from config
    nodes = _build_ssh_hosts(config)
    custom_params = _read_custom_params(config)
    
    if not nodes:
        logger.warning("[UBSE_HOOK] No nodes available, skipping hook execution")
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
            
            logger.info(f"[UBSE_HOOK] === {hook_path}.beforePreTestSet() ===")
            hook.beforePreTestSet()
            logger.info(f"[UBSE_HOOK] === {hook_path} beforePreTestSet completed ===")
            
            _hooks_executed[hook_path] = hook
        except Exception as exc:
            logger.error(f"[UBSE_HOOK] Failed to execute hook '{hook_path}': {exc}")
    
    # Run tests
    yield
    
    # Cleanup: execute each hook's afterPostTestSet
    for hook_path, hook in _hooks_executed.items():
        try:
            logger.info(f"[UBSE_HOOK] === {hook_path}.afterPostTestSet() ===")
            hook.afterPostTestSet()
            logger.info(f"[UBSE_HOOK] === {hook_path} afterPostTestSet completed ===")
        except Exception as exc:
            logger.error(f"[UBSE_HOOK] Failed to cleanup hook '{hook_path}': {exc}")
    
    # Clear executed hooks for next test run (if running multiple packages)
    _hooks_executed.clear()


# Keep package_hook_fixture import for backward compatibility
from libs.core.hook_runner import package_hook_fixture