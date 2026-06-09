import pytest

from libs.core.basecase.ubturbo import MempoolingBaseCase
from libs.ubturbo.api import numa, rack_manager, mempooling
from libs.ubturbo.hooks import hook_mem_pooling

MEM_POOLING_OBMM_SIZE_PER_NUMA = 8


@pytest.fixture(scope="package", autouse=True)
def mempooling_common_hook(resource_config: dict):
    from libs.host import Linux

    hosts = resource_config.get("hosts", {})
    nodes_list = []

    for host_id, host_info in hosts.items():
        if isinstance(host_info, dict):
            linux_node = Linux(host_info)
            nodes_list.append(linux_node)
        elif hasattr(host_info, "run"):
            nodes_list.append(host_info)
    basecase_executor = MempoolingBaseCase()
    basecase_executor.nodes = nodes_list
    basecase_executor.logStep("mempooling测试执行开始")
    basecase_executor.logStep("Hook_Mem_Pooling、确保OBMM内存池为8G/numa")
    numa_counts = numa.get_numa_count_with_cpu(nodes_list[0])
    total_obmm_mempool_size = numa_counts * MEM_POOLING_OBMM_SIZE_PER_NUMA
    before_mempool_mempool_size = numa.get_obmm_mempool_total_ub(nodes_list[0])
    if before_mempool_mempool_size != total_obmm_mempool_size:
        basecase_executor.logger.info("环境当前OBMM内存池大小不符合预期，需要重新设置")
        for node in reversed(nodes_list):
            rack_manager.shut_down_rack_manager(node, force=True)
        hook_mem_pooling.refill_obmm_mempool(node_list=nodes_list, size=total_obmm_mempool_size)
    rack_manager.restart_cluster_scbus(node_list=nodes_list)
    rack_manager.wait_master_consistent(node_list=nodes_list)
    basecase_executor.logStep("Hook_Mem_Pooling、创建mempooling测试目录并上传虚机创建镜像和xml")
    for node in nodes_list:
        hook_mem_pooling.mk_mp_work_dir(node)
        hook_mem_pooling.download_qcow(node)
        mempooling.upload_vm_files(node)
        mempooling.upload_sdk_scripts(node)

    yield

    basecase_executor.logStep("mempooling测试执行结束")
    basecase_executor.logStep("Hook_Mem_Pooling、恢复OBMM内存池")
    for node in nodes_list:
        rack_manager.shut_down_rack_manager(node, force=True)
    hook_mem_pooling.refill_obmm_mempool(node_list=nodes_list, size=1)
    rack_manager.restart_cluster_scbus(node_list=nodes_list)
    rack_manager.wait_master_consistent(node_list=nodes_list)
