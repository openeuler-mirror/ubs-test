"""MEM Pooling BaseCase.

Migrated from: legency/testcase/ubse/lib/basecase/ubse/Resource_Management/MEM_Pooling_Management/MEM_Pooling_BaseCase.py
Provides memory pooling management methods.

Legacy file is 1881 lines - this is a simplified pytest-compatible version.
Complex methods should be imported from libs.ubse.mem_ops.

CRITICAL CHANGE (2026-05-12):
- 移除__init__方法，解决pytest无法收集带__init__测试类的硬限制
- 使用@pytest.fixture(autouse=True)注入模块引用和计算参数
- 外部依赖参数(nodes, resource, custom_params)通过父类CMBaseCase.fixture注入
"""

import logging
import re
import time
import pytest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from libs.modules.ubse.basecase.cm_basecase import CMBaseCase
from libs.modules.ubse.common import topology
from libs.modules.ubse.api import cli_api
from libs.modules.ubse.common import ubse_process_ops

logger = logging.getLogger(__name__)

C_path = '/opt/install/package/ubse'


@pytest.fixture(autouse=True)
def inject_mem_pooling_dependencies(request: Any) -> None:
    """注入MEM_Pooling_BaseCase特有的模块引用和计算参数.
    
    只对MEM_Pooling_BaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase
    if not isinstance(instance, MEM_Pooling_BaseCase):
        return
    
    logger.info(f"[MEM_FIXTURE] request has instance: {hasattr(request, 'instance')}")
    logger.info(f"[MEM_FIXTURE] instance type: {type(instance).__name__}")
    
    instance.mem_sdk_path = instance.MEM_SDK_PATH
    instance.mem_borrow_shm_path = instance.MEM_BORROW_SHM_PATH

    instance.ubse_process_ops = ubse_process_ops
    instance.cli_api = cli_api
    instance.topo_common = topology
    instance.ub_common = topology
    
    if hasattr(instance, 'nodes') and instance.nodes:
        instance.master_node = instance.nodes[0]
        instance.agent_node = instance.nodes[1] if len(instance.nodes) > 1 else instance.nodes[0]
    else:
        instance.master_node = None
        instance.agent_node = None
    
    logger.info(f"MEM_Pooling_BaseCase initialized for {len(instance.nodes) if hasattr(instance, 'nodes') else 0} nodes")


class MEM_Pooling_BaseCase(CMBaseCase):
    """Base class for MEM pooling management tests.
    
    Provides methods for:
    - Memory borrowing/lending operations
    - SDK interface execution
    - NUMA management
    - Memory status query
    
    Legacy inheritance: MEM_Pooling_BaseCase(CMBaseCase)
    
    外部依赖参数（父类CMBaseCase.fixture注入）:
        - nodes: List[Any] - 测试节点列表
        - resource: Dict[str, Any] - 资源配置字典
        - custom_params: Dict[str, Any] - 自定义参数字典
    
    模块引用（本类fixture注入）:
        - mem_common, mem_pooling_common: mem_ops模块
        - ubse_process_ops: ubse_process_ops模块
        - cli_api: cli_api模块
        - DFX_common: dfx_ops模块
        - topo_common, ub_common: topology模块
    
    计算参数（本类fixture注入）:
        - master_node: 主节点（节点0）
        - agent_node: 备节点（节点1）
        - mem_sdk_path: SDK路径
        - mem_borrow_shm_path: 共享内存路径
    """
    
    RPM_PATH = "/usr/local/softbus/ctrlbus"
    CLI_PATH = "/usr/local/softbus/ctrlbus-cli"
    LOG_PATH = "/var/log/scbus"
    MEM_SDK_PATH = "/home/autotest/sdk"
    MEM_BORROW_SHM_PATH = "/rackmanager/mem_borrow_shm"
    
    def preTestCase(self) -> None:
        """Pre-test setup - verify MEM pooling environment."""
        super().preTestCase()
        logger.info("MEM pooling environment verified")
    
    def python_sdk_MemPublic(
        self,
        node: Any,
        python_version: str,
        sdk_interface: str,
        sdk_path: str = None
    ) -> str:
        """Execute Python SDK for MEM public interfaces."""
        if sdk_path is None:
            sdk_path = self.mem_sdk_path
        
        sdk_script = f"{sdk_path}/{sdk_interface}"
        cmd = f"{python_version} {sdk_script}"
        
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("stdout", "")
    
    def C_sdk_MemPublic(self, node: Any, sdk_interface: str) -> str:
        """Execute C SDK for MEM public interfaces."""
        cmd = f"{self.MEM_SDK_PATH}/{sdk_interface}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("stdout", "")
    
    def check_sdk_return_mem_value_status(self, data: str, status: str) -> bool:
        """Check SDK return value status for MEM operations."""
        pattern = f'status.*{status}'
        return bool(re.search(pattern, data))
    
    def check_sdk_return_BorrowAndLent_value_status(self, data: str, status: str) -> bool:
        """Check SDK return value status for borrow/lend operations."""
        pattern = f'(borrow_status|lend_status).*{status}'
        return bool(re.search(pattern, data))
    
    def mem_borrow(
        self,
        node: Any,
        bin_path: str = None,
        masking: bool = True,
        option: str = 'borrow',
        shm_name: str = '',
        start: bool = False,
        **kwargs
    ) -> str:
        """Execute memory borrow operation."""
        if bin_path is None:
            bin_path = f"{self.mem_sdk_path}/test/bin"
        
        cmd_parts = [f"{bin_path}/mem_borrow"]
        
        if option:
            cmd_parts.append(f"--{option}")
        if shm_name:
            cmd_parts.append(f"--name {shm_name}")
        
        for key, value in kwargs.items():
            cmd_parts.append(f"--{key} {value}")
        
        cmd = ' '.join(cmd_parts)
        result = node.run({"command": [cmd], "timeout": 120})
        return result.get("stdout", "")
    
    def mem_fd_borrow(
        self,
        node: Any,
        masking: bool = True,
        option: str = 'create',
        name: str = 'mem_borrow_test',
        size: str = '256M',
        numa_num: int = 1,
        slot_ids: str = '',
        params_dict: Optional[Dict[str, Any]] = None,
        wait_time: int = 120
    ) -> bool:
        """Execute FD memory borrow operation."""
        C_path = "/home/autotest"
        result = ''
        if params_dict is None:
            params_dict = {}
        
        if masking:
            node.run({'command': [f"cd {C_path}"]})
            node.run({'command': ["python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            
            if option == 'create':
                res = node.run(
                    {'command': [f"fd_create {name} {size}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
                result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
            elif option == 'create_with_lender':
                if numa_num == 1:
                    res = node.run(
                        {'command': [
                            f"fd_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size}"],
                            'waitstr': 'ubse_mem_app>', 'returnCode': False})
                else:
                    res = node.run(
                        {'command': [
                            f"fd_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size} --numa_id {params_dict.get('lender_numa_id1', '')} {params_dict.get('size1', '')}"],
                            'waitstr': 'ubse_mem_app>', 'returnCode': False})
                result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
            elif option == 'create_with_candidate':
                res = node.run(
                    {'command': [f"fd_create {name} {size} --slot_ids {slot_ids}"], 'waitstr': 'ubse_mem_app>',
                     'returnCode': False, 'timeout': wait_time})
                result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
            elif option == 'fd_permission':
                comm = f"fd_permission {name} {params_dict.get('owner_uid', '')} {params_dict.get('owner_gid', '')} {params_dict.get('mode', '')}"
                res = node.run(
                    {'command': [comm],
                     'waitstr': 'ubse_mem_app>',
                     'returnCode': False})
                result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
            
            node.run({'command': ["exit"]})
            
            if "Creation failed" in result:
                return False
            elif "Successfully created" in result:
                return True
            elif "Successfully modified" in result:
                return True
            else:
                return False
        else:
            node.run({'command': [f"cd {C_path}"]})
            node.run({'command': ["python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            res = node.run(
                {'command': [f"fd_delete {name}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False,
                 'timeout': wait_time})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
            node.run({'command': ["exit"]})
            
            if "Successfully deleted" in result:
                return True
            else:
                return False


    def mem_numa_borrow(
        self,
        node: Any,
        masking: bool = True,
        option: str = 'create',
        name: str = 'mem_borrow_test',
        size: str = '256M',
        numa_num: int = 1,
        slot_ids: str = '',
        params_dict: Optional[Dict[str, Any]] = None,
        wait_time: int = 120
    ) -> bool:
        """
        借出内存大小size, 单位Byte, 取值范围[128*1024*1024, 1024*1024*1024*256]
        slot_ids：借出节点范围，可传入多个slot_id
        lender_slot_id、lender_socket_id、lender_numa_id、lender_numa_id1、size1：指定借出节点信息
        numa_num：借出numa个数，当前create_with_lender借出方式可从两个numa借用
        params_dict:create_with_lender借用方式传入lender_slot_id、lender_socket_id、lender_numa_id等相关信息，字典格式
        timeout:命令结果等待时间
        """
        result = ''
        if params_dict is None:
            params_dict = {}
        if masking:
            node.run({'command': ["cd {}".format(C_path)]})
            node.run({'command': ["python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            if option == 'create':
                res = node.run(
                    {'command': [f"numa_create {name} {size}"], 'waitstr': 'ubse_mem_app>',
                     'returnCode': False, 'timeout': wait_time})
                result = str(res.get('stdout')) + str(res.get('stderr'))
            elif option == 'create_with_lender':
                if numa_num == 1:
                    res = node.run(
                        {'command': [
                            f"numa_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size}"],
                            'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
                else:
                    res = node.run(
                        {'command': [
                            f"numa_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size} --numa_id {params_dict.get('lender_numa_id1', '')} {params_dict.get('size1', '')}"],
                            'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
                result = str(res.get('stdout')) + str(res.get('stderr'))
            elif option == 'create_with_candidate':
                res = node.run(
                    {'command': [f"numa_create {name} {size} --slot_ids {slot_ids}"], 'waitstr': 'ubse_mem_app>',
                     'returnCode': False, 'timeout': wait_time})
                result = str(res.get('stdout')) + str(res.get('stderr'))
            node.run({'command': ["exit"], 'timeout': wait_time})
            if "Creation failed" in result:
                return False
            elif "Successfully created" in result:
                return True
            else:
                return False
        else:
            node.run({'command': ["cd {}".format(C_path)]})
            node.run({'command': ["python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            res = node.run(
                {'command': [f"numa_delete {name}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False,
                 'timeout': wait_time})
            result = str(res.get('stdout')) + str(res.get('stderr'))
            node.run({'command': ["exit"], 'timeout': wait_time})
            if "Successfully deleted" in result:
                return True
            else:
                return False

    
    def mem_query(
        self,
        node: Any,
        bin_path: str = None,
        option: str = 'mem_query'
    ) -> str:
        """Execute memory query operation."""
        if bin_path is None:
            bin_path = f"{self.mem_sdk_path}/test/bin"
        
        cmd = f"{bin_path}/mem_query --{option}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("stdout", "")
    
    def get_mem_pooling_info(self, node: Any, option: str = 'numa_status') -> str:
        """Get memory pooling information."""
        curl_cmd = f'curl --unix-socket /var/run/scbus/rackAgentUds.socket "http://localhost/redfish/v1/Managers/1/MemPoolService" -d \'{{"option": "{option}"}}\''
        result = node.run({"command": [curl_cmd], "timeout": 30})
        return result.get("stdout", "")
    
    def procedure(self) -> None:
        """Main test logic."""
        super().procedure()
    
    def postTestCase(self) -> None:
        """Post-test cleanup."""
        super().postTestCase()
        logger.info("MEM_Pooling_BaseCase postTestCase")

    
    def backup_rack_log(self, node: Any) -> bool:
        """Backup rackmanager.log directory."""
        C_path = "/home/autotest"
        bak_logs_path = f"{C_path}/bak_logs"
        
        res = node.run({'command': [f'ls {bak_logs_path}']})
        msg = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        if "No such file or directory" in msg:
            node.run({'command': [f'mkdir {bak_logs_path}']})
        
        res = node.run({'command': [f'ls {self.rackmanager_log}']}).get('stdout')
        if not res:
            return True
        
        timestamp = datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S.%f")[:-3]
        backup_file = f"{bak_logs_path}/ubse_{timestamp}.log"
        
        node.run({'command': [f'cp -r {self.rackmanager_log} {backup_file}']})
        res = node.run({'command': [f'ls {backup_file}']}).get('stdout')
        
        if res is None:
            logger.error(f"Failed to backup rack log to {backup_file}")
            return False
        else:
            logger.info(f"Successfully backed up rack log to {backup_file}")
            return True
    
    def get_node_memory_status(self, node_id: str, expect_value: str = "ok") -> str:
        """获取指定节点的内存状态.
        
        Legacy method: get_node_memory_status(node_id, expect_value="ok")
        
        Args:
            node_id: 节点ID
            expect_value: 期望的状态值（默认"ok"）
            
        Returns:
            内存状态字符串
        """
        status = ""
        for _ in range(60):
            status = cli_api.get_node_memory_status_by_node_id(self.master_node, node_id)
            if status == expect_value:
                break
            time.sleep(6)
        return status
    
    def mem_borrow_common(self, node: Any, command: str, wait_time: int = 120) -> bool:
        """通过内存借用工具执行不同方式的借用归还.
        
        Legacy method: mem_borrow_common(node, command, wait_time=120)
        
        Args:
            node: 节点对象
            command: 包含所需参数的内存借用归还命令
            wait_time: 等待超时时间
            
        Returns:
            True表示成功，False表示失败
        """
        C_path = "/home/autotest"
        
        node.run({'command': ["cd {}".format(C_path)]})
        node.run({'command': ["python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
        res = node.run(
            {'command': [f"{command}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
        result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        self.logInfo(result)
        if 'ubse_mem_app' in result:
            node.run({'command': ["exit"]})
        if "INFO: Successfully" in result:
            return True
        else:
            return False
    
    def mem_borrow_common_result(self, node: Any, command: str, borrow_app_path: Optional[str] = None, timeout: int = 10) -> str:
        """通过内存借用工具执行不同方式的借用归还并返回结果.
        
        Legacy method: mem_borrow_common_result(node, command, borrow_app_path=None, timeout=10)
        
        Args:
            node: 节点对象
            command: 包含所需参数的内存借用归还命令
            borrow_app_path: 借用工具路径（默认/home/autotest）
            timeout: 超时时间
            
        Returns:
            执行结果字符串
        """
        if borrow_app_path is None:
            ubse_mem_app_path = "/home/autotest"
        else:
            ubse_mem_app_path = borrow_app_path
        
        node.run({'command': ["cd {}".format(ubse_mem_app_path)], "timeout": 1})
        node.run(
            {'command': ["python3 ubse_mem_app.py"], "timeout": 1, 'waitstr': 'ubse_mem_app>', 'returnCode': False})
        res = node.run({'command': [f"{command}"], "timeout": timeout, 'waitstr': 'ubse_mem_app>', 'returnCode': False})
        result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        if "ubse_mem_app>" in result:
            node.run({'command': ["exit"], "timeout": 1})
        return result
    
    def mem_borrow_common_by_specify_user(
        self,
        node: Any,
        command: str,
        user: str,
        user_password: str = "BeiMing@123",
        is_ubse: bool = False,
        borrow_app_path: str = '/tmp'
    ) -> str:
        """通过内存借用工具执行不同方式的借用归还（指定用户）.
        
        Legacy method: mem_borrow_common_by_specify_user(node, command, user, user_password="BeiMing@123", is_ubse=False, borrow_app_path='/tmp')
        
        Args:
            node: 节点对象
            command: 包含所需参数的内存借用归还命令
            user: 执行命令的用户名
            user_password: 用户密码（默认BeiMing@123）
            is_ubse: 是否使用ubse用户执行
            borrow_app_path: 借用工具路径
            
        Returns:
            执行结果字符串
        """
        test_file_path = getattr(self, 'test_file_path', '/home/autotest')
        
        if is_ubse:
            node.run({'command': [f"cd {test_file_path}"]})
            node.run({'command': ["sudo -u ubse python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            res = node.run({'command': [f"{command}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            node.run({'command': ["exit"]})
        else:
            node.run({'command': [f"cd {borrow_app_path}"], 'username': f"{user}", 'password': f"{user_password}"})
            node.run({'command': ["python3 ubse_mem_app.py"], 'username': f"{user}", 'password': f"{user_password}", 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            res = node.run({'command': [f"{command}"], 'username': f"{user}", 'password': f"{user_password}", 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            node.run({'command': ["exit"], 'username': f"{user}", 'password': f"{user_password}"})
        
        result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        return result
    
    def mem_shm_borrow(
        self,
        node: Any,
        option: str = 'shm_create',
        name: str = 'mem_borrow_test',
        size: str = '256M',
        slot_ids: str = '',
        params_dict: Optional[Dict[str, Any]] = None,
        proviers: str = '',
        wait_time: int = 120
    ) -> bool:
        """共享内存借用操作.
        
        Legacy method: mem_shm_borrow(node, option='shm_create', name='mem_borrow_test', size='256M', slot_ids='', proviers='', wait_time=120)
        
        Args:
            node: 节点对象
            option: 操作类型（shm_create/shm_create_with_lender/shm_attach/shm_detach/shm_delete）
            name: 共享内存名称
            size: 共享内存大小
            slot_ids: 共享内存的节点范围
            proviers: 资源提供方节点范围
            wait_time: 等待超时时间
            
        Returns:
            True表示成功，False表示失败
        """
        C_path = "/home/autotest"
        result = ''
        if params_dict is None:
            params_dict = {}
        node.run({'command': ["cd {}".format(C_path)]})
        node.run({'command': ["python3 ubse_mem_app.py"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
        
        if option == 'shm_create':
            if proviers:
                res = node.run({'command': [f"shm_create {name} {size} --region={slot_ids} --provider={proviers}"], 'waitstr': 'ubse_mem_app>', 'timeout': wait_time, 'returnCode': False})
            elif slot_ids:
                res = node.run({'command': [f"shm_create {name} {size} --region={slot_ids}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            else:
                res = node.run({'command': [f"shm_create {name} {size}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        elif option == 'shm_create_with_lender':
            res = node.run({'command': [f"shm_create_with_lender {name} {size} "
                                        f"{params_dict.get('lender_slot_id', '')} "
                                        f"--socket_id={params_dict.get('lender_socket_id', '')} "
                                        f"--numa_id={params_dict.get('lender_numa_id', '')}"],
                            'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        elif option == 'shm_attach':
            res = node.run({'command': [f"shm_attach {name}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        elif option == 'shm_detach':
            res = node.run({'command': [f"shm_detach {name}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        elif option == 'shm_delete':
            res = node.run({'command': [f"shm_delete {name}"], 'waitstr': 'ubse_mem_app>', 'returnCode': False, 'timeout': wait_time})
            result = str(res.get('stdout', '')) + str(res.get('stderr', ''))
        
        self.logInfo(result)
        if 'ubse_mem_app' in result:
            node.run({'command': ["exit"]})
        
        if "Creation failed" in result:
            return False
        elif "Successfully created" in result:
            return True
        elif "Successfully attach" in result:
            return True
        elif "Successfully detach" in result:
            return True
        elif "Successfully delete" in result:
            return True
        else:
            return False
    
    def get_fd_desc_list(self, fd_desc: str) -> List[Dict[str, str]]:
        """解析FD描述信息返回列表.
        
        Legacy method: get_fd_desc_list(fd_desc)
        
        Args:
            fd_desc: FD描述字符串
            
        Returns:
            包含内存信息的字典列表
        """
        import re
        pattern = r'\([^)]*\)'
        matches = re.findall(pattern, fd_desc)
        fd_desc_list = []
        
        for item in matches:
            if 'name' not in item:
                continue
            item = item.replace('(', '').replace(')', '').replace(',', '')
            data = item.split("\r\n")
            mem_info = [info.strip() for info in data if info != '' and "usr_info (hex)" not in info]
            mem_info_key = [key_value.split('=')[0] for key_value in mem_info[:-1]]
            if 'name' not in mem_info_key:
                continue
            mem_info_value = [key_value.split('=')[1] for key_value in mem_info[:-1]]
            mem_info_dict = dict(zip(mem_info_key, mem_info_value))
            fd_desc_list.append(mem_info_dict)
        
        return fd_desc_list
    
    def clear_all_borrow_mem(self) -> bool:
        """清理所有借用内存（FD、NUMA、共享内存）- 完整版本.
        
        Legacy method: clear_all_borrow_mem() - 原版实现
        
        Returns:
            True表示清理成功
        """
        account_empty_text = "borrow detail information is empty"
        account_empty_text_sdk = "INFO: Found 0"
        
        # 清理fd内存
        for node in self.nodes:
            res = self.mem_borrow_common_result(node, 'fd_list')
            fd_list = self.get_fd_desc_list(res)
            for item in fd_list:
                res = self.mem_fd_borrow(node, masking=False, name=item['name'])
        
        # 清理numa内存
        for node in self.nodes:
            res = self.mem_borrow_common_result(node, 'numa_list')
            numa_list = self.get_fd_desc_list(res)
            for item in numa_list:
                res = self.mem_numa_borrow(node, masking=False, name=item['name'])
        
        # 清理共享内存
        names = []
        res = self.mem_borrow_common_result(self.nodes[0], 'shm_list')
        shm_list = self.get_fd_desc_list(res)
        for item in shm_list:
            names.append(item['name'])
        
        shm__borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        for item in shm__borrow_details:
            if item.get('borrow_node', '').isdigit():
                res = self.mem_shm_borrow(self.nodes[int(item['borrow_node']) - 1], option='shm_detach', name=item['name'])
        
        shm_borrow_name = [item.get('name') for item in shm__borrow_details]
        update_shm_borrow_name = list(set(shm_borrow_name))
        master, _ = self.ubse_process_ops.return_nodes_by_role(self.nodes)
        for name in update_shm_borrow_name:
            res = self.mem_shm_borrow(master, option='shm_delete', name=name)
            self.logInfo(f"清理结果: {res}")
        
        self.logStep('清理后账本信息')
        res = self.cli_api.check_mem_query(self.nodes[0])
        if res and account_empty_text not in res:
            return False
        return True

    def get_file_permissions(self, node, memid):
        """
        获取远程节点 /dev/obmm_shmdev{memid} 的权限（八进制数字形式）
        """
        file_path = f"/dev/obmm_shmdev{memid}"

        result = node.run({'command': [f'test -e {file_path} && echo EXISTS || echo NOTEXISTS']})
        if 'NOTEXISTS' in result.get('stdout', ''):
            return None

        result = node.run({'command': [f'stat -c "%a" {file_path}']})
        output = result.get('stdout', '').strip()

        try:
            permissions = int(output.split()[0])
            return permissions
        except ValueError:
            return None

    def check_obmm_files(self, node, memid, uid, gid):
        file_path = f"/dev/obmm_shmdev{memid}"

        result = node.run({'command': [f'test -e {file_path} && echo EXISTS || echo NOTEXISTS']})
        if 'NOTEXISTS' in result.get('stdout', ''):
            return False

        result = node.run({'command': [f'stat -c "%u %g" {file_path}']})
        output = result.get('stdout', '').strip()
        try:
            parts = output.split()
            file_uid, file_gid = parts[0], parts[1]
        except ValueError:
            return False

        if file_uid == uid and file_gid == gid:
            return True
        else:
            return False

    def get_socket_info(self, node):
        topo_info = cli_api.query_topo_info(node)
        result = {}
        for item in topo_info:
            if item['node'] not in result:
                result[item['node']] = []
            result[item['node']].append(item['socket'])
            if item['peer-node'] not in result:
                result[item['peer-node']] = []
            result[item['peer-node']].append(item['peer-socket'])
        new_result = {}
        for key, value in result.items():
            unique_values = set(value)
            new_key = key.split('(')[1].split(')')[0]
            new_result[new_key] = sorted(list(unique_values))
        return new_result

    def get_numa_info(self, node):
        numa_info = cli_api.display_numa_status_info(node)
        numa_dicts = {}
        result = {}
        for item in numa_info:
            key = item['node']
            new_key = key.split('(')[1].split(')')[0]
            numa = item['numa']
            if new_key not in numa_dicts:
                numa_dicts[new_key] = []
            numa_dicts[new_key].append(numa)
        for key, value in numa_dicts.items():
            sort_value = sorted(value)
            result[key] = sort_value
        return result

    def build_numa_hierarchy(self, mems, node_Info=''):
        """
        构建NUMA层次结构：node -> socket -> numa
        Args:
            mems: 包含NumaLoc信息的列表
        Returns:
            dict: 层次结构字典 {node: {socket: [numa1, numa2, ...]}}
        """
        if not node_Info:
            node = self.nodes[0]
        else:
            node = node_Info
        numa_info = self.get_numa_info(node)
        numa_info = {key: sorted(value, key=lambda x: int(x)) for key, value in numa_info.items()}
        socket_info = self.get_socket_info(node)
        socket_info = {key: sorted(value, key=lambda x: int(x)) for key, value in socket_info.items()}
        result = {}
        for node, sockets in socket_info.items():
            if node in numa_info:
                numas = numa_info[node]
                node_dict = {}
                for socket, numa in zip(sockets, numas):
                    node_dict[socket] = [numa]
                result[node] = node_dict
        return result

    def parse_sdk_numa_info(self, info: str) -> Dict[str, Dict[str, str]]:
        """Parse SDK NUMA memory info from output string.

        Args:
            info: Output string containing ubse_numa_mem_info entries

        Returns:
            Dict mapping numa id to NUMA info dict containing:
            - 'numa id': NUMA node ID
            - 'mem total': Total memory in GB
            - 'huge pages 2M': Total 2M huge pages
            - 'free huge pages 2M': Free 2M huge pages
        """
        res = {}
        temp = {}
        keys = ['numa id', 'mem total', 'huge pages 2M', 'free huge pages 2M']
        for line in info.split('\r\n'):
            if 'ubse_numa_mem_info' in line:
                if temp:
                    numa_id = temp.get('numa id')
                    if numa_id:
                        res[numa_id] = temp
                temp = {}
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                if key not in keys:
                    continue
                if key == 'mem total':
                    value = value.split('bytes')[0].strip()
                    try:
                        value = str(int(value) // 1024 // 1024 // 1024)
                    except ValueError:
                        pass
                else:
                    value = value.strip()
                temp[key] = value
        if temp:
            numa_id = temp.get('numa id')
            if numa_id:
                res[numa_id] = temp
        return res


    def get_env_numa_info(self, node: Any) -> Dict[str, Dict[str, str]]:
        """Get environment NUMA memory info from node.

        Args:
            node: Node object to query

        Returns:
            Dict mapping numa id to NUMA info dict containing:
            - 'numa id': NUMA node ID
            - 'mem total': Total memory in GB
            - 'huge pages 2M': Total 2M huge pages
            - 'free huge pages 2M': Free 2M huge pages
        """
        res = {}
        keys = {'size': 'mem total'}
        numa_stat = node.run({"command": ['numactl -H']}).get('stdout')
        info_list = numa_stat.rstrip('node distances').split('\r\n')
        for line in info_list:
            items = line.split(':')
            key = items[0].split(' ')
            if 'cpus' in items[0]:
                res.update({f'{key[1]}':{'numa id': key[1]}})
                continue
            if 'size' in items[0]:
                val = int(items[1].split('MB')[0].strip())
                res.get(key[1]).update({keys.get(key[2]): str(val //1024)})
        for i in list(res.keys()):
            total_2M = node.run(
                {"command": [f"cat /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages"]}
            )
            free_2M = node.run(
                {"command": [f"cat /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/free_hugepages"]}
            )
            res.get(i).update({"huge pages 2M": total_2M.get("stdout").split('\r\n')[0],
                               "free huge pages 2M": free_2M.get("stdout").split('\r\n')[0]
                               })
        return res