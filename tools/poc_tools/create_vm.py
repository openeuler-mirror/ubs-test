import argparse
import asyncio
import os
import subprocess
import math

from typing import List, Tuple

from poc_tools.common.config import init_config, CONF
from poc_tools.common.log import init_log, LOG
from poc_tools.common.params import GenerateXmlParams, MemInfo
from poc_tools.common.utils import retry, send_pipe_scripts
from poc_tools.common.validator import validate_params, validate_config
from poc_tools.virsh_cmd import virsh_undefine_vm, define_vm_through_xml, start_vm
from poc_tools.gen_xml import write_to_xml_file, generate_xml
from poc_tools.mem_free import mem_free
from poc_tools.vm_monitor import monitor_create_vm
from poc_tools.common.constant import MemConvertEnum, CollectHugePageType, MemBorrowLimitParam, AsyncTaskStatus
from ubse.ubs_virt_agent_fragmentation import ubs_task_result_query, ubs_mem_fragmentation_node_info_list, ubs_mem_borrow, ubs_page_swap_enable
from ubse.models.ubs_virt_agent_model import NodeInfoT
from ubse.models.ubs_virt_agent_model import NumaMetaInfoT, BorrowParamT
from ubse.models.ubs_virt_agent_model import PageSwapPairT, NumaQuotaT

REMOTE_MEMORY_USAGE_PERCENTAGE = 50
ONE_HUNDRED_PERCENT = 100
MEM_FLOW_RATIO = 1

async def virsh_define_and_start_vm(xml_params: GenerateXmlParams, borrow_in_node: str):
    is_defined = False
    vm_name = xml_params.vm_name
    try:
        xml_file_path = CONF["default"]["xml_path"]
        LOG.info(f"Xml file: {xml_file_path}, vm name: {vm_name}, vm size: {xml_params.vm_size}, "
                 f"memory usage information for each NUMA: {xml_params.numa_infos}.")
        uuid, domain = await generate_xml(xml_params)
        LOG.info(f"Writing params to generate xml file.")
        await write_to_xml_file(xml_file_path, domain)
        LOG.info(f"Define through xml file. Xml file path: {xml_file_path}.")
        await define_vm_through_xml(xml_file_path, uuid)
        is_defined = True
        LOG.info(f"Starting vm: {vm_name}.")
        await start_vm(vm_name)
        LOG.info(f"Create vm successfully, vm name: {vm_name}.")
    except Exception as e:
        LOG.error(f"Virsh define and start vm failed, error: {e}")
        if is_defined:
            await virsh_undefine_vm(vm_name)
        if any([not mem_info.is_local for mem_info in xml_params.numa_infos]):
            LOG.info("The xml params includes remote memory, execute mem free.")
            await retry(mem_free)
        raise


async def get_local_node(node_info_list: List[NodeInfoT]) -> int:
    for node_info in node_info_list:
        if node_info.is_current:
            return node_info.node_id
    raise ValueError("Couldn't get local_node_id")

async def get_borrow_mem(size: int, node_info_list: List[NodeInfoT], mem_borrow_unit: MemBorrowLimitParam) -> int:

    vm_size_mb = size * MemConvertEnum.GB_TO_MB

    local_free_huge_page = 0
    local_free_huge_page_for_flow = 0
    mem_flow_ratio = CONF.get("default", {}).get("mem_flow_ratio", MEM_FLOW_RATIO)
    for node_info in node_info_list:
        if not node_info.is_current:
            continue
        for numa_info in node_info.numa_infos:
            huge_page_free = (numa_info.numa_huge_page_info[2 * MemConvertEnum.MB_TO_KB].huge_page_free
                              * MemConvertEnum.HUGE_PAGE_TO_MB)
            local_free_huge_page += huge_page_free
            mem_flow = math.ceil((huge_page_free * mem_flow_ratio) / ONE_HUNDRED_PERCENT)
            local_free_huge_page_for_flow += huge_page_free - mem_flow
    local_free_huge_page = local_free_huge_page // mem_borrow_unit * mem_borrow_unit
    local_free_huge_page_for_flow = local_free_huge_page_for_flow // mem_borrow_unit * mem_borrow_unit

    borrow_mem = 0
    if vm_size_mb > local_free_huge_page:
        borrow_mem = vm_size_mb - local_free_huge_page_for_flow

    remote_memory_usage_percentage = (CONF.get("default", {}).get("remote_memory_usage_percentage",
                                                                  REMOTE_MEMORY_USAGE_PERCENTAGE))

    if int(vm_size_mb * remote_memory_usage_percentage / ONE_HUNDRED_PERCENT) < borrow_mem:
        # Borrow mem can not exceed local mem.
        msg = "The amount of borrowed memory cannot exceed the amount of local memory."
        LOG.error(msg)
        raise Exception(msg)

    return borrow_mem

async def get_numa_len_and_numa_info(node_info_list: List[NodeInfoT]) ->Tuple:

    new_numa_infos = []
    new_numa_len = 0
    for node_info in node_info_list:
        if not node_info.is_current:
            continue
        new_numa_len  = len(node_info.numa_infos)
        for numa_info in node_info.numa_infos:
            new_numa_info = NumaMetaInfoT(
                socket_id = numa_info.socket_id,
                numa_id = int(numa_info.numa_id)
            )
            new_numa_infos.append(new_numa_info)
    return new_numa_len, new_numa_infos


async def get_remote_local_dict(param: BorrowParamT, borrow_result: List):
    remote_local_dict = {}
    if len(param.numa_meta_infos) != len(borrow_result):
        raise ValueError("The numa_len of param is not equal to result_len.")

    for i in range(len(param.numa_meta_infos)):
        local_numa_id = param.numa_meta_infos[i].numa_id
        for remote_numa_id in borrow_result[i].present_numa_ids:
            remote_local_dict[remote_numa_id] = local_numa_id
    return remote_local_dict


async def get_mem_infos(vm_size_gb: int, node_info_list: List[NodeInfoT], borrow_mem: int, mem_borrow_unit: int) -> Tuple:
    vm_size_mb = vm_size_gb * MemConvertEnum.GB_TO_MB
    total_mem_info = []
    numa_mem_dict = {}
    mem_flow_ratio = CONF.get("default", {}).get("mem_flow_ratio", MEM_FLOW_RATIO)
    for node_info in node_info_list:
        if not node_info.is_current:
            continue
        for numa_info in node_info.numa_infos:
            size = (numa_info.numa_huge_page_info[MemConvertEnum.HUGE_PAGE_TO_KB].huge_page_free *
                    MemConvertEnum.HUGE_PAGE_TO_MB)
            if numa_info.is_local and borrow_mem > 0:
                mem_flow = math.ceil((size * mem_flow_ratio) / ONE_HUNDRED_PERCENT)
                size -= mem_flow
            size = size // mem_borrow_unit * mem_borrow_unit
            if size > vm_size_mb:
                size = vm_size_mb
            mem_info = MemInfo(
                numa_id = int(numa_info.numa_id),
                size = size,
                is_local = numa_info.is_local
            )
            total_mem_info.append(mem_info)
            numa_mem_dict[mem_info.numa_id] = size
            vm_size_mb -= size
            if vm_size_mb <= 0:
                break
    return total_mem_info, numa_mem_dict


async def get_pid(vm_name: str):
    pid = await send_pipe_scripts([["cat", f"/var/run/libvirt/qemu/{vm_name}.pid"]])
    if pid == "":
        raise ValueError(f"Failed to get pid for vm: {vm_name}")
    LOG.info(f"Get pid : {pid} of vm: {vm_name}")
    return int(pid)


async def get_page_swap_param(node_info_list: List[NodeInfoT], numa_mem_dict: dict) -> List[PageSwapPairT]:
    local_numas = []
    remote_numas = []
    for node_info in node_info_list:
        if not node_info.is_current:
            continue
        for numa_info in node_info.numa_infos:
            numa_quota = NumaQuotaT(
                numa_id = int(numa_info.numa_id),
                quota = numa_mem_dict[int(numa_info.numa_id)]
            )
            if numa_quota.quota == 0:
                continue
            if numa_info.is_local:
                local_numas.append(numa_quota)
            else:
                remote_numas.append(numa_quota)

    page_swap_pair = PageSwapPairT(
        local_numa_quotas = local_numas,
        remote_numa_quotas = remote_numas,
    )
    page_swap_pairs = [page_swap_pair]
    return page_swap_pairs

async def create():
    try:
        parser = argparse.ArgumentParser(description="接收bash传递的mem_size和image_name参数")
        parser.add_argument("mem_size", type=int, help="内存大小（整数，来自 -size 选项）")
        parser.add_argument("image_name", type=str, help="镜像路径（字符串，来自 -img 选项）")
        parser.add_argument("vm_name", type=str, help="虚机名称")
        args = parser.parse_args()
        LOG.info("Start creating vm.")
        # 准备阶段
        LOG.info("prepare")
        await validate_config() # 校验配置文件

        vm_name = args.vm_name
        size = args.mem_size
        await validate_params(args.mem_size, args.image_name)
        image_full_path = os.path.join(CONF["default"]["image_base_path"], args.image_name)

        # 获取节点信息
        LOG.info("start to get node_info_list")
        node_info_list = ubs_mem_fragmentation_node_info_list()
        if len(node_info_list) == 0 :
            raise RuntimeError("Failed to call ubs_mem_fragmentation_node_info_list.")

        # 获取当前nodeId和需要借用内存量
        LOG.info("get local_node and borrow_mem")
        local_node = await get_local_node(node_info_list)

        collect_hugepage_type = CONF.get("default", {}).get("collect_hugepage_type",
                                                            CollectHugePageType.COLLECT_HUGE_PAGE_GB)
        if collect_hugepage_type == CollectHugePageType.COLLECT_HUGE_PAGE_GB:
            mem_borrow_unit = MemBorrowLimitParam.MEM_BORROW_UNIT_GB
        else:
            mem_borrow_unit = MemBorrowLimitParam.MEM_BORROW_UNIT_MB

        borrow_mem = await get_borrow_mem(size, node_info_list, mem_borrow_unit)
        new_numa_len , new_numa_infos = await get_numa_len_and_numa_info(node_info_list)
        param = BorrowParamT(
            node_id = local_node,
            numa_meta_infos = new_numa_infos,
            borrow_size = borrow_mem
        )

        # 借用

        borrow_result = []
        if borrow_mem > 0:
            LOG.info("Borrow")
            borrow_result = ubs_mem_borrow(param, True)
            for i in range(len(borrow_result)):
                task_id = borrow_result[i].task_id
                flag = False
                for j in range(CONF.get("default", {}).get("async_max_retry", 3600)):
                    ret, task_info = ubs_task_result_query(task_id)
                    if ret != 0:
                        raise RuntimeError(f"Failed to get task result, task_id: {task_id}")
                    if task_info.status == AsyncTaskStatus.SUCCESS:
                        flag = True
                        borrow_result[i].borrow_ids = task_info.mem_borrow_result.borrow_ids
                        borrow_result[i].present_numa_ids = task_info.mem_borrow_result.present_numa_ids
                        break
                    await asyncio.sleep(CONF.get("default", {}).get("async_retry_interval", 10))
                if flag == False:
                    raise RuntimeError(f"Failed to get task result, task_id: {task_id}")



        node_info_list_after_borrow = ubs_mem_fragmentation_node_info_list()
        LOG.info("generate xml")
        numa_infos, numa_mem_dict = await get_mem_infos(size, node_info_list_after_borrow, borrow_mem, mem_borrow_unit)
        LOG.info(f"Vm name: {vm_name}, vm size: {size}GB, image full path: {image_full_path}.")
        xml_params = GenerateXmlParams(vm_name=vm_name, vm_size=size, numa_infos=numa_infos,
                                       image_full_path=image_full_path)

        LOG.info("start vm")
        await virsh_define_and_start_vm(xml_params, local_node)
        await monitor_create_vm(vm_name)
        if borrow_mem > 0:
            LOG.info("page swap")
            pid = await get_pid(vm_name)
            page_swap_enable = await get_page_swap_param(node_info_list_after_borrow, numa_mem_dict)
            res = ubs_page_swap_enable(pid, page_swap_enable)
            if res != 0 :
                raise RuntimeError("page swap failed")
    except Exception as e:
        LOG.error(str(e))
        raise SystemExit(1) from e


if __name__ == "__main__":
    init_config()
    init_log()
    asyncio.run(create())
