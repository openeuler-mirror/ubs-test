"""Unit tests for libs.utils module."""

import os

import pytest

from libs.utils import setup_test_env, cleanup_test_env, get_test_config, create_test_file


@pytest.mark.unit
class TestSetupTestEnv:
    """Test setup_test_env function."""

    def test_setup_default_config(self):
        """Test setup with default configuration."""
        config = setup_test_env()
        assert config["test_mode"] is True
        assert config["log_level"] == "DEBUG"
        assert config["timeout"] == 30
        assert "temp_dir" in config
        cleanup_test_env()

    def test_setup_custom_config(self):
        """Test setup with custom configuration."""
        config = setup_test_env({"test_mode": True, "log_level": "INFO", "timeout": 60})
        assert config["test_mode"] is True
        assert config["log_level"] == "INFO"
        assert config["timeout"] == 60
        cleanup_test_env()

    def test_setup_sets_env_vars(self):
        """Test that setup sets environment variables."""
        setup_test_env()
        assert os.environ.get("TEST_MODE") == "true"
        assert os.environ.get("LOG_LEVEL") == "DEBUG"
        cleanup_test_env()


@pytest.mark.unit
class TestCleanupTestEnv:
    """Test cleanup_test_env function."""

    def test_cleanup_restores_env(self):
        """Test that cleanup restores original environment."""
        original_value = os.environ.get("TEST_MODE")
        setup_test_env()
        cleanup_test_env()

        if original_value:
            assert os.environ.get("TEST_MODE") == original_value
        else:
            assert "TEST_MODE" not in os.environ


@pytest.mark.unit
class TestGetTestConfig:
    """Test get_test_config function."""

    def test_get_config_after_setup(self):
        """Test getting config after setup."""
        setup_test_env({"log_level": "WARNING", "timeout": 45})
        config = get_test_config()
        assert config["test_mode"] is True
        assert config["log_level"] == "WARNING"
        assert config["timeout"] == 45
        cleanup_test_env()


@pytest.mark.unit
class TestCreateTestFile:
    """Test create_test_file function."""

    def test_create_test_file(self):
        """Test creating a test file."""
        setup_test_env()
        test_file = create_test_file("test content", "test_file.txt")
        assert test_file.exists()
        assert test_file.read_text() == "test content"
        cleanup_test_env()

    def test_create_multiple_test_files(self):
        """Test creating multiple test files."""
        setup_test_env()
        file1 = create_test_file("content1", "file1.txt")
        file2 = create_test_file("content2", "file2.txt")
        assert file1.exists()
        assert file2.exists()
        assert file1.read_text() == "content1"
        assert file2.read_text() == "content2"
        cleanup_test_env()
