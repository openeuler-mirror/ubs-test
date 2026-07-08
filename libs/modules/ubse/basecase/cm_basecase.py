"""CMBaseCase - Root base class for ubse test cases.

Provides common initialization logic for all ubse tests.

Legacy inheritance: CMBaseCase(Case) 
Pytest adaptation: CMBaseCase(TestCase) - 使用fixture注入依赖
"""

import logging
import random
import pytest
from typing import Any, Dict, List, Optional

from libs.core.base import TestCase
from libs.utils.env_config import get_env_params, check_autotest_mkdir
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_cm_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入CMBaseCase外部依赖参数.
    
    只对CMBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.modules.ubse.basecase.cm_basecase import CMBaseCase
    if not isinstance(instance, CMBaseCase):
        return
    
    instance.nodes = nodes
    instance.resource = resource
    instance.customParam = custom_params
    
    instance._init_default_paths()
    
    if nodes:
        instance._load_env_params(nodes[0])
    
    instance.node = random.choice(nodes) if nodes else None
    
    instance.logger = Log.getLogger(instance.__class__.__name__)

    logger.info(f"CMBaseCase initialized: {len(nodes)} nodes, class={instance.__class__.__name__}")


class CMBaseCase(TestCase):
    """Root base class for ubse test cases.
    
    提供所有ubse测试的基础设施：
    - Node list管理 (self.nodes, self.node)
    - 环境参数加载
    - 路径配置
    - CLI API wrapper
    
    Legacy模式（已废弃）:
        class MyTest(CMBaseCase):
            def __init__(self, parameters):
                super().__init__(parameters)
    
    Pytest模式（当前）:
        class MyTest(CMBaseCase):
            # 无__init__方法！
            # 外部依赖参数通过父类fixture自动注入
            
            def setup_method(self):
                # 业务参数在此初始化
                pass
            
            def test_xxx(self):
                # 使用self.nodes, self.resource等
                pass
    
    外部依赖参数（fixture注入）:
        - nodes: List[Any] - 测试节点列表
        - resource: Dict[str, Any] - 资源配置字典
        - custom_params: Dict[str, Any] - 自定义参数字典
    
    公共方法（父类提供）:
        - logStep(), logInfo(), assertTrue(), assertEqual()等
        - export_lib_path(), preTestCase(), postTestCase()等
    """
    
    # 类属性（硬编码路径默认值）
    DEFAULT_RPM_PATH = "/usr/local/softbus/ctrlbus"
    DEFAULT_LOG_PATH = "/var/log/scbus"
    DEFAULT_CLI_RPM_PATH = "/usr/local/softbus/ctrlbus-cli"
    DEFAULT_RPM_CONF = "/usr/local/softbus/ctrlbus/conf"
    DEFAULT_UBSE_RPM_PATH = "/opt/install/package"
    DEFAULT_RUN_PATH = "/run/ubm"
    DEFAULT_CERT_LIB_PATH = "/usr/local/softbus/ctrlbus/lib"
    DEFAULT_SERVICE_CONF_PATH = "/etc/ubse"
    DEFAULT_TEST_FILE_PATH = "/home/autotest"
    DEFAULT_PACKAGE_PATH = "/home/autotest/packages"
    DEFAULT_DCAT_PATH = "/usr/local/dcat"
    
    def _init_default_paths(self) -> None:
        """初始化路径属性的默认值（在nodes可能为空时使用）."""
        self.rpm_path = self.DEFAULT_RPM_PATH
        self.RACK_PATH = self.DEFAULT_RPM_PATH
        self.LOG_PATH = self.DEFAULT_LOG_PATH
        self.CLI_RPM_PATH = self.DEFAULT_CLI_RPM_PATH
        self.RPM_CONF = self.DEFAULT_RPM_CONF
        self.DATA_SYNC_PATH = ""
        self.UBSE_RPM_PATH = self.DEFAULT_UBSE_RPM_PATH
        self.run_path = self.DEFAULT_RUN_PATH
        self.cert_lib_path = self.DEFAULT_CERT_LIB_PATH
        self.service_conf_path = self.DEFAULT_SERVICE_CONF_PATH
        self.test_file_path = self.DEFAULT_TEST_FILE_PATH
        self.package_path = self.DEFAULT_PACKAGE_PATH
        self.dcat_path = self.DEFAULT_DCAT_PATH
    
    def _load_env_params(self, node: Any) -> None:
        """从节点加载环境参数.
        
        Legacy: CM_AW.get_env_params(node, "param_name")
        
        Args:
            node: Node对象
        """
        if not hasattr(node, "run"):
            logger.warning("Node does not have run method")
            return
        
        # 检查并创建autotest目录
        check_autotest_mkdir(node)
        
        # 加载路径参数（从环境或使用默认值）
        self.rpm_path = get_env_params(node, "rack_path") or self.DEFAULT_RPM_PATH
        self.RACK_PATH = self.rpm_path
        self.LOG_PATH = get_env_params(node, "log_path") or self.DEFAULT_LOG_PATH
        self.CLI_RPM_PATH = get_env_params(node, "cli_path") or self.DEFAULT_CLI_RPM_PATH
        self.RPM_CONF = get_env_params(node, "rpm_conf") or self.DEFAULT_RPM_CONF
        self.DATA_SYNC_PATH = get_env_params(node, "data_sync_path") or ""
        self.UBSE_RPM_PATH = get_env_params(node, "ubse_path") or self.DEFAULT_UBSE_RPM_PATH
        self.run_path = get_env_params(node, "run_path") or self.DEFAULT_RUN_PATH
        self.cert_lib_path = get_env_params(node, "cert_lib_path") or self.DEFAULT_CERT_LIB_PATH
        self.service_conf_path = get_env_params(node, "service_conf_path") or self.DEFAULT_SERVICE_CONF_PATH
        self.test_file_path = get_env_params(node, "test_file_path") or self.DEFAULT_TEST_FILE_PATH
        self.package_path = get_env_params(node, "package_path") or self.DEFAULT_PACKAGE_PATH
        self.dcat_path = get_env_params(node, "dcat_path") or self.DEFAULT_DCAT_PATH
    
    def _init_paths(self) -> None:
        """初始化公共路径属性."""
        self.RACK_PATH = self.test_file_path
        self._create_directory(self.test_file_path)
    
    def _create_directory(self, *paths: str) -> None:
        """在所有节点创建目录.
        
        Args:
            paths: 目录路径列表
        """
        for node in self.nodes:
            for path in paths:
                node.run({"command": [f"mkdir -p {path}"]})
        logger.info(f"Created directories: {paths}")
    
    def export_lib_path(self) -> None:
        """在所有节点导出LD_LIBRARY_PATH."""
        for node in self.nodes:
            node.run({"command": [f"export LD_LIBRARY_PATH={self.rpm_path}/lib:$LD_LIBRARY_PATH"]})
        logger.info("Exported library paths")
    
    # Legacy兼容方法（保留）
    def preTestCase(self) -> None:
        """Pre-test setup hook (legacy兼容).
        
        Legacy method: preTestCase()
        Converted to: setup_method() in pytest
        
        子类可覆盖此方法实现自定义setup逻辑。
        """
        logger.info("CMBaseCase preTestCase hook")
    
    def procedure(self) -> None:
        """Main test logic (legacy兼容).
        
        Legacy method: procedure()
        Converted to: test_xxx() in pytest
        
        子类必须覆盖此方法。
        """
        logger.warning("CMBaseCase procedure not implemented")
    
    def postTestCase(self) -> None:
        """Post-test cleanup hook (legacy兼容).
        
        Legacy method: postTestCase()
        Converted to: teardown_method() in pytest
        
        子类可覆盖此方法实现自定义cleanup逻辑。
        """
        logger.info("CMBaseCase postTestCase hook")
        self.performCleanUp()
    
    def get_info_from_conf(self, node: Any, name: str) -> Optional[str]:
        """从配置文件获取信息.
        
        Args:
            node: Node对象
            name: 配置项名称
            
        Returns:
            配置值或None
        """
        # 默认实现（子类可覆盖）
        logger.warning(f"get_info_from_conf not implemented in CMBaseCase, name={name}")
        return None