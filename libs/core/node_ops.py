"""节点操作模块.

提供节点ID获取、主机名设置等功能。
"""

import logging

from typing import Any, List

logger = logging.getLogger(__name__)


def get_nodeId(nodes: List[Any]) -> List[Any]:
    """获取并设置节点ID属性.

    为每个节点设置nodeId属性（如果不存在），值为节点主机名。

    Args:
        nodes: 节点对象列表

    Returns:
        设置了nodeId属性的节点列表。

    Example:
        nodes = get_nodeId(nodes)
        print(nodes[0].nodeId)
    """
    for node in nodes:
        if not hasattr(node, "nodeId"):
            result = node.run({"command": ["hostname"]})
            hostname = result.get("stdout", "").rstrip("\r\nroot@#>").split("\n")[0]
            node.nodeId = hostname
    return nodes


def get_hostname(nodes: List[Any]) -> List[Any]:
    """获取并设置节点主机名属性.

    为每个节点设置hostname属性。

    Args:
        nodes: 节点对象列表

    Returns:
        设置了hostname属性的节点列表。

    Example:
        nodes = get_hostname(nodes)
        print(nodes[0].hostname)
    """
    for node in nodes:
        hostname = node.run({"command": ["hostname"]}).get("stdout", "").rstrip("\r\nroot@#>").split("\n")[0]
        node.hostname = hostname
    return nodes


__all__ = [
    "get_nodeId",
    "get_hostname",
]