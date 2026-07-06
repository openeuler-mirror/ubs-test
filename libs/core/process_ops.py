"""进程管理操作模块.

提供进程启动、停止、重启、状态查询等功能。
"""

import logging

from typing import Any, Optional

logger = logging.getLogger(__name__)


def get_process_pid(node: Any, process_name: str) -> Optional[int]:
    """获取指定进程的PID.

    Args:
        node: Node object with run() method
        process_name: 进程名称

    Returns:
        进程PID，未找到时返回None。

    Example:
        pid = get_process_pid(node, "nginx")
        if pid:
            print(f"nginx PID: {pid}")
    """
    cmd = f"ps aux | grep {process_name} | grep -v grep | awk '{{print $2}}'"
    res = node.run({"command": [cmd], "timeout": 30})
    stdout = res.get("stdout", "").strip()

    if not stdout:
        return None

    try:
        return int(stdout.split()[0])
    except (ValueError, IndexError):
        logger.warning(f"Failed to parse PID for process: {process_name}")
        return None


def stop_process(node: Any, process_name: str) -> bool:
    """停止指定进程.

    Args:
        node: Node object with run() method
        process_name: 进程名称

    Returns:
        停止成功返回True，失败返回False。

    Example:
        if stop_process(node, "nginx"):
            print("Process stopped successfully")
    """
    cmd = f"systemctl stop {process_name}"
    res = node.run({"command": [cmd], "timeout": 60})
    return res.get("rc", 1) == 0


def start_process(node: Any, process_name: str) -> bool:
    """启动指定进程.

    Args:
        node: Node object with run() method
        process_name: 进程名称

    Returns:
        启动成功返回True，失败返回False。

    Example:
        if start_process(node, "nginx"):
            print("Process started successfully")
    """
    cmd = f"systemctl start {process_name}"
    res = node.run({"command": [cmd], "timeout": 60})
    return res.get("rc", 1) == 0


def restart_process(node: Any, process_name: str) -> bool:
    """重启指定进程.

    Args:
        node: Node object with run() method
        process_name: 进程名称

    Returns:
        重启成功返回True，失败返回False。

    Example:
        if restart_process(node, "nginx"):
            print("Process restarted successfully")
    """
    cmd = f"systemctl restart {process_name}"
    res = node.run({"command": [cmd], "timeout": 60})
    return res.get("rc", 1) == 0


def check_process_is_active(node: Any, process_name: str) -> str:
    """检查进程是否运行.

    Args:
        node: Node object with run() method
        process_name: 进程名称

    Returns:
        进程状态（active/inactive/failed/unknown）。

    Example:
        status = check_process_is_active(node, "nginx")
        print(f"nginx status: {status}")
    """
    cmd = f"systemctl is-active {process_name}"
    res = node.run({"command": [cmd], "timeout": 30})
    return res.get("stdout", "").strip() or "unknown"


def check_process_status(node: Any, process_name: str) -> str:
    """检查进程运行状态详情.

    Args:
        node: Node object with run() method
        process_name: 进程名称

    Returns:
        systemctl status命令的完整输出内容。

    Example:
        output = check_process_status(node, "nginx")
        print(output)
    """
    cmd = f"systemctl status {process_name}"
    result = node.run({"command": [cmd], "timeout": 30})
    output = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    return output


def kill_process(node: Any, pid: str, option: str = "-9") -> bool:
    """按进程PID终止进程.

    Args:
        node: Node object with run() method
        pid: 进程PID
        option: kill命令选项（optional，默认为"-9"强制终止）

    Returns:
        终止成功返回True，失败返回False。

    Example:
        if kill_process(node, "1234"):
            print("Process killed")

        # 使用其他信号
        if kill_process(node, "1234", option="-15"):
            print("Process terminated gracefully")
    """
    cmd = f"kill {option} {pid}"
    result = node.run({"command": [cmd]})
    logger.info(f"Killed process {pid}")
    return result.get("rc", 1) == 0


def pkill_process(node: Any, process_name: str, option: str = "-9") -> bool:
    """按进程名终止进程.

    Args:
        node: Node object with run() method
        process_name: 进程名称
        option: pkill命令选项（optional，默认为"-9"强制终止）

    Returns:
        终止成功返回True，失败返回False。

    Example:
        if pkill_process(node, "nginx"):
            print("Process killed")

        # 使用其他信号
        if pkill_process(node, "nginx", option="-15"):
            print("Process terminated gracefully")
    """
    cmd = f"pkill {option} {process_name}"
    result = node.run({"command": [cmd]})
    logger.info(f"Killed process {process_name}")
    return result.get("rc", 1) == 0


__all__ = [
    "get_process_pid",
    "stop_process",
    "start_process",
    "restart_process",
    "check_process_is_active",
    "check_process_status",
    "kill_process",
    "pkill_process",
]