"""Utility functions for test environment management."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


_test_env_vars: Dict[str, str] = {}
_test_temp_dirs: list[Path] = []


def setup_test_env(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Setup test environment with configuration.

    Args:
        config: Optional configuration dictionary for test setup.

    Returns:
        Dictionary containing test environment configuration.
    """
    global _test_env_vars

    if config is None:
        config = {}

    config.setdefault("test_mode", True)
    config.setdefault("log_level", "DEBUG")
    config.setdefault("timeout", 30)

    env_vars = {
        "TEST_MODE": "true",
        "LOG_LEVEL": config["log_level"],
        "TEST_TIMEOUT": str(config["timeout"]),
    }

    for key, value in env_vars.items():
        _test_env_vars[key] = os.environ.get(key, "")
        os.environ[key] = value

    temp_dir = Path(tempfile.mkdtemp(prefix="ubs_test_"))
    _test_temp_dirs.append(temp_dir)
    config["temp_dir"] = str(temp_dir)

    return config


def cleanup_test_env() -> None:
    """Clean up test environment and restore original variables."""
    global _test_env_vars, _test_temp_dirs

    for key, original_value in _test_env_vars.items():
        if original_value:
            os.environ[key] = original_value
        else:
            os.environ.pop(key, None)

    _test_env_vars.clear()

    for temp_dir in _test_temp_dirs:
        if temp_dir.exists():
            for item in temp_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    for sub_item in item.rglob("*"):
                        if sub_item.is_file():
                            sub_item.unlink()
                    item.rmdir()
            temp_dir.rmdir()

    _test_temp_dirs.clear()


def get_test_config() -> Dict[str, Any]:
    """Get current test configuration.

    Returns:
        Dictionary with current test environment settings.
    """
    return {
        "test_mode": os.environ.get("TEST_MODE", "false").lower() == "true",
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),
        "timeout": int(os.environ.get("TEST_TIMEOUT", "30")),
        "temp_dir": os.environ.get("TEST_TEMP_DIR", ""),
    }


def create_test_file(content: str, filename: str) -> Path:
    """Create a temporary test file with given content.

    Args:
        content: File content to write.
        filename: Name for the test file.

    Returns:
        Path to the created test file.
    """
    if not _test_temp_dirs:
        setup_test_env()

    temp_dir = _test_temp_dirs[-1]
    test_file = temp_dir / filename
    test_file.write_text(content)
    return test_file
