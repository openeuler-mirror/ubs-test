"""RPM包管理操作模块.

提供RPM包安装、更新、卸载和版本查询功能。
"""

import logging
import re
import time

from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PACKAGES_PATH = "/opt/install/package"


def get_version(
    node: Any,
    name: str
) -> Dict[str, str]:
    """获取RPM包的版本信息.

    Args:
        node: Node object with run() method
        name: RPM包名称

    Returns:
        成功返回包含"version"和"release"的字典，失败返回空字典。

    Example:
        info = get_version(node, "nginx")
        if info:
            print(f"Version: {info['version']}, Release: {info['release']}")
    """
    wait_time = 0
    while wait_time < 60:
        res = node.run({"command": [f"rpm -qi {name}"]})
        output = str(res.get("stdout", "")) + str(res.get("stderr", ""))

        if "not installed" in output:
            return {}

        stdout = res.get("stdout", "")
        if stdout:
            version_info = stdout.rstrip("\r\nroot@#>").split("\n")[:-5]
            try:
                version = version_info[1].split(": ")[1].split("\r")[0]
                release = version_info[2].split(": ")[1].split("\r")[0]
                return {"version": version, "release": release}
            except (IndexError, ValueError):
                logger.warning(f"Failed to parse version info for: {name}")
                return {}

        wait_time += 5
        time.sleep(5)

    logger.error(f"Timeout while getting version for: {name}")
    return {}


def rpm_action(
    node: Any,
    action: str,
    package: str,
    tar_path: Optional[str] = None
) -> bool:
    """执行RPM包操作（安装、更新、卸载）.

    Args:
        node: Node object with run() method
        action: 操作类型，可选值：install, install_force, update, downgrade, uninstall
        package: RPM包名称或文件名
        tar_path: RPM包所在目录（optional，默认为/opt/install/package）

    Returns:
        操作成功返回True，失败返回False。

    Example:
        if rpm_action(node, "install", "nginx-1.18.0.rpm"):
            print("Package installed")

        # 强制安装
        if rpm_action(node, "install_force", "nginx-1.18.0.rpm"):
            print("Package force installed")

        # 卸载
        if rpm_action(node, "uninstall", "nginx"):
            print("Package uninstalled")
    """
    actions = {
        "install": "-ivh",
        "install_force": "-ivh --force",
        "update": "-Uvh",
        "downgrade": "-Uvh --oldpackage",
        "uninstall": "-evh"
    }

    if action not in actions:
        logger.error(f"Invalid action: {action}")
        return False

    tar_path = tar_path or PACKAGES_PATH

    if action != "uninstall":
        res = node.run({"command": [f"rpm {actions[action]} {tar_path}/{package}"]})
        output = str(res.get("stdout", "")) + str(res.get("stderr", ""))

        if not output:
            logger.error(f"RPM {action} failed for: {package}")
            return False

        match = re.match(r"^(.*?)-[0-9].*\.(?:rpm|noarch\.rpm|aarch64\.rpm)$", package)
        if not match:
            logger.error(f"Failed to parse package name: {package}")
            return False

        name = match.group(1)
        info = get_version(node, name)
        return bool(info)
    else:
        res = node.run({"command": [f"rpm {actions[action]} {package}"]})
        output = str(res.get("stdout", "")) + str(res.get("stderr", ""))

        if not output:
            logger.error(f"RPM {action} failed for: {package}")
            return False

        info = get_version(node, package)
        return not info


__all__ = [
    "get_version",
    "rpm_action",
]