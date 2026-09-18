import time

import pytest

from libs.core.basecase.ubturbo import MempoolingBaseCase
from libs.ubturbo.api import numa, rack_manager, mempooling, system, os_turbo
from libs.ubturbo.common import env, basic
from libs.ubturbo.hooks import hook_mem_pooling

MEM_POOLING_OBMM_SIZE_PER_NUMA = 8
UBSE_PLUGIN_ADMISSION_PATH = "/etc/ubse/ubse_plugin_admission.conf"
UBTURBO_PLUGIN_ADMISSION_PATH = "/opt/ubturbo/conf/ubturbo_plugin_admission.conf"
VIRT_AGENT_UBSE_PLUGIN = "virt_agent"
RMRS_UBSE_PLUGIN = "mempooling"
RMRS_UBTURBO_PLUGIN = "rmrs"


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
    need_reset_mempool_size = False
    if before_mempool_mempool_size != total_obmm_mempool_size:
        need_reset_mempool_size = True
        basecase_executor.logger.info("环境当前OBMM内存池大小不符合预期，需要重新设置")
        for node in reversed(nodes_list):
            rack_manager.shut_down_rack_manager(node, force=True)
    if need_reset_mempool_size:
        hook_mem_pooling.refill_obmm_mempool(node_list=nodes_list, size=total_obmm_mempool_size)

    basecase_executor.logStep("Hook_Mem_Pooling、打开ubse对应配置")
    for node in nodes_list:
        system.update_conf_file(node, UBSE_PLUGIN_ADMISSION_PATH, VIRT_AGENT_UBSE_PLUGIN, mode="uncomment")
        system.update_conf_file(node, UBSE_PLUGIN_ADMISSION_PATH, RMRS_UBSE_PLUGIN, mode="uncomment")
        system.update_conf_file(node, UBTURBO_PLUGIN_ADMISSION_PATH, RMRS_UBTURBO_PLUGIN, mode="uncomment")
        os_turbo.reset_osturbo(node)
    rack_manager.restart_cluster_scbus(nodes_list, sync=False)
    rack_manager.wait_master_consistent(node_list=nodes_list)

    basecase_executor.logStep("Hook_Mem_Pooling、创建mempooling测试目录并上传虚机创建镜像和xml")
    for node in nodes_list:
        hook_mem_pooling.mk_mp_work_dir(node)
        hook_mem_pooling.download_qcow(node)
        mempooling.upload_vm_files(node)
        mempooling.upload_sdk_scripts(node)

    basecase_executor.logStep("Hook_Mem_Pooling、注入1.0超分比")
    mempooling.check_memborrow_mode(nodes_list)

    yield

    basecase_executor.logStep("mempooling测试执行结束")
    basecase_executor.logStep("Hook_Mem_Pooling、恢复OBMM内存池")
    time.sleep(3 * 60) # 部分用例后置也会有重启ubse操作， 等待3分钟再进行重启
    for node in nodes_list:
        rack_manager.shut_down_rack_manager(node)
    hook_mem_pooling.refill_obmm_mempool(node_list=nodes_list, size=1)
    rack_manager.restart_cluster_scbus(node_list=nodes_list)
    rack_manager.wait_master_consistent(node_list=nodes_list)
