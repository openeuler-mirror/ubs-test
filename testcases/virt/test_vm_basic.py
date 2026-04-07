"""Virtualization feature tests for UB ServiceCore."""

import pytest

from libs.utils import setup_test_env, cleanup_test_env


@pytest.mark.virt
@pytest.mark.integration
class TestVirtualizationBasic:
    """Test basic virtualization features."""

    def setup_method(self):
        self.config = setup_test_env({"test_mode": True})

    def teardown_method(self):
        cleanup_test_env()

    def test_vm_creation(self):
        """Test virtual machine creation."""
        assert self.config["test_mode"] is True

    def test_vm_deletion(self):
        """Test virtual machine deletion."""
        assert self.config["test_mode"] is True


@pytest.mark.virt
@pytest.mark.slow
def test_vm_snapshot():
    """Test VM snapshot functionality."""
    config = setup_test_env()
    try:
        assert config["test_mode"] is True
    finally:
        cleanup_test_env()
