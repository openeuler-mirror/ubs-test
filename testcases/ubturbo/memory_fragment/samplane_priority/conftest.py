import pytest

from libs.core.basecase.ubturbo import MempoolingBaseCase


@pytest.fixture(scope="package", autouse=True)
def mempooling_sameplane_priority_hook(resource_config: dict):
    from libs.host import Linux

    hosts = resource_config.get("hosts", {})
    node_lists = []

    for host_id, host_info in hosts.items():
        if isinstance(host_info, dict):
            linux_node = Linux(host_info)
            node_lists.append(linux_node)
        elif hasattr(host_info, "run"):
            node_lists.append(host_info)
    basecase_executor = MempoolingBaseCase()
    basecase_executor.nodes = node_lists
    basecase_executor.logStep("Hook_Mem_Pooling、开启优先同平面配置并重启ubse")
    basecase_executor.switch_must_same_plane(target_set=False)

    yield

    basecase_executor.logStep("Hook_Mem_Pooling、关闭优先同平面配置并重启ubse")
    basecase_executor.switch_must_same_plane(target_set=True)
