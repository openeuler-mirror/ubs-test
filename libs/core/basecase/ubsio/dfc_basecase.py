"""DFCBaseCase - Base class for UBSIO DFC test cases.

Provides common initialization logic for all UBSIO DFC tests.

CRITICAL CHANGE (2026-05-16):
- Removed __init__ method to solve pytest collection limitation
- Uses @pytest.fixture(autouse=True) for dependency injection
- Provides helper objects dfc_node_cli and dfc_kv_cli for test operations
"""

import concurrent.futures
import copy
import logging
import os
import random
import time

import pytest
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from libs.core.base import TestCase
from libs.ubsio import dfc_global_var as Var
from libs.ubsio.dfc_node_cli import DFCNodeCLI
from libs.ubsio.dfc_kv_cli import DFCKVCLI
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_dfc_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """Inject DFCBaseCase external dependencies.
    
    Only executes injection for DFCBaseCase and its subclasses.
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    from libs.core.basecase.ubsio.dfc_basecase import DFCBaseCase
    if not isinstance(instance, DFCBaseCase):
        return
    instance.nodes = nodes if nodes else []
    instance.resource = resource
    instance.customParam = custom_params or {}
    
    instance._init_dfc_clients()
    
    instance.logger = Log.getLogger(instance.__class__.__name__)
    
    instance.date = datetime.now(tz=timezone(timedelta(hours=8))).strftime('%Y_%m_%d_%H_%M')
    
    logger.info(f"DFCBaseCase initialized: {len(instance.nodes)} nodes, class={instance.__class__.__name__}")


class DFCBaseCase(TestCase):
    """Base class for UBSIO DFC test cases.
    
    Provides:
    - Node list management (self.nodes, self.node)
    - Helper objects for node and KV operations (self.dfc_node_cli, self.dfc_kv_cli)
    - Common methods for DFC testing
    
    Legacy pattern (deprecated):
        class MyTest(DFCBaseCase):
            def __init__(self, parameters):
                super().__init__(parameters)
    
    Pytest pattern (current):
        class MyTest(DFCBaseCase):
            # No __init__ method!
            # Dependencies injected via parent fixture
            
            def setup_method(self):
                # Business parameters initialized here
                pass
            
            def test_xxx(self):
                # Use self.dfc_node_cli[0], self.dfc_kv_cli[0]
                pass
    """
    
    def _init_dfc_clients(self) -> None:
        """Initialize DFC node and KV CLI clients."""
        self.dfc_node_cli: List[DFCNodeCLI] = []
        self.dfc_kv_cli: List[DFCKVCLI] = []
        
        for node in self.nodes:
            node_cli = DFCNodeCLI(node)
            self.dfc_node_cli.append(node_cli)
            self.dfc_kv_cli.append(DFCKVCLI(node_cli))
        
        self.node_count = len(self.dfc_node_cli)
    
    def clear_env(self) -> None:
        """Clear environment - kill processes and unmount directories."""
        for node in self.dfc_node_cli:
            node.clear_process(Var.DFC_NAME)
            node.clear_process('bio_daemon')
            node.clear_process('python3', docker_name=Var.DOCKER_NAME)
            node.umount_dir()
    
    def concurrent_task(self, tasks: List[Tuple]) -> List[Any]:
        """Execute concurrent tasks.
        
        Args:
            tasks: List of (func, args) tuples
            
        Returns:
            List of results
        """
        future_ret = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_param = [executor.submit(func, *input_params_list) for func, input_params_list in tasks]
        for future in future_to_param:
            try:
                future_ret.append(future.result())
            except Exception as e:
                future_ret.append(e)
        return future_ret
    
    def start_bio(self, start_bio_timeout: int = 180) -> str:
        """Start bio_daemon process.
        
        Args:
            start_bio_timeout: Timeout in seconds
            
        Returns:
            Status string
        """
        start_bio_daemon_cmd = f"source /etc/profile; source ~/.bashrc;cd {Var.BIO_BIN_PATH};{Var.BIO_EXPORT};stdbuf -oL nohup ./bio_daemon > {Var.DAEMON_LOGPATH} 2>&1 &"
        docker_start_bio_cmd = f"docker exec {Var.DOCKER_NAME} bash -c \"{start_bio_daemon_cmd}\""
        for node in self.dfc_node_cli:
            node.run_input(docker_start_bio_cmd, timeout=30, waitstr="]#")
        
        bio_start_time = time.time()
        bio_total_time = 0
        check_docker_cmd = f"grep 'BoostIO Daemon Start Success' {Var.DAEMON_LOGPATH}"
        docker_check_bio_cmd = f"docker exec {Var.DOCKER_NAME} bash -c \"{check_docker_cmd}\""
        for node in self.dfc_node_cli:
            while bio_total_time <= start_bio_timeout:
                check_ret = node.run_input(docker_check_bio_cmd).get("stdout")
                if check_ret:
                    break
                else:
                    time.sleep(3)
                    bio_end_time = time.time()
                    bio_total_time = bio_end_time - bio_start_time
            if bio_total_time > start_bio_timeout:
                return f"{node.localIP}查看bio_daemon拉起失败"
        return "bio_daemon拉起成功"
    
    def start_falconfs(self, falconfs_node_id: int) -> str:
        """Start falconfs process.
        
        Args:
            falconfs_node_id: Falconfs node ID
            
        Returns:
            Status string
        """
        start_pg_cmd = f"cd {Var.FALCONDFS_PKG_PATH};sh start_falconfs.sh"
        check_start_ret = self.dfc_node_cli[falconfs_node_id].run_input(start_pg_cmd, timeout=180, waitstr="]#")
        for falcon_docker in ["falcon-cn-1", "falcon-dn-1", "falcon-zk-1"]:
            if falcon_docker not in check_start_ret.get("stdout", ""):
                return "PG执行sh start_falconfs.sh报错，PG拉起失败"
        if "healthy" not in check_start_ret.get("stdout", ""):
            return "PG执行sh start_falconfs.sh报错，PG拉起失败"
        
        zk_start_time = time.time()
        zk_total_time = 0
        zk_docker_name = "falcon-zk-1"
        check_docker_cmd = f"echo \"ls /falcon\" | docker exec -i {zk_docker_name} bin/zkCli.sh -server localhost:2181"
        while zk_total_time <= 180:
            check_ret = self.dfc_node_cli[falconfs_node_id].run_input(check_docker_cmd).get("stdout")
            if "ready" in check_ret:
                break
            else:
                time.sleep(3)
                zk_end_time = time.time()
                zk_total_time = zk_end_time - zk_start_time
        if zk_total_time > 180:
            return f"查看{zk_docker_name}没有ready"
        return "falconfs拉起成功"
    
    def start_Nexus(self, mode: str = "converged") -> str:
        """Start Nexus process.
        
        Args:
            mode: Deployment mode
            
        Returns:
            Status string
        """
        start_dfc = f"source /etc/profile; source ~/.bashrc;cd /opt/;stdbuf -oL nohup ./dfc_server {Var.FUSE_NAME} -d -f -o big_writes > {Var.DFC_LOGPATH}  2>&1 &"
        start_dfc_docker_cmd = f"docker exec {Var.DOCKER_NAME} bash -c \"{start_dfc}\""
        for node in self.dfc_node_cli:
            node.run_input(start_dfc_docker_cmd)
        
        grep_boostio_cmd = f"grep 'Start boostio success' {Var.DFC_LOGPATH}"
        grep_boostio_createcache_cmd = f"grep 'boostio createcache success' {Var.DFC_LOGPATH}"
        grep_dfc_cmd = f"grep \"unique: [0-9]\+, success, outsize: [0-9]\+\" {Var.DFC_LOGPATH}"
        grep_process_cmd = f'ps -ef | grep dfc_server | grep -v grep'
        base_cmd_list = [grep_boostio_cmd, grep_boostio_createcache_cmd, grep_dfc_cmd, grep_process_cmd]
        
        for node in self.dfc_node_cli:
            cmd_list = copy.copy(base_cmd_list)
            total_time = 0
            start_time = time.time()
            while total_time <= 300 and cmd_list:
                removed_commands = []
                for cmd in cmd_list:
                    check_ret = node.run_input(f"docker exec {Var.DOCKER_NAME} {cmd}")
                    if check_ret.get('stdout'):
                        removed_commands.append(cmd)
                for cmd in removed_commands:
                    cmd_list.remove(cmd)
                if cmd_list:
                    time.sleep(6)
                end_time = time.time()
                total_time = end_time - start_time
            if total_time > 300:
                return f"节点{node.localIP} 拉起dfc失败，剩余未匹配命令: {cmd_list}"
        return "Nexus拉起成功"
    
    def start_Nexus_and_Bio(self, only_Bio: bool = False, start_bio_timeout: int = 180) -> str:
        """Start bio_daemon and Nexus processes.
        
        Args:
            only_Bio: If True, only start bio_daemon
            start_bio_timeout: Timeout for bio_daemon startup
            
        Returns:
            Status string
        """
        self.falconfs_node_id: Optional[int] = None
        self.daemon_id: Optional[int] = None
        
        for node_index in range(len(self.dfc_node_cli)):
            if self.dfc_node_cli[node_index].localIP == Var.FALCONFS_NODE:
                self.falconfs_node_id = node_index
            else:
                self.daemon_id = node_index
        if self.falconfs_node_id is None:
            return "FALCONFS_NODE传参错误，未找到FALCONFS_NODE"
        
        for node in self.dfc_node_cli:
            node.clear_process(Var.DFC_NAME)
            node.clear_process('bio_daemon')
            node.clear_process('python3', docker_name=Var.DOCKER_NAME)
            node.umount_dir()
        
        for node in self.dfc_node_cli:
            node.run_input("dd bs=8k count=1024 if=/dev/zero of=/dev/nvme0n1")
            cache_cmd = "echo 3 > /proc/sys/vm/drop_caches"
            docker_cache_cmd = f"docker exec {Var.DOCKER_NAME} bash -c \"{cache_cmd}\""
            node.run_input(docker_cache_cmd)
        
        clean_zk_cmd = f"echo -e \"deleteall /cm\" | zkCli.sh"
        self.dfc_node_cli[self.falconfs_node_id].run_input(clean_zk_cmd)
        
        self.dfc_node_cli[self.falconfs_node_id].del_file(f"{Var.DOCKER_MOUNT_PATH}/*")
        
        start_bio_ret = self.start_bio(start_bio_timeout)
        if start_bio_ret != "bio_daemon拉起成功":
            return "bio_daemon拉起失败"
        if only_Bio:
            return "bio_daemon拉起成功"
        
        start_falconfs_ret = self.start_falconfs(self.falconfs_node_id)
        if start_falconfs_ret != "falconfs拉起成功":
            return "falconfs拉起失败"
        
        start_Nexus_ret = self.start_Nexus()
        if start_Nexus_ret != "Nexus拉起成功":
            return "Nexus拉起失败"
        return "成功拉起bio_daemon、falconfs、Nexus进程"
    
    def Check_Env_Allnodes(self) -> str:
        """Check environment status on all nodes.
        
        Returns:
            Status string
        """
        for node in self.dfc_node_cli:
            check_ret = node.Check_Env()
            if check_ret != "环境已就绪":
                return f"环境{node.localIP}未就绪"
        return "环境已就绪"
    
    def Execute_Shell_Scripts_Crossnode(self, node: DFCNodeCLI, scripts_name: str, arg: str,
                                        assert_str: str = "所有文件创建完成",
                                        docker_name: str = Var.DOCKER_NAME, time_out: int = 120,
                                        shell: bool = True) -> str:
        """Execute shell script on node.
        
        Args:
            node: Node object
            scripts_name: Script name
            arg: Arguments
            assert_str: Expected output string
            docker_name: Docker container name
            time_out: Timeout
            shell: Whether it's a shell script
            
        Returns:
            Status string
        """
        if shell:
            sh_cmd = f"sh {Var.MAP_DOCKER_PATH}/{scripts_name} {arg}"
            execute_ret = node.run_input(f"docker exec {docker_name} bash -c '{sh_cmd}'", timeout=time_out)
        else:
            python_cmd = f"python3 {Var.MAP_DOCKER_PATH}/{scripts_name} {arg}"
            execute_ret = node.run_input(f"docker exec {docker_name} bash -c \"{python_cmd}\"", timeout=time_out)
        if execute_ret.get('rc') != 0:
            return f"执行脚本：{scripts_name}出错"
        else:
            if assert_str in execute_ret.get('stdout', ''):
                return "脚本执行成功"
            else:
                return f"执行脚本：{scripts_name}出错"
    
    def generate_random_data(self, min_length: int = 1024 * 1024, max_length: int = 8 * 1024 * 1024) -> bytes:
        """Generate random data.
        
        Args:
            min_length: Minimum length
            max_length: Maximum length
            
        Returns:
            Random bytes
        """
        length = random.randint(min_length, max_length)
        return os.urandom(length)
    
    def generate_random_string_digits(self, min_length: int = 1, max_length: int = 255) -> str:
        """Generate random string.
        
        Args:
            min_length: Minimum length
            max_length: Maximum length
            
        Returns:
            Random string
        """
        import string
        length = random.randint(min_length, max_length)
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


    def check_disk(self, node, disk_name:str):
        """check disk is in use

        Args:
            disk_name:
        Returns:
        """
        cmd = f"set -o pipefail; lsblk | grep '{disk_name}' | awk '{{print $7}}'"
        ret = node.run_input(cmd, 30)
        if ret.get("rc") != 0:
            raise Exception("lsblk查看盘失败，请检查disk配置")
        if ret.get("stdout").split("\r\n")[0] != "":
            raise Exception("配置的disk盘已被使用，建议更换未使用的disk")

    def clear_mem_disk(self, disk_dict:dict = Var.disk_dict):
        for node in self.dfc_node_cli:
            cache_cmd = "echo 3 > /proc/sys/vm/drop_caches"
            node.run_input(cache_cmd)

            if disk_dict:
                disk = disk_dict.get(node.localIP)
                if not disk:
                    pass
                elif ":" in disk:
                    disk_list = disk.split(":")
                    for i in disk_list:
                        i_disk = "".join(i.split("/")[-1])
                        if "loop" not in disk:
                            self.check_disk(node, i_disk)
                        disk_cmd = f"dd bs=8k count=1024 if=/dev/zero of=/dev/{i_disk}"
                        node.run_input(disk_cmd)
                elif "loop" in disk:
                    disk_cmd = f"dd bs=8k count=1024 if=/dev/zero of=/dev/{i_disk}"
                    node.run_input(disk_cmd)
                else:
                    self.check_disk(node, disk)
                    disk_cmd = f"dd bs=8k count=1024 if=/dev/zero of=/dev/{disk}"
                    node.run_input(disk_cmd)



__all__ = ['DFCBaseCase', 'inject_dfc_basecase_dependencies']