"""pytest configuration for ubse test package.

Activates the framework-level hook runner. The hook class is specified
in ``ubse_suite.json`` via the ``hook`` field and passed to pytest
as ``--test-hook`` by ``run_suite.py``.

"""
import pytest
from libs.core.hook_runner import package_hook_fixture
from libs.modules.ubse.hook.mem_pooling_hook import MEM_Pooling_Hook

@pytest.fixture(autouse=True)
def mem_pooling_hook_fixture(nodes, custom_params):
    hook = MEM_Pooling_Hook()
    hook._init_from_fixture(nodes, custom_params)
    return hook
