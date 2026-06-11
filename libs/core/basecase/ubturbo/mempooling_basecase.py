#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

"""MempoolingBaseCase - Base class for ubturbo MemPooling test cases.

Migrated from legacy lib/basecase/MempoolingBaseCase.py
Integrated with libs.core.basecase.ubturbo.env_topo.EnvTopo.

CRITICAL: This class NO LONGER has __init__ method.
pytest cannot collect test classes with __init__ (even with default args).

Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
"""

import logging
import pytest
import time
from collections import namedtuple
from typing import Any, Dict, List

from libs.core.basecase.ubturbo.env_topo import EnvTopo
from libs.ubturbo.api import system
from libs.ubturbo.common import basic, env, connect
import libs.ubturbo.api.mempooling as mempooling
import libs.ubturbo.api.rack_manager as rack_manager
import libs.ubturbo.api.docker as docker
import libs.ubturbo.api.sysSentry as sysSentry
import libs.ubturbo.api.os_turbo as os_turbo
import libs.ubturbo.api.numa as numa
import libs.ubturbo.api.mempooling_api as api
from libs.ubturbo.model import libvirt
from libs.ubturbo.model.libvirt import TempVirtualMachine, TempVMInfo

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_mempooling_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入MempoolingBaseCase外部依赖参数.
    
    只对MempoolingBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase
    if not isinstance(instance, MempoolingBaseCase):
        return
    
    # EnvTopo parameters (already injected by inject_env_topo_dependencies)
    # Add Mempooling-specific parameters
    
    # State variables
    instance.simulation_host = None
    instance.power_off_flag = False
    instance.fault_nodes_list = []
    
    # Computed parameters (require nodemaster from EnvTopo)
    if instance.nodemaster:
        instance.num_of_local_numas = numa.get_numa_count_with_cpu(instance.nodemaster)
        instance.socket = numa.get_socket_ids(instance.nodemaster)
        instance.socket2numa, instance.numa2socket = numa.match_socket_numa(instance.nodemaster)
        
        # Node mappings (only for 4-node configuration)
        if len(instance.nodes) == 4:
            instance.getNode = {
                0: instance.nodemaster,
                1: instance.nodeagent,
                2: instance.nodeagent02,
                3: instance.nodeagent03
            }
            instance.getNodeName = {
                instance.nodemaster: 0,
                instance.nodeagent: 1,
                instance.nodeagent02: 2,
                instance.nodeagent03: 3
            }
        else:
            instance.getNode = {}
            instance.getNodeName = {}
    else:
        instance.num_of_local_numas = 0
        instance.socket = []
        instance.socket2numa = {}
        instance.numa2socket = {}
        instance.getNode = {}
        instance.getNodeName = {}
    
    logger.info(f"MempoolingBaseCase initialized: {instance.num_of_local_numas} local NUMAs, class={instance.__class__.__name__}")


class MempoolingBaseCase(EnvTopo):
    """Base class for ubturbo MemPooling tests.
    
    继承 EnvTopo，提供内存池化测试的公共方法和初始化。
    
    提供方法：
    - borrow_from_same_plane(): 同平面借用执行
    - create_vm_object(): 创建临时虚拟机对象
    - alloc_hugePage(): 分配大页内存
    - bmc_by_ra(): BMC下电事件处理
    - panic(): 节点panic处理
    """
    
    simulation_host: Any = None
    power_off_flag: bool = False
    fault_nodes_list: List[Any] = []
    num_of_local_numas: int = 0
    socket: List[int] = []
    socket2numa: Dict[int, List[int]] = {}
    numa2socket: Dict[int, int] = {}
    getNode: Dict[int, Any] = {}
    getNodeName: Dict[Any, int] = {}

    def preTestCase(self):
        basic.logger.tcStep("前处理：清理虚机、恢复各numa大页数为0、查询主从节点")
        for node in self.nodes:
            system.rm(node, f"{mempooling.REMOTE_WORK_PATH}/response.json")
            mempooling.clean_config_file(node)
            libvirt.TempVirtualMachine.clear_all(node)
            mempooling.set_hugePage_all_numa(node, size=0)
            basic.run(node, "numastat -cvm")
        basic.logger.tcStep("通过ubsectl指令查询主节点（代称nodeA）、备节点")
        rack_manager.wait_for_master_consistency(self.nodes)
        # 查询主节点
        master_node = rack_manager.query_master_standby_status(self.nodemaster, 'master')
        basic.logger.info(f"master：{master_node}")
        # 查询备节点
        standby_node = rack_manager.query_master_standby_status(self.nodemaster, 'standby')
        basic.logger.info(f"standby：{standby_node}")

        A = int(master_node) - 1
        B = int(standby_node) - 1
        basic.logger.info(f"主节点为Node{A},备节点为Node{B}")

        basic.logger.tcStep("检查白名单配置，重置反亲和性")
        for node in self.nodes:
            basic.run(node, 'cat /etc/ubse/ubse.conf | grep provider=')
            basic.run(node, 'cat /etc/ubse/ubse.conf | grep group=')
            basic.run(node, 'cat /etc/ubse/ubse.conf | grep obmm.memory.block.size=')
        mempooling.reset_anti_affinity(self.nodes, self.nodemaster)

    def postTestCase(self):
        basic.logger.tcStep("后处理：销毁虚机、归还内存、重置节点反亲和性")
        basic.logger.info('判断节点的mxe服务是否启动，没有启动则重启')
        for node in self.nodes:
            if rack_manager.check_mxe(node) is not True:
                rack_manager.activate_rack_manager(node)
        rack_manager.wait_for_master_consistency(self.nodes)
        for node in self.nodes:
            basic.run(node, "numastat -cvm")
            mempooling.clean_config_file(node)
            libvirt.TempVirtualMachine.clear_all(node)
            basic.run(node, "numastat -cvm")
        mem_return(self.nodes)
        mempooling.reset_anti_affinity(self.nodes, self.nodemaster)

    def actions_after_restart_env(self):
        basic.logger.tcStep("关闭mxe、osturbo，启动sysSentry")
        rack_manager.wait_for_master_consistency(self.nodes)
        for node in self.nodes:
            basic.run(node, f"systemctl stop {rack_manager.SERVICE_NAME_SCBUS_DAEMON}", timeout=200)
            basic.run(node, f"systemctl stop {os_turbo.SERVICE_NAME_OSTURBO_DAEMON}", timeout=200)
        for node in self.nodes:
            sysSentry.install_sySentry(node)

        basic.logger.tcStep("重启mxe、osturbo，等待mxe查主一致")
        for node in self.nodes:
            basic.run(node, f"systemctl start {os_turbo.SERVICE_NAME_OSTURBO_DAEMON}", timeout=200)
        for node in self.nodes:
            basic.run(node, f"systemctl start {rack_manager.SERVICE_NAME_SCBUS_DAEMON}", timeout=200)
        for node in self.nodes:
            rack_manager.wait_until_mxe_active(node)
        rack_manager.wait_for_master_consistency(self.nodes)

        basic.logger.tcStep("注入内存碎片模式")
        if mempooling.check_memborrow_mode(self.nodes):
            basic.logger.info("mxe启动成功，内存碎片模式")
        else:
            raise Exception("mxe启动有误，非内存碎片模式")

        # 关闭ubs-scheduler-agent.service服务
        basic.logger.tcStep("关闭ubs-scheduler-agent.service服务")
        for node in self.nodes:
            ret = basic.run(node, "systemctl stop ubs-scheduler-agent.service", timeout=600)

    def borrow_from_same_plane(self, src_nodeid, src_planeid, src_numa_index, dest_nodeid, dest_numa_index,
                               mem_size_kb):
        """
        同平面借用执行,仅适用于一次借用执行只有一个borrowid的情况
        :param src_nodeid:借入节点id，为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param src_planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :param src_numa_index:表示某节点{src_nodeid}的某平面{src_planeid}的numa_list中的序列号{src_numa_index},数据类型为数值
        :param dest_nodeid:借出节点id，为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param dest_numa_index:表示与节点{src_nodeid}的平面{src_planeid}同平面的|某节点{dest_nodeid}的numa_list中的序列号{dest_numa_index},数据类型为数值
        :param mem_size_kb:借用内存大小，单位kb
        :return res_tuple:返回元组，元素依次为接口返回值、借出方同平面numaid、借入方（拓扑成员）、借出方（拓扑成员）
        """
        lent_numaid = self.get_same_plane_numaid(src_nodeid=src_nodeid, src_planeid=src_planeid,
                                                 dest_nodeid=dest_nodeid, src_numa_index=src_numa_index,
                                                 dest_numa_index=dest_numa_index)
        borrow_numaid = self.get_numa(planeid=src_planeid, nodeid=src_nodeid, index=src_numa_index)
        borrow_socket = mempooling.get_socketid(self.getNode.get(src_nodeid), borrow_numaid)
        lent_socket = mempooling.get_socketid(self.getNode.get(dest_nodeid), lent_numaid)
        destparam = api.create_destparam([(dest_nodeid, lent_socket, 1, [lent_numaid], [mem_size_kb])])
        borrow_execute_input_parameter = api.BorrowExecuteInputParameter(srcnid=src_nodeid, srcnumaid=borrow_numaid,
                                                                         srcsocketid=borrow_socket, destparam=destparam)
        ret = api.function_borrow_execute(self.getNode.get(src_nodeid), borrow_execute_input_parameter)
        res_tuple = (ret, lent_numaid)
        return res_tuple

    def get_same_plane_numaid(self, src_nodeid, src_planeid, src_numa_index, dest_nodeid, dest_numa_index):
        """
        获得节点{dest_nodeid}的第{dest_index}个numa的numaid，与节点{src_nodeid}的平面{src_planeid}的第{src_index}个numa同平面
        :param src_nodeid:借入节点id，为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param src_planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :param src_numa_index:表示某节点{src_nodeid}的某平面{src_planeid}的numa_list中的序列号{src_numa_index},数据类型为数值
        :param dest_nodeid:借出节点id，为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param dest_numa_index:表示与节点{src_nodeid}的平面{src_planeid}同平面的|某节点{dest_nodeid}的numa_list中的序列号{dest_numa_index},数据类型为数值
        """
        src_member = super().create_member_of_borrow_topology(nodeid=src_nodeid, index=src_numa_index,
                                                              planeid=src_planeid)
        dest_member = self.get_same_plane_topology_members_list_from_dest_nodeid(src_member, dest_nodeid)[
            dest_numa_index]
        dest_numaid = dest_member.numaId
        return dest_numaid

    def parse_borrowId_and_presentNumaId(self, node):
        """
        在单次借用执行后，解析借入节点上的response.json，获得borrowids与远端numaid，仅适用于一次借用执行只有一个borrowid的情况
        :param node:借入节点
        :return res_tuple:返回元组，元素依次为borrowids、远端numaid
        """
        api.check_environment(self.nodes)
        borrowids = api.parse_borrow_execute_response(node)
        presentNumaId = api.parse_presentnumaid_from_borrow_execute_response(node)[0]
        res_tuple = (borrowids, presentNumaId)
        return res_tuple

    def get_remote_numaIds_list(self, node):
        """
        获得节点的远端numaId列表
        """
        remote_numas_info_list = api.parse_node_remote_numa_info(node)
        remote_numaIds_list = []
        if remote_numas_info_list:
            for remote_numa_info in remote_numas_info_list:
                numaid = int(''.join(filter(str.isdigit, remote_numa_info.get("name"))))
                remote_numaIds_list.append(numaid)
        return remote_numaIds_list

    def get_new_remote_numaids_list(self, node, origin_numaid_list, expected_num_of_new_remote_numaid):
        """故障处理后，节点的新远端numaId列表"""
        remote_numas_info_list = api.parse_node_remote_numa_info(node)
        origin_numa_list = [f"Node {origin_numaid}" for origin_numaid in origin_numaid_list]
        new_remote_numas_info_list = [remote_numa_info for remote_numa_info in remote_numas_info_list if remote_numa_info.get("name") not in origin_numa_list]
        num_of_new_remote_numa = len(new_remote_numas_info_list)
        new_remote_numaid_list = []
        for i in range(num_of_new_remote_numa):
            new_remote_numa = new_remote_numas_info_list[i].get("name")
            new_remote_numaId = int(''.join(filter(str.isdigit, new_remote_numa)))
            new_remote_numaid_list.append(new_remote_numaId)
        basic.logger.info(f'新的远端numaid：{new_remote_numaid_list}')
        if num_of_new_remote_numa != expected_num_of_new_remote_numaid:
            raise Exception(f'预期新的远端numa数量为{expected_num_of_new_remote_numaid},异常：实际新的远端numa数量为{num_of_new_remote_numa}')
        return new_remote_numaid_list

    def bmc_by_ra(self, fault_node, valid_nodes_before_bmc_by_ra):
        """
        使用ra工具通过xalarm向ubse发送一次bmc下电事件
        :param fault_node:预期发生BMC下电事件的节点
        :param valid_nodes_before_bmc_by_ra:
        """
        master_node = rack_manager.query_master_standby_status(valid_nodes_before_bmc_by_ra[0], 'master')
        mempooling.execut_BMC_poweroff(fault_node)
        self.fault_nodes_list.append(fault_node)
        if master_node == str(self.getNodeName.get(fault_node) + 1):
            rack_manager.wait_for_master_consistency(self.nodes, origin_master_str=master_node, flag=True)
            mempooling.execut_BMC_poweroff(fault_node)
        valid_nodes_after_bmc_by_ra = [node for node in valid_nodes_before_bmc_by_ra if node not in [fault_node]]
        master_node = rack_manager.query_master_standby_status(valid_nodes_after_bmc_by_ra[0], 'master')
        return valid_nodes_after_bmc_by_ra

    def num_of_remote_numa(self, node):
        """获得节点的远端numa数量"""
        remote_numas_info_list = api.parse_node_remote_numa_info(node)
        num_of_remote_numa = len(remote_numas_info_list)
        return num_of_remote_numa

    def get_nodeid_and_node(self):
        # 查询主节点
        master_node_str = rack_manager.query_master_standby_status(self.nodemaster, 'master')
        # 查询备节点
        standby_node_str = rack_manager.query_master_standby_status(self.nodemaster, 'standby')
        A = int(master_node_str) - 1
        B = int(standby_node_str) - 1
        basic.logger.info(f"主节点为node{A},备节点为node{B}")
        nodeA = self.getNode.get(A)
        nodeB = self.getNode.get(B)
        nodeC = [node for node in self.nodes if node not in [nodeA, nodeB]][0]
        nodeD = [node for node in self.nodes if node not in [nodeA, nodeB]][1]
        C = self.getNodeName.get(nodeC)
        D = self.getNodeName.get(nodeD)
        basic.logger.info(f'A节点为node{A},B节点为node{B},C节点为node{C},D节点为node{D}')
        return [A, B, C, D, nodeA, nodeB, nodeC, nodeD]

    def panic(self, fault_node):
        basic.run(fault_node, "echo c > /proc/sysrq-trigger")
        cur_nodes = [node for node in self.nodes if node not in [fault_node]]
        rack_manager.wait_for_master_consistency(cur_nodes)
        api.check_environment(cur_nodes)
        return cur_nodes

    def get_numa_info_tuple(self, node, numaid):
        """以元组形式返回numa信息"""
        memTotal = api.parse_node_numa_attribute(node, numaid, "MemTotal")
        hugePageTotal = api.parse_node_numa_attribute(node, numaid, "HugePages_Total")
        hugePageFree = api.parse_node_numa_attribute(node, numaid, "HugePages_Free")
        return (memTotal, hugePageTotal, hugePageFree)

    NodeNumaAttributeInfo_namedtuple = namedtuple("NodeNumaAttributeInfo_namedtuple", ["node", "numaid", "attribute"])
    VmNumaId_namedtuple = namedtuple("VmNumaId_namedtuple", ["node", "vm_pid", "numaid"])

    def batch_parse_node_numa_attribute(self, node_numa_attribute_tuplelist):
        """批量解析某节点{info.node}上某个numa{info.numaid}的某属性值{info.attribute}，并将解析得到的数值放入列表中返回"""
        res = []
        for node_numa_attribute_tuple in node_numa_attribute_tuplelist:
            info = self.NodeNumaAttributeInfo_namedtuple(*node_numa_attribute_tuple)
            node_numa_attribute = api.parse_node_numa_attribute(info.node, info.numaid, info.attribute)
            res.append(node_numa_attribute)
        return res

    def batch_parse_vm_numa_huge(self, vm_numaid_tuplelist):
        """批量解析某节点{info.node}上的某虚机{info.vm_pid}的某个numa{info.numaid}的huge，并将解析得到的数值放入列表中返回"""
        res = []
        for vm_numaid_tuple in vm_numaid_tuplelist:
            info = self.VmNumaId_namedtuple(*vm_numaid_tuple)
            vm_numaid_huge = numa.get_huge_of_specific_numa_on_vm(info.node, info.vm_pid, info.numaid)
            res.append(vm_numaid_huge)
        return res

    def recover_ub_status(self, host_node,
                          ub_node_list,
                          container_name: str = 'qemu-ub',
                          stop_cmd: str = 'sh -c "bash /workdir/scripts/stop.sh"',
                          start_cmd: str = '',
                          timeout: int = 30 * 60):
        docker.exec_out_of_container(host_node, container_name, stop_cmd)
        basic.wait_until(lambda: int(docker.exec_out_of_container(host_node, container_name, 'ps -ef | grep qemu-system-aarch64 | wc -l').stdout.strip()) == 0,
                         timeout=1300)
        basic.logger.info(f"仿真环境已完成停止")
        if start_cmd == '':
            start_cmd = f'sh -c "bash /workdir/scripts/start.sh -n 4 --extra-disk=0-3:sata:1:500 --ram=128:numa:{self.num_of_local_numas},8  --extra-nic=1 --mem-ipc=2 --tcg-accel --2die --mesh-type=1"'
        docker.exec_out_of_container(host_node, container_name, start_cmd)
        for node in ub_node_list:
            mempooling.wait_ub_recover(node, timeout=15 * 60)

    def create_vm_object(self, node, nodeid, planeid, numa_index, vm_index, init_login=True, remote=False):
        """
        创建临时的虚机对象
        :param node:创建虚机的节点对象
        :param nodeid:为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :param numa_index:表示某节点{nodeid}的某平面{planeid}的numa_list中的序列号{index},数据类型为数值
        :param vm_index:每个numa提前准备了三个虚机的xml，表示创建第{vm_index}的虚机
        :param init_login:True表示创建虚机对象时配置免密登录，False表示用户需要自行配置免密登录
        :param remote:默认False,使用本地内存创建虚机
        """
        numa2vm = {0: ['A', 'B', 'C'], 1: ['D', 'E', 'F'], 2: ['G', 'H', 'I'], 3: ['J', 'K', 'L']}
        numaid = self.get_numa(planeid, nodeid, numa_index)
        vm_id = numa2vm.get(numaid)[vm_index]

        hardware_str = ''
        if env.get_env_type(self.nodemaster) == env.UB_hardware:
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
            api.check_vm_function(vm)
        return vm

    def set_auto_xml(self, node, xml_path, vm_id, node_ids, cpus, num_of_cpu, start_index_of_cpu):
        """
        具体修改xml
        :param node: 设置xml的节点
        :param xml_path: xml的绝对路径
        :param vm_id: 虚机名称
        :param node_ids: 虚机所在node_id列表
        :param cpus: 虚机所在cpu列表
        :param num_of_cpu: 虚机的cpu数目
        :param start_index_of_cpu: 虚机绑定的cpu在该cpu列表中的起始位置
        """
        if len(node_ids) <= 0 or len(cpus) <= 0:
            raise Exception("传入参数有误！")
        if num_of_cpu <= 0 or start_index_of_cpu < 0:
            raise Exception("传入参数有误！")
        basic.run(node,
                  f"sed -i 's/<memory mode=\"strict\" nodeset=\"[^\"]*\"/<memory mode=\"strict\" nodeset=\"{node_ids[0]}\"/' {xml_path}")
        start = int(basic.run(node, f"grep -n 'memory mode' {xml_path}").stdout.strip().split(':')[0])
        for i in range(1, len(node_ids)):
            basic.run(node, f'sed -i "{start}a\ \   <memory mode=\"strict\" nodeset=\"{node_ids[i]}\" />" {xml_path}')
            start += 1

        basic.run(node,
                  f"sed -i 's/<vcpupin vcpu=\"0\" cpuset=\"[^\"]*\"/<vcpupin vcpu=\"0\" cpuset=\"{cpus[start_index_of_cpu]}\"/' {xml_path}")
        start = int(basic.run(node, f"grep -n 'vcpupin vcpu' {xml_path}").stdout.strip().split(':')[0])
        vcpu_start = 1
        for i in range(start_index_of_cpu + 1, min(start_index_of_cpu + num_of_cpu, len(cpus))):
            basic.run(node,
                      f'sed -i "{start}a\ \   <vcpupin vcpu=\"{str(vcpu_start)}\" cpuset=\"{cpus[i]}\" />" {xml_path}')
            start += 1
            vcpu_start += 1
        basic.run(node,
                  f"sed -i 's/<emulatorpin cpuset=\"[^\"]*\"/<emulatorpin cpuset=\"{cpus[0]}-{cpus[-1]}\"/' {xml_path}")

        basic.run(node, f"sed -i 's|<name>mempooling-A</name>|<name>mempooling-{vm_id}</name>|' {xml_path}")
        basic.run(node,
                  f"sed -i 's|openEuler-22.03-LTS-SP1-aarch64-A|openEuler-22.03-LTS-SP1-aarch64-{vm_id}|' {xml_path}")

    def set_vml(self, node, node_id, filename_xml, vm_id, plane_id, index_of_numa, start_index_of_cpu, num_of_cpu):
        """
        根据具体环境中的numa节点对应的cpu修改xml
        :param node: 设置xml的节点
        :param node_id: 虚机创建节点id
        :param filename_xml: xml的绝对路径
        :param vm_id: 虚机名称
        :param plane_id: 虚机所在平面id
        :param index_of_numa: 虚机所在numa的索引
        :param start_index_of_cpu: 虚机绑定的cpu在该soket中的起始位置
        :param num_of_cpu: 虚机的cpu数目
        """
        numa_id = self.get_numa(plane_id, node_id, index_of_numa)
        cpu_to_numa = {}
        cpus = []
        ret = basic.run(node, f'''lscpu | grep \"NUMA node{numa_id} CPU(s):\"''')
        nums = ret.stdout.strip().split()[-1].split("-")
        for i in range(int(nums[0]), int(nums[-1]) + 1):
            cpus.append(i)
            cpu_to_numa[i] = numa_id
        if start_index_of_cpu >= len(cpus) or start_index_of_cpu + num_of_cpu > len(cpus):
            raise Exception("传入平面及numa所属cpu无法满足对应创建虚机请求")
        node_ids = {cpu_to_numa.get(cpus[start_index_of_cpu], "无该cpu对应的numa")}
        for i in range(start_index_of_cpu, start_index_of_cpu + num_of_cpu):
            node_ids.add(cpu_to_numa.get(cpus[i], "无该cpu对应的numa"))
        node_ids = list(node_ids)
        if basic.run(node, f"cat {filename_xml}").rc == 0:
            basic.run(node, f"rm -f {filename_xml}")
        basic.run(node, f"cp /home/mempooling-test/xml/mempooling-A-ub.xml {filename_xml}")
        self.set_auto_xml(node, filename_xml, vm_id, node_ids, cpus, num_of_cpu, start_index_of_cpu)

    def create_vm_object_auto_set_cpu(self, node, node_id, vm_id="AA", plane_id=0, index_of_numa=0,
                                      start_index_of_cpu=0, num_of_cpu=1, init_login=True, remote=False):
        """
        创建临时的虚机对象
        :param node: 虚机创建所在节点
        :param node_id: 虚机创建所在节点id，默认1
        :param vm_id: 虚机名称，默认"AA"
        :param plane_id: 虚机所在平面id，默认0平面
        :param index_of_numa: 虚机所在numa的位置索引，默认0
        :param start_index_of_cpu: 虚机绑定的cpu在该其对应numa中的起始位置，默认为0
        :param num_of_cpu: 虚机的cpu数目，默认为1
        :param init_login:True表示创建虚机对象时配置免密登录，False表示用户需要自行配置免密登录
        :param remote:默认False,使用本地内存创建虚机
        """
        hardware_str = ''
        if env.get_env_type(self.nodemaster) == env.UB_hardware:
            hardware_str = 'hardware_'

        filename_xml = f'/home/mempooling-test/{hardware_str}xml/mempooling-{vm_id}-ub.xml'
        if remote:
            filename_xml = f'/home/mempooling-test/{hardware_str}xml/remote-mempooling-{vm_id}-ub.xml'
        self.set_vml(node, node_id, filename_xml, vm_id, plane_id, index_of_numa, start_index_of_cpu, num_of_cpu)

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
            api.check_vm_function(vm)
        return vm

    def alloc_hugePage(self, node, numa_id, huge_MB, huge_2M=True):
        """
        给某节点{node}的某numa{numa_id}分配大页，内存总量为{huge_MB},大页粒度为2M或512M
        :param node:节点对象
        :param numaid：数据类型为int
        :param huge_MB:数据类型为int,为待分配大页的内存总量
        :param huge_2M:如果为True，表示分配2M大页；为False,表示分配512M大页
        """
        # 分配大页
        command = f"timeout 55s echo {huge_MB // 2} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
        if not huge_2M:
            command = f"timeout 55s echo {huge_MB // 512} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-524288kB/nr_hugepages"
        basic.run(node, 'timeout 55s echo 3 > /proc/sys/vm/drop_caches', timeout=120)
        basic.run(node, command, timeout=180)
        basic.run(node, 'numastat -cvm')

    def switch_must_same_plane(self, target_set=True):
        key_value = "true" if target_set else "false"
        for node in self.nodes:
            system.update_conf_file(node, rack_manager.RACK_PLUGIN_CONF_PATH + rack_manager.MEMPOOLNG_PLUGIN_CONF,
                                    "rmrs.fragment.mustSamePlane", key_value)
        rack_manager.restart_cluster_scbus(self.nodes, sync=False)
        rack_manager.wait_master_consistent(self.nodes)


def mem_return(nodes, timeout=30 * 60):
    for node_id in range(len(nodes)):
        api.function_return(nodes[node_id], node_id, timeout=timeout)
        basic.run(nodes[node_id], "numastat -cvm")

