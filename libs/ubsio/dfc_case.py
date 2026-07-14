"""DFC helper functions for pytest test cases.

These standalone functions are used by delete test cases that use pydfc directly.
"""

import os
import random
import string
import logging
from typing import Any, Dict, List

from libs.ubsio import (
    DOCKER_NAME,
    MAP_DOCKER_PATH,
)

logger = logging.getLogger(__name__)


def generate_random_string_digits(min_length: int = 1, max_length: int = 255) -> str:
    """Generate random string with digits.
    
    Args:
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        Random string
    """
    length = random.randint(min_length, max_length)
    if length <= 0:
        return ""
    first_char = random.choice(string.ascii_letters + string.digits)
    allowed_chars = string.ascii_letters + string.digits + "@" + "?" + "_" + "-" + ":"
    remaining_chars = ''.join(random.choices(allowed_chars, k=length - 1))
    return first_char + remaining_chars


def generate_random_data(min_length: int = 1024 * 1024, max_length: int = 8 * 1024 * 1024) -> bytes:
    """Generate random binary data.
    
    Args:
        min_length: Minimum length in bytes
        max_length: Maximum length in bytes
        
    Returns:
        Random bytes
    """
    length = random.randint(min_length, max_length)
    return os.urandom(length)


class DFCNodeCLIHelper:
    """Helper class for DFC node operations.
    
    Provides methods for node-level operations used by Get/Put/Deploy test cases.
    Wraps node.run() calls with Docker-specific command formatting.
    """
    
    def __init__(self, node: Any):
        self.node = node
        self.localIP = getattr(node, 'ip', None) or getattr(node, 'localIP', None)
    
    def run_docker_cmd(self, cmd: str, docker_name: str = DOCKER_NAME, timeout: int = 60) -> Dict[str, Any]:
        """Run command inside Docker container.
        
        Args:
            cmd: Command to run
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            Result dict with stdout, stderr, returnCode
        """
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        return self.node.run({"command": [docker_cmd], "timeout": timeout})
    
    def clear_process(self, process_name: str = 'python3', docker_name: str = DOCKER_NAME) -> None:
        """Clear process in Docker container.
        
        Args:
            process_name: Process name to kill
            docker_name: Docker container name
        """
        pkill_cmd = f"pkill -9 -f {process_name}"
        cmd = f"docker exec {docker_name} bash -c '{pkill_cmd}'"
        self.node.run({"command": [cmd], "timeout": 30})
    
    def delete_for_kvfile(self, put_file: str = 'put_value.txt', get_file: str = 'get_value.txt',
                          work_dir: str = MAP_DOCKER_PATH, docker_name: str = DOCKER_NAME) -> None:
        """Delete KV operation files.
        
        Args:
            put_file: Put file name
            get_file: Get file name
            work_dir: Working directory
            docker_name: Docker container name
        """
        for file in (put_file, get_file):
            cmd = f"rm -f {work_dir}/{file}"
            docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
            self.node.run({"command": [docker_cmd], "timeout": 30})
    
    def delete_file(self, file_name: str, work_dir: str = MAP_DOCKER_PATH, 
                    docker_name: str = DOCKER_NAME) -> None:
        """Delete a file in Docker container.
        
        Args:
            file_name: File name to delete
            work_dir: Working directory
            docker_name: Docker container name
        """
        cmd = f"rm -f {work_dir}/{file_name}"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        self.node.run({"command": [docker_cmd], "timeout": 30})
    

    def Compare_md5sum_file(self, put_file: str = 'put_value.txt', get_file: str = 'get_value.txt',
                            work_dir: str = MAP_DOCKER_PATH, docker_name: str = DOCKER_NAME,
                            timeout: int = 60) -> bool:
        """Compare MD5sum of put and get files.
        
        Args:
            put_file: Put file name
            get_file: Get file name
            work_dir: Working directory
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            True if MD5sum matches, False otherwise
        """
        cmd = f"cd {work_dir};md5sum {put_file} {get_file}"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        result = self.node.run({"command": [docker_cmd], "timeout": timeout})
        
        if result.get("returnCode", -1) != 0:
            return False
        
        stdout = result.get("stdout", "")
        import re
        put_md5sum_ret = re.search(f'(.*?)\\s+{put_file}', stdout)
        put_md5sum = put_md5sum_ret.group().split(' ')[0] if put_md5sum_ret else None
        get_md5sum_ret = re.search(f'(.*?)\\s+{get_file}', stdout)
        get_md5sum = get_md5sum_ret.group().split(' ')[0] if get_md5sum_ret else None
        
        return put_md5sum == get_md5sum if put_md5sum and get_md5sum else False


class DFCKVCLIHelper:
    """Helper class for DFC KV operations.
    
    Provides methods for KV-level operations used by Get/Put test cases.
    Executes Python scripts via pydfc.
    """
    
    def __init__(self, node: Any):
        self.node = node
    
    def Execute_Python_Scripts(self, script_name: str, args: str,
                               scripts_path: str = MAP_DOCKER_PATH,
                               docker_name: str = DOCKER_NAME,
                               timeout: int = 3 * 60) -> tuple:
        """Execute Python script in Docker container.
        
        Args:
            script_name: Script name
            args: Script arguments
            scripts_path: Scripts directory path
            docker_name: Docker container name
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (status, output)
        """
        cmd = f"cd {scripts_path};python3 {script_name} {args}"
        docker_cmd = f"docker exec {docker_name} bash -c '{cmd}'"
        result = self.node.run({"command": [docker_cmd], "timeout": timeout})
        
        rc = result.get("returnCode", -1)
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        
        if rc != 0:
            if stderr:
                if "AssertionError" in stderr:
                    return ('断言错误', stderr)
                else:
                    return ('未知错误', stderr)
            return ('未知错误', stdout)
        else:
            if '脚本执行成功' in stdout:
                return ('脚本执行成功', stdout)
            else:
                return ('未知错误', stdout)