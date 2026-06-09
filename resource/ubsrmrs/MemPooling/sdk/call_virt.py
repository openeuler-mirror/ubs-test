#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2024. All rights reserved.

import sys
import json
import os
import re
import logging
import ast
from typing import Any, Dict
from dataclasses import is_dataclass, asdict

sys.path.append("/usr/lib/python3.11/site-packages/ubse/ffi")
sys.path.append("/usr/lib/python3.11/site-packages/ubse")

from ubse.ffi.ubs_virt_agent_node_anti_affinity import UbsVirtAgentNodeAntiAffinity
from ubse.ffi.ubs_virt_agent_mem_borrow_strategy import UbsVirtAgentMemBorrowStrategy
from ubse.ffi.ubs_virt_agent_mem_borrow_execute import UbsVirtAgentMemBorrowExecute
from ubse.ffi.ubs_virt_agent_node_info import UbsVirtAgentNodeInfo
from ubse.ffi.ubs_virt_agent_vm_info import UbsVirtAgentVmInfo
from ubse.ffi.ubs_virt_agent_mem_migrate_strategy import UbsVirtAgentMemMigrateStrategy
from ubse.ffi.ubs_virt_agent_mem_migrate_execute import UbsVirtAgentMemMigrateExecute
from ubse.ffi.ubs_virt_agent_mem_return import UbsVirtAgentMemReturn
from ubse.ffi.ubs_virt_agent_mem_rollback import UbsVirtAgentMemRollback
from ubse.ffi.ubs_virt_agent_case_conf_set import UbsVirtAgentCaseConfSet
from ubse.ubs_virt_agent_case_conf import ubs_case_conf_info

logging.basicConfig(level=logging.NOTSET, format='%(message)s')


def save_result_to_json(result: Any, output_path: str = "./response.json") -> bool:
    """将结果转换为 JSON 并写入指定文件"""
    try:
        result_data = result if isinstance(result, (dict, list)) else str(result)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


def call_anti_affinity(param_json: str) -> bool:
    """调用 ubs_node_anti_affinity 接口"""
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentNodeAntiAffinity()
        ret = api.ubs_node_anti_affinity(param)
        return True if ret == 0 else False
    except Exception:
        return False


def borrow_strategy_to_dict(ret: Any) -> Dict:
    """将 BorrowStrategyT(...) 对象或字符串转换为指定 JSON dict 格式"""
    ret_str = str(ret)
    src_match = re.search(
        r"src_host_id='(\d+)', src_socket_id=(\d+), src_numa_id=(\d+), borrow_size=(\d+), dest_numa_infos=\[(.*)\]",
        ret_str
    )
    if not src_match:
        raise ValueError("无法匹配 BorrowStrategyT 结构")
    src_host_id, src_socket_id, src_numa_id, borrow_size, dest_info_raw = src_match.groups()
    dest_matches = re.findall(
        r"DstNumaInfoT\(host_id='(\d+)', socket_id=(\d+), numa_nums=(\d+), numa_ids=\[([0-9, ]+)\], mem_sizes=\[([0-9, ]+)\]\)",
        dest_info_raw
    )
    dest_param = []
    for host_id, socket_id, numa_nums, numa_ids, mem_sizes in dest_matches:
        dest_param.append({
            "destNid": host_id,
            "destSocketId": int(socket_id),
            "destNumaNum": int(numa_nums),
            "destNumaId": [int(x.strip()) for x in numa_ids.split(",")],
            "memSize": [int(x.strip()) for x in mem_sizes.split(",")]
        })
    return {
        "srcParam": {
            "srcNid": src_host_id,
            "srcSocketId": int(src_socket_id),
            "srcNumaId": int(src_numa_id)
        },
        "borrowSize": int(borrow_size),
        "destParam": dest_param
    }


def node_info_to_dict(node_info) -> dict:
    """
    将 NodeNumaInfoT 转换为对外 JSON 协议结构
    - 保持原有 nodeId / numaInfos / metaData 结构
    - 新增 numaHugePageInfo
    - 字段名使用 camelCase
    - 数值统一转字符串（与旧接口行为一致）
    """
    result = {
        "nodeId": str(node_info.host_id),
        "numaInfos": []
    }

    for numa in node_info.numa_infos:
        # 组装 numaHugePageInfo
        numa_huge_page_info = []
        for page_size, hp in numa.numa_huge_page_info.items():
            numa_huge_page_info.append({
                "pageSize": str(hp.page_size),
                "hugePageTotal": str(hp.huge_page_total),
                "hugePageFree": str(hp.huge_page_free),
            })

        meta = {
            "nodeId": str(numa.host_id),
            "hostName": numa.hostname,
            "numaId": str(numa.numa_id),
            "isLocal": str(bool(numa.is_local)),
            "memTotal": str(numa.mem_total),
            "memFree": str(numa.mem_free),
            "socketId": str(numa.socket_id),
            "numaHugePageInfo": numa_huge_page_info
        }

        result["numaInfos"].append({
            "metaData": [meta],
        })

    return result


def vm_info_to_dict(nodeVmInfo) -> Dict[str, Any]:
    """
    将 新版 NodeVmInfoT （metadata + numaInfo） 转换为对外JSON ：
    - 去除local*/remote* 扁平字段
    - NUMA 信息统一放入numaInfo 数组
    """
    def s(v):
        return "" if v is None else str(v)

    if not hasattr(nodeVmInfo, "vm_infos"):
        return {}

    out = {
        "timestamp": "",
        "nodeId": "",
        "vmDomainInfos": []
    }

    vm_list = nodeVmInfo.vm_infos or []
    if not vm_list:
        return out

    # 顶层 nodeId：优先取第一条 vm 的 host_id
    first_vm = vm_list[0]
    out["timestamp"] = s(first_vm.timestamp)
    out["nodeId"] = s(first_vm.metadata.host_id if first_vm.metadata else None)

    # 填充 vmDomainInfos
    for vm in vm_list:
        meta = vm.metadata
        numa_datas = getattr(vm, "numaInfo", None) or getattr(vm, "numa_datas", {}) or {}

        numa_info_list = []
        for numa in numa_datas.values():
            numa_info_list.append({
                "numaId": s(numa.numa_id),
                "socketId": s(numa.socket_id),
                "isLocal": s(bool(numa.is_local)),
                "pageSize": s(numa.page_size),
                "usedMem": s(numa.used_mem),
            })

        vm_dict = {
            "hostname": s(getattr(meta, "hostname", None)),
            "nodeId": s(getattr(meta, "host_id", None)),
            "pid": s(getattr(meta, "pid", None)),
            "uuid": s(getattr(meta, "uuid", None)),
            "name": s(getattr(meta, "name", None)),
            "state": s(getattr(meta, "state", None)),
            "vmCreateTime": s(getattr(meta, "vm_create_time", None)),
            "maxMem": s(getattr(meta, "max_mem", None)),
            "numaInfo": numa_info_list,
        }

        out["vmDomainInfos"].append(vm_dict)

    return out


def call_get_borrow_strategy(param_json: str, output_path: str = "./response.json") -> bool:
    """调用 ubs_mem_borrow_strategy 接口"""
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentMemBorrowStrategy()
        ret = api.ubs_mem_borrow_strategy(param)
        result_dict = borrow_strategy_to_dict(ret)
        success = save_result_to_json(result_dict, output_path)
        return success
    except Exception:
        return False


def call_get_node_info(param_json: str, output_path: str = "./response.json") -> bool:
    """调用 ubs_node_info_list 接口"""
    try:
        api = UbsVirtAgentNodeInfo()
        ret = api.ubs_node_info_list()
        result_dict = node_info_to_dict(ret)
        success = save_result_to_json(result_dict, output_path)
        return success
    except Exception:
        return False


def call_get_vm_info(param_json: str, output_path: str = "./response.json") -> bool:
    """调用 ubs_vm_info_list 接口"""
    try:
        api = UbsVirtAgentVmInfo()
        api.ubs_virt_agent_initialize()
        ret = api.ubs_vm_info_list()
        result_dict = vm_info_to_dict(ret)
        success = save_result_to_json(result_dict, output_path)
        return success
    except Exception:
        return False


def borrow_execute_res_to_dict(ret: Any) -> Dict:
    """将 BorrowExecuteResT(...) 对象或字符串转换为指定 JSON dict 格式"""
    ret_str = str(ret)
    # 匹配 BorrowExecuteResT(borrow_ids=[...], present_numa_id=[...])
    match = re.search(
        r"BorrowExecuteResT\(borrow_ids=\[([^\]]*)\],\s*present_numa_ids=\[([^\]]*)\]\)",
        ret_str
    )
    if not match:
        raise ValueError("无法匹配 BorrowExecuteResT 结构")

    borrow_ids_raw, present_numa_raw = match.groups()

    borrow_ids = [x.strip().strip("'\"") for x in borrow_ids_raw.split(",") if x.strip()]
    present_numa_id = [int(x.strip()) for x in present_numa_raw.split(",") if x.strip()]

    return {
        "borrowIds": borrow_ids,
        "presentNumaId": present_numa_id
    }


def call_borrow_execute(param_json: str, output_path: str = "./response.json") -> bool:
    """调用 ubs_mem_borrow_strategy 接口"""
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentMemBorrowExecute()
        ret, _ = api.ubs_mem_borrow_execute(param) # 出参：返回值，任务ID
        result_dict = borrow_execute_res_to_dict(ret)
        success = save_result_to_json(result_dict, output_path)
        return success
    except Exception:
        return False


def migrate_strategy_res_to_dict(ret: Any) -> Dict:
    """将 MemMigrateStrategyT(...) 字符串转换为指定 JSON dict 格式（支持多个 VM）"""
    ret_str = str(ret)

    # 1. 匹配 waiting_time
    waiting_match = re.search(r"waiting_time=(\d+)", ret_str)
    if not waiting_match:
        raise ValueError("无法匹配 waiting_time")
    waiting_time = int(waiting_match.group(1))

    # 2. 提取 vm_info_list=[ ... ] 内容（非贪婪）
    vm_raw_match = re.search(r"vm_info_list=\[(.*?)\]", ret_str, re.DOTALL)
    if not vm_raw_match:
        raise ValueError("无法匹配 vm_info_list")
    vm_list_str = vm_raw_match.group(1)

    # 3. 匹配多个 VmMigrateStrategyT(...)
    vm_matches = re.findall(
        r"VmMigrateStrategyT\s*\(\s*dest_numa_id=(\d+),\s*mem_size=(\d+),\s*pid=(\d+)\s*\)",
        vm_list_str
    )

    vm_info_list = []
    for dest_numa_id, mem_size, pid in vm_matches:
        vm_info_list.append({
            "destNumaId": int(dest_numa_id),
            "memSize": int(mem_size),
            "pid": int(pid)
        })

    return {
        "vmInfoList": vm_info_list,
        "waitingTime": waiting_time
    }


def call_migrate_strategy(param_json: str, output_path: str = "./response.json") -> bool:
    "调用ubs_virt_agent_mem_migrate_strategy接口"
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentMemMigrateStrategy()
        ret = api.ubs_mem_migrate_strategy(param)
        result_dict = migrate_strategy_res_to_dict(ret)
        success = save_result_to_json(result_dict, output_path)
        return success
    except Exception:
        return False


def call_migrate_execute(param_json: str, output_path: str = "./response.json") -> bool:
    "调用UbsVirtAgentMemMigrateExecute"
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentMemMigrateExecute()
        ret = api.ubs_mem_migrate_execute(param)
        return True if ret == 0 else False
    except Exception:
        return False


def call_mem_return(param_json: str, output_path: str = "./response.json") -> bool:
    "调用ubs_mem_return"
    try:
        api = UbsVirtAgentMemReturn()
        ret, _ = api.ubs_mem_return()  # 出参： 返回值，任务ID
        return True if ret == 0 else False
    except Exception:
        return False


def call_mem_roolback(param_json: str, output_path: str = "./response.json") -> bool:
    "ubs_mem_rollback"
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentMemRollback()
        ret = api.ubs_mem_rollback(param["borrowInNode"], param["borrowIds"])
        return True if ret == 0 else False
    except Exception:
        return False


def case_conf_to_dict(ret: Any) -> Dict:
    """
    将 CaseConfInfoT(...) 的字符串或对象解析成 JSON dict 格式。
    示例输入：
        CaseConfInfoT(case_type='memFragmentation', over_commitment=1.0, migrate_water_line=85, index=0, host_id='1')
    """

    # 转成字符串
    ret_str = str(ret)

    # 正则匹配 CaseConfInfoT(...) 中的字段
    match = re.search(
        r"CaseConfInfoT\("
        r"case_type='([^']*)',\s*"
        r"over_commitment=([\d\.]+),\s*"
        r"migrate_water_line=([\d]+),\s*"
        r"index=\d+,\s*"
        r"host_id='([^']*)'"
        r"\)",
        ret_str
    )

    if not match:
        raise ValueError(f"无法匹配 CaseConfInfoT 结构: {ret_str}")

    case_type, over_commitment, migrate_water_line, host_id = match.groups()

    return {
        "data": {
            "caseType": case_type,
            "migrateWaterLine": int(migrate_water_line),
            "overCommitment": float(over_commitment)
        },
        "msg": "Get caseConf and migrateWaterLine success.",
        "ret": 0
    }


def call_set_caseconf(param_json: str, output_path: str = "./response.json") -> bool:
    "ubs_case_conf_set"
    try:
        param = json.loads(param_json)
        api = UbsVirtAgentCaseConfSet()
        ret = api.ubs_case_conf_set(param)
        return True if ret == 0 else False
    except Exception:
        return False


def call_get_caseconf(param_json: str, output_path: str = "./response.json") -> bool:
    """
    调用 ubs_case_conf_info 并返回 JSON 结构
    """
    try:
        ret = ubs_case_conf_info()

        try:
            result_dict = case_conf_to_dict(ret)
        except Exception as e:
            # case_conf_to_dict 解析失败
            result_dict = {
                "data": {},
                "msg": f"Parse caseConf failed: {e}",
                "ret": 500
            }
            logging.info(result_dict)
            return False

        logging.info(result_dict)
        return True

    except Exception as e:
        # API 调用失败
        result_dict = {
            "data": {},
            "msg": f"Call caseConf failed: {e}",
            "ret": 500
        }
        logging.info(result_dict)
        return False


def main():
    if len(sys.argv) < 3:
        logging.info("500")
        sys.exit(1)

    func_name = sys.argv[1]
    param_input = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) >= 4 else "./response.json"

    # 支持传 JSON 文件路径或 JSON 字符串
    if os.path.isfile(param_input):
        with open(param_input, "r", encoding="utf-8") as f:
            param_json = f.read()
    else:
        param_json = param_input

    func = globals().get(func_name)
    if not callable(func):
        logging.info("500")
        sys.exit(1)

    # 如果函数支持 output_path 参数就传入
    try:
        success = func(param_json, output_path)
    except TypeError:
        # 如果函数只接受一个参数
        success = func(param_json)

    logging.info("200" if success else "500")


if __name__ == "__main__":
    main()
