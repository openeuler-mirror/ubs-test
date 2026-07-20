"""文件操作模块.

提供文件修改、备份、上传、比较等功能。
"""

import logging
import time

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def change_file(
    nodes: List[Any],
    key: str,
    value: str,
    path: str,
    filename: str
) -> bool:
    """在多个节点上修改配置文件中的键值.

    Args:
        nodes: 节点对象列表
        key: 要修改的键名
        value: 新的键值
        path: 文件所在目录路径
        filename: 文件名

    Returns:
        修改成功返回True。

    Example:
        if change_file(nodes, "MAX_CONN", "1000", "/etc/app", "config.ini"):
            print("Config changed")
    """
    for node in nodes:
        cmd = f"sed -i 's/{key}=.*/{key}={value}/' {path}/{filename}"
        node.run({"command": [cmd]})
    return True


def modify_conf_value(node: Any, key: str, value: Optional[str] = None) -> bool:
    """修改ubse.conf配置文件中的键值.

    Args:
        node: Node object with run() method
        key: 配置键名
        value: 新的配置值（optional，默认为None表示删除该键）

    Returns:
        修改成功返回True。

    Example:
        # 修改配置值
        if modify_conf_value(node, "MAX_CONN", "1000"):
            print("Config updated")

        # 删除配置项
        if modify_conf_value(node, "MAX_CONN"):
            print("Config removed")
    """
    conf_path = "/usr/local/softbus/ctrlbus/conf/ubse.conf"
    if value is None:
        cmd = f"sed -i '/{key}=/d' {conf_path}"
    else:
        cmd = f"sed -i 's/{key}=.*/{key}={value}/' {conf_path}"
    node.run({"command": [cmd]})
    return True


def backup_file(
    node: Any,
    path1: str,
    path2: str,
    filename: str
) -> bool:
    """备份文件到指定目录.

    Args:
        node: Node object with run() method
        path1: 源文件目录路径
        path2: 目标目录路径
        filename: 文件名

    Returns:
        备份成功返回True，失败返回False。

    Example:
        if backup_file(node, "/etc/app", "/backup/app", "config.ini"):
            print("Backup successful")
    """
    res = node.run({"command": [f"ls {path2}"]})
    if not res.get("stdout"):
        node.run({"command": [f"mkdir -p {path2}"]})
    else:
        logger.info(f"Directory {path2} already exists")

    node.run({"command": [f"cp -p {path1}/{filename} {path2}/{filename}"]})
    res = node.run({"command": [f"cat {path2}/{filename}"]})
    return res.get("stdout") is not None


def create_directory_and_upload(
    nodes: List[Any],
    files: List[str],
    relative_path: str,
    dir_path: str,
    source_base: Optional[str] = None
) -> bool:
    """在节点上创建目录并上传文件.

    Args:
        nodes: 节点对象列表
        files: 要上传的文件列表
        relative_path: 相对于源目录的路径
        dir_path: 目标目录路径
        source_base: 源文件基础目录（optional，默认为工作空间根目录）

    Returns:
        所有节点上传成功返回True，否则返回False。

    Example:
        if create_directory_and_upload(
            nodes, ["config.ini", "app.bin"], "data/config", "/opt/app"
        ):
            print("Files uploaded")
    """
    if not source_base:
        source_base = str(Path(__file__).parent.parent.parent).replace("\\", "/")

    success = True
    for node in nodes:
        try:
            node.run({"command": [f"mkdir -p {dir_path}"]})
            for file in files:
                src_path = f"{source_base}/{relative_path}/{file}"
                dst_path = f"{dir_path}/{file}"
                logger.info(f"Uploading {src_path} to {node.nodeId}:{dst_path}")
                node.putFile(src_path, dst_path)
            node.run({"command": [f"chmod -R 777 {dir_path}"]})
        except Exception as e:
            logger.error(f"Failed to upload to {node.nodeId}: {e}")
            success = False

    return success


def get_file_nums(
    node: Any,
    file_path: str,
    file_name: Optional[str] = None
) -> int:
    """获取目录中的文件数量.

    Args:
        node: Node object with run() method
        file_path: 目录路径
        file_name: 文件名匹配模式（optional，默认统计所有文件）

    Returns:
        文件数量。

    Example:
        count = get_file_nums(node, "/var/log")
        print(f"Log files: {count}")

        # 按模式匹配
        count = get_file_nums(node, "/var/log", "error*.log")
        print(f"Error logs: {count}")
    """
    res = node.run({"command": [f"ll {file_path}"]})
    output = str(res.get("stdout", "")) + str(res.get("stderr", ""))

    if "total 0" in output:
        return 0

    if not file_name:
        res = node.run({"command": [f"ll {file_path} | grep -c '^-'"]})
    else:
        res = node.run({"command": [f"ll {file_path} | grep -c {file_name}"]})

    stdout = res.get("stdout", "")
    if not stdout:
        return 0

    return int(stdout.rstrip("\r\nroot@#>").split("\n")[0])


def compare_file(node: Any, file1: str, file2: str) -> bool:
    """比较两个文件内容是否相同.

    Args:
        node: Node object with run() method
        file1: 第一个文件路径
        file2: 第二个文件路径

    Returns:
        文件内容相同返回True，不同返回False。

    Example:
        if compare_file(node, "/etc/app/config.ini", "/backup/config.ini"):
            print("Files are identical")
    """
    res = node.run({"command": [f"diff {file1} {file2}"]})
    return not res.get("stderr")


def get_latest_log_date(
    node: Any,
    msg: str,
    log_file: str = "/var/log/ubse/ubse*"
) -> str:
    """获取最新日志条目的时间戳.

    Args:
        node: Node object with run() method
        msg: 日志消息匹配模式
        log_file: 日志文件路径模式（optional，默认为/var/log/ubse/ubse*）

    Returns:
        时间戳字符串（如'2025-01-01 00:00:00.000'），未找到返回'0'。

    Example:
        date = get_latest_log_date(node, "ERROR")
        if date != '0':
            print(f"Last error: {date}")
    """
    res = node.run({"command": [f"zgrep -a '{msg}' {log_file} | awk 'END{{print}}'"]})
    stdout = res.get("stdout", "")

    if stdout and stdout != "\r\nroot@#>":
        return stdout.split("+")[0].split("[")[-1]

    return "0"


def get_latest_journal_date(node: Any, keyword: str) -> str:
    """获取最新一条journal日志的时间并转换格式.

    Args:
        node: Node object with run() method
        keyword: 日志关键字

    Returns:
        格式化后的时间字符串（MM-DD HH:MM:SS），未找到时返回'0'。

    Example:
        date = get_latest_journal_date(node, "error")
        if date != '0':
            print(f"Last error: {date}")
    """
    def _get_date_with_retry(node: Any, keyword: str, retry_count: int = 0) -> str:
        res = node.run({
            "command": [f"journalctl -u ubse.service | grep -v ubse_uds_client | grep '{keyword}' | awk 'END{{print $1, $2, $3}}'"]
        })

        stdout = res.get("stdout", "")
        if not stdout or not stdout.split("\r\n")[0].strip():
            return "0"
        try:
            date_str = stdout.split("\r\n")[0]
            if date_str.strip():
                date_str = datetime.strptime(date_str, "%b %d %H:%M:%S").strftime("%m-%d %H:%M:%S")
        except ValueError:
            logger.error(f"Failed to parse journal date: {stdout[:200]}")
            if retry_count < 3:
                return _get_date_with_retry(node, keyword, retry_count + 1)
            return "0"
        return date_str
    
    return _get_date_with_retry(node, keyword)


def check_log_date_update(
    node: Any,
    msg: str,
    pre_date: str,
    log_file: str = "/var/log/ubse/ubse*",
    frequency: int = 10,
    sleep_time: int = 2
) -> bool:
    """检查日志条目是否在指定时间内更新.

    Args:
        node: Node object with run() method
        msg: 日志消息匹配模式
        pre_date: 之前的时间戳用于比较
        log_file: 日志文件路径模式（optional）
        frequency: 检查次数（optional，默认10次）
        sleep_time: 每次检查间隔秒数（optional，默认2秒）

    Returns:
        日志已更新返回True，否则返回False。

    Example:
        if check_log_date_update(node, "ERROR", old_date):
            print("New error occurred")
    """
    for _ in range(frequency):
        date2 = get_latest_log_date(node, msg, log_file)
        if date2 > pre_date:
            return True
        time.sleep(sleep_time)

    return False


__all__ = [
    "change_file",
    "modify_conf_value",
    "backup_file",
    "get_latest_journal_date",
    "create_directory_and_upload",
    "get_file_nums",
    "compare_file",
    "get_latest_log_date",
    "check_log_date_update",
]