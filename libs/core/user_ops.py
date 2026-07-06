"""用户管理操作模块.

提供用户创建、删除、UID/GID查询等功能。
"""

import logging
import re

from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def create_user(
    node: Any,
    name: str = "test_user",
    group: Optional[str] = None,
    passwd: Optional[str] = None
) -> bool:
    """创建用户并设置密码和用户组.

    Args:
        node: Node object with run() method
        name: 用户名（optional，默认为test_user）
        group: 用户组名（optional，默认不创建用户组）
        passwd: 用户密码（optional，默认不设置密码）

    Returns:
        创建成功返回True，失败返回False。

    Example:
        if create_user(node, "myuser"):
            print("User created")

        # 创建带密码和用户组的用户
        if create_user(node, "myuser", group="mygroup", passwd="mypass"):
            print("User created with group and password")
    """
    if passwd:
        node.run({"command": [f"useradd {name} && echo {passwd} | passwd --stdin {name}"]})
    else:
        node.run({"command": [f"useradd {name}"]})

    if group:
        node.run({"command": [f"groupadd {group}"]})
        node.run({"command": [f"usermod -aG {group} {name}"]})

    res = node.run({"command": [f"id {name}"]}).get("stdout", "")
    if not res or "no such user" in res:
        logger.error(f"Failed to create user: {name}")
        return False

    return True


def get_uid_gid(
        node: Any,
        username: str
) -> Tuple[Optional[int], Optional[int]]:
    """获取用户的UID和GID.

    Args:
        node: Node object with run() method
        username: 用户名

    Returns:
        包含UID和GID的元组，格式为 (uid, gid)。
        解析失败时对应位置返回None。

    Example:
        uid, gid = get_uid_gid(node, "nginx")
        if uid and gid:
            print(f"UID: {uid}, GID: {gid}")
    """
    res = node.run({"command": [f"id {username}"]}).get("stdout", "")
    res = res.rstrip("\r\nroot@#>")

    uid_match = re.search(r"uid=(\d+)", res)
    gid_match = re.search(r"gid=(\d+)", res)

    uid = int(uid_match.group(1)) if uid_match else None
    gid = int(gid_match.group(1)) if gid_match else None

    return uid, gid


def delete_user(
    node: Any,
    name: str = "test_user",
    group: Optional[str] = None
) -> bool:
    """删除用户和关联的用户组.

    Args:
        node: Node object with run() method
        name: 用户名（optional，默认为test_user）
        group: 用户组名（optional，默认不删除用户组）

    Returns:
        删除成功返回True，失败返回False。

    Example:
        if delete_user(node, "myuser"):
            print("User deleted")

        # 删除用户并同时删除用户组
        if delete_user(node, "myuser", group="mygroup"):
            print("User and group deleted")
    """
    node.run({"command": [f"userdel {name}"]})

    if group:
        node.run({"command": [f"groupdel {group}"]})

    res = node.run({"command": [f"id {name}"]}).get("stdout", "")
    if res and "no such user" not in res:
        logger.warning(f"User still exists after deletion: {name}")
        return False

    logger.info(f"Deleted user: {name}")
    return True


__all__ = [
    "create_user",
    "get_uid_gid",
    "delete_user",
]