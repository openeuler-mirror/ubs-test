"""Host adapters for different operating systems.

Migrated from: legency/framework/lib/UniAutos/Device/Host/
Provides Linux host operations with SSH command execution.

Classes:
    Linux: Linux host class with file, disk, iSCSI, and service operations
    NodeAdapter: SSH connection adapter for remote command execution
"""

from libs.host.linux import Linux
from libs.host.node_adapter import NodeAdapter, LocalNodeAdapter, create_node_adapter

__all__ = ["Linux", "NodeAdapter", "LocalNodeAdapter", "create_node_adapter"]