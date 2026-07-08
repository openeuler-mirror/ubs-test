"""Topology management functions for RackControl tests.

Provides topology information query and device management.
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_curl_info_from_lcne(node: Any, command: str) -> str:
    res = node.run({"command": [f"{command}"]})
    res_stdout = res.get('stdout')
    if res.get('stderr') or 'HTTP/1.1 200 OK' not in res_stdout:
        return False
    else:
        return res_stdout


def extract_xml_data(info: str, pattern: str) -> Optional[str]:
    """Extract XML data matching pattern.
    
    Legacy method: extract_xml_data(info, pattern)
    
    Args:
        info: XML content string
        pattern: Regex pattern to extract
        
    Returns:
        Extracted XML string or None
    """
    match = re.search(pattern, info, re.DOTALL)
    if match:
        return match.group(0)
    return None


def get_bonding_eid_from_lcne(nodes: List[Any]) -> Dict[str, str]:
    """Get bonding EID from all nodes via LCNE.
    
    Legacy method: get_bonding_eid_from_lcne(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        Dictionary mapping nodeId to bonding EID
    """
    bonding_eid = {}
    curl_command = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock "http://localhost/restconf/data/huawei-vbussw-service:vbussw-service/iou-infos" -v'
    
    for node in nodes:
        curl_info = get_curl_info_from_lcne(node, curl_command)
        xml_data = extract_xml_data(curl_info, r"<iou-infos>.*?</iou-infos>")
        
        if xml_data:
            try:
                xml = ET.fromstring(xml_data)
                for node_data in xml.findall(".//iou-info"):
                    slot_id = node_data.find("slot-id").text if node_data.find("slot-id") is not None else ""
                    eid = f"4245:4944:0000:0000:0000:0000:0{slot_id}00:0000"
                    bonding_eid[slot_id] = eid
            except ET.ParseError as e:
                logger.error(f"Failed to parse XML for node: {e}")
    
    logger.info(f"Found bonding EIDs for {len(bonding_eid)} nodes")
    return bonding_eid


def port_down_up(nodes: List[Any], node_id: str, status: str, port_name: str) -> bool:
    """Set port status (down/up) on node.
    
    Legacy method: port_down_up(nodes, node_id, status, port_name)
    
    Args:
        nodes: List of node objects
        node_id: Target node ID
        status: 'down' or 'up'
        port_name: Port name
        
    Returns:
        True if operation successful, False otherwise
    """
    link_status = 0 if status == "down" else 1
    
    for node in nodes:
        if hasattr(node, "nodeId") and node.nodeId == node_id:
            command = f"gmcmd update port_status set link_status={link_status} where port={port_name}"
            result = node.run({"command": [command], "timeout": 5, "returnCode": True})
            
            output = str(result.get("stdout", "")) + str(result.get("stderr", ""))
            if "Update set value Successful" in output:
                logger.info(f"Port {port_name} set to {status} on node {node_id}")
                return True
            logger.error(f"Failed to set port {port_name} to {status}")
            return False
    
    logger.error(f"Node {node_id} not found")
    return False


def get_node_guid(node: Any) -> str:
    """Get node GUID from inventory.
    
    Legacy method: get_node_guid(node)
    
    Args:
        node: Node object
        
    Returns:
        GUID string or empty string if not found
    """
    curl_command = 'curl -X GET --unix-socket /run/ubm/socket/restconf.sock "http://localhost/restconf/data/huawei-vbussw-inventory:vbussw-inventory/logic-entities" -v'
    curl_info = get_curl_info_from_lcne(node, curl_command)
    
    xml_data = extract_xml_data(curl_info, r"<logic-entities>.*?</logic-entities>")
    if not xml_data:
        xml_data = extract_xml_data(curl_info, r"<vbussw-inventory.*?</vbussw-inventory>")
    
    if xml_data:
        try:
            xml = ET.fromstring(xml_data)
            guid_element = xml.find(".//guid")
            if guid_element is not None and guid_element.text:
                logger.info(f"Found GUID: {guid_element.text}")
                return guid_element.text
        except ET.ParseError as e:
            logger.error(f"Failed to parse GUID XML: {e}")
    
    return ""


def change_lcne_socketId_os(nodes: List[Any]) -> Dict[str, str]:
    """Map LCNE socket IDs to OS socket IDs.
    
    Legacy method: change_lcne_socketId_os(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        Dictionary mapping LCNE socket ID to OS socket ID
    """
    cpu_path = '/sys/devices/system/cpu'
    dev_dict = []
    lcne_dev_dict = []
    commond = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock "http://localhost/restconf/data/huawei-vbussw-service:vbussw-service/iou-infos" -H "Accept: application/yang-data+xml" -H "Content-Type: application/yang-data+xml" -v'
    for node in nodes:
        nodeId = ''
        curl_info = get_curl_info_from_lcne(node, commond)
        xml_data = extract_xml_data(curl_info, r'<iou-infos>.*?</iou-infos>')
        xml = ET.fromstring(xml_data)
        for node_data in xml.findall('.//iou-info'):
            slot_id = node_data.find('slot-id').text
            nodeId = slot_id
            chip_id = node_data.find('ubpu-id').text
            lcne_dev_dict.append(slot_id + '-' + chip_id)

        res_cpu = node.run({'command': [f"ls -d {cpu_path}/cpu[0-9]*"]}).get('stdout').split('\r\nroot@#>')[0]
        all_cpus = res_cpu.split()
        cpu_cores = len(all_cpus) // 2
        for i in range(len(all_cpus) // cpu_cores):
            result = node.run({'command': [f"cat {cpu_path}/cpu{i * cpu_cores}/topology/physical_package_id"]})
            cpuName = result.get('stdout').split('\r\n')[0]
            dev_dict.append(nodeId + '-' + cpuName)

    list1_sorted = sorted(dev_dict, key=lambda x: (int(x.split('-')[0]), int(x.split('-')[1])))
    list2_sorted = sorted(lcne_dev_dict, key=lambda x: (int(x.split('-')[0]), int(x.split('-')[1])))
    paired_lists = zip(list2_sorted, list1_sorted)
    result_dict = {key: value for key, value in paired_lists}
    return result_dict


def replace_socketId(info: Any, mapping: Dict[str, str]) -> Any:
    """Replace socket IDs in data structure using mapping.
    
    Legacy method: replace_socketId(info, mapping)
    
    Args:
        info: Data structure (dict/list/string)
        mapping: Socket ID mapping dictionary
        
    Returns:
        Transformed data structure
    """
    if isinstance(info, dict):
        new_dict = {}
        for key, value in info.items():
            new_key = mapping.get(key, key)
            new_dict[new_key] = replace_socketId(value, mapping)
        return new_dict
    elif isinstance(info, list):
        result = []
        for item in info:
            result.append(replace_socketId(item, mapping))
        return result
    else:
        return info


def get_current_nodeInfo_from_lcne(
    node: Any,
    nodes: List[Any],
    command: str,
    info: str = 'interface-name'
) -> tuple:
    curl_info = get_curl_info_from_lcne(node, command)
    xml_data = extract_xml_data(curl_info, r'<nodes>.*?</nodes>')
    
    if not xml_data:
        return [], {}, {}, {}
    
    xml = ET.fromstring(xml_data)
    socketId = []
    dict_slot = {}
    chip_type_dict = {}
    bindWitch_dict = {}
    socketId_os = change_lcne_socketId_os(nodes)
    
    for node_data in xml.findall('.//node'):
        slot_id = node_data.find('slot').text if node_data.find('slot') is not None else ''
        chip_id = node_data.find('ubpu').text if node_data.find('ubpu') is not None else ''
        chip_type = node_data.find('ubpu-type').text if node_data.find('ubpu-type') is not None else ''
        if chip_type:
            chip_type = chip_type.split('-')[0]
        dev_id = f"{slot_id}-{chip_id}"
        chip_type_dict[dev_id] = chip_type
        socketId.append(str(chip_id))

        if len(nodes) > 1:
            process_physical_ports(node_data, dev_id, dict_slot, bindWitch_dict, socketId_os, info)
            for dev_id_key, value in dict_slot.items():
                dict_slot[dev_id_key] = list(value)
    
    return socketId, dict_slot, chip_type_dict, bindWitch_dict


def process_physical_ports(
    node_data: Any,
    dev_id: str,
    dict_slot: Dict[str, set],
    bindWitch_dict: Dict[str, str],
    socketId_os: Dict[str, str],
    info: str
) -> None:
    for port in node_data.findall('.//physical-port'):
        port_status = port.find('physical-port-status').text if port.find('physical-port-status') is not None else ''
        value, interface_name = '', ''
        
        if port_status == 'up':
            remote_slot_id = port.find('remote-slot').text if port.find('remote-slot') is not None else ''
            remote_chip_id = port.find('remote-ubpu').text if port.find('remote-ubpu') is not None else ''
            interface_name_elem = port.find(info)
            interface_name = interface_name_elem.text if interface_name_elem is not None else ''
            value = f"{remote_slot_id}-{remote_chip_id}"
        
        if dev_id not in dict_slot:
            dict_slot[dev_id] = set()
        
        if value:
            dict_slot[dev_id].add(value)
            dev_id1 = socketId_os.get(dev_id, dev_id)
            value1 = socketId_os.get(value, value)
            connect_id = f"{dev_id1}-{value1}"
            bindWitch_dict[connect_id] = interface_name


def get_bindWitch_chipType_from_lcne(nodes: List[Any]) -> tuple:
    dict_slot_all_nodes = {}
    bindWitch_dict_all_nodes = {}
    chipType_dict_all_nodes = {}
    
    command = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock "http://localhost/restconf/data/huawei-lingqu-topology:lingqu-topology/nodes" -H "Accept: application/yang-data+xml" -H "Content-Type: application/yang-data+xml" -v'
    
    for node in nodes:
        socketId, dict_slot, chip_type_dict, bindWitch_dict = get_current_nodeInfo_from_lcne(node, nodes, command)
        socketId_os = change_lcne_socketId_os(nodes)
        bindWitch_dict_change_socketId = replace_socketId(bindWitch_dict, socketId_os)
        
        bindWitch_dict_all_nodes.update(bindWitch_dict_change_socketId)
        chipType_dict_all_nodes.update(chip_type_dict)
        dict_slot_all_nodes.update(dict_slot)
    
    logger.info(f"Found topology info for {len(dict_slot_all_nodes)} nodes")
    return dict_slot_all_nodes, bindWitch_dict_all_nodes, chipType_dict_all_nodes


def get_unit_port_from_lcne(node: Any) -> Dict[str, Dict[str, Any]]:
    command = 'curl -X GET --unix-socket /run/ubm/socket/ubm_nuds/restconf.sock "http://localhost/restconf/data/huawei-lingqu-topology:lingqu-topology/nodes" -H "Accept: application/yang-data+xml" -H "Content-Type: application/yang-data+xml" -v'
    
    curl_info = get_curl_info_from_lcne(node, command)
    xml_data = extract_xml_data(curl_info, r'<nodes>.*?</nodes>')
    
    if not xml_data:
        return {}
    
    unit_port_dict = {}
    xml = ET.fromstring(xml_data)
    
    for node_data in xml.findall('.//node'):
        chip_id = node_data.find('ubpu').text if node_data.find('ubpu') is not None else ''
        
        for port in node_data.findall('.//physical-port'):
            port_status = port.find('physical-port-status').text if port.find('physical-port-status') is not None else ''
            
            if port_status == 'up':
                port_id = port.find('physical-port-id').text if port.find('physical-port-id') is not None else ''
                interface_name = port.find('interface-name').text if port.find('interface-name') is not None else ''
                unit = int(chip_id) - 1 if chip_id else -1
                unit_port_dict[interface_name] = {
                    'unit': unit,
                    'port_id': port_id
                }
    
    return unit_port_dict


def get_unit_port_info_from_lcne(nodes: List[Any]) -> Dict[str, Dict[str, Any]]:
    merged_dict = {}
    for node in nodes:
        unit_port_dict = get_unit_port_from_lcne(node)
        merged_dict.update(unit_port_dict)
    
    logger.info(f"Found unit/port info for {len(merged_dict)} interfaces")
    return merged_dict


def get_node_port_info_from_lcne(
    bindWitch_dict_all_nodes: Dict[str, str],
    node: Any,
    target_combinations: str = ''
) -> Dict[str, str]:
    node_connect_port = {}
    node_id = getattr(node, 'nodeId', '')
    
    for key, value in bindWitch_dict_all_nodes.items():
        parts = key.split('-')
        if node_id in parts and any(part == node_id for part in parts):
            node_connect_port[key] = value
    
    logger.info(f"Found {len(node_connect_port)} ports for node {node_id}")
    return node_connect_port


def port_down_up_gmcmd(
    nodes: List[Any],
    node_id: str,
    status: str,
    unit: int,
    port: int
) -> bool:
    link_status = 0 if status == 'down' else 1
    
    for node in nodes:
        if hasattr(node, 'nodeId') and node.nodeId == node_id:
            command = f'update devm_port_status set devm_port_status.link_status={link_status} where devm_port_status.unit={unit} and devm_port_status.port={port};'
            res = node.run({'command': [command], "timeout": 5, 'returnCode': False, 'waitstr': 'gmcmd'})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
            
            if 'Update set value Successful' in result:
                logger.info(f"Port {port} on unit {unit} set to {status} on node {node_id}")
                return True
            logger.error(f"Failed to set port {port} to {status}")
            return False
    
    logger.error(f"Node {node_id} not found")
    return False


def get_info_from_conf(node: Any, name: str) -> Optional[str]:
    result = node.run({'command': [f"grep '{name}=' /usr/local/softbus/ctrlbus/conf/rackmanager.conf"]})
    stdout = result.get("stdout", "")
    
    if "root@#>" in stdout:
        stdout = stdout.split("root@#>")[0]
    
    if stdout and "=" in stdout:
        return stdout.split("=")[1].strip().split("\r\n")[0]
    return None


def start_lcne(node: Any) -> bool:
    node.run({"command": ["systemctl start lcne"]})
    logger.info(f"LCNE started on node {getattr(node, 'nodeId', 'unknown')}")
    return True


def check_port(node: Any, port: int) -> bool:
    result = node.run({"command": [f"netstat -tuln | grep {port}"]})
    stdout = result.get("stdout", "")
    return bool(stdout and str(port) in stdout)


def change_lcne_port(node: Any, path: str, filename: str, port: str) -> bool:
    cmd = f"sed -i 's/port=.*/port={port}/' {path}/{filename}"
    node.run({"command": [cmd]})
    logger.info(f"Changed LCNE port to {port}")
    return True


def make_port_in_use(node: Any, port: int) -> bool:
    node.run({"command": [f"nc -l {port}&"]})
    
    for _ in range(10):
        if check_port(node, port):
            logger.info(f"Port {port} is now in use")
            return True
        time.sleep(1)
    
    logger.warning(f"Failed to make port {port} in use")
    return False