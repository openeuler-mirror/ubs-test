"""Node adapter for SSH command execution.

Migrated from: legency/framework/lib/UniAutos/Command/Connection/SSHConnection.py
Provides SSH connection with shell-mode execution, waitstr support, and file transfer.

Key features from Legacy SSHConnection:
- Shell mode (invoke_shell) for interactive commands
- waitstr pattern matching for command completion
- Windows SSH special handling
- Automatic reconnect on timeout
- ANSI color code filtering
- File transfer via SFTP

Usage:
    node = NodeAdapter({"ip": "192.168.1.1", "port": 22, "user": "root", "password": "..."})
    result = node.run({"command": ["ls -la"], "timeout": 30})
    result = node.run({"command": ["python3 app.py"], "waitstr": "app>", "timeout": 60})
"""

import logging
import os
import re
import socket
import time
import threading
import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConnectionException(Exception):
    """SSH connection exception."""
    pass


class TimeoutException(Exception):
    """Command execution timeout exception."""
    pass


class NodeAdapter:
    """SSH connection adapter with shell-mode execution.
    
    Compatible with legacy SSHConnection.run() interface.
    
    Attributes:
        ip: Node IP address
        port: SSH port (default: 22)
        user: SSH username
        password: SSH password
        nodeId: Node identifier
        localIP: Local IP address
        detail: Extended parameters (params field from config)
    
    Example:
        node = NodeAdapter({
            "ip": "192.168.1.1",
            "port": 22,
            "user": "root",
            "password": "password",
            "nodeId": "Node0"
        })
        
        # Simple command
        result = node.run({"command": ["hostname"], "timeout": 10})
        
        # Interactive command with waitstr
        result = node.run({
            "command": ["python3 ubse_mem_app.py"],
            "waitstr": "ubse_mem_app>",
            "timeout": 60
        })
        
        # Multi-step interactive command
        result = node.run({
            "command": ["python3 app.py"],
            "input": ["cmd1", "prompt1", "cmd2", "prompt2"],
            "timeout": 120
        })
    """
    
    ip: str
    port: int
    user: str
    password: str
    nodeId: str
    localIP: str
    detail: Dict[str, Any]
    linesep: str
    transport: Optional[paramiko.Transport]
    channel: Optional[paramiko.Channel]
    is_windows: bool
    waitstrDict: Dict[str, str]
    status: Optional[str]
    current_cmd: str
    clear_channel: bool
    
    def __init__(self, node_info: Dict[str, Any]) -> None:
        """Initialize from node info dictionary.
        
        Args:
            node_info: Dictionary containing:
                - ip: Node IP address
                - port: SSH port (default: 22)
                - user: SSH username (default: "root")
                - password: SSH password
                - nodeId: Node identifier
                - localIP: Local IP (optional)
                - params: Extended parameters dict (optional)
        """
        self.ip = node_info.get("ip", "")
        self.port = node_info.get("port", 22)
        self.username = node_info.get("user", "root")
        self.password = node_info.get("password", "")
        self.nodeId = node_info.get("nodeId", node_info.get("id", ""))
        self.localIP = node_info.get("localIP", "")
        self.detail = node_info.get("params", {})
        
        self.linesep = '\n'
        self.transport: Optional[paramiko.Transport] = None
        self.channel: Optional[paramiko.Channel] = None
        self.is_windows = False
        self.waitstrDict: Dict[str, str] = {}
        self.status: Optional[str] = None
        self.current_cmd = ''
        self.clear_channel = False
    
    def create_client(self) -> paramiko.Transport:
        """Create SSH transport connection.
        
        Returns:
            Transport object
            
        Raises:
            ConnectionException: If connection fails after 3 retries
        """
        transport = None
        count = 0
        
        while count < 3:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(30)
                sock.connect((self.ip, self.port))
                transport = paramiko.Transport(sock)
                transport.start_client()
                
                if not transport.is_active():
                    raise ConnectionException("SSH client start failed")
                break
            except (socket.error, EOFError, paramiko.SSHException, ConnectionException) as e:
                logger.warning(f"Connection failed to {self.ip}:{self.port}: {e}")
                count += 1
                if sock:
                    sock.close()
                time.sleep(3)
        
        if transport is None:
            raise ConnectionException(f"Failed to connect to {self.ip}:{self.port}")
        
        return transport
    
    def authentication(self, transport: paramiko.Transport) -> None:
        """Authenticate SSH connection.
        
        Args:
            transport: Transport object
        """
        if not transport.is_authenticated():
            try:
                transport.auth_password(self.username, self.password)
            except paramiko.BadAuthenticationType as error:
                if 'keyboard-interactive' not in error.allowed_types:
                    raise
                self._auth_interactive(transport)
        
        logger.debug(f"Authentication successful for {self.username}@{self.ip}")
    
    def _auth_interactive(self, transport: paramiko.Transport) -> None:
        """Keyboard-interactive authentication fallback."""
        password = self.password
        
        def handler(title: str, instructions: str, fields: List) -> List:
            if len(fields) > 1:
                raise SSHException('Fallback authentication failed')
            if len(fields) == 0:
                return []
            return [password]
        
        transport.auth_interactive(self.username, handler, '')
        
        if not transport.is_authenticated():
            raise AuthenticationException('Interactive authentication failed')
    
    def login(self) -> None:
        """Login to SSH server and open shell session."""
        try:
            if self.transport is None or not self.transport.is_active():
                self.transport = self.create_client()
            self.authentication(self.transport)
        except Exception as e:
            logger.warning(f"Login failed, retrying: {e}")
            time.sleep(5)
            self.close()
            if self.transport is None or not self.transport.is_active():
                self.transport = self.create_client()
            self.authentication(self.transport)
        
        self.channel = self.transport.open_session()
        self.channel.get_pty(width=350, height=200)
        self.channel.invoke_shell()
        self.channel.settimeout(10)
        
        if self.channel.transport.remote_version.find('Windows') >= 0:
            self.is_windows = True
        
        result, is_match, _ = self.recv(timeout=15)
        if not is_match:
            logger.warning('Did not receive command prompt after login')
        
        default_waitstr = '@#>'
        if self.is_windows:
            default_waitstr = r'(PS )?[Cc]:.*>$'
            self.linesep = '\r'
        else:
            self.exec_command('PS1="\\u@#>"', waitstr=self.username + default_waitstr, timeout=15)
            self.exec_command('LS_OPTIONS="-A -N"', waitstr=default_waitstr, timeout=15)
        
        self.waitstrDict = {'normal': default_waitstr}
        self.status = 'normal'
        logger.info(f"SSH login successful: {self.username}@{self.ip}:{self.port}")
    
    def is_active(self) -> bool:
        """Check if connection is active."""
        if self.channel:
            return not self.channel.closed
        return False
    
    def close(self) -> None:
        """Close SSH connection."""
        if self.transport:
            self.transport.close()
            self.transport = None
            self.channel = None
            logger.info(f"SSH connection closed: {self.ip}")
    
    def reconnect(self) -> None:
        """Reconnect to SSH server."""
        self.close()
        self.login()
    
    def send(self, cmd: str, timeout: int = 120) -> bool:
        """Send command to shell.
        
        Args:
            cmd: Command string
            timeout: Send timeout
            
        Returns:
            True if sent successfully
        """
        now_time = time.time()
        end_time = now_time + timeout
        channel = self.channel
        
        if self.clear_channel:
            channel_time = time.time()
            while channel.recv_ready() and time.time() - channel_time < 3:
                channel.in_buffer.empty()
                time.sleep(1)
            self.clear_channel = False
        
        while now_time < end_time:
            try:
                size = channel.send(cmd + self.linesep)
                logger.debug(f"Sent to {self.ip}: {cmd}, size={size}")
                return True
            except socket.timeout:
                logger.warning(f"Send timeout for: {cmd}")
            except socket.error as e:
                if 'Socket is closed' in str(e):
                    raise ConnectionException('Connection closed')
                raise
            now_time = time.time()
        
        return False
    
    def recv(
        self,
        waitstr: str = "[>#]",
        nbytes: int = 32768,
        timeout: int = 120,
        raise_exception: bool = False
    ) -> Tuple[Optional[str], bool, Optional[str]]:
        """Receive command output with pattern matching.
        
        Args:
            waitstr: Regex pattern for completion detection
            nbytes: Buffer size
            timeout: Receive timeout
            raise_exception: Raise TimeoutException on timeout
            
        Returns:
            Tuple of (output, is_match, matched_string)
        """
        if not self.is_active():
            raise ConnectionException('Connection closed')
        
        is_match = False
        match_str = None
        recv_data = ""
        now_time = time.time()
        end_time = now_time + timeout
        channel = self.channel
        
        while now_time < end_time:
            str_get = ''
            match = None
            
            try:
                if self.is_windows:
                    time.sleep(0.1)
                str_get = channel.recv(nbytes)
                
                if self.is_windows:
                    str_get = self._format_win2019(str_get)
            except socket.timeout:
                logger.warning('No echo received')
            
            if str_get:
                if isinstance(str_get, bytes):
                    try:
                        str_get = str_get.decode('utf-8', errors='strict')
                    except UnicodeDecodeError:
                        str_get = str_get.decode('utf-8', errors='ignore')
                        logger.warning('Unicode decode error, using ignore mode')
                
                recv_data += str_get
                match = re.search(waitstr, recv_data.strip('\r\n'))
            
            if match:
                is_match = True
                match_str = match.group()
                break
            
            now_time = time.time()
            
            if not is_match and now_time >= end_time:
                logger.warning(
                    f"Timeout {timeout}s waiting for pattern: {waitstr}\n"
                    f"Received data:\n{recv_data}"
                )
                if raise_exception:
                    raise TimeoutException(f"Receive timeout waiting for: {waitstr}")
        
        recv_data = self._filter_ANSI_color(recv_data)
        
        if recv_data == "":
            recv_data = None
        
        logger.debug(f"Received from {self.ip}:\n{recv_data if recv_data else 'None'}")
        return recv_data, is_match, match_str
    
    def _filter_ANSI_color(self, text: str) -> str:
        """Remove ANSI color codes from output."""
        if not text:
            return text
        
        text_bytes = text.encode()
        patterns = [
            b'\x1b\\[(?:\\d{1,2};)?\\d{0,2}m',
            b'\x1b\\[\\?\\d{,4}[lh]?\r?',
            b'\x1b\\[K',
            b'\x1b\\[\\d{,4}\\w{,1}\r{,1}',
            b' \x08',
        ]
        
        for pattern in patterns:
            text_bytes = re.sub(pattern, b'', text_bytes)
        
        return text_bytes.decode('utf-8', errors='strict')
    
    def _format_win2019(self, text: bytes) -> bytes:
        """Format Windows 2019 SSH output."""
        text = re.sub(b'\x1b\\[\\d+\\w\x1b\\[\\d+\\w', b'', text)
        text = re.sub(b'(\\r\\n)+', b'\r\n', text)
        text = re.sub(b' *\x08*\x1b[^:\\\\\r\n\\.]+$', b'', text).strip(b' ')
        text = re.sub(b'\x1b\\[\\d+J', b'', text)
        text = re.sub(b'\x1b\\[\\?25\\w', b'', text)
        text = re.sub(b'(\\x1b\\[K\\r\\n)+', b'\r\n', text)
        text = re.sub(b'(\\x1b\\[K|\\x1b\\[\\d+X)', b'', text)
        return text
    
    def exec_command(
        self,
        cmd: str,
        waitstr: str = "[>#]",
        timeout: int = 120,
        nbytes: int = 32768,
        delay: int = 0,
        raise_exception: bool = True,
        directory: Optional[str] = None
    ) -> Tuple[Optional[str], bool, Optional[str]]:
        """Execute command and wait for response.
        
        Args:
            cmd: Command string
            waitstr: Wait pattern
            timeout: Timeout seconds
            nbytes: Buffer size
            delay: Delay before receive
            raise_exception: Raise exception on timeout
            directory: Directory to cd before execution
            
        Returns:
            Tuple of (result, is_match, match_str)
        """
        if directory:
            if not self.send(f"cd {directory}", timeout):
                return None, False, None
            self.recv(waitstr, nbytes, timeout)
        
        if not self.send(cmd, timeout):
            return None, False, None
        
        if delay:
            time.sleep(delay)
        
        return self.recv(waitstr, nbytes, timeout, raise_exception=raise_exception)
    
    def _get_last_cmd_status(self) -> Optional[int]:
        """Get last command exit status."""
        default_waitstr = self.waitstrDict.get('normal', '[#|>]')
        result = self.exec_command('echo $?', default_waitstr, timeout=5)[0]
        
        if result:
            lines = result.strip().split('\r\n')
            for line in lines:
                if line.isdigit():
                    return int(line)
        
        return None
    
    def run(self, cmd_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command (legacy-compatible interface).
        
        Args:
            cmd_spec: Command specification dict:
                - "command": List of commands or single string
                - "timeout": Timeout in seconds (default: 120)
                - "waitstr": Wait pattern (default: shell prompt)
                - "returnCode": Return exit code (default: True)
                - "input": List of [input_str, waitstr] pairs for interactive commands
                - "directory": Directory to cd before execution
                - "clearChannel": Clear buffer before execution
                
        Returns:
            Dict with:
                - "stdout": Command output (if success)
                - "stderr": Command output (if failed)
                - "rc": Exit code
        """
        if not self.is_active():
            try:
                self.login()
            except Exception as e:
                return {
                    "stdout": "",
                    "stderr": f"Connection failed: {e}",
                    "rc": -1
                }
        
        keep_cmd = cmd_spec.get("keepCmd", False)
        default_waitstr = self.waitstrDict.get('normal', '[#|>]')
        result = {"rc": None, "stderr": None, "stdout": ""}
        
        if cmd_spec.get('clearChannel', False):
            self.clear_channel = True
        
        timeout = cmd_spec.get('timeout', 600)
        waitstr = cmd_spec.get('waitstr', default_waitstr)
        
        cmd_str = " ".join(cmd_spec["command"])
        cmd_str = re.sub('^sh -c', '', cmd_str)
        
        cmd_list = [[cmd_str, waitstr]]
        
        if cmd_spec.get('input'):
            input_list = cmd_spec['input']
            for i in range(0, len(input_list), 2):
                w_str = input_list[i + 1] if (i + 1) < len(input_list) else default_waitstr
                cmd_list.append([input_list[i], w_str])
        
        stdout = ''
        is_match = True
        self.current_cmd = cmd_str
        
        for idx, cmd_item in enumerate(cmd_list):
            directory = cmd_spec.get("directory") if idx == 0 else None
            tmp_result, is_match, _ = self.exec_command(
                cmd_item[0],
                cmd_item[1] + '|' + default_waitstr,
                timeout,
                directory=directory,
                raise_exception=cmd_spec.get('raise_exception_if_timeout', True)
            )
            
            if not is_match and cmd_spec.get("cmd_timeout_interrupt", False):
                self.exec_command(chr(3), cmd_item[1] + '|' + default_waitstr, timeout, delay=3)
            
            if tmp_result:
                stdout += tmp_result
        
        self.current_cmd = ''
        
        std_list = stdout.split('\r\n')
        if not keep_cmd and len(std_list) > 1:
            if ">" + cmd_str in std_list[0] or cmd_str == std_list[0]:
                std_list.pop(0)
        
        if is_match and cmd_spec.get("shnormal", False) and not self.is_windows:
            default_wait_str = self.waitstrDict.get('normal', '@#>')
            self.exec_command('PS1="\\u@#>"', waitstr=self.username + default_wait_str, timeout=5)
            self.exec_command('LS_OPTIONS="-A -N"', waitstr=default_wait_str, timeout=5)
        
        if self.is_windows:
            result["rc"] = 0
        else:
            result["rc"] = self._get_last_cmd_status() if cmd_spec.get("returnCode", True) else 0
        
        if self.is_windows:
            if cmd_str in std_list[0]:
                std_list[0] = cmd_str
            while std_list and std_list[-1] == '':
                std_list.pop()
        elif std_list and std_list[-1] == default_waitstr:
            std_list.pop(-1)
        
        if result["rc"] == 0:
            result['stdout'] = '\r\n'.join(std_list)
            result['stderr'] = None
        else:
            result['stderr'] = '\r\n'.join(std_list)
            result['stdout'] = None
        
        return result
    
    def create_sftp_client(self) -> paramiko.SFTPClient:
        """Create SFTP client for file transfer."""
        if self.transport is None or not self.transport.is_active():
            self.login()
        return paramiko.SFTPClient.from_transport(self.transport)
    
    def putFile(self, src: str, dst: str) -> bool:
        """Upload file via SFTP.
        
        Args:
            src: Local file path
            dst: Remote file path
            
        Returns:
            True if successful
        """
        try:
            sftp = self.create_sftp_client()
            sftp.put(src, dst)
            sftp.close()
            logger.info(f"Uploaded {src} to {dst}")
            return True
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    
    def getFile(self, src: str, dst: str) -> bool:
        """Download file via SFTP.
        
        Args:
            src: Remote file path
            dst: Local file path
            
        Returns:
            True if successful
        """
        try:
            sftp = self.create_sftp_client()
            sftp.get(src, dst)
            sftp.close()
            logger.info(f"Downloaded {src} to {dst}")
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def __del__(self):
        """Cleanup on destruction."""
        self.close()
    
    def __repr__(self) -> str:
        return f"NodeAdapter(nodeId={self.nodeId}, ip={self.ip}:{self.port})"


class LocalNodeAdapter(NodeAdapter):
    """Local node adapter for testing without SSH."""
    
    def __init__(self, node_info: Dict[str, Any]) -> None:
        super().__init__(node_info)
        self.ip = "localhost"
    
    def login(self) -> None:
        pass
    
    def is_active(self) -> bool:
        return True
    
    def close(self) -> None:
        pass
    
    def run(self, cmd_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command locally via subprocess."""
        import subprocess
        
        commands = cmd_spec.get("command", [])
        timeout = cmd_spec.get("timeout", 30)
        
        if isinstance(commands, str):
            commands = [commands]
        
        full_cmd = " && ".join(commands)
        
        try:
            proc = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "rc": proc.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "rc": -1
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "rc": -1
            }
    
    def putFile(self, src: str, dst: str) -> bool:
        import shutil
        try:
            shutil.copy(src, dst)
            return True
        except Exception as e:
            logger.error(f"Copy failed: {e}")
            return False
    
    def getFile(self, src: str, dst: str) -> bool:
        return self.putFile(src, dst)


def create_node_adapter(node_info: Dict[str, Any], use_local: bool = False) -> NodeAdapter:
    """Factory function to create node adapter.
    
    Args:
        node_info: Node configuration dict
        use_local: Use LocalNodeAdapter if True
        
    Returns:
        NodeAdapter instance
    """
    if use_local:
        return LocalNodeAdapter(node_info)
    return NodeAdapter(node_info)