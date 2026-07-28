import pytest

from libs.ubturbo.api import system, rack_manager, os_turbo
from libs.ubturbo.common import basic

UBSE_PLUGIN_ADMISSION_PATH = "/etc/ubse/ubse_plugin_admission.conf"
UBTURBO_PLUGIN_ADMISSION_PATH = "/opt/ubturbo/conf/ubturbo_plugin_admission.conf"
VIRT_AGENT_UBSE_PLUGIN = "virt_agent"
RMRS_UBSE_PLUGIN = "mempooling"
RMRS_UBTURBO_PLUGIN = "rmrs"


@pytest.fixture(scope="package", autouse=True)
def container_common_hook(resource_config: dict):
    from libs.host import Linux

    hosts = resource_config.get("hosts", {})
    nodes_list = []

    for host_id, host_info in hosts.items():
        if isinstance(host_info, dict):
            linux_node = Linux(host_info)
            nodes_list.append(linux_node)
        elif hasattr(host_info, "run"):
            nodes_list.append(host_info)
    basic.logger.info("rmrs-容器超分测试执行开始")
    basic.logger.info("Hook_Container_Overcommit、打开ubse对应配置")
    for node in nodes_list:
        system.update_conf_file(node, UBSE_PLUGIN_ADMISSION_PATH, VIRT_AGENT_UBSE_PLUGIN, mode="uncomment")
        system.update_conf_file(node, UBSE_PLUGIN_ADMISSION_PATH, RMRS_UBSE_PLUGIN, mode="uncomment")
        system.update_conf_file(node, UBTURBO_PLUGIN_ADMISSION_PATH, RMRS_UBTURBO_PLUGIN, mode="uncomment")
        os_turbo.reset_osturbo(node)
    rack_manager.restart_cluster_scbus(nodes_list, sync=False)


    yield

    basic.logger.info("rmrs-容器超分测试执行结束")

