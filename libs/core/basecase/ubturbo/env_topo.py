#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

"""EnvTopo - Base class for ubturbo MemPooling test cases with topology management.

Migrated from legacy lib/basecase/EnvTopo.py
Integrated with libs.core.basecase.ubturbo.at_basecase.ATBaseCase.

CRITICAL: This class NO LONGER has __init__ method.
pytest cannot collect test classes with __init__ (even with default args).

Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
"""

import copy
import logging
import pytest
from typing import Any, Dict, List

from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
import libs.ubturbo.api.numa as numa
import libs.ubturbo.api.mempooling as mempooling
import libs.ubturbo.api.rack_manager as rack_manager
from libs.ubturbo.common import basic
from libs.ubturbo.common.string_utils import STR_ENTER

logger = logging.getLogger(__name__)

# Global cache for topology data (shared across test instances)
_sock_node_numa_cache: Dict[int, Dict[int, List[int]]] = None
_topology_cache: Dict[Any, List[Any]] = None


@pytest.fixture(autouse=True)
def inject_env_topo_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入EnvTopo外部依赖参数.
    
    只对EnvTopo及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.ubturbo.env_topo import EnvTopo
    if not isinstance(instance, EnvTopo):
        return
    
    # ATBaseCase parameters (already injected by inject_at_basecase_dependencies)
    # Just ensure topology-specific parameters are set
    
    # Initialize topology cache if needed
    global _sock_node_numa_cache, _topology_cache
    
    # Hardcoded constants
    instance.pool_size = 8 * 1024
    
    # Computed parameters (require nodemaster from ATBaseCase)
    if instance.nodemaster:
        instance.num_of_sock = len(numa.get_socket_ids(instance.nodemaster))
        instance.num_of_numa = numa.get_numa_count_with_cpu(instance.nodemaster)
        
        # Initialize topology cache
        if _sock_node_numa_cache is None:
            _sock_node_numa_cache = instance._get_sock_node_numa()
        instance.sock_node_numa = _sock_node_numa_cache
        
        if _topology_cache is None:
            _topology_cache = instance._get_borrow_topology()
        instance.topology = _topology_cache
    else:
        instance.num_of_sock = 0
        instance.num_of_numa = 0
        instance.sock_node_numa = {}
        instance.topology = {}
    
    logger.info(f"EnvTopo initialized: {instance.num_of_sock} sockets, {instance.num_of_numa} NUMAs, class={instance.__class__.__name__}")


class MemBerOfBorrowTopology:
    """
    该类的对象表示拓扑信息中的成员，成员属性有nodeId、planeId、numaId
    :nodeId:为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
    :planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
    :numaId:表示numa{numaId},数据类型为数值
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

    def __repr__(self):
        return f"MemBerOfBorrowTopology({self.nodeId}, {self.planeId}, {self.numaId})"


class EnvTopo(ATBaseCase):
    """Base class for ubturbo MemPooling tests with topology management.
    
    继承 ATBaseCase，提供NUMA拓扑信息管理和借用拓扑计算功能。
    
    节点配置和拓扑信息通过fixture注入，无需__init__方法。
    
    提供方法：
    - get_numa(): 获取指定平面、节点、索引的NUMA ID
    - get_numa_list(): 获取指定平面、节点的NUMA列表
    - create_member_of_borrow_topology(): 创建拓扑成员对象
    - get_same_plane_topology_members_list(): 获取同平面拓扑成员列表
    """
    
    pool_size: int = 8 * 1024  # Pool size constant (MB)

    def slotid_to_nodeid(self, slotid):
        """
        slotid与nodeid映射
        比如：node0的slotid为"1",nodeid为0
        """
        if slotid in ["1", "2", "3", "4"]:
            node_dict = {"1": 0, "2": 1, "3": 2, "4": 3}
            return node_dict.get(slotid)
        else:
            raise Exception(f"槽号错误，当前为{slotid}，查看topo信息指令：sudo -u ubse ubsectl display topo -t cpu")

    def get_same_planeid_numa_dic(self, planeid, nodeid):
        """
        获得与某节点{nodeid}某平面{planeid}同平面的其他各节点的numa列表，数据结构为字典
        :param planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :param nodeid:为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :return same_planeid_numa_dic:获得与某节点{nodeid}某平面{planeid}同平面的其他各节点的numa列表，数据结构为字典
        比如，返回与node0的numa0同平面的其他各节点的numa列表：
        {1: [2, 3], 2: [0, 1], 3: [2, 3]}
        可以理解为
        {node1_id: numaid_list, node2_id: numaid_list, node3_id: numaid_list}
        """
        same_planeid_numa_dic = copy.deepcopy({k: v for k, v in self.sock_node_numa.get(planeid).items() if k != nodeid})
        return same_planeid_numa_dic

    def get_numa(self, planeid: object, nodeid: object, index: object) -> object:
        """
        以node0的numa0作为plane0=0为标准，获得节点{nodeid}上某平面{planeid}的numa列表，并通过序列号{index}获得numaid
        :param planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :param nodeid:为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param index:numa列表的序列号，数据类型int
        :return numaid:返回numaid，数据类型int
        """
        numaid = self.sock_node_numa.get(planeid).get(nodeid)[index]
        return numaid

    def get_numa_list(self, planeid, nodeid):
        """
        以node0的numa0作为plane0=0为标准，获得节点{nodeid}上某平面{planeid}的numa列表
        :param planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :param nodeid:为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :return numaid_list:返回numaid列表，元素数据类型为int
        """
        numaid_list = copy.deepcopy(self.sock_node_numa.get(planeid).get(nodeid))
        return numaid_list

    def del_index_of_numa_list(self, planeid, nodeid, removed_index):
        numaid_list = self.get_numa_list(planeid=planeid, nodeid=nodeid)
        del numaid_list[removed_index]
        return numaid_list

    def del_elem_in_numa_list(self, planeid, nodeid, removed_elem):
        numaid_list = self.get_numa_list(planeid=planeid, nodeid=nodeid)
        numaid_list.remove(removed_elem)
        return numaid_list

    def create_member_of_borrow_topology(self, nodeid, index, planeid):
        """
        创建对象，表示拓扑信息中的成员
        :param nodeId:为"Node0"、"Node1"、"Node2"、"Node3"的数字位,数据类型为数值
        :param index:表示某节点{nodeid}的某平面{planeid}的numa_list中的序列号{index},数据类型为数值
        :param planeid:有0、1，表示逻辑上的平面，以node0的numa0所在平面为0为标准，数据类型为数值
        :return:返回拓扑信息中的成员
        """
        numaid = self.get_numa(planeid, nodeid, index)
        borrow_topology = MemBerOfBorrowTopology(nodeid, planeid, numaid)
        return borrow_topology

    def get_same_plane_topology_members_list(self, src_member_of_borrow_topology):
        """
        获得与节点{src_member_of_borrow_topology.nodeId}的numa{src_member_of_borrow_topology.numaId}同平面的拓扑成员列表
        :src_member_of_borrow_topology:数据类型为类MemBerOfBorrowTopology
        :return same_plane_topology_members_list:返回同平面的拓扑成员列表
        """
        same_plane_topology_members_list = copy.deepcopy(self.topology.get(src_member_of_borrow_topology))
        return same_plane_topology_members_list

    def get_same_plane_topology_members_list_from_dest_nodeid(self, src_member_of_borrow_topology, dest_nodeid):
        """
        获得与节点{src_member_of_borrow_topology.nodeId}的numa{src_member_of_borrow_topology.numaId}同平面的某个节点{dest_nodeid}的拓扑成员列表
        :src_member_of_borrow_topology:数据类型为类MemBerOfBorrowTopology
        :return same_plane_topology_members_list:返回同平面的某个节点{dest_nodeid}的拓扑成员列表
        """
        same_plane_topology_members_list = self.get_same_plane_topology_members_list(src_member_of_borrow_topology)
        same_plane_topology_members_list_from_dest_nodeid = [d for d in same_plane_topology_members_list if d.nodeId == dest_nodeid]
        return same_plane_topology_members_list_from_dest_nodeid

    def _get_sock(self):  # 前缀 `_` 表示“私有”
        """
        获得各节点同平面的socketid，数据结构为
        {
        0: {0: 36, 1: 36, 2: 37, 3: 38},
        1: {0: 216, 1: 216, 2: 216, 3: 216}
        }
        可以理解为
        {
        plane0: {node0_id: socketid, node1_id: socketid, node2_id: socketid, node3_id: socketid},
        plane1: {node0_id: socketid, node1_id: socketid, node2_id: socketid, node3_id: socketid}
        }
        """
        plane0 = 0
        plane1 = 1
        node0_id = 0
        sock_info = {plane0: {}, plane1: {}}  # 这里的键值表示不同平面的抽象，我们不关心socket值具体是什么，
        rack_manager.wait_for_master_consistency(self.nodes)  # 检查环境正常
        valid_cputopo_list = rack_manager.get_valid_cputopo_list(self.nodemaster)
        node0_socket0_id, node0_socket1_id = numa.get_socket_ids(self.nodemaster)
        sock_info.get(plane0)[node0_id] = node0_socket0_id
        sock_info.get(plane1)[node0_id] = node0_socket1_id
        for valid_cputop in valid_cputopo_list:
            if valid_cputop.get('node_slotId') == mempooling.node_to_num(node0_id) and int(valid_cputop.get('socket')) == node0_socket0_id:
                sock_info.get(plane0)[self.slotid_to_nodeid(valid_cputop.get('peer_node_slotId'))] = int(valid_cputop.get('peer-socket'))
            if valid_cputop.get('peer_node_slotId') == mempooling.node_to_num(node0_id) and int(valid_cputop.get('peer-socket')) == node0_socket0_id:
                sock_info.get(plane0)[self.slotid_to_nodeid(valid_cputop.get('node_slotId'))] = int(valid_cputop.get('socket'))
            if valid_cputop.get('node_slotId') == mempooling.node_to_num(node0_id) and int(valid_cputop.get('socket')) == node0_socket1_id:
                sock_info.get(plane1)[self.slotid_to_nodeid(valid_cputop.get('peer_node_slotId'))] = int(valid_cputop.get('peer-socket'))
            if valid_cputop.get('peer_node_slotId') == mempooling.node_to_num(node0_id) and int(valid_cputop.get('peer-socket')) == node0_socket1_id:
                sock_info.get(plane1)[self.slotid_to_nodeid(valid_cputop.get('node_slotId'))] = int(valid_cputop.get('socket'))
        basic.logger.info(f"sock_info:{sock_info}")
        return sock_info

    def _get_sock_node_numa(self):  # 前缀 `_` 表示“私有”
        """
        获得各节点同平面的numaid_list，数据结构为
        {
        0: {0: [0, 1], 1: [2, 3], 2: [0, 1], 3: [2, 3]},
        1: {0: [2, 3], 1: [0, 1], 2: [2, 3], 3:[1, 2]}}
        可以理解为
        {
        plane0: {node0_id: numaid_list, node1_id: numaid_list, node2_id: numaid_list, node3_id: numaid_list},
        plane1: {node0_id: numaid_list, node1_id: numaid_list, node2_id: numaid_list, node3_id: numaid_list}
        }
        """
        plane0 = 0
        plane1 = 1
        sock_info = self._get_sock()
        sock_node_numa_dic = {plane0: {}, plane1: {}}
        local_numa_counts = numa.get_numa_count_with_cpu(self.nodemaster)
        numa_per_socket = local_numa_counts // self.num_of_sock
        numa_list0 = list(range(0, numa_per_socket))
        numa_list1 = list(range(numa_per_socket, local_numa_counts))
        for nodeid, _ in enumerate(self.nodes):
            sock_node_numa_dic.get(plane0)[nodeid] = []
            sock_node_numa_dic.get(plane1)[nodeid] = []
            try:
                socket_cpu0 = int(basic.run(self.nodes[nodeid], 'cat /sys/devices/system/cpu/cpu0/topology/physical_package_id').stdout.strip())
            except Exception as e:
                raise Exception(f"获取 socket_cpu0 失败: {e}") from e
            if socket_cpu0 == sock_info.get(plane0).get(nodeid):
                sock_node_numa_dic.get(plane0)[nodeid] = numa_list0
                sock_node_numa_dic.get(plane1)[nodeid] = numa_list1
            else:
                sock_node_numa_dic.get(plane0)[nodeid] = numa_list1
                sock_node_numa_dic.get(plane1)[nodeid] = numa_list0
        basic.logger.info(f"sock_node_numa:{sock_node_numa_dic}")
        return sock_node_numa_dic

    def _get_borrow_topology(self, fm="1DFM"):  # 前缀 `_` 表示“私有”
        """
        获得MatrixServer的1D FM组网拓扑，数据类型为字典；
        字典key的数据类型为MemBerOfBorrowTopology类，
        字典value的数据类型为列表，列表元素为MemBerOfBorrowTopology类对象
        4节点4numa全量topo信息打印：
        {
        MemBerOfBorrowTopology(0, 0, 0): [MemBerOfBorrowTopology(1, 0, 0), MemBerOfBorrowTopology(1, 0, 1), MemBerOfBorrowTopology(2, 0, 0), MemBerOfBorrowTopology(2, 0, 1), MemBerOfBorrowTopology(3, 0, 0), MemBerOfBorrowTopology(3, 0, 1)],
        MemBerOfBorrowTopology(0, 0, 1): [MemBerOfBorrowTopology(1, 0, 0), MemBerOfBorrowTopology(1, 0, 1), MemBerOfBorrowTopology(2, 0, 0), MemBerOfBorrowTopology(2, 0, 1), MemBerOfBorrowTopology(3, 0, 0), MemBerOfBorrowTopology(3, 0, 1)],
        MemBerOfBorrowTopology(1, 0, 0): [MemBerOfBorrowTopology(0, 0, 0), MemBerOfBorrowTopology(0, 0, 1), MemBerOfBorrowTopology(2, 0, 0), MemBerOfBorrowTopology(2, 0, 1), MemBerOfBorrowTopology(3, 0, 0), MemBerOfBorrowTopology(3, 0, 1)],
        MemBerOfBorrowTopology(1, 0, 1): [MemBerOfBorrowTopology(0, 0, 0), MemBerOfBorrowTopology(0, 0, 1), MemBerOfBorrowTopology(2, 0, 0), MemBerOfBorrowTopology(2, 0, 1), MemBerOfBorrowTopology(3, 0, 0), MemBerOfBorrowTopology(3, 0, 1)],
        MemBerOfBorrowTopology(2, 0, 0): [MemBerOfBorrowTopology(0, 0, 0), MemBerOfBorrowTopology(0, 0, 1), MemBerOfBorrowTopology(1, 0, 0), MemBerOfBorrowTopology(1, 0, 1), MemBerOfBorrowTopology(3, 0, 0), MemBerOfBorrowTopology(3, 0, 1)],
        MemBerOfBorrowTopology(2, 0, 1): [MemBerOfBorrowTopology(0, 0, 0), MemBerOfBorrowTopology(0, 0, 1), MemBerOfBorrowTopology(1, 0, 0), MemBerOfBorrowTopology(1, 0, 1), MemBerOfBorrowTopology(3, 0, 0), MemBerOfBorrowTopology(3, 0, 1)],
        MemBerOfBorrowTopology(3, 0, 0): [MemBerOfBorrowTopology(0, 0, 0), MemBerOfBorrowTopology(0, 0, 1), MemBerOfBorrowTopology(1, 0, 0), MemBerOfBorrowTopology(1, 0, 1), MemBerOfBorrowTopology(2, 0, 0), MemBerOfBorrowTopology(2, 0, 1)],
        MemBerOfBorrowTopology(3, 0, 1): [MemBerOfBorrowTopology(0, 0, 0), MemBerOfBorrowTopology(0, 0, 1), MemBerOfBorrowTopology(1, 0, 0), MemBerOfBorrowTopology(1, 0, 1), MemBerOfBorrowTopology(2, 0, 0), MemBerOfBorrowTopology(2, 0, 1)],
        MemBerOfBorrowTopology(0, 1, 2): [MemBerOfBorrowTopology(1, 1, 2), MemBerOfBorrowTopology(1, 1, 3), MemBerOfBorrowTopology(2, 1, 2), MemBerOfBorrowTopology(2, 1, 3), MemBerOfBorrowTopology(3, 1, 2), MemBerOfBorrowTopology(3, 1, 3)],
        MemBerOfBorrowTopology(0, 1, 3): [MemBerOfBorrowTopology(1, 1, 2), MemBerOfBorrowTopology(1, 1, 3), MemBerOfBorrowTopology(2, 1, 2), MemBerOfBorrowTopology(2, 1, 3), MemBerOfBorrowTopology(3, 1, 2), MemBerOfBorrowTopology(3, 1, 3)],
        MemBerOfBorrowTopology(1, 1, 2): [MemBerOfBorrowTopology(0, 1, 2), MemBerOfBorrowTopology(0, 1, 3), MemBerOfBorrowTopology(2, 1, 2), MemBerOfBorrowTopology(2, 1, 3), MemBerOfBorrowTopology(3, 1, 2), MemBerOfBorrowTopology(3, 1, 3)],
        MemBerOfBorrowTopology(1, 1, 3): [MemBerOfBorrowTopology(0, 1, 2), MemBerOfBorrowTopology(0, 1, 3), MemBerOfBorrowTopology(2, 1, 2), MemBerOfBorrowTopology(2, 1, 3), MemBerOfBorrowTopology(3, 1, 2), MemBerOfBorrowTopology(3, 1, 3)],
        MemBerOfBorrowTopology(2, 1, 2): [MemBerOfBorrowTopology(0, 1, 2), MemBerOfBorrowTopology(0, 1, 3), MemBerOfBorrowTopology(1, 1, 2), MemBerOfBorrowTopology(1, 1, 3), MemBerOfBorrowTopology(3, 1, 2), MemBerOfBorrowTopology(3, 1, 3)],
        MemBerOfBorrowTopology(2, 1, 3): [MemBerOfBorrowTopology(0, 1, 2), MemBerOfBorrowTopology(0, 1, 3), MemBerOfBorrowTopology(1, 1, 2), MemBerOfBorrowTopology(1, 1, 3), MemBerOfBorrowTopology(3, 1, 2), MemBerOfBorrowTopology(3, 1, 3)],
        MemBerOfBorrowTopology(3, 1, 2): [MemBerOfBorrowTopology(0, 1, 2), MemBerOfBorrowTopology(0, 1, 3), MemBerOfBorrowTopology(1, 1, 2), MemBerOfBorrowTopology(1, 1, 3), MemBerOfBorrowTopology(2, 1, 2), MemBerOfBorrowTopology(2, 1, 3)],
        MemBerOfBorrowTopology(3, 1, 3): [MemBerOfBorrowTopology(0, 1, 2), MemBerOfBorrowTopology(0, 1, 3), MemBerOfBorrowTopology(1, 1, 2), MemBerOfBorrowTopology(1, 1, 3), MemBerOfBorrowTopology(2, 1, 2), MemBerOfBorrowTopology(2, 1, 3)]
        }
        """
        topo = {}

        def set_borrow_topology(plane_id):
            basic.logger.info(f"正在获得环境上平面{plane_id}的topo信息")
            for src_nodeid in range(len(self.nodes)):
                src_node_plane_numalist = self.get_numa_list(plane_id, src_nodeid)
                dest_same_plane_numa_dic = self.get_same_planeid_numa_dic(plane_id, src_nodeid)
                basic.logger.info((f"-节点{src_nodeid}的平面{plane_id}的numa_list为：{src_node_plane_numalist}"))
                basic.logger.info(f"-与节点{src_nodeid}的平面{plane_id}同平面的节点numa信息为 {dest_same_plane_numa_dic}")
                count = 0
                for src_index in range(len(src_node_plane_numalist)):
                    count += 1
                    basic.logger.info(f"--将节点{src_nodeid}的平面{plane_id}的numa_list中第{src_index}个numa作为键目标")
                    src_topo = self.create_member_of_borrow_topology(src_nodeid, src_index, plane_id)
                    topo[src_topo] = []
                    for dest_nodeid, dest_numaid_list in dest_same_plane_numa_dic.items():
                        basic.logger.info(f"---节点{dest_nodeid}与键目标同平面的numaid_list:{dest_numaid_list}")
                        topo[src_topo] += [self.create_member_of_borrow_topology(dest_nodeid, dest_index, plane_id) for dest_index in range(len(dest_numaid_list))]
                    basic.logger.info(f"--节点{src_nodeid}的平面{plane_id}的numa_list中第{src_index}个numa的topo信息：key为{src_topo},value为{topo.get(src_topo)}")

        if fm == "1DFM":
            plane0 = 0
            plane1 = 1
            set_borrow_topology(plane0)
            set_borrow_topology(plane1)
            basic.logger.info(f"全量topo信息：{topo}")
        return topo