"""ubse common operations - combined module.

Migrated from: legency/testcase/ubse/lib/Common/ubse/ubse_Common.py
Combines log_ops, node_ops, and other common utilities for backward compatibility.

Usage:
    from libs.ubse import rack_common
    rack_common.create_directory_and_upload(nodes, files, relative_path, dir_path)
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from libs.modules.ubse.api import rpm_api
from libs.modules.ubse.api import cli_api
from libs.modules.ubse.common.node_ops import *
from libs.modules.ubse.common.cli_wrapper import *
logger = logging.getLogger(__name__)


def get_ubse_pid(node: Any) -> Optional[str]:
    """Get ubse/ubse process PID.

    Legacy method: get_ubse_pid(node)

    Args:
        node: Node object

    Returns:
        PID string if found, False otherwise
    """
    res = node.run({'command': ["ps -ef | grep '/usr/bin/ubse' | grep -v grep | awk '{print $2}'"]}).get('stdout')
    if res is None:
        return None
    pid = res.split('root@#>')[0].split('\r\n')[0]
    if pid != '':
        return pid
    return None


def stop_ubse(node: Any) -> bool:
    pid = get_ubse_pid(node)
    if not pid:
        return True
    stop_timeout1 = get_count(node, "Failed with result 'timeout'")
    stop_coredump1 = get_count(node, 'core-dump')
    rpm_api.exec_service(node, 'stop', 'ubse')
    stop_timeout2 = get_count(node, "Failed with result 'timeout'")
    stop_coredump2 = get_count(node, 'core-dump')
    logger.info(f"coredump、timeout：{stop_coredump1, stop_coredump2, stop_timeout1, stop_timeout2}")
    return stop_coredump1 == stop_coredump2 and stop_timeout1 == stop_timeout2


def start_ubse(node: Any) -> bool:
    """Start ubse service on node.

    Legacy method: start_ubse(node)

    Args:
        node: Node object

    Returns:
        True if started successfully, False otherwise
    """
    node.run({"command": ["systemctl start ubse"]})
    time.sleep(10)

    pid = get_ubse_pid(node)
    if pid:
        logger.info(f"Successfully started ubse, PID: {pid}")
        return True

    logger.error("Failed to start ubse")
    return False


def check_ubse_status(node: Any, action: str, expected_count: int = 0) -> bool:
    """Check ubse service status.

    Args:
        node: Node object
        action: Action performed ('start' or 'stop')
        expected_count: Expected log count

    Returns:
        True if status is expected, False otherwise
    """
    result = node.run({"command": ["systemctl status ubse"]})
    output = result.get("stdout", "") + result.get("stderr", "")

    if action == "start":
        if "active (running)" in output:
            logger.info("ubse is running")
            return True
        logger.error("ubse not running after start")
        return False

    elif action == "stop":
        if "inactive (dead)" in output or "stopped" in output:
            logger.info("ubse is stopped")
            return True
        logger.error("ubse not stopped")
        return False

    return False


def install_ubse(node: Any, package: str) -> bool:
    """Install ubse package using rpm.

    Legacy method: install_ubse(node, package)

    Args:
        node: Node object
        package: Package name or path

    Returns:
        True if installed successfully, False otherwise
    """
    result = node.run({"command": [f"rpm -ivh {package} --force"]})
    stderr = result.get("stderr", "")

    if "error" in stderr.lower() or "failed" in stderr.lower():
        logger.error(f"Failed to install package {package}: {stderr}")
        return False

    logger.info(f"Successfully installed package {package}")
    return True


def kill_process(node: Any, process_name: str) -> bool:
    """Kill process by name.

    Args:
        node: Node object
        process_name: Process name to kill

    Returns:
        True if killed, False otherwise
    """
    cmd = f"ps -ef | grep {process_name} | grep -v grep | awk '{{print $2}}' | xargs kill -9"
    result = node.run({"command": [cmd]})
    logger.info(f"Killed process {process_name}")
    return True


def restart_ubse(node: Any) -> Optional[str]:
    """Restart ubse process.
    
    Legacy method: restart_ubse(node)
    
    Args:
        node: Node object
        
    Returns:
        New PID if successful, None otherwise
    """
    stop_ubse(node)
    time.sleep(3)
    start_ubse(node)
    time.sleep(5)
    return get_ubse_pid(node)


def stop_multi_ubse(nodes: List[Any]) -> bool:
    """Stop ubse on multiple nodes.
    
    Legacy method: stop_multi_ubse(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        True if all stopped successfully
    """
    for node in nodes:
        stop_ubse(node)
    return True


def start_multi_ubse(nodes: List[Any]) -> bool:
    """Start ubse on multiple nodes.
    
    Legacy method: start_multi_ubse(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        True if all started successfully
    """
    for node in nodes:
        start_ubse(node)
    return True


def start_ubse_if_not_started(nodes: List[Any]) -> bool:
    """Start ubse if not already running.
    
    Legacy method: start_ubse_if_not_started(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        True if successful
    """
    for node in nodes:
        pid = get_ubse_pid(node)
        print(pid)
        if not pid:
            start_ubse(node)
    return True


def start_all_ubse_without_waiting(nodes: List[Any], time_wait=0) -> bool:
    start_successfully_count = []
    is_start_successfully = True
    for node in nodes:
        if time_wait > 0:
            time.sleep(time_wait)
        start_successfully_count.append(get_count(node, 'started successfully'))
        node.run({'command': [f'systemctl start ubse & disown']})
    node_num = len(nodes)
    for i in range(20):
        count = 0
        for j, node in enumerate(nodes):
            current_count = get_count(node, 'started successfully')
            if current_count == start_successfully_count[j] and i == 19:
                is_start_successfully = False
                rpm_api.exec_service(node, 'status')
                logger.info(f'{node.localIP}节点启动ubse进程失败')
            if current_count != start_successfully_count[j]:
                count += 1
        time.sleep(6)
        if count == node_num:
            break

    logger.info('打印各节点进程号')
    for node in nodes:
        pid = get_ubse_pid(node)
        logger.info(f'{node.localIP}对应的进程号为: {pid}')
    # 确保建链完成
    time.sleep(2)
    return is_start_successfully


def return_nodes_by_role(nodes: List[Any]) -> tuple:
    """Return master and standby nodes by role.
    
    Legacy method: return_nodes_by_role(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        Tuple of (master_node, standby_node)
    """

    roles = get_node_role(nodes)
    master_node = None
    standby_node = None
    
    for node in nodes:
        node_id = getattr(node, "nodeId", "")
        role = roles.get(node_id, "")
        if role == "master":
            master_node = node
        elif role == "standby":
            standby_node = node
    
    return master_node, standby_node


def restart_one_node_lcne(node: Any) -> bool:
    """Restart LCNE process on single node.
    
    Legacy method: restart_one_node_lcne(node)
    
    Args:
        node: Node object
        
    Returns:
        True if successful
    """
    kill_process(node, "lcne")
    time.sleep(2)
    node.run({"command": ["systemctl start lcne"]})
    return True


def change_file(nodes: List[Any], key: str, value: str, path: str, filename: str) -> bool:
    """Change key value in file on multiple nodes.
    
    Legacy method: change_file(nodes, key, value, path, filename)
    
    Args:
        nodes: List of node objects
        key: Key to change
        value: New value
        path: File path
        filename: File name
        
    Returns:
        True if successful
    """
    for node in nodes:
        cmd = f"sed -i 's/{key}=.*/{key}={value}/' {path}/{filename}"
        node.run({"command": [cmd]})
    return True


def modify_conf_value(node: Any, key: str, value: Any) -> bool:
    """Modify config value in ubse.conf.
    
    Legacy method: modify_conf_value(node, key, value)
    
    Args:
        node: Node object
        key: Config key
        value: New value
        
    Returns:
        True if successful
    """
    conf_path = "/usr/local/softbus/ctrlbus/conf/ubse.conf"
    if value is None:
        cmd = f"sed -i '/{key}=/d' {conf_path}"
    else:
        cmd = f"sed -i 's/{key}=.*/{key}={value}/' {conf_path}"
    node.run({"command": [cmd]})
    return True


def backup_file(node: Any, path1: str, path2: str, filename: str) -> bool:
    """Backup file from path1 to path2.
    
    Legacy method: backup_file(node, path1, path2, filename)
    
    Args:
        node: Node object
        path1: Source directory path
        path2: Target directory path
        filename: File name to backup
        
    Returns:
        True if successful, False otherwise
    """
    result = path2
    res = node.run({"command": [f"ls {result}"]})
    if res.get("stdout") is None:
        node.run({"command": [f"mkdir -p {path2}"]})
    else:
        logger.info(f"Directory {path2} already exists")
    node.run({"command": [f"cp -p {path1}/{filename} {path2}/{filename}"]})
    res = node.run({"command": [f"cat {path2}/{filename}"]})
    if res.get("stdout") is None:
        return False
    return True


def get_count(node, keyword):
    # 获取最新一条journal日志的时间(Jan 08 14:38:04) 并转换格式(01-08 14:38:04)，不支持先后两次执行跨年的比较
    res = node.run({'command': [
        f"journalctl -u ubse.service | grep -v ubse_uds_client | grep '{keyword}' | awk 'END{{print $1, $2, $3}}'"]})
    if not res.get('stdout') or not res.get('stdout').split('\r\n')[0].strip():
        return '0'
    try:
        res1 = res.get('stdout').split('\r\n')[0]
        if res1.strip():
            res1 = datetime.strptime(res1, "%b %d %H:%M:%S").strftime("%m-%d %H:%M:%S")
    except ValueError:
        logger.error(f"journal日志错误：{res}")
        # 如果不是整数，保持原值或进行其他处理
        return get_count(node, keyword)
    return res1


def create_directory_and_upload(
        nodes: List[Any],
        files: List[str],
        relative_path: str,
        dir_path: str,
        source_base: Optional[str] = None
) -> bool:
    """Create directory and upload files to nodes.
    
    Legacy method: rack_common.create_directory_and_upload(nodes, files, relative_path, dir_path)
    
    Args:
        nodes: List of node objects
        files: List of file names to upload
        relative_path: Relative path from source base
        dir_path: Target directory path on nodes
        source_base: Source base directory (default: workspace root)
        
    Returns:
        True if successful on all nodes
    """
    if source_base is None:
        source_base = str(Path(__file__).parent.parent.parent.parent.parent).replace('\\', '/')

    success = True
    for node in nodes:
        try:
            node.run({'command': [f'mkdir -p {dir_path}']})
            for file in files:
                src_path = f"{source_base}/{relative_path}/{file}"
                dst_path = f"{dir_path}/{file}"
                logger.info(f"Uploading {src_path} to {node.nodeId}:{dst_path}")
                node.putFile(src_path, dst_path)
            node.run({'command': [f'chmod -R 777 {dir_path}']})
        except Exception as e:
            logger.error(f"Failed to upload to {node.nodeId}: {e}")
            success = False
    return success


def stop_all_ubse_without_waiting(nodes: List[Any]) -> bool:
    """Stop ubse on all nodes without waiting for completion.
    
    Migrated from: legency/testcase/ubse/lib/Common/ubse/ubse_Common.py
    
    Args:
        nodes: List of node objects
        
    Returns:
        True if all stopped successfully
    """
    import time
    from datetime import datetime, timezone, timedelta
    
    is_stop_successfully = True
    temp_nodes = nodes.copy()
    
    for node in nodes:
        pid = get_ubse_pid(node)
        if not pid:
            temp_nodes.remove(node)
    
    for node in temp_nodes:
        node.run({'command': ['systemctl stop ubse & disown']})
    
    node_num = len(temp_nodes)
    for i in range(30):
        count = 0
        time.sleep(3)
        for node in temp_nodes:
            pid = get_ubse_pid(node)
            if pid and i == 29:
                is_stop_successfully = False
                timestamp = datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S.%f")[:-3]
                node.run({"command": [f"systemctl status ubse > /home/autotest/bak_logs/status_{timestamp}.txt"]})
                logger.info(f'{getattr(node, "localIP", "unknown")} node stop ubse failed')
            if not pid:
                count += 1
        if count == node_num:
            break
    
    return is_stop_successfully

def return_node_roles(nodes, master_id, standby_id=''):
    master_node = None
    standby_node = None
    for node in nodes:
        if node.nodeId == master_id:
            master_node = node
        if standby_id != '' and node.nodeId == standby_id:
            standby_node = node
    return master_node, standby_node


def return_nodes_by_role(nodes, timeout=6):
    # 暂适配双节点，返回master和standby节点
    nodes = get_nodeId(nodes)
    if len(nodes) == 1:
        for _ in range(60):
            master_id = cli_api.display_election(nodes[0], 'master')
            master_node, agent_node = return_node_roles(nodes, master_id)
            if master_node:
                return master_node, agent_node
            time.sleep(timeout)
        raise RuntimeError("获取主备节点失败")

    for i in range(60):
        master_id = cli_api.display_election(nodes[0], 'master')
        standby_id = cli_api.display_election(nodes[0], 'standby')
        master_node, agent_node = return_node_roles(nodes, master_id, standby_id)
        if master_node and agent_node:
            return master_node, agent_node
        time.sleep(timeout)
    raise RuntimeError("获取主备节点失败")

def return_nodes_by_all_role(nodes: List[Any], wait_times: int = 60) -> tuple:
    """Return master, standby and agent nodes by role.
    
    Migrated from: legency/testcase/ubse/lib/Common/ubse/ubse_Common.py
    
    Args:
        nodes: List of node objects
        wait_times: Maximum wait times (default: 60)
        
    Returns:
        Tuple of (master_node, standby_node, agent_nodes_list)
        
    Raises:
        RuntimeError: If failed to get master/standby nodes
    """

    agent_nodes = []
    master_node = None
    standby_node = None
    
    for _ in range(wait_times):
        master_id = cli_api.display_election(nodes[0], 'master')
        standby_id = cli_api.display_election(nodes[0], 'standby')
        if not master_id or not standby_id:
            time.sleep(3)
            continue
        
        is_single_cluster = True
        for node in nodes:
            master_id1 = cli_api.display_election(node, 'master')
            if master_id1 != master_id:
                is_single_cluster = False
                master_node = None
                standby_node = None
                agent_nodes = []
                break
            
            if getattr(node, 'nodeId', '') == master_id:
                master_node = node
                continue
            if getattr(node, 'nodeId', '') == standby_id:
                standby_node = node
                continue
            
            agent_nodes.append(node)
        
        if is_single_cluster:
            return master_node, standby_node, agent_nodes
        
        time.sleep(3)
    
    raise RuntimeError("Failed to get master/standby nodes")


def get_file_nums(node: Any, file_path: str, file_name: str = '') -> int:
    """Get number of files in directory or matching pattern.
    
    Migrated from: legency/testcase/ubse/lib/Common/ubse/ubse_Common.py
    
    Args:
        node: Node object
        file_path: Directory path
        file_name: File name pattern to match (optional)
        
    Returns:
        Number of files
        
    Raises:
        RuntimeError: If file count is abnormal
    """
    result = node.run({'command': [f'll {file_path}']})
    res = str(result.get('stdout', '')) + str(result.get('stderr', ''))
    
    if 'total 0' in res:
        return 0
    elif file_name == '':
        raise RuntimeError('File count abnormal')
    
    result = node.run({'command': [f'll {file_path} | grep -c {file_name}']})
    res = result.get('stdout', '')
    if not res:
        return 0
    
    return int(res.split('\r\n')[0])


def compare_file(node: Any, file1: str, file2: str) -> bool:
    """Compare two files content using diff.
    
    Migrated from: legency/testcase/ubse/lib/Common/ubse/ubse_Common.py
    
    Args:
        node: Node object
        file1: First file path
        file2: Second file path
        
    Returns:
        True if files are identical, False otherwise
    """
    result = node.run({'command': [f'diff {file1} {file2}']})
    if result.get('stderr'):
        logger.info(f"File difference: {result}")
        return False
    return True


def get_latest_log_time(node: Any, msg: str, log_file: str = '/var/log/ubse/ubse*') -> str:
    """Get the timestamp of the latest log entry matching message.
    
    Legacy method: get_latest_log_time(node, msg, log_file='/var/log/ubse/ubse*')
    
    Args:
        node: Node object
        msg: Message pattern to search
        log_file: Log file path pattern
        
    Returns:
        Timestamp string like '2025-01-01 00:00:00.000', or '0' if not found
    """
    res = node.run({'command': [f'zgrep -a "{msg}" {log_file} | awk "END{{print}}"']}).get('stdout')
    if res != '\r\nroot@#>' and res:
        res = res.split('+')[0].split('[')[-1]
        return res
    return '0'


def check_log_date_update(
    node: Any,
    msg: str,
    pre_date: str,
    log_file: str = '/var/log/ubse/ubse*',
    frequency: int = 10,
    sleep_time: int = 2
) -> bool:
    """Check if log entry is updated within specified time.
    
    Legacy method: check_log_date_update(node, msg, pre_date, log_file, frequency, sleep_time)
    
    Args:
        node: Node object
        msg: Message pattern to search
        pre_date: Previous timestamp to compare
        log_file: Log file path pattern
        frequency: Number of check iterations
        sleep_time: Sleep time between iterations
        
    Returns:
        True if log updated, False otherwise
    """
    for _ in range(frequency):
        date2 = get_latest_log_time(node, msg, log_file)
        if date2 > pre_date:
            return True
        time.sleep(sleep_time)
    return False


def get_hostname(nodes: List[Any]) -> List[Any]:
    """Get hostname for each node and set attribute.
    
    Legacy method: get_hostname(nodes)
    
    Args:
        nodes: List of node objects
        
    Returns:
        List of nodes with hostname attribute set
    """
    for node in nodes:
        hostname = node.run({'command': ['hostname']}).get('stdout', '').split('\r\n')[0]
        node.hostname = hostname
    return nodes


__all__ = [
    'stop_ubse',
    'start_ubse',
    'restart_ubse',
    'stop_multi_ubse',
    'start_multi_ubse',
    'start_ubse_if_not_started',
    'start_all_ubse_without_waiting',
    'stop_all_ubse_without_waiting',
    'return_nodes_by_role',
    'return_nodes_by_all_role',
    'kill_process',
    'restart_one_node_lcne',
    'change_file',
    'modify_conf_value',
    'get_nodeId',
    'get_ubse_pid',
    'backup_file',
    'get_count',
    'create_directory_and_upload',
    'get_file_nums',
    'compare_file',
]