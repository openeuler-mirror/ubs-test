"""DFC KV CLI wrapper.

Provides KV-level operations for DFC testing.
"""

import logging
from typing import Any, Dict, Tuple

from libs.ubsio import dfc_global_var as Var
from libs.ubsio.dfc_node_cli import DFCNodeCLI

logger = logging.getLogger(__name__)


class DFCKVCLI:
    """DFC KV CLI wrapper for KV-level operations.
    
    Provides methods for:
    - Execute Python scripts in Docker
    """
    
    def __init__(self, node_cli: DFCNodeCLI):
        """Initialize DFCKVCLI with a DFCNodeCLI.
        
        Args:
            node_cli: DFCNodeCLI instance
        """
        self._node_cli = node_cli
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def Execute_Python_Scripts(self, Scripts_name: str, args: str, 
                                Scripts_path: str = Var.MAP_DOCKER_PATH,
                                Timeout: int = 180) -> Tuple[str, str]:
        """Execute Python script in Docker.
        
        Args:
            Scripts_name: Script name
            args: Script arguments
            Scripts_path: Script path
            docker_name: Docker container name
            Timeout: Timeout in seconds
            
        Returns:
            Tuple of (status, output)
        """
        cmd = f"cd {Scripts_path};python3 {Scripts_name} {args}"
        operation_ret = self._node_cli.run_input(cmd, timeout=Timeout)
        
        if operation_ret.get('rc', -1) != 0:
            if operation_ret.get('stderr'):
                if "AssertionError" in operation_ret.get('stderr'):
                    return '断言错误', operation_ret.get('stderr')
                else:
                    return "未知错误", operation_ret.get('stderr')
            else:
                return "未知错误"
        else:
            if '脚本执行成功' in operation_ret.get('stdout', ''):
                return '脚本执行成功', operation_ret.get('stdout')
            else:
                return "未知错误", operation_ret.get('stdout')