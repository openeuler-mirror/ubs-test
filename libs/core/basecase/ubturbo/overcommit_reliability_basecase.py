"""OvercommitReliabilityBaseCase - Base class for overcommit reliability test cases.

Migrated from legacy lib/basecase/OvercommitReliabilityBaseCase.py
Inherits from VMOvercommitBaseCase (already migrated).

CRITICAL: This class NO LONGER has __init__ method.
pytest cannot collect test classes with __init__ (even with default args).

Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
"""

import logging
from typing import Any, Dict, List

import pytest

from libs.core.basecase.ubturbo.vm_overcommit_basecase import VMOvercommitBaseCase
from libs.ubturbo.common import basic, env
from libs.ubturbo.api import ub_operation, os_reliability

try:
    from libs.ubturbo.api import RA_mock
except ImportError:
    RA_mock = None

logger = logging.getLogger(__name__)

scbus_log_path = '/var/log/ubse'
sys_sentry_log_path = '/var/log/sysSentry'


@pytest.fixture(autouse=True)
def inject_overcommit_reliability_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入OvercommitReliabilityBaseCase依赖参数.
    
    只对OvercommitReliabilityBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.ubturbo.overcommit_reliability_basecase import OvercommitReliabilityBaseCase
    if not isinstance(instance, OvercommitReliabilityBaseCase):
        return
    
    instance.fault_mock = False
    instance.scbus_log_path = scbus_log_path
    instance.sys_sentry_log_path = sys_sentry_log_path
    
    logger.info(f"OvercommitReliabilityBaseCase initialized: class={instance.__class__.__name__}")


class OvercommitReliabilityBaseCase(VMOvercommitBaseCase):
    """Base class for overcommit reliability test cases.
    
    继承 VMOvercommitBaseCase，提供故障注入和可靠性测试功能。
    
    环境支持：
    - UB仿真环境 (env.UB_simulation)
    
    故障注入类型：
    - BMC下电
    - 重启
    - Panic
    
    使用示例：
        class MyReliabilityTest(OvercommitReliabilityBaseCase):
            def test_bmc_power_off(self):
                self.ub_bmc_power_off("Node1")
                self.wait_ub_env_reboot("Node1")
    """
    
    def setup_method(self):
        """Pre-test setup hook (legacy: preTestCase)."""
        super().setup_method()
        if self.env_type == env.UB_simulation:
            self.logStep("P1、仿真4节点")
            self.logStep("P2、sysSentry已部署")
            self.enable_in_band_notify()
            self.logStep("P3、检测sysSentry建链情况")
            self.check_in_band_notify()
            self.logStep("P4、scbus,nova为超分场景配置且超分比例为1.25")
            self.confirm_scene_config()
    
    def teardown_method(self):
        """Post-test cleanup hook (legacy: postTestCase)."""
        fault_node_list = []
        for node_slot in self.fault_nodes:
            fault_node_list.append(self.node_dict[node_slot].ssh_node)
        
        if self.env_type == env.UB_simulation:
            if self.isPassed():
                self.clear_logs('/var/log/ubse/*.tar.gz')
            else:
                case_name = self.__class__.__name__
                self.dump_logs(case_name, '/var/log/ubse')
            if self.env_type == env.UB_simulation:
                ub_operation.recover_ub_status(host_node=self.simulation_host, ub_node_list=self.agent_list, fault_nodes=fault_node_list)
        super().teardown_method()
    
    def ub_bmc_power_off(self, node_name):
        """BMC下电."""
        if self.env_type == env.UB_simulation:
            os_reliability.ub_graceful_shutdown(self.simulation_host, qmp_port=self.qmp_port[node_name])
        else:
            raise NotImplementedError("hardware bmc power off not impl!!!")
    
    def ub_reboot(self, node_name):
        """重启节点."""
        node_name = str(node_name)
        if not self.fault_mock:
            basic.run(self.node_dict[node_name].ssh_node, 'reboot -f', returnCode=False, timeout=10)
        else:
            self.logInfo(f"测试：fault_mock={self.fault_mock}")
            if RA_mock:
                working_nodes = [node.ssh_node for node in self.node_dict.values()]
                RA_mock.mock_reboot(working_nodes, self.node_dict[node_name].ssh_node)
        self.fault_nodes.append(node_name)
    
    def ub_panic(self, node_name):
        """注入Panic."""
        node_name = str(node_name)
        if not self.fault_mock:
            basic.run(self.node_dict[node_name].ssh_node, 'echo c > /proc/sysrq-trigger &', returnCode=False, timeout=10)
        else:
            self.logInfo(f"测试：fault_mock={self.fault_mock}")
            if RA_mock:
                working_nodes = [node.ssh_node for node in self.node_dict.values()]
                RA_mock.mock_panic(working_nodes, self.node_dict[node_name].ssh_node)
        self.fault_nodes.append(node_name)
    
    def confirm_power_off(self, node_name):
        """确认节点下电."""
        node_ssh = self.node_dict[node_name].ssh_node
        node_ssh.waitForShutdown()
    
    def wait_ub_env_reboot(self, node_name):
        """等待UB环境重启."""
        node_ssh = self.node_dict[node_name].ssh_node
        ub_operation.wait_ub_recover(node_ssh, timeout=30 * 60)
    
    def enable_in_band_notify(self):
        """配置sysSentry自定义超时时间."""
        for _, node in self.node_dict.items():
            basic.run(node.ssh_node, f'modprobe sentry_reporter reboot_timeout_ms=300000')
            basic.run(node.ssh_node, f'modprobe sentry_remote_reporter')
            basic.run(node.ssh_node,
                      f'sentryctl set sentry_remote_reporter --panic_timeout_ms=300000 --kernel_reboot_timeout_ms=300000')
    
    def check_in_band_notify(self):
        """检查集群内带内故障事件上报建链."""
        other_node_num = len(self.node_dict) - 1
        for _, node in self.node_dict.items():
            res = basic.run(node.ssh_node, "urma_admin show --all")
            basic.run(node.ssh_node, f'dmesg -T |grep "import: {other_node_num}/{other_node_num} success for device udma"')
            if '22   ' in res.stdout:
                continue
            return False
        return True
    
    def check_log_for_keyword(self, node_name, keyword, log_dir='/var/log/ubse'):
        """根据关键词检索日志."""
        res = basic.run(self.node_dict[node_name].ssh_node, f'zgrep -a "{keyword}" {log_dir}/*')
        if keyword in res.stdout:
            return
        raise Exception("未收到事件上报/答复消息")
    
    def check_fault_nodes_log(self, fault_nodes, keyword, log_dir='/var/log/ubse'):
        """检索故障节点日志."""
        for node_name in fault_nodes:
            self.check_log_for_keyword(node_name, keyword, log_dir)