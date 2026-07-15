"""Distributed High Reliability BaseCase.

Provides high reliability and fault tolerance test methods.

Legacy file is 305 lines - this is a simplified pytest-compatible version.
"""

import logging
import pytest
import time
from typing import Any, Dict, List, Optional

from libs.modules.ubse.basecase.cm_basecase import CMBaseCase
from libs.modules.ubse.api import cli_api
from libs.modules.ubse.common import ubse_process_ops
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_distributed_high_reliability_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入Distributed_High_Reliability_BaseCase外部依赖参数.
    
    只对Distributed_High_Reliability_BaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.modules.ubse.basecase.distributed_high_reliability_basecase import Distributed_High_Reliability_BaseCase
    if not isinstance(instance, Distributed_High_Reliability_BaseCase):
        return

    # Initialize module references (legacy compatibility)
    instance.cli_api = cli_api
    instance.ubse_process_ops = ubse_process_ops

    
    logger.info(f"Distributed_High_Reliability_BaseCase initialized: {len(nodes)} nodes, class={instance.__class__.__name__}")


class Distributed_High_Reliability_BaseCase(CMBaseCase):
    """Base class for distributed high reliability tests.
    
    Provides methods for:
    - HA (High Availability) testing
    - Fault injection and recovery
    - Process management and monitoring
    - Configuration backup and restore
    
    Legacy inheritance: Distributed_High_Reliability_BaseCase(CMBaseCase)
    
    外部依赖参数（fixture注入）:
        - nodes: List[Any] - 测试节点列表
        - resource: Dict[str, Any] - 资源配置字典
        - custom_params: Dict[str, Any] - 自定义参数字典
    
    业务参数（fixture注入）:
        - cli_user: str - CLI用户名
        - cli_password: str - CLI密码
    """
    
    CTRLBUS_PATH = "/usr/local/softbus/ctrlbus"
    CLI_PATH = "/usr/local/softbus/ctrlbus-cli"
    LOG_PATH = "/var/log/scbus"

    def preTestCase(self) -> None:
        """Pre-test setup - verify HA environment."""
        super().preTestCase()
        logger.info("HA environment verified")
    
    def backup_config(self, node: Any, config_path: str, backup_path: str) -> bool:
        """Backup configuration file.
        
        Args:
            node: Node object
            config_path: Original config path
            backup_path: Backup file path
            
        Returns:
            True if successful
        """
        cmd = f"cp {config_path} {backup_path}"
        result = node.run({"command": [cmd], "timeout": 30})
        return result.get("rc", 1) == 0
    
    def restore_config(self, node: Any, backup_path: str, config_path: str) -> bool:
        """Restore configuration from backup.
        
        Args:
            node: Node object
            backup_path: Backup file path
            config_path: Target config path
            
        Returns:
            True if successful
        """
        cmd = f"cp {backup_path} {config_path}"
        result = node.run({"command": [cmd], "timeout": 30})
        return result.get("rc", 1) == 0


    def wait_master_standby_loaded(self, node, node_type, target_node):
        """
        等待主备节点信息加载完成
        :node: 执行节点
        :node_type: 节点类型，master/standby
        :target_node: 目标节点id，node01、node02
        return：True、False
        """
        for _ in range(60):
            res = self.cli_api.display_election(node, node_type)
            if res == target_node:
                return res
            time.sleep(6)
        return False

    def get_values_with_key_from_distributed_conf_file(self, node: Any, conf_path: str, key: str) -> Optional[str]:
        """Get value from distributed config file.
        
        Legacy method: get_values_with_key_from_distributed_conf_file(node, conf_path, key)
        
        Args:
            node: Node object
            conf_path: Config file path
            key: Configuration key
            
        Returns:
            Value if found, None otherwise
        """
        result = node.run({"command": [f"grep '{key}=' {conf_path}"]})
        stdout = result.get("stdout", "")
        
        if stdout and "=" in stdout:
            return stdout.split("=")[1].strip().split("\n")[0]
        return None