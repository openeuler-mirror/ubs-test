"""Pytest fixtures for resource management, logging, and test utilities.

These fixtures provide compatibility layer for legacy UniAutos framework
resources and utilities.
"""

import pytest
import logging
from typing import Any, Dict, List, Optional, Generator, Callable
from pathlib import Path

from libs.core.base import TestCase

Logger = logging.Logger
# 使用_module_logger避免与logger fixture命名冲突
_module_logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def resource_config(request: pytest.FixtureRequest) -> dict:
    """
    只负责加载资源配置。

    不依赖 test_case,
    因此可以安全地使用 session/package scope。
    """

    resource_data = {
        "hosts": {},
        "devices": {},
        "global": {}
    }

    from libs.utils.env_config import get_default_config_path

    resource_config = request.config.getoption(
        "--resource-config",
        None
    )

    if resource_config:
        config_path = Path(resource_config)
    else:
        config_path = get_default_config_path()

    if config_path and config_path.exists():
        import json
        with open(config_path, encoding="utf-8") as f:
            resource_data.update(json.load(f))
    else:
        pytest.fail(
            f"Resource config file not found at {config_path}"
        )

    return resource_data



@pytest.fixture
def test_case(request: pytest.FixtureRequest) -> Generator[TestCase, Any, None]:
    """Fixture providing TestCase instance with pytest request context.
    
    TestCase不再有__init__方法（pytest无法收集带__init__的测试类），
    因此直接创建实例并设置属性。
    """
    case = TestCase()
    case.name = request.node.name
    case.description = request.node.obj.__doc__ or ""
    
    case.node = request.node
    case.config = request.config
    
    yield case
    
    case.performCleanUp()


@pytest.fixture
def resource(request: pytest.FixtureRequest, test_case: TestCase) -> Generator[Any | None, Any, None]:
    """Fixture providing test resource management.
    
    Legacy: self.resource from UniAutos framework
    Maps to pytest fixture that loads test resources from configuration.
    
    Configuration loading priority:
    1. --resource-config CLI parameter (if specified)
    2. Default path: {PROJECT_ROOT}/conf/env.json
    
    Args:
        request: pytest fixture request
        test_case: TestCase instance
        
    Returns:
        Resource dictionary with hosts, devices, etc.
    """
    test_case.resource = {
        "hosts": {},
        "devices": {},
        "global": {}
    }
    
    from libs.utils.env_config import get_default_config_path
    
    resource_config = request.config.getoption("--resource-config", None)
    
    if resource_config:
        config_path = Path(resource_config)
    else:
        config_path = get_default_config_path()
        if config_path.exists():
            _module_logger.info(f"Using default config path: {config_path}")
    
    if config_path and config_path.exists():
        import json
        with open(config_path) as f:
            test_case.resource.update(json.load(f))
    elif not resource_config:
        _module_logger.warning(f"Default config not found at {config_path}, using empty resource")
    
    yield test_case.resource


@pytest.fixture
def nodes(resource: Dict[str, Any], test_case: TestCase) -> Generator[list[Any], Any, None]:
    """Fixture providing test node list as Linux objects.
    
    Legacy: self.nodes from UniAutos framework
    Converts host dictionaries to Linux objects for command execution.
    Linux provides full Linux host operations (file, disk, iSCSI, service, etc.)
    
    Args:
        resource: Resource fixture
        test_case: TestCase instance
        
    Returns:
        List of Linux objects with run(), putFile(), getFile() and Linux operations
    """
    from libs.host import Linux
    
    hosts = resource.get("hosts", {})
    nodes_list = []
    
    for host_id, host_info in hosts.items():
        if isinstance(host_info, dict):
            linux_node = Linux(host_info)
            nodes_list.append(linux_node)
        elif hasattr(host_info, "run"):
            nodes_list.append(host_info)
    
    test_case.nodes = nodes_list
    if nodes_list:
        test_case.node = nodes_list[0]
    yield nodes_list


@pytest.fixture
def logger(test_case: TestCase) -> Generator[Logger, Any, None]:
    """Fixture providing test logger.
    
    Legacy: self.logger from UniAutos framework
    
    Args:
        test_case: TestCase instance
        
    Returns:
        Logger instance
    """
    yield test_case.logger


@pytest.fixture
def node_dict(nodes) -> Generator[dict[Any, Any], Any, None]:
    """Fixture providing node dictionary mapping.
    
    Legacy: self.node_dict from basecase
    Maps node names to node objects with role labels.
    
    Args:
        nodes: nodes fixture
        
    Returns:
        Dictionary mapping node names to node objects
    """
    node_mapping = {}
    
    if nodes:
        for i, node in enumerate(nodes):
            # Basic node mapping
            node_mapping[f"node{i}"] = node
            
            # Role-based mapping (standard naming)
            if i == 0:
                node_mapping["master"] = node
                node_mapping["controller"] = node
            elif i == 1:
                node_mapping["worker1"] = node
                node_mapping["agent"] = node
            elif i == 2:
                node_mapping["worker2"] = node
            elif i == 3:
                node_mapping["worker3"] = node
                
    yield node_mapping


@pytest.fixture
def custom_params(request: pytest.FixtureRequest) -> Generator[dict[Any, Any], Any, None]:
    """Fixture providing test parameters from testset.xml.
    
    Legacy: self.customParam from testset XML
    Maps to pytest parametrize or command-line options.
    
    Args:
        request: pytest fixture request
        
    Returns:
        Dictionary of test parameters
    """
    params = {}
    
    # From testset marker
    # marker = request.node.get_closest_marker("parametrize")
    # if marker and marker.args:
    #     params.update(marker.args[0])
    
    # From command-line
    cli_params = request.config.getoption("--test-params", None)
    if cli_params:
        import json
        try:
            params.update(json.loads(cli_params))
        except json.JSONDecodeError:
            pass
    
    yield params


@pytest.fixture
def test_case_with_deps(test_case, nodes, node_dict, custom_params) -> Generator[TestCase, Any, None]:
    """Fixture providing TestCase with all dependencies injected.
    
    Legacy: self from basecase with all attributes
    Injects all legacy dependencies into TestCase.
    
    Args:
        test_case: TestCase fixture
        nodes: nodes fixture
        node_dict: node_dict fixture
        custom_params: custom_params fixture
        
    Returns:
        TestCase instance with all dependencies
    """
    # Inject dependencies
    test_case.nodes = nodes
    test_case.node_dict = node_dict
    test_case.customParam = custom_params
    
    # Set convenience attributes
    if nodes:
        test_case.node = nodes[0]
        test_case.master = nodes[0] if len(nodes) > 0 else None
        test_case.controller = nodes[0] if len(nodes) > 0 else None
        test_case.agent = nodes[1] if len(nodes) > 1 else None
    
    yield test_case


@pytest.fixture
def cleanup_stack(test_case: TestCase) -> Generator[list[Callable[..., Any]], Any, None]:
    """Fixture providing cleanup stack management.
    
    Legacy: self.addCleanUpStack() and self.performCleanUp()
    
    Args:
        test_case: TestCase instance
        
    Returns:
        Cleanup stack (handled by TestCase.performCleanUp())
    """
    yield test_case._cleanup_stack


@pytest.fixture(scope="session")
def test_env_config() -> Generator[dict[str, Any], Any, None]:
    """Session-scoped fixture for test environment configuration.
    
    Returns:
        Global test environment configuration
    """
    from libs.utils import setup_test_env
    config = setup_test_env()
    yield config
    from libs.utils import cleanup_test_env
    cleanup_test_env()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom pytest command-line options for legacy compatibility.
    
    Args:
        parser: pytest parser object
    """
    parser.addoption(
        "--resource-config",
        action="store",
        default=None,
        help="Path to resource configuration file (legacy test_bed.xml equivalent)"
    )
    
    parser.addoption(
        "--test-params",
        action="store",
        default=None,
        help="JSON string of test parameters (legacy customParam equivalent)"
    )
    
    parser.addoption(
        "--testset",
        action="store",
        default=None,
        help="Testset name to run (legacy testset.xml equivalent)"
    )

    parser.addoption(
        "--test-hook",
        action="store",
        default=None,
        help="Fully qualified hook class path (e.g. libs.ubsmem.ubsshmem.ubs_mem_hook.UbsMemHook)"
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers for legacy compatibility.
    
    Args:
        config: pytest config object
    """
    config.addinivalue_line(
        "markers", "parametrize(params): mark test with custom parameters (legacy customParam)"
    )
    config.addinivalue_line(
        "markers", "testset(name): mark test as part of a testset (legacy testset.xml)"
    )
    config.addinivalue_line(
        "markers", "level(level): mark test level (0/1/2) (legacy RunLevel)"
    )
    config.addinivalue_line(
        "markers", "envtype(type): mark test environment type (legacy EnvType)"
    )
    config.addinivalue_line(
        "markers", "hook(module): mark test with legacy hook module to run"
    )


# ========== Node execution and Hook fixtures ==========

@pytest.fixture
def node_executor(nodes: List[Any]) -> Generator[list[Any], Any, None]:
    """Fixture providing node command execution wrapper.
    
    Converts legacy node.run() pattern to pytest-compatible interface.
    Each node is already a Linux instance from nodes fixture.
    
    Args:
        nodes: nodes fixture
        
    Returns:
        List of Linux nodes (already wrapped from nodes fixture)
    """
    yield nodes


@pytest.fixture
def hook_runner(request: pytest.FixtureRequest):
    """Fixture for running legacy test hooks.
    
    Converts legacy hook mechanism to pytest fixture.
    Hooks are executed in setup phase before test runs.
    
    Args:
        request: pytest fixture request
        
    Returns:
        Hook module object or None
    """
    hook_marker = request.node.get_closest_marker("hook")
    if hook_marker and hook_marker.args:
        hook_module_path = hook_marker.args[0]
        try:
            import importlib
            parts = hook_module_path.split(".")
            module_name = parts[-1]
            if len(parts) > 1:
                module_path = ".".join(parts[:-1])
                hook_module = importlib.import_module(f"libs.{module_path}.{module_name}")
            else:
                hook_module = importlib.import_module(f"libs.hooks.{hook_module_path}")
            yield hook_module
        except ImportError as e:
            _module_logger.warning(f"Hook module not found: {hook_module_path}, error: {e}")
            yield None
    else:
        yield None


@pytest.fixture
def resource_loader(request: pytest.FixtureRequest, test_case: TestCase) -> Generator[
    dict[str, Any] | None | Any, Any, None]:
    """Fixture for loading test resources from configuration.
    
    Legacy pattern: self.resource = Resource.load(test_bed.xml)
    
    Args:
        request: pytest fixture request
        test_case: TestCase instance
        
    Returns:
        Resource dictionary loaded from config file
    """
    from libs.utils.env_config import load_resource_config
    
    resource_config_path = request.config.getoption("--resource-config", None)
    if resource_config_path:
        resource = load_resource_config(resource_config_path)
        test_case.resource = resource
        yield resource
    else:
        test_case.resource = {"hosts": {}, "devices": {}, "global": {}}
        yield test_case.resource


def create_multibase_fixture(basecase_names: List[str]):
    """Factory function for creating multi-BaseCase combination fixture.
    
    Legacy pattern: class TestCase(Base1, Base2, Base3)
    Converted to: fixture injecting methods from multiple BaseCase classes
    
    Args:
        basecase_names: List of BaseCase class names to combine
                       e.g., ["AuditLog_BaseCase", "BrainLog_BaseCase"]
        
    Returns:
        pytest fixture function that injects combined BaseCase methods
        
    Example:
        # In test file:
        auditlog_brainlog_fixture = create_multibase_fixture([
            "blade.auditlog_basecase.AuditLog_BaseCase",
            "blade.brainlog_basecase.BrainLog_BaseCase"
        ])
        
        def test_xxx(auditlog_brainlog_fixture):
            # TestCase now has methods from both BaseCases
            pass
    """
    @pytest.fixture
    def multibase_fixture(test_case_with_deps):
        test_case, nodes, resource, node_dict, custom_params = test_case_with_deps
        
        for basecase_path in basecase_names:
            try:
                import importlib
                if "." in basecase_path:
                    module_path, class_name = basecase_path.rsplit(".", 1)
                    module = importlib.import_module(f"libs.core.basecase.{module_path}")
                    basecase_class = getattr(module, class_name)
                else:
                    module = importlib.import_module(f"libs.core.basecase.{basecase_path.lower()}")
                    basecase_class = getattr(module, basecase_path)
                
                basecase_instance = basecase_class(nodes, resource, custom_params)
                
                for attr_name in dir(basecase_instance):
                    if not attr_name.startswith("_") and not hasattr(test_case, attr_name):
                        attr_value = getattr(basecase_instance, attr_name)
                        if callable(attr_value) and not isinstance(attr_value, type):
                            setattr(test_case, attr_name, attr_value)
                        elif not callable(attr_value):
                            setattr(test_case, attr_name, attr_value)
                            
            except (ImportError, AttributeError) as e:
                _module_logger.warning(f"Failed to load BaseCase {basecase_path}: {e}")
        
        yield test_case
    
    return multibase_fixture

