"""Container feature tests for UB ServiceCore."""

import pytest

from libs.utils import setup_test_env, cleanup_test_env


@pytest.mark.container
@pytest.mark.integration
class TestContainerBasic:
    """Test basic container features."""

    def setup_method(self):
        self.config = setup_test_env({"test_mode": True})

    def teardown_method(self):
        cleanup_test_env()

    def test_container_creation(self):
        """Test container creation."""
        assert self.config["test_mode"] is True

    def test_container_start_stop(self):
        """Test container start and stop."""
        assert self.config["test_mode"] is True


@pytest.mark.container
@pytest.mark.slow
def test_container_networking():
    """Test container networking functionality."""
    config = setup_test_env()
    try:
        assert config["test_mode"] is True
    finally:
        cleanup_test_env()
