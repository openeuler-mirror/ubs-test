#!/usr/local/python
# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import inject_kubernetes_basecase_dependencies


@pytest.fixture
def shm_base_path(request) -> str:
    """Get shared memory yaml base path.

    Returns:
        str: Path to yaml files for current test case
    """
    test_name = request.node.parent.name if hasattr(request.node, 'parent') else request.node.name
    test_case_name = test_name.replace(".py", "")

    base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / test_case_name

    return base_path

@pytest.fixture(autouse=True)
def inject_shm_base_path(request, shm_base_path):
    """Inject shm_base_path into test instance for setup_method usage."""
    if hasattr(request, 'instance') and request.instance:
        request.instance.shm_base_path = shm_base_path

