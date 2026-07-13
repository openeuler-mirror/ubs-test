import pytest

from libs.modules.ubsvirt.basecase import OpenStackBaseCase


openstack_nova_conf = "/etc/nova/nova.conf"

@pytest.fixture(scope="package", autouse=True)
def set_overcommitment(resource_config: dict):
    from libs.host import Linux

    hosts = resource_config.get("hosts", {})
    nodes_list = []

    for host_id, host_info in hosts.items():
        if isinstance(host_info, dict):
            linux_node = Linux(host_info)
            nodes_list.append(linux_node)
        elif hasattr(host_info, "run"):
            nodes_list.append(host_info)

    basecase = OpenStackBaseCase()
    
    # 初始化特定属性
    basecase.nodes = nodes_list if nodes_list else []
    basecase.resource = resource_config
    basecase.is_Simulation = resource_config.get('global', {}).get('is_simulation', False)
    basecase.controller = None
    basecase.agent_list = []
    basecase.master = None
    basecase.agent = None
    basecase.node_list = basecase._load_nodes() if nodes_list else []
    basecase.ubse_node_list = [basecase.master] + basecase.agent_list
    
    basecase.logStep("开始切换为超分环境")
    basecase.change_overcommitment(openstack_nova_conf, 1.25)
    basecase.logStep("成功切换为超分环境")
    basecase.logStep("ubsvirt超分用例开始执行")

    yield

    basecase.logStep("ubsvirt超分用例执行结束")