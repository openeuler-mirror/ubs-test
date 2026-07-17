"""pytest configuration for all testcases.

This file imports and exposes fixtures from libs/core/fixtures.py,
making them available to all tests under testcases/ directory.

pytest fixture discovery mechanism:
  pytest searches conftest.py files from test directory upward to root.
  This top-level conftest.py makes libs/core/fixtures.py fixtures available globally.
"""
import logging
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.openstack_basecase import inject_openstack_basecase_dependencies as inject_virtualization_openstack_basecase_dependencies
from libs.modules.ubsvirt.basecase.vmxml_basecase import inject_vmxml_basecase_dependencies


logger = logging.getLogger(__name__)

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
