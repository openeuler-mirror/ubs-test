# -*- coding: utf-8 -*-
"""UniAutos node stub for pytest compatibility.

This module provides minimal stub implementations needed for ubturbo test cases:
- Linux: Node adapter stub (not in libs.core.base.py)

Note: Case/Logger/断言 methods are NOT duplicated here - they are in libs.core.base.TestCase.
ATBaseCase now inherits TestCase directly, eliminating duplicate functionality.
"""

from typing import Any, Dict


class Linux:
    """Stub implementation of UniAutos.Device.Host.Linux.
    
    Represents a Linux host node in the test environment.
    Provides minimal interface for node.run() compatibility.
    """
    
    def __init__(self, hostname: str = None, ip_address: str = None):
        self.hostname = hostname or "localhost"
        self.ip_address = ip_address or "127.0.0.1"
        self.localIP = self.ip_address
    
    def run(self, command_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command on the host (stub implementation).
        
        Args:
            command_dict: Dictionary with:
                - 'command': List of command strings
                - 'waitstr': Expected wait string (default '#')
                - 'timeout': Timeout in seconds
        
        Returns:
            Dict with 'stdout', 'stderr', 'rc'
        """
        return {'stdout': '', 'stderr': '', 'rc': 0}
    
    def getIpAddress(self) -> str:
        """Get the IP address of this host."""
        return self.ip_address
    
    def waitForReboot(self, waitForShutdown: bool = True, timeout: int = 300):
        """Wait for host to reboot (stub)."""
        pass


class Resource:
    """Stub implementation of resource object.
    
    Simple container for hosts dictionary.
    """
    
    def __init__(self, hosts: Dict[str, Linux] = None):
        self.hosts = hosts or {}


__all__ = ['Linux', 'Resource']