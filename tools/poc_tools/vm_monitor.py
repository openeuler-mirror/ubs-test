from poc_tools.common.config import CONF
from poc_tools.common.log import LOG
from poc_tools.common.constant import VmStatusEnum, MemConvertEnum
from poc_tools.common.utils import retry, send_pipe_scripts
from ubse.ubs_virt_agent_fragmentation import ubs_mem_fragmentation_node_info_list

MONITOR_INTERVAL = 10
MAX_MONITOR_ATTEMPTS = 720


async def get_vm_status(vm_name: str, check=True):
    try:
        return await send_pipe_scripts([["virsh", "list", "--all"], ["grep", vm_name], ["awk", "{print $3}"]],
                                       check=check)
    except Exception as e:
        LOG.error(f"Get vm: {vm_name} status failed, error: {e}")
        raise


async def wait_status_to_running(vm_name: str):
    status = await get_vm_status(vm_name)

    if status == VmStatusEnum.RUNNING:
        LOG.info(f"VM: {vm_name} status is running.")
        return
    raise Exception(f"The status of vm: {vm_name} is {status}.")


async def wait_vm_to_delete(vm_name: str):
    status = await get_vm_status(vm_name, check=False)

    if not status:
        LOG.info(f"Vm: {vm_name} has been deleted.")
        return
    raise Exception(f"The status of vm: {vm_name} is {status}.")


async def wait_vm_release_mem():
    node_info_list = ubs_mem_fragmentation_node_info_list()
    for node_info in node_info_list:
        for numa_info in node_info.numa_infos:
            is_local = numa_info.is_local
            huge_page_free = numa_info.numa_huge_page_info[MemConvertEnum.HUGE_PAGE_TO_KB].huge_page_free
            huge_page_total = numa_info.numa_huge_page_info[MemConvertEnum.HUGE_PAGE_TO_KB].huge_page_total
            if not is_local and huge_page_free != huge_page_total:
                raise Exception("Waiting vm mem release")
    LOG.info("Release vm mem successfully.")


async def monitor_create_vm(vm_name: str):
    LOG.info(f"Start monitoring vm: {vm_name}")
    await retry(wait_status_to_running, vm_name,
                max_retry=CONF.get("task", {}).get("max_monitor_attempt", MAX_MONITOR_ATTEMPTS),
                retry_interval=CONF.get("task", {}).get("monitor_interval", MONITOR_INTERVAL))


async def monitor_delete_vm(vm_name: str):
    LOG.info(f"Start monitoring vm: {vm_name} deletion.")
    await retry(wait_vm_to_delete, vm_name,
                max_retry=CONF.get("task", {}).get("max_monitor_attempt", MAX_MONITOR_ATTEMPTS),
                retry_interval=CONF.get("task", {}).get("monitor_interval", MONITOR_INTERVAL))
