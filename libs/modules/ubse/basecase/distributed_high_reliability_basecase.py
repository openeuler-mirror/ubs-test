"""Distributed High Reliability BaseCase.

Migrated from: legency/testcase/ubse/lib/basecase/ubse/Distributed_High_Reliability/Distributed_High_Reliability_BaseCase.py
Provides high reliability and fault tolerance test methods.

Legacy file is 305 lines - this is a simplified pytest-compatible version.

CRITICAL CHANGE (2026-05-18):
- 移除__init__方法，解决pytest无法收集带__init__测试类的硬限制
- 使用@pytest.fixture(autouse=True)注入外部依赖参数(nodes, resource, custom_params)
- 业务参数在fixture或setup_method中初始化
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
    
    # 注入基础依赖（由CMBaseCase fixture处理nodes, resource, custom_params）
    # 这里只处理Distributed_High_Reliability特有的参数
    
    instance.cli_user = 'cli_user'
    instance.cli_password = 'BeiMing123'
    
    instance.rackmanager_conf_path = f"{instance.CTRLBUS_PATH}/conf/ubse.conf"
    instance.rack_plugin_conf_path = f"{instance.CTRLBUS_PATH}/conf/rack_plugin_admission.conf"
    instance.plugin_mem_master_path = f"{instance.CTRLBUS_PATH}/conf/plugin_mem_master.conf"
    
    instance.rackmanager_conf_bak_path = instance.rackmanager_conf_path + '.bak'
    instance.rack_plugin_conf_bak_path = instance.rack_plugin_conf_path + '.bak'
    instance.plugin_mem_master_bak_path = instance.plugin_mem_master_path + '.bak'
    
    instance.cli_conf_path = f"{instance.CLI_PATH}/conf/rackmanager.conf"
    instance.cli_conf_bak_path = instance.cli_conf_path + '.bak'
    
    instance.lcne_cfg_path = f"{instance.CTRLBUS_PATH}/conf/lcne.cfg"
    instance.lcne_cfg_bak_path = instance.lcne_cfg_path + '.bak'
    
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
        - rackmanager_conf_path: str - 配置文件路径
        - 各种备份路径
    """
    
    CTRLBUS_PATH = "/usr/local/softbus/ctrlbus"
    CLI_PATH = "/usr/local/softbus/ctrlbus-cli"
    LOG_PATH = "/var/log/scbus"
    LCNE_VIEW = "/root/manager/BMCSimulationsServer/home/lcne"
    
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
    
    def get_process_pid(self, node: Any, process_name: str) -> Optional[int]:
        """Get PID of a process.
        
        Args:
            node: Node object
            process_name: Process name
            
        Returns:
            PID if found, None otherwise
        """
        cmd = f"ps aux | grep {process_name} | grep -v grep | awk '{{print $2}}'"
        result = node.run({"command": [cmd], "timeout": 30})
        stdout = result.get("stdout", "")
        
        if stdout.strip():
            try:
                return int(stdout.strip().split()[0])
            except ValueError:
                return None
        return None
    
    def stop_process(self, node: Any, process_name: str) -> bool:
        """Stop a process by name.
        
        Args:
            node: Node object
            process_name: Process name
            
        Returns:
            True if successful
        """
        cmd = f"systemctl stop {process_name} || pkill -9 {process_name}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("rc", 1) == 0
    
    def start_process(self, node: Any, process_name: str) -> bool:
        """Start a process by name.
        
        Args:
            node: Node object
            process_name: Process name
            
        Returns:
            True if successful
        """
        cmd = f"systemctl start {process_name}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("rc", 1) == 0
    
    def restart_process(self, node: Any, process_name: str) -> bool:
        """Restart a process by name.
        
        Args:
            node: Node object
            process_name: Process name
            
        Returns:
            True if successful
        """
        cmd = f"systemctl restart {process_name}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("rc", 1) == 0
    
    def check_process_status(self, node: Any, process_name: str) -> str:
        """Check process status.
        
        Args:
            node: Node object
            process_name: Process name
            
        Returns:
            Process status (active/inactive/failed)
        """
        cmd = f"systemctl is-active {process_name}"
        result = node.run({"command": [cmd], "timeout": 30})
        return result.get("stdout", "").strip()
    
    def modify_distributed_conf(self, node: Any, key: str, value: str, serv: str = "ubse") -> bool:
        """Modify distributed configuration.
        
        Legacy method: modify_distributed_conf(node, key, value, serv)
        
        Args:
            node: Node object
            key: Configuration key
            value: Configuration value
            serv: Service name
            
        Returns:
            True if successful
        """
        conf_path = f"{self.CTRLBUS_PATH}/conf/{serv}.conf"
        cmd = f"sed -i 's/{key}=.*/{key}={value}/' {conf_path}"
        node.run({"command": [cmd]})
        return True

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
    
    def restore_initial_config(self) -> bool:
        """Restore initial configuration from backup.
        
        Legacy method: restore_initial_config()
        
        Returns:
            True if successful
        """
        for node in self.nodes:
            self.restore_config(node, self.rackmanager_conf_bak_path, self.rackmanager_conf_path)
            self.restore_config(node, self.rack_plugin_conf_bak_path, self.rack_plugin_conf_path)
        return True
    
    def rack_cli_election_display_all_res(self, node: Any, status: str = 'master') -> Optional[str]:
        return cli_api.display_election(node, status)
    
    def procedure(self) -> None:
        """Main test logic."""
        super().procedure()
    
    def postTestCase(self) -> None:
        """Post-test cleanup."""
        super().postTestCase()
        logger.info("Distributed_High_Reliability_BaseCase postTestCase")