"""UBSE进程操作模块.

提供UBSE进程的启动、停止、重启和状态检查功能。

Usage:
    from libs.modules.ubse.common.ubse_process_ops import start_ubse
    start_ubse(node)
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from libs.core import file_ops, process_ops
from libs.modules.ubse.api import cli_api

logger = logging.getLogger(__name__)


def stop_ubse(node: Any) -> bool:
    """停止UBSE进程.

    Args:
        node: Node object with run() method

    Returns:
        True if stopped successfully without timeout or coredump.
        False if timeout or coredump occurred during stop.

    Example:
        result = stop_ubse(node)
        if result:
            logger.info("UBSE stopped successfully")
    """
    pid = process_ops.get_process_pid(node, "/usr/bin/ubse")
    if not pid:
        return True

    stop_timeout_before = file_ops.get_latest_journal_date(
        node, "Failed with result 'timeout'"
    )
    stop_coredump_before = file_ops.get_latest_journal_date(node, "core-dump")

    process_ops.stop_process(node, "ubse")

    stop_timeout_after = file_ops.get_latest_journal_date(
        node, "Failed with result 'timeout'"
    )
    stop_coredump_after = file_ops.get_latest_journal_date(node, "core-dump")

    logger.info(
        f"coredump、timeout: before=({stop_coredump_before}, {stop_timeout_before}), "
        f"after=({stop_coredump_after}, {stop_timeout_after})"
    )

    return (
        stop_coredump_before == stop_coredump_after
        and stop_timeout_before == stop_timeout_after
    )


def start_ubse(node: Any) -> bool:
    """启动UBSE进程.

    Args:
        node: Node object with run() method

    Returns:
        True if started successfully with valid PID.
        False if failed to start.

    Example:
        result = start_ubse(node)
        if not result:
            logger.error("Failed to start UBSE")
    """
    process_ops.start_process(node, "ubse")
    time.sleep(1)

    pid = process_ops.get_process_pid(node, "/usr/bin/ubse")
    if pid:
        logger.info(f"Successfully started ubse, PID: {pid}")
        return True

    logger.error("Failed to start ubse")
    return False


def restart_ubse(node: Any) -> bool:
    """重启UBSE进程.

    Args:
        node: Node object with run() method

    Returns:
        True if restarted successfully without timeout or coredump.
        False if restart failed or timeout/coredump occurred.

    Example:
        result = restart_ubse(node)
        if not result:
            logger.error("UBSE restart failed")
    """
    timeout_count_before = file_ops.get_latest_journal_date(
        node, "Failed with result 'timeout'"
    )
    coredump_count_before = file_ops.get_latest_journal_date(node, "core-dump")
    restart_success_count_before = file_ops.get_latest_journal_date(
        node, "started successfully"
    )

    process_ops.restart_process(node, "ubse & disown")

    for attempt in range(20):
        current_count = file_ops.get_latest_journal_date(node, "started successfully")
        if current_count == restart_success_count_before and attempt == 19:
            process_ops.check_process_status(node, "ubse")
            logger.error(f"{node.localIP}节点启动UBSE进程失败")
            return False
        if current_count != restart_success_count_before:
            break
        time.sleep(6)

    timeout_count_after = file_ops.get_latest_journal_date(
        node, "Failed with result 'timeout'"
    )
    coredump_count_after = file_ops.get_latest_journal_date(node, "core-dump")

    if timeout_count_after != timeout_count_before:
        logger.error(f"{node.localIP}节点发生timeout")
        return False

    if coredump_count_after != coredump_count_before:
        logger.error(f"{node.localIP}节点发生coredump")
        return False

    return True


def check_ubse_status(node: Any, action: str, expected_count: int = 0) -> bool:
    """检查UBSE服务状态.

    Args:
        node: Node object with run() method
        action: Action performed ('start' or 'stop')
        expected_count: Expected log count (optional, default 0)

    Returns:
        True if status matches expected action result.
        False if status does not match.

    Example:
        result = check_ubse_status(node, "start")
        if not result:
            logger.error("UBSE not running after start")
    """
    output = process_ops.check_process_status(node, "ubse")

    if action == "start":
        if "active (running)" in output:
            logger.info("ubse is running")
            return True
        logger.error("ubse not running after start")
        return False

    if action == "stop":
        if "inactive (dead)" in output or "stopped" in output:
            logger.info("ubse is stopped")
            return True
        logger.error("ubse not stopped")
        return False

    return False


def start_ubse_if_not_started(nodes: list[Any]) -> bool:
    """启动未运行的UBSE进程.

    Args:
        nodes: List of node objects

    Returns:
        True if all nodes processed successfully.

    Example:
        result = start_ubse_if_not_started(nodes)
        if not result:
            logger.error("Failed to start UBSE on some nodes")
    """
    for node in nodes:
        pid = process_ops.get_process_pid(node, "/usr/bin/ubse")
        logger.info(f"Node {node.localIP} PID: {pid}")
        if not pid:
            start_ubse(node)
    return True


def start_all_ubse_without_waiting(
    nodes: list[Any], time_wait: int = 0
) -> bool:
    """在所有节点上启动UBSE进程（不等待完成）.

    Args:
        nodes: List of node objects
        time_wait: Time to wait between node starts (optional, default 0)

    Returns:
        True if all nodes started successfully.
        False if any node failed to start.

    Example:
        result = start_all_ubse_without_waiting(nodes, time_wait=2)
        if not result:
            logger.error("Some nodes failed to start UBSE")
    """
    start_success_count_before = []
    is_start_successful = True

    for node in nodes:
        if time_wait > 0:
            time.sleep(time_wait)
        start_success_count_before.append(
            file_ops.get_latest_journal_date(node, "started successfully")
        )
        process_ops.start_process(node, "ubse & disown")

    node_num = len(nodes)
    for attempt in range(20):
        count = 0
        for idx, node in enumerate(nodes):
            current_count = file_ops.get_latest_journal_date(
                node, "started successfully"
            )
            if current_count == start_success_count_before[idx] and attempt == 19:
                is_start_successful = False
                process_ops.check_process_status(node, "ubse")
                logger.error(f"{node.localIP}节点启动ubse进程失败")
            if current_count != start_success_count_before[idx]:
                count += 1
        time.sleep(6)
        if count == node_num:
            break

    logger.info("打印各节点进程号")
    for node in nodes:
        pid = process_ops.get_process_pid(node, "/usr/bin/ubse")
        logger.info(f"{node.localIP}对应的进程号为: {pid}")

    time.sleep(2)
    return is_start_successful



def stop_all_ubse_without_waiting(nodes: list[Any]) -> bool:
    """在所有节点上停止UBSE进程（不等待完成）.

    Args:
        nodes: List of node objects

    Returns:
        True if all nodes stopped successfully.
        False if any node failed to stop.

    Example:
        result = stop_all_ubse_without_waiting(nodes)
        if not result:
            logger.error("Some nodes failed to stop UBSE")
    """
    is_stop_successful = True
    temp_nodes = nodes.copy()

    for node in nodes:
        pid = process_ops.get_process_pid(node, "/usr/bin/ubse")
        if not pid:
            temp_nodes.remove(node)

    for node in temp_nodes:
        process_ops.stop_process(node, "ubse & disown")

    node_num = len(temp_nodes)
    for attempt in range(30):
        count = 0
        time.sleep(3)
        for node in temp_nodes:
            pid = process_ops.get_process_pid(node, "/usr/bin/ubse")
            if pid and attempt == 29:
                is_stop_successful = False
                timestamp = datetime.now(tz=timezone(timedelta(hours=8))).strftime(
                    "%Y%m%d_%H%M%S.%f"
                )[:-3]
                process_ops.check_process_status(node, "ubse")
                logger.error(
                    f"{getattr(node, 'localIP', 'unknown')} node stop ubse failed"
                )
            if not pid:
                count += 1
        if count == node_num:
            break

    return is_stop_successful


def restart_all_ubse_without_waiting(nodes: list[Any]) -> bool:
    """在所有节点上重启UBSE进程（不等待完成）.

    Args:
        nodes: List of node objects

    Returns:
        True if all nodes restarted successfully without timeout or coredump.
        False if any node failed or timeout/coredump occurred.

    Example:
        result = restart_all_ubse_without_waiting(nodes)
        if not result:
            logger.error("Some nodes failed to restart UBSE")
    """
    node_num = len(nodes)
    restart_success_count_before = []
    timeout_count_before = []
    coredump_count_before = []
    is_restart_successful = True

    for node in nodes:
        timeout_count_before.append(
            file_ops.get_latest_journal_date(node, "Failed with result 'timeout'")
        )
        coredump_count_before.append(
            file_ops.get_latest_journal_date(node, "core-dump")
        )
        restart_success_count_before.append(
            file_ops.get_latest_journal_date(node, "started successfully")
        )
        process_ops.restart_process(node, "ubse & disown")

    for attempt in range(20):
        count = 0
        for idx, node in enumerate(nodes):
            current_count = file_ops.get_latest_journal_date(
                node, "started successfully"
            )
            if current_count == restart_success_count_before[idx] and attempt == 19:
                is_restart_successful = False
                process_ops.check_process_status(node, "ubse")
                logger.error(f"{node.localIP}节点启动UBSE进程失败")
            if current_count != restart_success_count_before[idx]:
                count += 1
        time.sleep(6)
        if count == node_num:
            break

    for idx, node in enumerate(nodes):
        timeout_count_after = file_ops.get_latest_journal_date(
            node, "Failed with result 'timeout'"
        )
        coredump_count_after = file_ops.get_latest_journal_date(node, "core-dump")

        if timeout_count_after != timeout_count_before[idx]:
            is_restart_successful = False
            logger.error(f"{node.localIP}节点发生timeout")

        if coredump_count_after != coredump_count_before[idx]:
            is_restart_successful = False
            logger.error(f"{node.localIP}节点发生coredump")

    return is_restart_successful


def return_nodes_by_all_role(
    nodes: list[Any], wait_times: int = 60
) -> tuple[Optional[Any], Optional[Any], list[Any]]:
    """根据角色返回主节点、备节点和代理节点.

    Args:
        nodes: List of node objects
        wait_times: Maximum wait times in seconds (optional, default 60)

    Returns:
        Tuple containing:
        - master_node: Master node object or None if not found
        - standby_node: Standby node object or None if not found
        - agent_nodes: List of agent node objects

    Raises:
        RuntimeError: If failed to get master/standby nodes within wait_times

    Example:
        master, standby, agents = return_nodes_by_all_role(nodes)
        if master:
            logger.info(f"Master node: {master.localIP}")
    """
    agent_nodes: list[Any] = []
    master_node: Optional[Any] = None
    standby_node: Optional[Any] = None

    for _ in range(wait_times):
        master_id = cli_api.display_election(nodes[0], "master")
        standby_id = cli_api.display_election(nodes[0], "standby")
        if not master_id or not standby_id:
            time.sleep(3)
            continue

        is_single_cluster = True
        for node in nodes:
            master_id_on_node = cli_api.display_election(node, "master")
            if master_id_on_node != master_id:
                is_single_cluster = False
                master_node = None
                standby_node = None
                agent_nodes = []
                break

            if getattr(node, "nodeId", "") == master_id:
                master_node = node
                continue
            if getattr(node, "nodeId", "") == standby_id:
                standby_node = node
                continue

            agent_nodes.append(node)

        if is_single_cluster:
            return master_node, standby_node, agent_nodes

        time.sleep(3)

    raise RuntimeError("Failed to get master/standby nodes")


__all__ = [
    "stop_ubse",
    "start_ubse",
    "restart_ubse",
    "check_ubse_status",
    "start_ubse_if_not_started",
    "start_all_ubse_without_waiting",
    "stop_all_ubse_without_waiting",
    "restart_all_ubse_without_waiting",
    "return_nodes_by_all_role",
]
