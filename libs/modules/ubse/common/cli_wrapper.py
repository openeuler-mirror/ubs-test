"""CLI command wrappers for RackControl tests.

Provides CLI command execution and output parsing functions.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from libs.modules.ubse.api.cli_api import(
    display_cluster
)
logger = logging.getLogger(__name__)



def get_node_role(nodes: List[Any]) -> Dict[str, str]:
    """Get node roles from cluster info.

    Args:
        nodes: List of node objects

    Returns:
        Dictionary mapping nodeId to role
    """
    if not nodes:
        return {}

    node = nodes[0]
    cluster_info_list = display_cluster(node)

    role_dict = {}
    for cluster_info in cluster_info_list:
        node_name = cluster_info.get("node", "")
        pattern = r"\([^()]*\)"
        matches = re.findall(pattern, node_name)
        if matches:
            node_id = re.sub(r"[()]", "", matches[0])
            role_dict[node_id] = cluster_info.get("role", "")

    return role_dict


def get_bonding_eid(node: Any) -> Dict[str, str]:
    """Get bonding EID from node.

    Args:
        node: Node object

    Returns:
        Dictionary mapping nodeId to bonding EID
    """
    result = node.run({"command": ["ubsectl display cluster | grep -A 1 'bonding'"]})
    output = result.get("stdout", "")

    eid_dict = {}
    lines = output.split("\r\n")

    for line in lines:
        if "bondingeid" in line.lower():
            parts = line.strip().split()
            if len(parts) >= 2:
                eid_dict[node.nodeId if hasattr(node, "nodeId") else "unknown"] = parts[-1]

    logger.info(f"Found bonding EID: {eid_dict}")
    return eid_dict




__all__ = [
    "get_node_role",
    "get_bonding_eid"
]
