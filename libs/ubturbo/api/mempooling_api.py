#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2024. All rights reserved.

import time
import re
import json
from typing import Union
from libs.ubturbo.common import basic, env
import libs.ubturbo.api.mempooling as mempooling
import libs.ubturbo.api.numa as numa
import libs.ubturbo.api.system as sys
from libs.ubturbo.model.libvirt import TempVirtualMachine, TempVMInfo
from libs.ubturbo.common.string_utils import STR_ENTER
MEM_INFO_PATH = '/home/mempooling-test/mem_info/getAllBorrowInfo'
SDK_RESPONSE_PATH = "/home/mempooling-test/sdk/"


class MemBerOfBorrowTopology:
    """
    该类的对象表示拓扑信息中的成员，成员属性有nodeId、planeId、numaId
    :nodeId:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :planeId:数据类型为数值，有0、1，表示逻辑上的平面
    :numaId:数据类型为数值，表示numa{numaId}
    """

    def __init__(self, nodeid=None, planeid=None, numaid=None):
        self.nodeId = nodeid
        self.planeId = planeid
        self.numaId = numaid

    def __eq__(self, other):
        return (self.nodeId == other.nodeId and
                self.numaId == other.numaId)

    def __hash__(self):
        return hash((self.nodeId, self.numaId))


def create_member_of_borrow_topology(nodeid, numaid, planeid=None):
    """
    创建对象，表示拓扑信息中的成员
    :nodeId:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :planeId:数据类型为数值，有0、1，表示逻辑上的平面
    :numaId:数据类型为数值，表示numa{numaId}
    :return:返回拓扑信息中的成员
    """
    borrow_topology = MemBerOfBorrowTopology(nodeid, planeid, numaid)
    return borrow_topology


def get_borrow_topology(fm="1DFM"):
    """
    获得MatrixServer的1D FM组网拓扑，数据类型为字典；
    字典key的数据类型为MemBerOfBorrowTopology类，
    字典value的数据类型为列表，列表元素为MemBerOfBorrowTopology类对象
    """
    topology = {}
    if fm == "1DFM":
        node0_plane0_numa0 = create_member_of_borrow_topology(0, 0, 0)
        node0_plane1_numa1 = create_member_of_borrow_topology(0, 1, 1)
        node1_plane0_numa0 = create_member_of_borrow_topology(1, 0, 0)
        node1_plane1_numa1 = create_member_of_borrow_topology(1, 1, 1)
        node2_plane0_numa0 = create_member_of_borrow_topology(2, 0, 0)
        node2_plane1_numa1 = create_member_of_borrow_topology(2, 1, 1)
        node3_plane0_numa0 = create_member_of_borrow_topology(3, 0, 0)
        node3_plane1_numa1 = create_member_of_borrow_topology(3, 1, 1)
        topology = {node0_plane0_numa0: [node1_plane0_numa0, node2_plane0_numa0, node3_plane0_numa0],
                    node0_plane1_numa1: [node1_plane1_numa1, node2_plane1_numa1, node3_plane1_numa1],
                    node1_plane0_numa0: [node0_plane0_numa0, node2_plane0_numa0, node3_plane0_numa0],
                    node1_plane1_numa1: [node0_plane1_numa1, node2_plane1_numa1, node3_plane1_numa1],
                    node2_plane0_numa0: [node0_plane0_numa0, node1_plane0_numa0, node3_plane0_numa0],
                    node2_plane1_numa1: [node0_plane1_numa1, node1_plane1_numa1, node3_plane1_numa1],
                    node3_plane0_numa0: [node0_plane0_numa0, node1_plane0_numa0, node2_plane0_numa0],
                    node3_plane1_numa1: [node0_plane1_numa1, node1_plane1_numa1, node2_plane1_numa1]}
    return topology


def get_same_plane_topology_members_list(src_member_of_borrow_topology):
    """
    获得与节点{src_member_of_borrow_topology.nodeId}的numa{src_member_of_borrow_topology.numaId}同平面的拓扑成员列表
    :src_member_of_borrow_topology:数据类型为类MemBerOfBorrowTopology
    :return same_plane_topology_members_list:返回同平面的拓扑成员列表
    """
    topology = get_borrow_topology()
    same_plane_topology_members_list = topology.get(src_member_of_borrow_topology)
    return same_plane_topology_members_list


def get_same_plane_topology_members_list_from_dest_nodeid(src_member_of_borrow_topology, dest_nodeid):
    """
    获得与节点{src_member_of_borrow_topology.nodeId}的numa{src_member_of_borrow_topology.numaId}同平面的某个节点{dest_nodeid}的拓扑成员列表
    :src_member_of_borrow_topology:数据类型为类MemBerOfBorrowTopology
    :return same_plane_topology_members_list:返回同平面的某个节点{dest_nodeid}的拓扑成员列表
    """
    same_plane_topology_members_list = get_same_plane_topology_members_list(src_member_of_borrow_topology)
    same_plane_topology_members_list_from_dest_nodeid = [d for d in same_plane_topology_members_list if d.nodeId == dest_nodeid]
    return same_plane_topology_members_list_from_dest_nodeid


def create_destparam(param_list):
    """
    用于获得借用执行方法function_borrow_execute的入参borrow_execute_input_parameter的属性destParam
    :param param_list:列表元素为元组，形如[(0,1,1,[2],[262144])，(0,1,1,[2],[262144])]
               元组第一个元素表示借出节点destNid,数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
               元组第二个元素表示destSocketId，数值
               元组第三个元素表示destNumaNum，数值
               元组第四个元素表示destNumaId，列表，列表元素是数值
               元组第五个元素表示memSize,列表，列表元素是数值
    :return:转换为列表，元素是字典
    """
    length_of_destparam = len(param_list)
    destparam = [
        {"destNid": None, "destSocketId": None, "destNumaNum": None, "destNumaId": None, "memSize": None}
        for d in range(length_of_destparam)]
    for i in range(length_of_destparam):
        destparam[i]["destNid"] = mempooling.node_to_num(param_list[i][0])
        destparam[i]["destSocketId"] = int(param_list[i][1])
        destparam[i]["destNumaNum"] = param_list[i][2]
        destparam[i]["destNumaId"] = param_list[i][3]
        destparam[i]["memSize"] = param_list[i][4]
    return destparam


class BorrowExecuteInputParameter:
    """
    创建类对象，用于定义借用执行方法function_borrow_execute的入参borrow_execute_input_parameter，属性有srcNid,srcSocket,srcNumaId,destParam
    :param srcnid:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :param srcnumaid:数据类型是数值
    :param srcsocketid:数据类型为数值，可通过mempooling.get_socketid方法获得
    :param destparam:数据类型是列表，通过方法lib.api.mempooling_api.create_destParam获得
    """

    def __init__(self, srcnid=None, srcnumaid=None, srcsocketid=None, destparam=None):
        self.srcNid = mempooling.node_to_num(srcnid)
        self.srcNumaId = srcnumaid
        self.srcSocketId = int(srcsocketid)
        self.destParam = destparam


def function_borrow_execute(node, borrow_execute_input_parameter: Union[BorrowExecuteInputParameter, dict],
                            file_path="/home/mempooling-test/response.json", timeout: int = 30 * 60):
    """
    调用内存借用执行接口，返回http返回码
    :param node
    :param borrow_execute_input_parameter:表示借用执行的入参
    相关用例有两种场景：1、需要自己构造借用执行的入参：通过创建lib.api.mempooling_api.py中BorrowExecuteInputParameter类的对象获得borrow_execute_input_parameter
                     2、将借用策略的回显作为借用执行的入参：通过方法lib.api.mempooling_api.parse_full_borrow_strategy_response获得borrow_execute_input_parameter，数据类型dict
    :param file_path
    :param timeout
    :return:返回http返回码
    """
    borrow_execute = ""
    basic.run(node, f"rm -rf {file_path}")
    if isinstance(borrow_execute_input_parameter, BorrowExecuteInputParameter):
        srcnid = borrow_execute_input_parameter.srcNid
        payload = {
            "srcParam": {
                "srcNid": srcnid,
                "srcSocketId": int(borrow_execute_input_parameter.srcSocketId),
                "srcNumaId": borrow_execute_input_parameter.srcNumaId
            },
            "borrowSize": 1048576,
            "destParam": borrow_execute_input_parameter.destParam
        }
        json_cmd = json.dumps(payload)
        borrow_execute = f"python3 /home/mempooling-test/sdk/call_virt.py call_borrow_execute '{json_cmd}' {file_path}"
    elif isinstance(borrow_execute_input_parameter, dict):
        json_dict = json.dumps(borrow_execute_input_parameter)
        borrow_execute = f"python3 /home/mempooling-test/sdk/call_virt.py call_borrow_execute '{json_dict}' {file_path}"
    ret_stdout = basic.run(node, borrow_execute, timeout=timeout).stdout
    ret = int([x for x in ret_stdout.splitlines() if x.strip()][-1])
    if ret == 200:
        time.sleep(20)
    basic.run(node, f"sync {file_path}", timeout=15)
    basic.run(node, f"cat {file_path}", timeout=15)
    return ret


def parse_borrow_execute_response(node, http_code=200, file_path="/home/mempooling-test/response.json"):
    """
    紧跟function_borrow_execute接口之后，解析接口返回的response.json
    :param node:调用内存借用执行接口的节点
    :param http_code:调用内存借用执行接口,返回的http返回码，200表示成功
    :param file_path
    :return:返回借用执行结果的borrowIds，列表元素是字符串，列表形如["6509ae6ce425e447b8980479939599f1","75f9e4d414ac1f9a1c797ec0b25db56a"]
    """
    if http_code == 200:
        data = mempooling.json2dict(node, file_path)
        borrowids = data["borrowIds"]
        return borrowids
    else:
        return []


def parse_presentnumaid_from_borrow_execute_response(node, http_code=200, file_path="/home/mempooling-test/response.json"):
    """
    紧跟function_borrow_execute接口之后，解析接口返回的response.json,response.json形如：
    {
        "borrowIds": [
            "1-763654f0c937f0f32684757ff31c7e0c"
        ],
        "presentNumaId": [
            7
        ]
    }
    :param node:调用内存借用执行接口的节点
    :param http_code:调用内存借用执行接口,返回的http返回码，200表示成功
    :param file_path
    :return:返回借用执行结果的presentNumaId，列表元素是远端numa的Id，列表形如[2,3]
    """
    if http_code == 200:
        data = mempooling.json2dict(node, file_path)
        presentnumaid = data.get("presentNumaId")
        return presentnumaid
    else:
        return []


def parse_borrow_execute_response_full(node, http_code=200, file_path="/home/mempooling-test/response.json"):
    """
    紧跟function_borrow_execute接口之后，一次性解析接口返回的response.json，同时返回borrowIds和presentNumaId。
    response.json形如：
    {
        "borrowIds": [
            "1-763654f0c937f0f32684757ff31c7e0c"
        ],
        "presentNumaId": [
            7
        ]
    }
    :param node: 调用内存借用执行接口的节点
    :param http_code: 调用内存借用执行接口返回的http返回码，200表示成功
    :param file_path: response.json文件路径
    :return: (borrowIds, presentNumaId) 元组
             borrowIds: 借用执行结果的borrowIds，列表元素是字符串，形如["6509ae6ce425e447b8980479939599f1"]
             presentNumaId: 远端numa的Id列表，形如[2,3]
    """
    if http_code == 200:
        data = mempooling.json2dict(node, file_path)
        borrowids = data.get("borrowIds", [])
        presentnumaid = data.get("presentNumaId", [])
        return borrowids, presentnumaid
    else:
        return [], []


def parse_node_numa_attribute(node, numaid, attribute):
    """
    解析{node}节点的numa信息
    :param node
    :param numaid：numa的id，例如0,1,2,3
    :param attribute:可以查询的属性有'MemFree', 'HugePages_Total', 'HugePages_Free', 'MemTotal'
    :return:返回{node}节点的numa{numaId}的属性{attribute}的值
    """
    numas_info = mempooling.get_numaInfos(node)
    numa_info = [d for d in numas_info if int(''.join(filter(str.isdigit, d.get("name")))) == numaid][0]
    attribute_value = numa_info[attribute]
    return attribute_value


def get_num_of_numas(node):
    """
    获得{node}节点的numa数量
    """
    numas_info = mempooling.get_numaInfos(node)
    return len(numas_info)


def parse_node_remote_numa_info(node):
    """
    获得{node}节点的远端numa信息
    :param node:需要解析远端numa信息的node节点
    :param num_of_local_numas:本地numa的数量
    :return:返回远端numa信息的列表，列表元素的数据类型是字典，表示借入节点的远端numa信息，字典键值有'name', 'HugePages_Total', 'HugePages_Free', 'MemTotal'
    """
    numas_info = mempooling.get_numaInfos(node)
    remote_numa_info_list = [d for d in numas_info if int(''.join(filter(str.isdigit, d.get("name")))) not in range(numa.get_numa_count_with_cpu(node))]
    check_remote_numa_info_list = [{} for d in range(len(remote_numa_info_list))]
    length_of_remote_numa_info_list = len(remote_numa_info_list)
    for i in range(length_of_remote_numa_info_list):
        check_remote_numa_info_list[i]["name"] = remote_numa_info_list[i].get("name")
        check_remote_numa_info_list[i]["MemTotal"] = remote_numa_info_list[i].get("MemTotal")
        check_remote_numa_info_list[i]["HugePages_Total"] = remote_numa_info_list[i].get("HugePages_Total")
        check_remote_numa_info_list[i]["HugePages_Free"] = remote_numa_info_list[i].get("HugePages_Free")
    return check_remote_numa_info_list


def function_rollback(node, borrowinnode, borrowids):
    """
    调用内存回滚接口，返回http返回码；
    :param node
    :param borrowinnode:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :param borrowids
    :borrowIds:parse_borrow_execute_response方法的返回值
    :return:返回http返回码
    """
    payload = {
        "borrowInNode": mempooling.node_to_num(borrowinnode),
        "borrowIds": borrowids
    }
    mem_roolback = f"python3 /home/mempooling-test/sdk/call_virt.py call_mem_roolback '{json.dumps(payload)}'"
    ret_stdout = basic.run(node, mem_roolback, timeout=120).stdout
    ret = int([x for x in ret_stdout.splitlines() if x.strip()][-1])
    # 由于回滚接口返回500存在部分回滚的情况，所以不需要判断http返回码是否是200，一律等待100s
    time.sleep(100)
    return ret


def function_return(node, nodeid, timeout=30 * 60):
    """
    调用内存归还接口，返回http返回码
    :param node
    :param nodeid:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :borrowIds:parse_borrow_execute_response方法的返回值
    :return:返回http返回码
    """
    cmd = f"python3 /home/mempooling-test/sdk/call_virt.py call_mem_return '{str(mempooling.node_to_num(nodeid))}'"
    ret_stdout = basic.run(node, cmd, timeout=timeout).stdout
    ret = int([x for x in ret_stdout.splitlines() if x.strip()][-1])
    if ret == 200:
        time.sleep(30)
    return ret


def clear_env_temporary_vms(nodes):
    for node in nodes:
        TempVirtualMachine.clear_all(node)


def create_vm_object(node, vm_id, init_login=True, remote=False):
    """
    创建临时的虚机对象
    :param node:
    :param vm_id:可选id有‘A’,'B','C'
    :param init_login:True表示创建虚机对象时配置免密登录，False表示用户需要自行配置免密登录
    :param remote:默认False,使用本地内存创建虚机
    """

    hardware_str = ''
    if env.get_env_type(node) == env.UB_hardware:
        hardware_str = 'hardware_'

    filename_xml = f'/home/mempooling-test/{hardware_str}xml/mempooling-{vm_id}-ub.xml'
    if remote:
        filename_xml = f'/home/mempooling-test/{hardware_str}xml/remote-mempooling-{vm_id}-ub.xml'

    vm = TempVirtualMachine(
        node,
        tmp_vm_info=TempVMInfo(
            node,
            template_xml=filename_xml,
            template_img=f'/home/mempooling-test/img/openEuler-22.03-LTS-SP1-aarch64.qcow2',
            vm_name=f'mempooling-{vm_id}',
        ),
        init_login=init_login
    )
    if init_login:
        check_vm_function(vm)
    return vm


def check_vm_function(vm):
    """
    在主机端让虚机执行一次echo 123命令，检查虚机功能是否正常
    :param vm:虚机对象，可以通过lib/model/libvirt.py中的TempVirtualMachine类创建
    """
    ret = vm.execute_without_login('echo 123').stdout.strip()[-3:]
    if ret[-3:] != '123':
        raise Exception('虚拟机功能不正常')
    basic.logger.info("虚机功能正常")


def get_vm_infolist(vm_list, used_for_strategy=False):
    """
    获取节点上虚机信息列表，用于内存迁出策略接口或内存迁出执行接口的入参
    :param vm_list:虚机信息列表，元素是元祖，形如[(pid,ratio)]或[(pid,memSize,destNumaId)],元组的元素都是数值; 虚机pid可通过mempooling.get_pid(node,vm_name)获得
    :param used_for_strategy:如果是True，表示迁出策略，如果是False，表示迁出执行，默认False
    :return:返回虚机信息列表，元素是字典，形如[{"pid":375969,"ratio":10}]或[{"pid:375969","memSize":208896,"destNumaId":4}]
    """
    if used_for_strategy:
        vm_info_list = [{"pid": None, "ratio": None} for d in range(len(vm_list))]
    elif not used_for_strategy:
        vm_info_list = [{"pid": None, "memSize": None, "destNumaId": None} for d in range(len(vm_list))]
    len_of_vm_list = len(vm_list)
    for i in range(len_of_vm_list):
        if used_for_strategy:
            vm_info_list[i]["pid"] = vm_list[i][0]
            vm_info_list[i]["ratio"] = vm_list[i][1]
        elif not used_for_strategy:
            vm_info_list[i]["pid"] = vm_list[i][0]
            vm_info_list[i]["memSize"] = vm_list[i][1]
            vm_info_list[i]["destNumaId"] = vm_list[i][2]

    return vm_info_list


def function_migrate_strategy(node, borrowinnode, borrowsize, vminfolist, file_path="/home/mempooling-test/response.json"):
    """
    调用内存迁出策略接口，返回http返回码
    :param node
    :param borrowinnode:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :param borrowsize
    :param vminfolist:get_vm_infolist方法的返回值
    :param file_path
    :return:返回http返回码
    #todo:文件目录作为入参，可使用默认值，不能是工号
    """
    basic.run(node, f"rm -rf {file_path}", timeout=60)
    payload = {
        "borrowInNode": mempooling.node_to_num(borrowinnode),
        "borrowSize": int(borrowsize),
        "vmInfoList": vminfolist
    }
    migrate_strategy = f"python3 /home/mempooling-test/sdk/call_virt.py call_migrate_strategy '{json.dumps(payload)}' {file_path}"
    ret_stdout = basic.run(node, migrate_strategy, timeout=180).stdout
    ret = int([x for x in ret_stdout.splitlines() if x.strip()][-1])
    basic.run(node, f"sync {file_path}", timeout=15)
    basic.run(node, f"cat {file_path}", timeout=15)
    return ret


def parse_migrate_strategy_response(node, file_path="/home/mempooling-test/response.json"):
    """
    紧跟function_migrate_strategy接口之后，解析接口返回的response.json
    :param node
    :param file_path
    :return:返回虚机的迁出策略结果vmInfoList，列表元素是字典，形如[{"pid":375969,"memSize":208896,"destNumaId":4},{"pid":376186,"memSize":124928,"destNumaId":5}]
    """
    data = mempooling.json2dict(node, file_path)
    vm_info_list = data["vmInfoList"]
    return vm_info_list


def parse_migrate_strategy_response_vm_field(vm_infolist, vm_pid, field):
    """
    解析内存迁出策略接口返回的虚机迁出信息
    :param vm_infolist:parse_migrate_strategy_response方法的返回值
    :param vm_pid:虚机的pid
    :param field:可以查询的字段有"memSize","destNumaId"
    :return:返回虚机的参数的值，例如memSize,destNumaId
    """
    vm_info = [vmInfo for vmInfo in vm_infolist if vmInfo.get("pid") == vm_pid][0]
    field_value = vm_info.get(field)
    return field_value


def function_borrow_strategy(node, srcnid, srcsocketid, srcnumaid, borrowsize, timeout: int = 60,
                             file_path="/home/mempooling-test/response.json"):
    """
    调用内存借用策略接口,返回http返回码
    :param node：内存借用策略执行节点，正常需保证为借入节点
    :param srcnid: 数据类型为int，为"Node0"、"Node1"、"Node2"、"Node3"的数字位，例如：0/1/2/3
    :param srcsocketid：借入节点的socket_id，数据类型为int，例如：36/216
    :param srcnumaid：借入节点的借入numa_id，数据类型int，例如：0/1
    :param borrowsize：本次需要借用的内存大小，数据类型int，单位kb，例如：131072/262144(128M/256M)
    :param timeout：本次内存借用策略的超时时间，数据类型int，单位s，默认60s
    :param file_path：内存借用策略的返回结果存储josn绝对路径，数据类型str，默认/home/mempooling-test/response.json
    :return：借用策略的返回码，数据类型int，例如：200/500
    """
    basic.run(node, f"rm -rf {file_path}", timeout=timeout)
    payload = {
        "srcParam": {
            "srcNid": mempooling.node_to_num(srcnid),
            "srcSocketId": int(srcsocketid),
            "srcNumaId": srcnumaid,
        },
        "borrowSize": borrowsize
    }
    borrow_strategy = \
        f"python3 /home/mempooling-test/sdk/call_virt.py call_get_borrow_strategy '{json.dumps(payload)}' {file_path}"
    ret_stdout = basic.run(node, borrow_strategy).stdout
    ret = int([x for x in ret_stdout.splitlines() if x.strip()][-1])
    if ret != 200 and ret != 500:
        raise Exception(f"本次借用策略的返回码既不是200也不是500，实际返回码为：{ret}")
    if ret == 200:
        basic.run(node, f"sync {file_path}", timeout=15)
        basic.run(node, f"cat {file_path}", timeout=15)
    return ret


def parse_borrow_strategy_response(node, http_code=200, file_path="/home/mempooling-test/response.json"):
    """
    在function_borrow_strategy接口之后，解析接口返回的response.json
    :param node：和方法function_borrow_strategy同个node，正确保证需要为借用策略中的借入节点
    :param http_code：调用内存借用策略接口返回的http返回码，数据类型int，200表示成功，例如：200/500
    :param file_path：借用策略返回josn的保存路径，默认为/home/mempooling-test/response.json
    :return：返回借用策略结果destParam，列表元素为字典，destParam形如
    [{"destNid":"3","destSocketId":1,"destNumaNum":1,"destNumaId":[2],"memSize":[262144]}]
    如果http_code不等于200，则返回空列表
    """
    data = []
    if http_code == 200:
        data = mempooling.json2dict(node, file_path)
    return data


def function_migrate_execute(node, borrowinnode, borrowids, vminfolist, waitingtime):
    """
    调用内存迁出执行接口，返回http返回码
    :param node
    :param borrowinnode:数据类型为数值，为"Node0"、"Node1"、"Node2"、"Node3"的数字位
    :param borrowids:parse_borrow_execute_response方法的返回值
    :param vminfolist:parse_migrate_strategy_response方法的返回值
    :param waitingtime
    :return:返回http返回码
    """
    payload = {
        "borrowInNode": mempooling.node_to_num(borrowinnode),
        "borrowIds": borrowids,
        "vmInfoList": vminfolist,
        "waitingTime": waitingtime
    }
    migrate_execute = f"python3 /home/mempooling-test/sdk/call_virt.py call_migrate_execute '{json.dumps(payload)}'"
    ret_stdout = basic.run(node, migrate_execute, timeout=180).stdout
    ret = int([x for x in ret_stdout.splitlines() if x.strip()][-1])
    return ret


def get_borrows_from_memory_borrow_info(nodes, file_path="/home/mempooling-test/mem_info.json"):
    """
    查询完整的内存账本信息
    :param node:节点对象
    :param file_path: 账本信息写入的文件
    :return borrows_list:返回内存账本信息中的borrows部分，数据类型为列表，列表元素数量可以有多个，元素为字典,
    字典的键值有borrowLocalNuma、borrowMemId、borrowNode、borrowRemoteNuma、lentMemId、lentNode、lentNuma、lentSocketId、name、obmmDescHccs、size
    """
    basic.logger.info("开始查询内存账本")
    borrows_list = []
    for node in nodes:
        cmd = f"{MEM_INFO_PATH} > {file_path}"
        basic.run(node, cmd, timeout=20)
        basic.run(node, f"sync {file_path}", timeout=15)
        basic.run(node, f"cat {file_path}", timeout=15)
        borrows_list += mempooling.json2dict(node, jsonfile_path=file_path)['borrows']
    return borrows_list


def get_memory_borrow_info_from_borrownode(node, file_path="/home/mempooling-test/mem_info.json"):
    """
    只能查看到本节点(借入节点)的账本信息
    :param node:节点对象,不做特殊限制
    :param file_path: 账本信息写入的文件
    :return borrows_list:返回借入节点对应的账本信息中的borrows部分，数据类型为列表，列表元素数量可以有多个，元素为字典,
    字典的键值有borrowLocalNuma、borrowMemId、borrowNode、borrowRemoteNuma、lentMemId、lentNode、lentNuma、lentSocketId、name、obmmDescHccs、size
    """
    basic.logger.info("开始查询内存账本")
    cmd = f"{MEM_INFO_PATH} > {file_path}"
    basic.run(node, cmd, timeout=20)
    basic.run(node, f"sync {file_path}", timeout=15)
    basic.run(node, f"cat {file_path}", timeout=15)
    borrows_list = mempooling.json2dict(node, jsonfile_path=file_path)['borrows']
    return borrows_list


def check_environment(nodes):
    for node in nodes:
        basic.run(node, "numastat -cvm")
        try:
            get_memory_borrow_info_from_borrownode(node)
        except Exception as e:
            basic.logger.error("查询节点的账本信息时发生异常")


def set_anti_affinity(node, affinity_set):
    """
    根据需要设置节点的反亲和性，返回设置结果的返回码
    :param node: 设置反亲和性的节点
    :param affinity_set: 反亲和性节点设置入参，例如：{1: [], 2: [], 3: [], 4: []}
    :return: 本次设置反亲和性的返回码，数据类型int，例如：200/500
    """
    affinity_set_str = json.dumps(affinity_set)
    cmd = f"python3 /home/mempooling-test/sdk/call_virt.py call_anti_affinity '{affinity_set_str}'"
    ret = basic.run(node, cmd, timeout=300).stdout
    return int([x for x in ret.splitlines() if x.strip()][-1])


def get_peer_socket_id(node, native_node_id, native_socket_id, target_node_id):
    """
    根据传入的本地节点id和本地节点socket_id获取目标节点对应的同平面socket_id
    :param node:本地节点
    :param native_node_id:本地节点id
    :param native_socket_id:本地节点socket_id
    :param target_node_id:目标节点id
    :return:目标节点对应同平面socket_id，没有则返回-1
    """
    ret = basic.run(node, f"ubsectl display topo -t cpu | grep \"{native_node_id}/{native_socket_id}\" | grep \"{target_node_id}/\"")
    if ret.rc != 0:
        return -1
    line = ret.stdout.strip().split()[0].split("-")
    for ans in line:
        if f"{target_node_id}/" in ans:
            return int(ans.split("/")[1])
    return -1


def function_vm_info(node, file_path=SDK_RESPONSE_PATH + "vm_info.json", timeout=20):
    """
    指定节点调用vm信息查询接口
    """
    vm_info_json_dict = {}
    sys.rm(node, file_path)
    vm_info_query = f'''python3 /home/mempooling-test/sdk/call_virt.py call_get_vm_info "" {file_path}'''
    ret = basic.run(node, vm_info_query, timeout=timeout).stdout
    code = int([x for x in ret.splitlines() if x.strip()][-1])
    if code == 200:
        basic.run(node, f"sync {file_path}", timeout=15)
        basic.run(node, f"cat {file_path}", timeout=15)
        vm_info_json_dict = mempooling.json2dict(node, file_path)
    return code, vm_info_json_dict


def function_node_info(node, file_path=SDK_RESPONSE_PATH + "node_info.json", timeout=20):
    """
    指定节点调用numa信息查询接口
    """
    node_info_json_dict = {}
    sys.rm(node, file_path)
    node_info_query = f'''python3 /home/mempooling-test/sdk/call_virt.py call_get_node_info "" {file_path}'''
    ret = basic.run(node, node_info_query, timeout=timeout).stdout
    code = int([x for x in ret.splitlines() if x.strip()][-1])
    if code == 200:
        basic.run(node, f"sync {file_path}", timeout=15)
        basic.run(node, f"cat {file_path}", timeout=15)
        node_info_json_dict = mempooling.json2dict(node, file_path)
    return code, node_info_json_dict
