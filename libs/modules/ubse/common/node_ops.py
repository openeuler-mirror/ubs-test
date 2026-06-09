"""Node operations for ubse tests.

Migrated from: legency/testcase/ubse/lib/Common/ubse/ubse_Common.py
Provides node management functions like process management, package installation.
"""

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


def get_nodeId(nodes: List[Any]) -> List[Any]:
    """Set nodeId attribute on nodes.

    Legacy method: get_nodeId(nodes)

    Args:
        nodes: List of node objects

    Returns:
        List of nodes with nodeId set
    """
    for node in nodes:
        if not hasattr(node, "nodeId"):
            result = node.run({"command": ["hostname"]})
            hostname = result.get("stdout", "").split("\r\n")[0]
            node.nodeId = hostname
    return nodes