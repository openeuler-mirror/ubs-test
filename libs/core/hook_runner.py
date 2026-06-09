"""Shared hook runner — framework-level test suite hook capability.

Any test package can activate hooks by adding one import in its conftest.py:

    from libs.core.hook_runner import package_hook_fixture

The suite JSON declares the hook class via a ``hook`` field:

    {
        "tests": [...],
        "hook": "libs.ubsmem.ubsshmem.ubs_mem_hook.UbsMemHook",
        "params": {...}
    }

``run_suite.py`` reads the ``hook`` field and passes it as ``--test-hook``
to pytest. This fixture imports the class, instantiates it via
``_init_from_fixture()``, and runs ``beforePreTestSet()`` / ``afterPostTestSet()``.

This replaces the legacy UniAutos hook mechanism at the test-set level.
The pattern follows the existing Mem_SDK/conftest.py fixture style.
"""

import importlib
import json
import logging
from pathlib import Path
from typing import Any, List

import pytest

logger = logging.getLogger(__name__)


def _build_ssh_hosts(config) -> List[Any]:
    """Build SSH Linux host objects from --resource-config.

    Package-scoped fixtures cannot depend on function-scoped fixtures
    (nodes, resource), so the config file is read directly.
    """
    from libs.host import Linux

    config_path = config.getoption("--resource-config", None)
    if not config_path:
        logger.warning("[HookRunner] No --resource-config specified, skipping hook")
        return []

    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"[HookRunner] Config file not found: {config_file}, skipping hook")
        return []

    with open(config_file) as f:
        resource = json.load(f)

    nodes_list = [Linux(h) for h in resource.get("hosts", {}).values() if isinstance(h, dict)]

    try:
        nodes_list.sort(key=lambda n: getattr(n, "localIP", getattr(n, "ip", "")))
    except Exception:
        pass

    return nodes_list


def _read_custom_params(config) -> dict:
    """Read custom parameters from --test-params CLI option."""
    raw = config.getoption("--test-params", None)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[HookRunner] Invalid --test-params JSON: {raw}")
    return {}


@pytest.fixture(scope="package", autouse=True)
def package_hook_fixture(request):
    """Package-level fixture: runs the hook specified by ``--test-hook``.

    The hook class (e.g. ``libs.ubsmem...UbsMemHook``) must provide:

      - ``_init_from_fixture(ssh_hosts, custom_params)``
      - ``beforePreTestSet()``   — called before all tests in the package
      - ``afterPostTestSet()``   — called after all tests in the package

    Usage via suite JSON::

        {
            "tests": ["..."],
            "hook": "path.to.module.HookClass",
            "params": {...}
        }

    ``run_suite.py`` reads the ``hook`` field and passes it as ``--test-hook``.
    """
    hook_path: str | None = request.config.getoption("--test-hook", None)
    if not hook_path:
        yield
        return

    # --- Import hook class ---------------------------------------------------
    try:
        module_path, class_name = hook_path.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        hook_class = getattr(mod, class_name)
    except (ImportError, AttributeError, ValueError) as exc:
        logger.error(f"[HookRunner] Cannot load hook '{hook_path}': {exc}")
        yield
        return

    # --- Build SSH hosts & read params ---------------------------------------
    ssh_hosts = _build_ssh_hosts(request.config)
    custom_params = _read_custom_params(request.config)

    if not ssh_hosts:
        logger.warning("[HookRunner] No SSH hosts — skipping hook setup")
        yield
        return

    # --- Instantiate & initialise hook ---------------------------------------
    hook = hook_class()
    if hasattr(hook, "_init_from_fixture"):
        hook._init_from_fixture(ssh_hosts, custom_params)
    else:
        logger.warning(
            f"[HookRunner] Hook class {hook_path} has no _init_from_fixture() — "
            "attributes may not be set"
        )

    # --- Run pre-test-set logic ----------------------------------------------
    logger.info(f"[HookRunner] === {hook_path}.beforePreTestSet() ===")
    hook.beforePreTestSet()
    logger.info("[HookRunner] === beforePreTestSet completed ===")

    yield

    # --- Run post-test-set logic ---------------------------------------------
    logger.info(f"[HookRunner] === {hook_path}.afterPostTestSet() ===")
    hook.afterPostTestSet()
    logger.info("[HookRunner] === afterPostTestSet completed ===")
