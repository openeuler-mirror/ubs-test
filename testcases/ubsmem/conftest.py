"""pytest configuration for ubsmem test package.

Activates the framework-level hook runner. The hook class is specified
in ``ubsmem_suite.json`` via the ``hook`` field and passed to pytest
as ``--test-hook`` by ``run_suite.py``.

Example suite JSON hook field::

    "hook": "libs.modules.ubsmem.ubsshmem.ubs_mem_hook.UbsMemHook"
"""

from libs.core.hook_runner import package_hook_fixture
from libs.modules.ubsmem.ubsshmem.ubs_mem_case import inject_ubs_mem_case_dependencies
