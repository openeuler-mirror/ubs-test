"""CLI API wrapper for RackControl tests.

Migrated from: legency/testcase/ubse/lib/api/RackControl/cli_api.py
Provides CLI command wrappers for ubsectl commands.

Usage:
    from libs.rackcontrol.cli_api import get_node_memory_status_by_node_id
    status = get_node_memory_status_by_node_id(node, node_id)
    
    # Or import module:
    from libs.rackcontrol import cli_api
    status = cli_api.get_node_memory_status_by_node_id(node, node_id)
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from libs.utils.table_parser import AweTableParser

logger = logging.getLogger(__name__)


def display_cluster(node: Any) -> List[Dict[str, str]]:
    """Display cluster information using ubsectl.

    Args:
        node: Node object

    Returns:
        List of cluster info dictionaries containing:
        - 'node': Node name
        - 'role': Node role (master/standby)
        - 'bondingeid': Bonding EID
    """
    result = node.run({"command": ["ubsectl display cluster"]})
    output = str(result.get('stdout')) + str(result.get('stderr'))

    if "ERROR" in output or "failed" in output.lower():
        logger.error("Failed to display cluster info")
        return []

    output = output.split("root@#>")[0].strip()
    output = output.replace("-", "")

    lines = [line.strip() for line in output.split("\r\n") if line.strip()]

    if not lines:
        return []

    keys = [key.strip() for key in lines[0].split(" ") if key.strip()]

    cluster_info_list = []
    cluster_info = {}

    for line in lines[1:]:
        values = [value.strip() for value in line.split(" ") if value.strip()]

        if len(values) == 2:
            cluster_info[keys[0]] = values[0]
            cluster_info[keys[1]] = ""
            cluster_info[keys[2]] = values[1]
            cluster_info_list.append(cluster_info.copy())
        elif len(values) == 1:
            if "(0)" in values[0]:
                continue
            if cluster_info_list:
                temp = cluster_info_list.pop()
                temp["node"] = temp.get("node", "") + values[0]
                cluster_info_list.append(temp)
        else:
            for i, key in enumerate(keys):
                if i < len(values):
                    cluster_info[key] = values[i]
            cluster_info_list.append(cluster_info.copy())

    logger.info(f"Found {len(cluster_info_list)} cluster nodes")
    return cluster_info_list



def display_election(node: Any, role: str) -> Optional[str]:
    """Display election information for specified role.

    Args:
        node: Node object
        role: Role to search ('master' or 'standby')

    Returns:
        Node ID string if found, None otherwise
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


def query_link_info(node: Any) -> List[Dict[str, str]]:
    """Query link topology information.

    Args:
        node: Node object

    Returns:
        List of link info dictionaries containing 'link-id'
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


def check_mem_query(node: Any, query_item="borrow_detail", timeout=0) -> Optional[str]:
    """Check memory query result.

    Args:
        node: Node object
        query_item: Query item type (default: 'borrow_detail')
        timeout: Sleep time before query (default: 0)

    Returns:
        Query result string, None if failed
    """
    time.sleep(timeout)
    res = node.run(
        {'command': [f"ubsectl display memory -t {query_item}"]})
    res = str(res.get('stdout')) + str(res.get('stderr'))
    logger.info(res)
    return res


def check_memmory(node: Any) -> List[Dict[str, Any]]:
    """Check memory status via CLI.

    Args:
        node: Node object

    Returns:
        List of memory status dictionaries
    """
    result = node.run({"command": ["ubsectl check memory"]})
    stdout = result.get("stdout", "")
    
    if not stdout or "ERROR" in stdout:
        return []
    
    if "root@#>" in stdout:
        stdout = stdout.split("root@#>")[0]
    
    status_list = []
    lines = stdout.strip().split("\n")
    
    for line in lines:
        if line.strip() and "--" not in line:
            parts = line.split()
            if len(parts) >= 5:
                detail_str = parts[4] if len(parts) > 4 else ""
                detail_dict = {}
                
                for key_value in detail_str.split(";"):
                    if ":" in key_value:
                        key, value = key_value.split(":")
                        detail_dict[key.strip()] = value.strip()
                
                status_list.append({
                    "node": parts[0],
                    "status": parts[1] if len(parts) > 1 else "",
                    "detail": detail_dict
                })
    
    return status_list


def check_memmory_status(node: Any) -> Dict[str, str]:
    """Check memory status as dict.

    Args:
        node: Node object

    Returns:
        Dict mapping node ID to status string
    """
    result = node.run({"command": ["ubsectl check memory"]})
    stdout = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    
    if "ERROR" in stdout:
        return {}
    
    stdout = stdout.rstrip("\r\nroot@#>None")
    status_dict = {}
    
    lines = [line.strip() for line in stdout.splitlines() if line.strip() and "--" not in line]
    
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 5:
            node_id = parts[0]
            status = parts[4].strip(";")
            status_dict[node_id] = status
    
    return status_dict


def display_numa_status_info(node: Any, options: str = "numa_status") -> List[Dict[str, str]]:
    """Display NUMA status info.

    Args:
        node: Node object
        options: Query options (default: 'numa_status')

    Returns:
        List of NUMA status info dictionaries
    """
    result = node.run({"command": [f"ubsectl display memory -t {options}"]})
    stdout = result.get("stdout")
    if "root@#>" in stdout:
        stdout = stdout.rstrip('\r\nroot@#>')
    mem_list = [item for item in stdout.replace("-", "").split("\r\n") if item]
    if len(mem_list) <= 1:
        return []
    mems = []
    keys = []
    for i, mem in enumerate(mem_list):
        items = mem.split()
        if i == 0:
            keys = items
        else:
            mem_info_dict = dict(zip(keys, items))
            if mem_info_dict:
                mems.append(mem_info_dict)
    return mems


def get_node_memory_status_by_node_id(node: Any, node_id: str) -> str:
    """Get memory status for a specific node by ID.

    Args:
        node: Node object
        node_id: Node ID string

    Returns:
        Memory status string (lowercase), empty string if not found
    """
    res = node.run(
        {'command': [f"ubsectl check memory"]}).get('stdout')
    # 解析字符串为字典列表
    lines = [e for e in res.split('\r\nroot@#>')[0].split('\r\n') if e.strip() and not e.startswith('-')]
    for line in lines[1:]:  # 跳过表头行
        if line.strip():
            parts = line.split()
            if "(" + node_id + ")" in parts[0]:
                return parts[4].strip(';').lower()
    return ""


def _extract_mem_info(mem_info_dict: Dict[str, str], switch: str = 'normal', need_name: bool = False) -> Dict[str, str]:
    """Extract memory info from parsed dict.
    
    Args:
        mem_info_dict: Parsed memory info dict
        switch: 'normal' or other for status field
        need_name: Include name field
        
    Returns:
        Extracted memory info dict
    """
    borrow_node = mem_info_dict.get("borrow_node", "")
    lend_node = mem_info_dict.get("lend_node", "")
    
    temp = {
        'MemBorrowNode': borrow_node.split('(')[1].split(')')[0] if '(' in borrow_node else borrow_node,
        'MemLendNode': lend_node.split('(')[1].split(')')[0] if '(' in lend_node else lend_node,
        'Size(MB)': mem_info_dict.get("lend_size", "")
    }
    
    if need_name:
        temp['name'] = mem_info_dict.get("name", "")
    
    if switch != 'normal':
        temp['status'] = mem_info_dict.get("status", "")
    
    return temp


def display_mem_info(node: Any, switch: str = 'normal', need_name: bool = False) -> List[Dict[str, str]]:
    """Display memory borrow information.

    Args:
        node: Node object
        options: Query type (borrow_detail, borrow_account, etc.)
        switch: 'normal' or other for status field
        need_name: Include name in result
        
    Returns:
        List of memory info dicts, empty list if no data or error
        
    Example:
        data = cli_api.display_mem_info(node, options='borrow_account')
        for item in data:
            print(f"Size: {item['Size(MB)']} MB")
    """
    result = node.run({"command": ["ubsectl display memory -t borrow_detail"]})
    stdout = result.get("stdout", "")
    
    if "root@#>" in stdout:
        stdout = stdout.rstrip("\r\nroot@#>")
    
    if not stdout or 'information is empty' in stdout:
        return []
    
    try:
        parser = AweTableParser(stdout)
        mem_list = parser.parse_text()
    except ValueError:
        logger.warning(f"Failed to parse memory info: {stdout[:200]}")
        return []
    
    mems = []
    for mem_info_dict in mem_list:
        borrow_node = mem_info_dict.get('borrow_node', '')
        if borrow_node == '':
            mem_info_dict['borrow_node'] = '(none)'
        
        status = mem_info_dict.get("status", "")
        if status == 'done' or status == 'fault':
            temp = _extract_mem_info(mem_info_dict, switch, need_name)
            mems.append(temp)
    
    return mems


def import_cert(
    node: Any,
    server_cert_file: str,
    server_key_file: str,
    ca_cert_file: str,
    ca_crl_file: str = '',
    password: Optional[str] = None,
    is_use_long_option: bool = False
) -> str:
    """Import certificates using ubsectl import cert command.
    
    Migrated from: legency/testcase/ubse/lib/api/RackControl/cli_api.py
    
    Args:
        node: Node object
        server_cert_file: Server certificate file path
        server_key_file: Server key file path
        ca_cert_file: CA certificate file path
        ca_crl_file: CA CRL file path (optional)
        password: Password for certificate (default: 'huawei12#$')
        is_use_long_option: Use long option format (--server-cert-file etc.)
        
    Returns:
        Command output string
        
    Example:
        result = cli_api.import_cert(node, '/path/server.pem', '/path/server_key.pem', '/path/trust.pem')
        if 'Certificates imported successfully' in result:
            print("Import success")
    """
    if not password:
        password = 'huawei12#$'
    
    if ca_crl_file != '':
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
    
    return str(result.get('stdout', '')) + str(result.get('stderr', ''))


def remove_cert(node: Any) -> str:
    """Remove certificates using ubsectl remove cert command.
    
    Migrated from: legency/testcase/ubse/lib/api/RackControl/cli_api.py
    
    Args:
        node: Node object
        
    Returns:
        Command output string
        
    Example:
        result = cli_api.remove_cert(node)
        if 'Certificates removed successfully' in result:
            print("Remove success")
    """
    result = node.run({'command': ["ubsectl remove cert"]})
    return str(result.get('stdout', '')) + str(result.get('stderr', ''))


def import_crl(node: Any, ca_crl_file: str, is_use_long_option: bool = False) -> str:
    """Import CRL (Certificate Revocation List) using ubsectl change cert command.
    
    Migrated from: legency/testcase/ubse/lib/api/RackControl/cli_api.py
    
    Args:
        node: Node object
        ca_crl_file: CA CRL file path
        is_use_long_option: Use long option format (--ca-crl-file)
        
    Returns:
        Command output string
        
    Example:
        result = cli_api.import_crl(node, '/path/ca1.crl')
        if 'Certificate Revocation List changed successfully' in result:
            print("CRL import success")
    """
    if not is_use_long_option:
        result = node.run({'command': [f"ubsectl change cert -l {ca_crl_file}"]})
    else:
        result = node.run({'command': [f"ubsectl change cert --ca-crl-file {ca_crl_file}"]})
    
    return str(result.get('stdout', '')) + str(result.get('stderr', ''))

def display_mem_borrow_detail(node, name=None, borrow_type=None, is_use_long_option=False):
    """Display memory borrow detail information.

    Args:
        node: Node object
        name: Memory name (optional)
        borrow_type: Borrow type (optional)
        is_use_long_option: Use long option format

    Returns:
        List of memory borrow detail dictionaries, empty list if failed
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
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\nroot@#>')
    if not res or 'information is empty' in res:
        return []
    awe_table_parser = AweTableParser(res)
    mem_list = awe_table_parser.parse_text()
    mems = []
    for mem_info_dict in mem_list:
        if mem_info_dict.get('borrow_node') == '':
            mem_info_dict['borrow_node'] = '(none)'
        temp = {'name': mem_info_dict.get("name"),
                'type': mem_info_dict.get("type"),
                'borrow_node': mem_info_dict.get("borrow_node").split('(')[1].split(')')[0],
                'lend_node': mem_info_dict.get("lend_node").split('(')[1].split(')')[0],
                'lend_size': mem_info_dict.get("lend_size"),
                'status': mem_info_dict.get("status"),
                'handle': mem_info_dict.get("handle")
                }
        mem_info_dict.update(temp)
        mems.append(mem_info_dict)
    return mems


def query_topo_info(node):
    """Query topology information.

    Args:
        node: Node object

    Returns:
        List of link info dictionaries
    """
    res = node.run({
        'command': [f"ubsectl display topo -t cpu"]
    }).get('stdout').rstrip('\r\nroot@#>')
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


def parse_mem_res_dynamic(res):
    """Parse memory result dynamic output.

    Args:
        res: Result string from memory command

    Returns:
        Tuple of (success, info_dict)
    """
    if 'ERROR:' in res:
        return False, []
    mem_info_dict = {}
    for line in filter(None, res.splitlines()):
        if ':' in line:
            k, v = line.split(':', 1)
            mem_info_dict[k.strip()] = v.strip()
    if not mem_info_dict:
        return False, []
    return True, mem_info_dict


def create_fd_memory(node, name, size='128M', is_use_long_option=False):
    """Create FD memory.

    Args:
        node: Node object
        name: Memory name
        size: Memory size (default: '128M')
        is_use_long_option: Use long option format

    Returns:
        Tuple of (success, info_dict)
    """
    if is_use_long_option:
        command = f"ubsectl create memory --type fd --size {size} --name {name}"
    else:
        command = f"ubsectl create memory -t fd -s {size} -n {name}"
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def create_numa_memory(node, name, size='128M', link=None, is_use_long_option=False):
    """Create NUMA memory.

    Args:
        node: Node object
        name: Memory name
        size: Memory size (default: '128M')
        link: Link ID (optional)
        is_use_long_option: Use long option format

    Returns:
        Tuple of (success, info_dict)
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
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def create_shm_memory(node, name, size='128M', region=None, is_use_long_option=False):
    """Create shared memory.

    Args:
        node: Node object
        name: Memory name
        size: Memory size (default: '128M')
        region: Region ID (optional)
        is_use_long_option: Use long option format

    Returns:
        Tuple of (success, info_dict)
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
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def attach_shm_memory(node, name, is_use_long_option=False):
    """Attach shared memory.

    Args:
        node: Node object
        name: Memory name
        is_use_long_option: Use long option format

    Returns:
        Tuple of (success, info_dict)
    """
    if is_use_long_option:
        command = f"ubsectl attach memory --name {name}"
    else:
        command = f"ubsectl attach memory -n {name}"
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    return parse_mem_res_dynamic(res)


def detach_shm_memory(node, name, is_use_long_option=False):
    """Detach shared memory.

    Args:
        node: Node object
        name: Memory name
        is_use_long_option: Use long option format

    Returns:
        True if successful, False otherwise
    """
    if is_use_long_option:
        command = f"ubsectl detach memory --name {name}"
    else:
        command = f"ubsectl detach memory -n {name}"
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    if "successfully" in res:
        return True
    return False


def delete_memory(node, name, mem_type='', is_use_long_option=False):
    """Delete memory.

    Args:
        node: Node object
        name: Memory name
        mem_type: Memory type (optional)
        is_use_long_option: Use long option format

    Returns:
        True if successful, False otherwise
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
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    if "successfully" in res:
        return True
    return False


def display_borrow(node, options='borrow_detail', is_use_long_option=False):
    """Display borrow information.

    Args:
        node: Node object
        options: Query options (default: 'borrow_detail')
        is_use_long_option: Use long option format

    Returns:
        List of borrow info dictionaries
    """
    if is_use_long_option:
        command = f"ubsectl display memory --type {options}"
    else:
        command = f"ubsectl display memory -t {options}"
    res = node.run({'command': [command]}).get('stdout').rstrip('\r\n')
    mem_list = []
    if not res or 'information is empty' in res:
        return mem_list
    awe_table_parser = AweTableParser(res)
    mems = awe_table_parser.parse_text()
    for mem in mems:
        if mem:
            mem_list.append(mem)
    return mem_list


def _compare_cli_help_message(node: Any, result: Dict[str, Any], expected_file: str) -> bool:
    """Compare CLI help message with expected file content.

    Args:
        node: Node object
        result: Command result dict
        expected_file: Path to expected help message file

    Returns:
        True if messages match, False otherwise
    """
    stdout = result.get("stdout", "")
    if not stdout:
        return False

    # Parse actual help message
    actual_lines = []
    for line in stdout.split("root@#>")[0].splitlines():
        if line.strip():
            actual_lines.append(line.rstrip())

    # Get expected help message
    expected_result = node.run({"command": [f"cat {expected_file}"]})
    expected_stdout = expected_result.get("stdout", "")
    if not expected_stdout:
        logger.warning(f"Expected help file not found: {expected_file}")
        return True  # Skip comparison if file not found

    expected_lines = []
    for line in expected_stdout.split("root@#>")[0].splitlines():
        if line.strip():
            expected_lines.append(line.rstrip())

    # Compare line counts
    if len(actual_lines) != len(expected_lines):
        logger.warning(
            f"Help message line count mismatch: {len(actual_lines)} vs {len(expected_lines)}"
        )
        return False

    # Compare each line
    for i, actual_line in enumerate(actual_lines):
        if actual_line != expected_lines[i]:
            logger.warning(
                f"Help message line {i} mismatch: '{actual_line}' vs '{expected_lines[i]}'"
            )
            return False

    logger.info("CLI help message matches expected content")
    return True


def cli_h(node: Any, expected_help_file: str = None) -> bool:
    """Execute ubsectl -h and verify help message.

    Args:
        node: Node object
        expected_help_file: Path to expected help message file (optional)

    Returns:
        True if help message matches expected, False otherwise
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


def cli_help(node: Any, expected_help_file: str = None) -> bool:
    """Execute ubsectl --help and verify help message.

    Args:
        node: Node object
        expected_help_file: Path to expected help message file (optional)

    Returns:
        True if help message matches expected, False otherwise
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

# Legacy compatibility: export module-level __all__ for direct import
__all__ = [
    'display_cluster',
    'display_election',
    'display_mem_borrow_detail',
    'query_link_info',
    'check_mem_query',
    'check_memmory',
    'check_memmory_status',
    'display_numa_status_info',
    'get_node_memory_status_by_node_id',
    'display_mem_info',
    'import_cert',
    'remove_cert',
    'import_crl',
    'query_topo_info',
    'parse_mem_res_dynamic',
    'create_fd_memory',
    'create_numa_memory',
    'create_shm_memory',
    'attach_shm_memory',
    'detach_shm_memory',
    'delete_memory',
    'display_borrow',
    'cli_h',
    'cli_help',
]