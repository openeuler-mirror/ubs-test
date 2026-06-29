"""CLI API wrapper for UBSE tests.

Provides CLI command wrappers for ubsectl commands.

Usage:
    from libs.modules.ubse.api.cli_api import get_node_memory_status_by_node_id
    status = get_node_memory_status_by_node_id(node, node_id)
    
    # Or import module:
    from libs.modules.ubse.api import cli_api
    status = cli_api.get_node_memory_status_by_node_id(node, node_id)
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from libs.utils.table_parser import AweTableParser

logger = logging.getLogger(__name__)


# ========== 内置辅助方法 ==========

def parse_mem_res_dynamic(res: str) -> Tuple[bool, Dict[str, str]]:
    """解析内存命令输出的键值对信息。

    Args:
        res: Result string from memory command output

    Returns:
        Tuple of (success, info_dict) where:
        - success: True if parsing succeeded, False if ERROR found
        - info_dict: Dictionary of parsed key-value pairs, empty dict if failed

    Example:
        success, info = cli_api.parse_mem_res_dynamic("handle: 123\\nsize: 128M")
        if success:
            print(f"Handle: {info['handle']}")
    """
    if 'ERROR:' in res:
        return False, {}
    mem_info_dict = {}
    for line in filter(None, res.splitlines()):
        if ':' in line:
            k, v = line.split(':', 1)
            mem_info_dict[k.strip()] = v.strip()
    if not mem_info_dict:
        return False, {}
    return True, mem_info_dict


def _compare_cli_help_message(node: Any, result: Dict[str, Any], expected_file: str) -> bool:
    """比对CLI帮助信息与预期文件内容。

    Args:
        node: Node object with run() method
        result: Command result dict containing 'stdout' and 'stderr'
        expected_file: Path to expected help message file

    Returns:
        True if messages match line-by-line, False otherwise
        Returns True if expected_file not found (skip comparison)

    Example:
        result = node.run({"command": ["ubsectl -h"]})
        if cli_api._compare_cli_help_message(node, result, '/path/help.txt'):
            print("Help message matches expected")
    """
    stdout = result.get("stdout", "")
    if not stdout:
        return False

    actual_lines = []
    for line in stdout.split("root@#>")[0].splitlines():
        if line.strip():
            actual_lines.append(line.rstrip())

    expected_result = node.run({"command": [f"cat {expected_file}"]})
    expected_stdout = expected_result.get("stdout", "")
    if not expected_stdout:
        logger.warning(f"Expected help file not found: {expected_file}")
        return True

    expected_lines = []
    for line in expected_stdout.split("root@#>")[0].splitlines():
        if line.strip():
            expected_lines.append(line.rstrip())

    if len(actual_lines) != len(expected_lines):
        logger.warning(
            f"Help message line count mismatch: {len(actual_lines)} vs {len(expected_lines)}"
        )
        return False

    for i, actual_line in enumerate(actual_lines):
        if actual_line != expected_lines[i]:
            logger.warning(
                f"Help message line {i} mismatch: '{actual_line}' vs '{expected_lines[i]}'"
            )
            return False

    logger.info("CLI help message matches expected content")
    return True


# ========== 证书管理 ==========

def import_cert(
    node: Any,
    server_cert_file: str,
    server_key_file: str,
    ca_cert_file: str,
    password: str,
    ca_crl_file: Optional[str] = None,
    is_use_long_option: bool = False
) -> bool:
    """通过ubsectl import cert命令向UBSE导入证书

    Args:
        node: Node object with run() method
        server_cert_file: Server certificate file path
        server_key_file: Server key file path
        ca_cert_file: CA certificate file path
        ca_crl_file: CA CRL file path (optional, None to skip)
        password: Password for certificate
        is_use_long_option: Use long option format (--server-cert-file etc.)
        
    Returns:
        True if import succeeded (output contains 'successfully'), False otherwise
        
    Example:
        if cli_api.import_cert(
            node, '/path/server.pem', '/path/server_key.pem', '/path/trust.pem'
        ):
            print("Import success")
    """
    if ca_crl_file:
        if not is_use_long_option:
            result = node.run({
                'command': [
                    f"echo {password} | ubsectl import cert -s {server_cert_file} -k {server_key_file} "
                    f"-c {ca_cert_file} -l {ca_crl_file}"
                ]
            })
        else:
            result = node.run({
                'command': [
                    f"echo {password} | ubsectl import cert --server-cert-file {server_cert_file} "
                    f"--server-key-file {server_key_file} --ca-cert-file {ca_cert_file} --ca-crl-file {ca_crl_file}"
                ]
            })
    else:
        if not is_use_long_option:
            result = node.run({
                'command': [
                    f"echo {password} | ubsectl import cert -s {server_cert_file} -k {server_key_file} "
                    f"-c {ca_cert_file}"
                ]
            })
        else:
            result = node.run({
                'command': [
                    f"echo {password} | ubsectl import cert --server-cert-file {server_cert_file} "
                    f"--server-key-file {server_key_file} --ca-cert-file {ca_cert_file}"
                ]
            })
    
    output = str(result.get('stdout', '')) + str(result.get('stderr', ''))
    return "successfully" in output


def remove_cert(node: Any) -> bool:
    """通过ubsectl remove cert命令从UBSE中移除证书信息

    Args:
        node: Node object with run() method
        
    Returns:
        True if remove succeeded (output contains 'successfully'), False otherwise
        
    Example:
        if cli_api.remove_cert(node):
            print("Remove success")
    """
    result = node.run({'command': ["ubsectl remove cert"]})
    output = str(result.get('stdout', '')) + str(result.get('stderr', ''))
    return "successfully" in output


def import_crl(node: Any, ca_crl_file: str, is_use_long_option: bool = False) -> bool:
    """通过ubsectl change cert命令向UBSE更新吊销证书信息

    Args:
        node: Node object with run() method
        ca_crl_file: CA CRL file path to import
        is_use_long_option: Use long option format (--ca-crl-file)
        
    Returns:
        True if import succeeded (output contains 'successfully'), False otherwise
        
    Example:
        if cli_api.import_crl(node, '/path/ca1.crl'):
            print("CRL import success")
    """
    if not is_use_long_option:
        result = node.run({'command': [f"ubsectl change cert -l {ca_crl_file}"]})
    else:
        result = node.run({'command': [f"ubsectl change cert --ca-crl-file {ca_crl_file}"]})
    
    output = str(result.get('stdout', '')) + str(result.get('stderr', ''))
    return "successfully" in output


# ========== 内存池化 ==========

def check_memory(node: Any) -> List[Dict[str, Any]]:
    """通过ubsectl check memory命令检查各节点内存池化功能健康状态。

    Args:
        node: Node object with run() method

    Returns:
        List of memory status dictionaries containing:
        - 'node': Node identifier
        - 'status': Memory status string
        - 'detail': Dictionary of detailed status info
        Empty list if query failed or 'ERROR' found

    Example:
        status_list = cli_api.check_memmory(node)
        for status in status_list:
            print(f"Node: {status['node']}, Status: {status['status']}")
    """
    result = node.run({"command": ["ubsectl check memory"]})
    stdout = result.get("stdout", "")
    
    if not stdout or "ERROR" in stdout:
        return []
    
    if "root@#>" in stdout:
        stdout = stdout.split("root@#>")[0]
    
    try:
        parser = AweTableParser(stdout)
        mem_list = parser.parse_text()
    except ValueError:
        logger.warning(f"Failed to parse memory status: {stdout[:200]}")
        return []
    
    status_list = []
    for mem_info in mem_list:
        if mem_info:
            detail_str = mem_info.get("detail", "")
            detail_dict = {}
            
            if detail_str:
                for key_value in detail_str.split(";"):
                    if ":" in key_value:
                        key, value = key_value.split(":")
                        detail_dict[key.strip()] = value.strip()
            
            status_list.append({
                "node": mem_info.get("node", ""),
                "status": mem_info.get("status", ""),
                "detail": detail_dict
            })
    
    return status_list


def check_mem_query(
    node: Any,
    query_item: str = "borrow_detail",
    timeout: int = 0
) -> str:
    """通过ubsectl display memory命令查询内存借用信息原始输出。

    Args:
        node: Node object with run() method
        query_item: Query item type (default: 'borrow_detail')
        timeout: Sleep time in seconds before query (default: 0)

    Returns:
        Query result string (stdout + stderr combined)

    Example:
        result = cli_api.check_mem_query(node, query_item='borrow_account', timeout=2)
        if 'information is empty' not in result:
            print("Memory data found")
    """
    time.sleep(timeout)
    res = node.run(
        {'command': [f"ubsectl display memory -t {query_item}"]})
    res = str(res.get("stdout", "")) + str(res.get("stderr", ""))
    logger.info(res)
    return res


def get_node_memory_status_by_node_id(node: Any, node_id: str) -> str:
    """通过check_memory获取指定节点的内存状态。

    Args:
        node: Node object with run() method
        node_id: Node ID string to search (e.g., 'Node0')

    Returns:
        Memory status string in lowercase (e.g., 'ok', 'fault')
        Empty string if node_id not found

    Example:
        status = cli_api.get_node_memory_status_by_node_id(node, 'Node0')
        if status == 'ok':
            print("Node memory status is OK")
    """
    status_list = check_memory(node)
    
    for status_info in status_list:
        node_str = status_info.get("node", "")
        if "(" + node_id + ")" in node_str:
            return status_info.get("status", "").lower()
    
    return ""


def display_mem_borrow_detail(
    node: Any,
    name: Optional[str] = None,
    borrow_type: Optional[str] = None,
    is_use_long_option: bool = False
) -> List[Dict[str, str]]:
    """通过ubsectl display memory命令查询内存借用账本详细信息。

    Args:
        node: Node object with run() method
        name: Memory name for filtering (optional)
        borrow_type: Borrow type for filtering (optional)
        is_use_long_option: Use long option format (--type, --name)

    Returns:
        List of memory borrow detail dictionaries containing:
        - 'name': Memory name
        - 'type': Memory type (fd/numa/share)
        - 'borrow_node': Borrow node slot ID (empty string if "")
        - 'lend_node': Lend node slot ID
        - 'lend_numa': Lend NUMA socket ID (extracted from 'numaId(socketId)' format)
        - 'lend_size': Lend size (MB)
        - 'status': Memory status
        - 'handle': Memory handle (empty string if "-")
        Empty list if query failed or no data

    Example:
        mems = cli_api.display_mem_borrow_detail(node, name="test_mem")
        for mem in mems:
            print(f"Name: {mem['name']}, Status: {mem['status']}")
    """
    if is_use_long_option:
        command = f"ubsectl display memory --type borrow_detail"
        if name:
            command += f" --name {name}"
        if borrow_type:
            command += f" --borrow-type {borrow_type}"
    else:
        command = f"ubsectl display memory -t borrow_detail"
        if name:
            command += f" -n {name}"
        if borrow_type:
            command += f" -bt {borrow_type}"
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\nroot@#>')
    if not res or 'information is empty' in res:
        return []
    try:
        parser = AweTableParser(res)
        mem_list = parser.parse_text()
    except ValueError:
        logger.warning(f"Failed to parse memory info: {res[:200]}")
        return []
    mems = []
    for mem_info_dict in mem_list:
        borrow_node = mem_info_dict.get("borrow_node", "")
        lend_node = mem_info_dict.get("lend_node", "")
        temp = {'borrow_node': borrow_node.split('(')[1].split(')')[0] if '(' in borrow_node else borrow_node,
                'lend_node': lend_node.split('(')[1].split(')')[0] if '(' in lend_node else lend_node
                }
        mem_info_dict.update(temp)
        mems.append(mem_info_dict)
    return mems


def display_borrow(
    node: Any,
    options: str = 'borrow_detail',
    is_use_long_option: bool = False
) -> List[Dict[str, str]]:
    """通过ubsectl display memory命令查询各节点内存借用信息。

    Args:
        node: Node object with run() method
        options: Query options type (default: 'borrow_detail')
        is_use_long_option: Use long option format (--type)

    Returns:
        List of borrow info dictionaries parsed from table output
        Empty list if query failed or 'information is empty'

    Example:
        mems = cli_api.display_borrow(node, options='borrow_account')
        for mem in mems:
            print(f"Name: {mem.get('name')}, Size: {mem.get('lend_size')}")
    """
    if is_use_long_option:
        command = f"ubsectl display memory --type {options}"
    else:
        command = f"ubsectl display memory -t {options}"
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\nroot@#>')
    mem_list = []
    if not res or 'information is empty' in res:
        return mem_list
    awe_table_parser = AweTableParser(res)
    mems = awe_table_parser.parse_text()
    for mem in mems:
        if mem:
            mem_list.append(mem)
    return mem_list


def display_numa_status_info(node: Any, options: str = "numa_status") -> List[Dict[str, str]]:
    """通过ubsectl display memory命令查询NUMA状态信息。

    Args:
        node: Node object with run() method
        options: Query options type (default: 'numa_status')

    Returns:
        List of NUMA status info dictionaries containing:
        - 'node': Node info (hostname(slot_id))
        - 'numa': NUMA ID
        - 'total': Total memory (MB)
        - 'used': Used memory (MB)
        - 'free': Free memory (MB)
        - 'used_percent': Usage percentage (float string)
        - '2M_total': Total 2M huge pages (optional)
        - '2M_free': Free 2M huge pages (optional)
        - '1G_total': Total 1G huge pages (optional)
        - '1G_free': Free 1G huge pages (optional)
        - '512M_total': Total 512M huge pages (optional, 64k pages)
        - '512M_free': Free 512M huge pages (optional, 64k pages)
        Empty list if query failed or no data rows

    Example:
        numa_info = cli_api.display_numa_status_info(node)
        for numa in numa_info:
            print(f"NUMA {numa.get('numa')}, Used: {numa.get('used')}MB")
    """
    result = node.run({"command": [f"ubsectl display memory -t {options}"]})
    stdout = result.get("stdout", "")
    
    if not stdout:
        return []
    
    if "root@#>" in stdout:
        stdout = stdout.rstrip('\r\nroot@#>')
    
    try:
        parser = AweTableParser(stdout)
        numa_list = parser.parse_text()
    except ValueError:
        logger.warning(f"Failed to parse NUMA status: {stdout[:200]}")
        return []
    
    mems = []
    for numa_info in numa_list:
        if numa_info:
            mems.append(numa_info)
    
    return mems


def create_numa_memory(
    node: Any,
    name: str,
    size: str = '128M',
    link: Optional[str] = None,
    is_use_long_option: bool = False
) -> Tuple[bool, Dict[str, str]]:
    """通过ubsectl create memory命令借用NUMA类型内存。

    Args:
        node: Node object with run() method
        name: Memory name for identification
        size: Memory size string (default: '128M')
        link: Link ID for remote memory (optional)
        is_use_long_option: Use long option format (--type, --size, --name, --link)

    Returns:
        Tuple of (success, info_dict) where:
        - success: True if creation succeeded
        - info_dict: Dictionary containing handle, size, numa_id, etc.

    Example:
        success, info = cli_api.create_numa_memory(node, "test_numa", link="Link0")
        if success:
            print(f"Created NUMA memory on link: {link}")
    """
    if is_use_long_option:
        base_cmd = f"ubsectl create memory --type numa --size {size} --name {name}"
        link_flag = "--link"
    else:
        base_cmd = f"ubsectl create memory -t numa -s {size} -n {name}"
        link_flag = "-l"
    if link:
        command = f"{base_cmd} {link_flag} {link}"
    else:
        command = base_cmd
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def create_fd_memory(
    node: Any,
    name: str,
    size: str = '128M',
    is_use_long_option: bool = False
) -> Tuple[bool, Dict[str, str]]:
    """通过ubsectl create memory命令借用FD类型内存。

    Args:
        node: Node object with run() method
        name: Memory name for identification
        size: Memory size string (default: '128M', e.g., '256M', '1G')
        is_use_long_option: Use long option format (--type, --size, --name)

    Returns:
        Tuple of (success, info_dict) where:
        - success: True if creation succeeded
        - info_dict: Dictionary containing handle, size, etc.

    Example:
        success, info = cli_api.create_fd_memory(node, "test_fd", size="256M")
        if success:
            print(f"Created FD memory with handle: {info.get('handle')}")
    """
    if is_use_long_option:
        command = f"ubsectl create memory --type fd --size {size} --name {name}"
    else:
        command = f"ubsectl create memory -t fd -s {size} -n {name}"
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def create_shm_memory(
    node: Any,
    name: str,
    size: str = '128M',
    region: Optional[str] = None,
    is_use_long_option: bool = False
) -> Tuple[bool, Dict[str, str]]:
    """通过ubsectl create memory命令借用共享内存。

    Args:
        node: Node object with run() method
        name: Memory name for identification
        size: Memory size string (default: '128M')
        region: Region IDs for shared memory scope, comma-separated (optional)
        is_use_long_option: Use long option format (--type, --size, --name, --region)

    Returns:
        Tuple of (success, info_dict) where:
        - success: True if creation succeeded
        - info_dict: Dictionary containing handle, size, region, etc.

    Example:
        success, info = cli_api.create_shm_memory(node, "test_shm", region="1,2")
        if success:
            print(f"Created shared memory for region: {region}")
    """
    if is_use_long_option:
        base_cmd = f"ubsectl create memory --type share --size {size} --name {name}"
        region_flag = "--region"
    else:
        base_cmd = f"ubsectl create memory -t share -s {size} -n {name}"
        region_flag = "-r"
    if region:
        command = f"{base_cmd} {region_flag} {region}"
    else:
        command = base_cmd
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def delete_memory(
    node: Any,
    name: str,
    mem_type: Optional[str] = None,
    is_use_long_option: bool = False
) -> bool:
    """通过ubsectl delete memory命令删除内存借用。

    Args:
        node: Node object with run() method
        name: Memory name to delete
        mem_type: Memory type for filtering (optional, e.g., 'fd', 'numa', 'share')
        is_use_long_option: Use long option format (--name, --type)

    Returns:
        True if delete succeeded (output contains 'successfully'), False otherwise

    Example:
        result = cli_api.delete_memory(node, "test_mem")
        if result:
            print(f"Deleted memory: test_mem")
        
        result = cli_api.delete_memory(node, "test_fd", mem_type="fd")
        if result:
            print("Deleted FD memory")
    """
    if is_use_long_option:
        base_cmd = f"ubsectl delete memory --name {name}"
        mem_type_flag = "--type"
    else:
        base_cmd = f"ubsectl delete memory -n {name}"
        mem_type_flag = "-t"
    if mem_type:
        command = f"{base_cmd} {mem_type_flag} {mem_type}"
    else:
        command = base_cmd
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\n')
    return "successfully" in res


def attach_shm_memory(
    node: Any,
    name: str,
    is_use_long_option: bool = False
) -> Tuple[bool, Dict[str, str]]:
    """通过ubsectl attach memory命令导入共享内存。

    Args:
        node: Node object with run() method
        name: Memory name to attach
        is_use_long_option: Use long option format (--name)

    Returns:
        Tuple of (success, info_dict) where:
        - success: True if attach succeeded
        - info_dict: Dictionary containing handle, status, etc.

    Example:
        success, info = cli_api.attach_shm_memory(node, "test_shm")
        if success:
            print(f"Attached shared memory: {name}")
    """
    if is_use_long_option:
        command = f"ubsectl attach memory --name {name}"
    else:
        command = f"ubsectl attach memory -n {name}"
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def detach_shm_memory(
    node: Any,
    name: str,
    is_use_long_option: bool = False
) -> bool:
    """通过ubsectl detach memory命令删除导入的共享内存。

    Args:
        node: Node object with run() method
        name: Memory name to detach
        is_use_long_option: Use long option format (--name)

    Returns:
        True if detach succeeded (contains 'successfully'), False otherwise

    Example:
        result = cli_api.detach_shm_memory(node, "test_shm")
        if result:
            print(f"Detached shared memory: {name}")
    """
    if is_use_long_option:
        command = f"ubsectl detach memory --name {name}"
    else:
        command = f"ubsectl detach memory -n {name}"
    res = node.run({'command': [command]}).get("stdout", "").rstrip('\r\n')
    return "successfully" in res


# ========== 拓扑链接 ==========

def query_topo_info(node: Any) -> List[Dict[str, str]]:
    """通过ubsectl display topo命令查询拓扑链接信息。

    Args:
        node: Node object with run() method

    Returns:
        List of link info dictionaries containing:
        - 'link-id': Link identifier
        - 'node': Node ID
        - 'socket': Socket ID
        - 'port': Port ID
        - 'interface-name': Interface name
        - 'peer-node': Peer node ID
        - 'peer-socket': Peer socket ID
        - 'peer-port': Peer port ID
        - 'peer-interface-name': Peer interface name
        Empty list if query failed

    Example:
        links = cli_api.query_topo_info(node)
        for link in links:
            print(f"Link: {link['link-id']}, Node: {link['node']}")
    """
    res = node.run({
        'command': [f"ubsectl display topo -t cpu"]
    }).get("stdout", "").rstrip('\r\nroot@#>')
    link_list = [item for item in res.replace('-', '').split('\r\n') if item]
    if len(link_list) <= 1:
        return []
    link_info = []
    keys = ['link-id', 'node', 'socket', 'port', 'interface-name', 'peer-node', 'peer-socket', 'peer-port',
            'peer-interface-name']
    for i, links in enumerate(link_list):
        items = links.split()
        if i <= 2:
            continue
        if len(items) > 4:
            link_info_dict = dict(zip(keys, items))
            if link_info_dict:
                link_info.append(link_info_dict)
    return link_info


def query_link_info(node: Any) -> List[Dict[str, str]]:
    """通过ubsectl display topo命令查询链路拓扑信息。

    Args:
        node: Node object with run() method

    Returns:
        List of link info dictionaries containing 'link-id'
        Empty list if query failed or no links found

    Example:
        links = cli_api.query_link_info(node)
        for link in links:
            print(f"Link ID: {link['link-id']}")
    """
    result = node.run({"command": ["ubsectl display topo -t cpu"]})
    stdout = result.get("stdout", "") + result.get("stderr", "")
    
    if "root@#>" in stdout:
        stdout = stdout.split("root@#>")[0]
    
    links = []
    lines = stdout.strip().split("\n")
    
    for line in lines:
        if line.strip() and "Link" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                links.append({"link-id": parts[1].strip()})
    
    return links


def display_cluster(node: Any) -> List[Dict[str, str]]:
    """通过ubsectl display cluster命令查询集群节点信息。

    Args:
        node: Node object with run() method

    Returns:
        List of cluster info dictionaries containing:
        - 'node': Node name with ID in parentheses
        - 'role': Node role ('master' or 'standby')
        - 'bondingeid': Bonding EID identifier
        Empty list if query failed or no data

    Example:
        cluster_info = cli_api.display_cluster(node)
        for info in cluster_info:
            print(f"Node: {info['node']}, Role: {info['role']}")
    """
    result = node.run({"command": ["ubsectl display cluster"]})
    output = str(result.get("stdout", "")) + str(result.get("stderr", ""))

    if "ERROR" in output or "failed" in output.lower():
        logger.error("Failed to display cluster info")
        return []

    output = output.split("root@#>")[0].strip()
    output = output.replace("-", "")

    try:
        parser = AweTableParser(output)
        cluster_info_list = parser.parse_text()
    except ValueError:
        logger.warning(f"Failed to parse cluster info: {output[:200]}")
        return []

    logger.info(f"Found {len(cluster_info_list)} cluster nodes")
    return cluster_info_list


def display_election(node: Any, role: str) -> Optional[str]:
    """通过display_cluster获取指定角色的节点ID。

    Args:
        node: Node object with run() method
        role: Role to search ('master' or 'standby')

    Returns:
        Node ID string if found, None otherwise

    Example:
        master_id = cli_api.display_election(node, 'master')
        if master_id:
            print(f"Master node ID: {master_id}")
    """
    cluster_info_list = display_cluster(node)

    if not cluster_info_list:
        return None

    pattern = r"\([^()]*\)"

    for cluster_info in cluster_info_list:
        if cluster_info.get("role") == role:
            matches = re.findall(pattern, cluster_info.get("node", ""))
            if matches:
                node_id = re.sub(r"[()]", "", matches[0])
                logger.info(f"Found {role} node: {node_id}")
                return node_id

    logger.info(f"No {role} node found")
    return None


# ========== Help命令 ==========

def cli_h(node: Any, expected_help_file: Optional[str] = None) -> bool:
    """执行ubsectl -h命令并验证帮助信息。

    Args:
        node: Node object with run() method
        expected_help_file: Path to expected help message file (optional)

    Returns:
        True if help message matches expected or no file specified
        False if command failed or message mismatch

    Example:
        if cli_api.cli_h(node):
            print("ubsectl -h works correctly")
        
        if cli_api.cli_h(node, '/expected/help.txt'):
            print("Help message matches expected format")
    """
    result = node.run({"command": ["ubsectl -h"]})
    output = str(result.get("stdout", "")) + str(result.get("stderr", ""))

    if "failed" in output.lower():
        logger.error("ubsectl -h command failed")
        return False

    if expected_help_file:
        return _compare_cli_help_message(node, result, expected_help_file)

    logger.info("CLI help message retrieved successfully")
    return True


def cli_help(node: Any, expected_help_file: Optional[str] = None) -> bool:
    """执行ubsectl --help命令并验证帮助信息。

    Args:
        node: Node object with run() method
        expected_help_file: Path to expected help message file (optional)

    Returns:
        True if help message matches expected or no file specified
        False if command failed or message mismatch

    Example:
        if cli_api.cli_help(node):
            print("ubsectl --help works correctly")
    """
    result = node.run({"command": ["ubsectl --help"]})
    output = str(result.get("stdout", "")) + str(result.get("stderr", ""))

    if "failed" in output.lower():
        logger.error("ubsectl --help command failed")
        return False

    if expected_help_file:
        return _compare_cli_help_message(node, result, expected_help_file)

    logger.info("CLI help message retrieved successfully")
    return True


# ========== Legacy compatibility: export module-level __all__ ==========

__all__ = [
    'parse_mem_res_dynamic',
    '_compare_cli_help_message',
    'import_cert',
    'remove_cert',
    'import_crl',
    'check_memmory',
    'check_memmory_status',
    'check_mem_query',
    'get_node_memory_status_by_node_id',
    'display_mem_borrow_detail',
    'display_borrow',
    'display_numa_status_info',
    'create_numa_memory',
    'create_fd_memory',
    'create_shm_memory',
    'delete_memory',
    'attach_shm_memory',
    'detach_shm_memory',
    'query_topo_info',
    'query_link_info',
    'display_cluster',
    'display_election',
    'cli_h',
    'cli_help',
]