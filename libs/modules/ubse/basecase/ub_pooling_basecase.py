"""UB Pooling and Topology Management BaseCase.

Migrated from: legency/testcase/ubse/lib/basecase/ubse/UB_Pooling_And_Topology_Management/UB_Pooling_And_Topology_Management_BaseCase.py
Provides topology query and pooling management methods.

Legacy file is 907 lines - this is a simplified pytest-compatible version.
Complex methods should be imported from libs.ubse.topology.

CRITICAL CHANGE (2026-05-12):
- 移除__init__方法，解决pytest无法收集带__init__测试类的硬限制
- 使用@pytest.fixture(autouse=True)注入模块引用和计算参数
- 外部依赖参数(nodes, resource, custom_params)通过父类CMBaseCase.fixture注入
"""

import logging
import pytest
from typing import Any, Dict, List, Optional

from libs.modules.ubse.basecase.cm_basecase import CMBaseCase
from libs.modules.ubse.common import topology
from libs.modules.ubse.common.cli_wrapper import get_node_role
from libs.modules.ubse.common import ubse_process_ops
from libs.modules.ubse.api import cli_api

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_ub_pooling_dependencies(request: Any) -> None:
    """注入UB_Pooling_BaseCase特有的模块引用和计算参数.
    
    只对UB_Pooling_BaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.modules.ubse.basecase.ub_pooling_basecase import UB_Pooling_BaseCase
    if not isinstance(instance, UB_Pooling_BaseCase):
        return
    
    instance.ub_topology_common = topology
    instance.ub_common = topology
    instance.topo_common = topology
    
    instance.ubse_process_ops = ubse_process_ops
    instance.cli_api = cli_api

    
    instance.sdk_path = instance.SDK_PATH
    instance.audit_log = instance.AUDIT_LOG
    instance.manager_log = instance.MANAGER_LOG
    instance.rackmanager_log = instance.MANAGER_LOG
    
    if hasattr(instance, 'nodes') and instance.nodes:
        instance._classify_nodes(instance.nodes)
        instance.node_roles = get_node_role(instance.nodes)
    else:
        instance.ub_nodes = []
        instance.qemu_nodes = []
        instance.qemu_node = None
        instance.node_roles = {}
    
    logger.info(f"UB_Pooling_BaseCase initialized: hardware={len(instance.ub_nodes)}, qemu={len(instance.qemu_nodes)}")


class UB_Pooling_BaseCase(CMBaseCase):
    """Base class for UB pooling and topology management tests.
    
    Provides methods for:
    - Topology query via LCNE REST API
    - Device information management
    - Node role identification
    - Port status control
    
    Legacy inheritance: UB_Pooling_And_Topology_Management_BaseCase(CMBaseCase)
    
    外部依赖参数（父类CMBaseCase.fixture注入）:
        - nodes: List[Any] - 测试节点列表
        - resource: Dict[str, Any] - 资源配置字典
        - custom_params: Dict[str, Any] - 自定义参数字典
    
    模块引用（本类fixture注入）:
        - ub_topology_common, ub_common, topo_common: topology模块
        - ubse_process_ops: ubse_process_ops模块
        - DFX_common: dfx_ops模块
        - cli_api: cli_api模块
        - resource_aw, dpu_sdk_common, dpu_aw: sdk_helper模块
    
    计算参数（本类fixture注入）:
        - ub_nodes: 硬件节点列表
        - qemu_nodes: QEMU节点列表
        - qemu_node: QEMU节点（单个）
        - node_roles: 节点角色字典
    """
    
    # 类属性（硬编码路径）
    CTRLBUS_PATH = "/usr/local/softbus/ctrlbus"
    CLI_PATH = "/usr/local/softbus/ctrlbus-cli"
    AUDIT_LOG = "/var/log/audit/audit.log"
    MANAGER_LOG = "/var/log/scbus/rackmanager.log"
    SDK_PATH = "/home/autotest/sdk"
    
    def _classify_nodes(self, nodes: List[Any]) -> None:
        """Classify nodes as hardware or QEMU.
        
        Legacy pattern: checks node.localIP for '192.168'
        
        Args:
            nodes: List of node objects
        """
        self.ub_nodes = []
        self.qemu_nodes = []
        self.qemu_node = None
        
        for node in nodes:
            local_ip = getattr(node, "localIP", getattr(node, "localIP", ""))
            if "192.168" in local_ip:
                self.ub_nodes.append(node)
            else:
                self.qemu_nodes.append(node)
        
        # Adjust node list based on test environment
        if self.ub_nodes:
            # Hardware test - use hardware nodes
            self.nodes = self.ub_nodes
            if self.qemu_nodes:
                self.qemu_node = self.qemu_nodes[0]
        else:
            # QEMU test - use QEMU nodes
            self.nodes = self.qemu_nodes
    
    def preTestCase(self) -> None:
        """Pre-test setup - verify LCNE installation.
        
        Legacy method: preTestCase()
        """
        super().preTestCase()
        
        curl_cmd = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock "http://localhost/restconf/data/huawei-vbussw-service:vbussw-service/iou-infos"'
        
        for node in self.nodes:
            result = topology.get_curl_info_from_lcne(node, curl_cmd)
            self.assertNotEqual(result, False, "LCNE installation failed")
        
        logger.info("LCNE installation verified")

    @staticmethod
    def compare_dicts_list(list1, list2, name='name'):
        # 对每个字典进行排序
        sorted_list1 = sorted(list1, key=lambda x: x[f'{name}'])
        sorted_list2 = sorted(list2, key=lambda x: x[f'{name}'])
        return sorted_list1 == sorted_list2


    def extract_xml_data(self, info: str, pattern: str) -> Optional[str]:
        """Extract XML data matching pattern.
        
        Delegates to topology.extract_xml_data
        
        Args:
            info: XML content
            pattern: Regex pattern
            
        Returns:
            Extracted XML string or None
        """
        return topology.extract_xml_data(info, pattern)
    
    def get_curl_info_from_lcne(self, node: Any, command: str) -> str:
        """Get curl info from LCNE.
        
        Delegates to topology.get_curl_info_from_lcne
        
        Args:
            node: Node object
            command: Curl command
            
        Returns:
            Response string
        """
        return topology.get_curl_info_from_lcne(node, command)
    
    def port_down_up(
        self,
        node_id: str,
        status: str,
        unit: Optional[int] = None,
        port: Optional[int] = None
    ) -> bool:
        if unit is not None and port is not None:
            return topology.port_down_up_gmcmd(self.nodes, node_id, status, unit, port)
        else:
            return topology.port_down_up(self.nodes, node_id, status, node_id)
    
    def get_bonding_eid_from_lcne(self) -> Dict[str, str]:
        """Get bonding EID from all nodes.
        
        Delegates to topology.get_bonding_eid_from_lcne
        
        Returns:
            Dictionary mapping nodeId to EID
        """
        return topology.get_bonding_eid_from_lcne(self.nodes)
    
    def get_node_guid(self, node: Any) -> str:
        """Get node GUID.
        
        Delegates to topology.get_node_guid
        
        Args:
            node: Node object
            
        Returns:
            GUID string
        """
        return topology.get_node_guid(node)
    
    def change_lcne_socketId_os(self) -> Dict[str, str]:
        """Map LCNE socket IDs to OS socket IDs.
        
        Delegates to topology.change_lcne_socketId_os
        
        Returns:
            Socket ID mapping dictionary
        """
        return topology.change_lcne_socketId_os(self.nodes)
    
    def procedure(self) -> None:
        """Main test logic."""
        super().procedure()
    
    def postTestCase(self) -> None:
        """Post-test cleanup."""
        super().postTestCase()
        logger.info("UB_Pooling_BaseCase postTestCase")
    
    def get_bindWitch_chipType_from_lcne(self) -> tuple:
        return topology.get_bindWitch_chipType_from_lcne(self.nodes)
    
    def get_unit_port_from_lcne(self, node: Any) -> Dict[str, Dict[str, Any]]:
        return topology.get_unit_port_from_lcne(node)
    
    def get_unit_port_info_from_lcne(self, nodes: List[Any] = None) -> Dict[str, Dict[str, Any]]:
        if nodes is None:
            nodes = self.nodes
        return topology.get_unit_port_info_from_lcne(nodes)
    
    def get_node_port_info_from_lcne(
        self,
        bindWitch_dict_all_nodes: Dict[str, str],
        node: Any,
        target_combinations: str = ''
    ) -> Dict[str, str]:
        return topology.get_node_port_info_from_lcne(bindWitch_dict_all_nodes, node, target_combinations)
    
    def port_down_up_gmcmd(self, node_id: str, status: str, unit: int, port: int) -> bool:
        return topology.port_down_up_gmcmd(self.nodes, node_id, status, unit, port)
    
    def get_info_from_conf(self, name: str) -> Optional[str]:
        """从配置文件获取信息.
        
        Args:
            name: 配置项名称
            
        Returns:
            配置值或None
        """
        return topology.get_info_from_conf(self.nodes[0], name)
    
    def start_lcne(self, node: Any) -> bool:
        return topology.start_lcne(node)
    
    def check_port(self, node: Any, port: int) -> bool:
        return topology.check_port(node, port)
    
    def change_lcne_port(self, node: Any, path: str, filename: str, port: str) -> bool:
        return topology.change_lcne_port(node, path, filename, port)
    
    def make_port_in_use(self, node: Any, port: int) -> bool:
        return topology.make_port_in_use(node, port)
    
    def get_unit_and_port(self, node: Any) -> tuple:
        """Get unit_id and port_id from LCNE topology.
        
        Legacy method: get_unit_and_port(node)
        
        Args:
            node: Node object
            
        Returns:
            Tuple of (unit_id, port_id), or (-1, -1) if not found
        """
        import xml.etree.ElementTree as ET
        
        commond = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock "http://localhost/restconf/data/huawei-lingqu-topology:lingqu-topology/nodes" -H "Accept: application/yang-data+xml" -H "Content-Type: application/yang-data+xml" -v'
        curl_info = topology.get_curl_info_from_lcne(node, commond)
        xml_data = topology.extract_xml_data(curl_info, r'<nodes>.*?</nodes>')
        
        if not xml_data:
            return -1, -1
        
        xml = ET.fromstring(xml_data)
        
        for node_data in xml.findall('.//node'):
            for port in node_data.findall('.//physical-port'):
                port_status = port.find('physical-port-status').text
                if port_status == 'up':
                    remote_port_id = port.find('physical-port-id').text
                    remote_chip_id = port.find('remote-ubpu').text
                    port_id = int(remote_port_id)
                    unit_id = int(remote_chip_id) - 1
                    return unit_id, port_id
        return -1, -1
    
    def send_cmd_to_gmcmd(self, node: Any, state: int, unit_id: int, port_id: int) -> None:
        """Send command to gmcmd for port status control.
        
        Legacy method: send_cmd_to_gmcmd(node, state, unit_id, port_id)
        
        Args:
            node: Node object
            state: Port state (0=down, 1=up)
            unit_id: Unit ID
            port_id: Port ID
        """
        import time
        
        inter_cmd = "timeout 3s /usr/local/ubm/bin/gmcmd -s usocket:/run/ubm/socket/unix_emserver"
        result_cmd = f"update devm_port_status set devm_port_status.link_status={state} where devm_port_status.unit={unit_id} and devm_port_status.port={port_id};"
        node.run({"command": [inter_cmd], "timeout": 1, "waitstr": "gmcmd", 'returnCode': False})
        node.run({"command": [result_cmd], "timeout": 1, "waitstr": "gmcmd", 'returnCode': False})
        time.sleep(3)
        if hasattr(node, 'reconnect'):
            node.reconnect()


    def get_cpu_topo_info(self, info):
        result = []
        topo_info = {}
        for line in info.splitlines():
            line = line.strip()
            if line.startswith('INFO: ubse_cpu_topo_info('):
                topo_info = {}
            elif line == ')':
                if topo_info:
                    result.append(topo_info)
            else:
                items = line.split('=')
                if len(items) != 2:
                    continue
                if items[0] == 'slot id':
                    topo_info['node'] = items[1]
                elif items[0] == 'socket ids':
                    topo_info['socket'] = items[1]
                elif items[0] == 'port id':
                    topo_info['port'] = items[1]
                elif items[0] == 'peer slot id':
                    topo_info['peer-node'] = items[1]
                elif items[0] == 'peer socket ids':
                    topo_info['peer-socket'] = items[1]
                elif items[0] == 'peer port id':
                    topo_info['peer-port'] = items[1]
        return result


    def replace_socketId(self, info, mapping):
        result = []
        if isinstance(info, dict):
            new_dict = {}
            for key, value in info.items():
                new_key = mapping.get(key, key)
                new_dict[new_key] = self.replace_socketId(value, mapping)
            return new_dict
        elif isinstance(info, list):
            for item in info:
                if isinstance(item, list):
                    result.append(self.replace_socketId(item, mapping))
                else:
                    result.append(mapping.get(item, item))
            return result
        else:
            return info

    def get_node_hostname(self):
        hostname_dict = {}
        for node in self.nodes:
            hostname_dict[node.nodeId] = node.run({'command': ["hostname"]}).get('stdout').split('\r\n')[0]
        return hostname_dict

    def get_topo_info_from_lcne(self, nodes, one_step_info):
        """
        返回包含各项信息的字典列表
        [{'link-id': '', 'node': '', 'socket': '', 'port': '', 'peer-node': '', 'peer-socket': '', 'peer-port': ''}]
        """
        port_info_dict = {}
        topo_infos = []
        link_ids = []
        for node in nodes:
            commond = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock http://localhost/restconf/data/huawei-lingqu-topology:lingqu-topology/nodes -H "Accept: application/yang-data+xml" -H "Content-Type: application/yang-data+xml" -v'
            try:
                _, _, _, bindWitch_dict = topology.get_current_nodeInfo_from_lcne(node, nodes, commond,
                                                                              info='physical-port-id')
                if bindWitch_dict is None:
                    raise ValueError('bindWitch_dict为空')
                else:
                    port_info_dict.update(bindWitch_dict)
            except Exception as e:
                raise ValueError('bindWitch_dict为空') from e

        hostname_dict = self.get_node_hostname()

        for key, values in one_step_info.items():
            nodeId = key.split('-')[0]
            socketId = key.split('-')[1]
            for value in sorted(values):
                peer_nodeId = value.split('-')[0]
                peer_socketId = value.split('-')[1]
                k1 = nodeId + '-' + socketId + '-' + peer_nodeId + '-' + peer_socketId
                port = port_info_dict.get(k1, "")
                k2 = peer_nodeId + '-' + peer_socketId + '-' + nodeId + '-' + socketId
                peer_port = port_info_dict.get(k2, "")
                link_id = nodeId + '/' + socketId + '/' + port + peer_nodeId + '/' + peer_socketId + '/' + peer_port
                link_id_revert = peer_nodeId + '/' + peer_socketId + '/' + peer_port + nodeId + '/' + socketId + '/' + port
                if link_id in link_ids or link_id_revert in link_ids:
                    continue
                link_ids.append(link_id)
                topo_info = {'link-id': link_id, 'node': hostname_dict[nodeId] + '(' + nodeId + ')', 'socket': socketId,
                             'port': port, 'peer-node': hostname_dict[peer_nodeId] + '(' + peer_nodeId + ')',
                             'peer-socket': peer_socketId, 'peer-port': peer_port}
                topo_infos.append(topo_info)
        return topo_infos


    def process_cpu_topo_dict(self, dict_info):
        for item in dict_info:
            for key, _ in item.items():
                if key == 'node':
                    item['node'] = item[key].split('(')[1].split(')')[0]
                elif key == 'peer-node':
                    item['peer-node'] = item[key].split('(')[1].split(')')[0]
        return dict_info