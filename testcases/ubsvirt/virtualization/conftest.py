# -*- coding: utf-8 -*-
"""
Pytest fixtures for ubsvirt virtualization tests.

Provides:
- topo_dir: Base path for topo files (resource/ubsvirt/topo)
- xml_base_path: Base path for XML files (resource/ubsvirt/xml)
- get_topo_path: Factory function to get topo file path for specific test
"""

from pathlib import Path

import pytest

TOPO_BASE_PATH = Path(__file__).parent.parent.parent.parent / "resource" / "ubsvirt" / "topo"
XML_BASE_PATH = Path(__file__).parent.parent.parent.parent / "resource" / "ubsvirt" / "xml"


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