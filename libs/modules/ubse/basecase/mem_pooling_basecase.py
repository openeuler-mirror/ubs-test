"""MEM Pooling BaseCase.
Provides memory pooling management methods.
"""

import contextlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest

from libs.modules.ubse.api import cli_api
from libs.modules.ubse.basecase.cm_basecase import CMBaseCase
from libs.modules.ubse.common import topology, ubse_process_ops

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_mem_pooling_dependencies(request: Any) -> None:
    """注入MEM_Pooling_BaseCase特有的模块引用和计算参数.

    只对MEM_Pooling_BaseCase及其子类执行注入。
    """
    if not hasattr(request, "instance"):
        return

    instance = request.instance

    from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase

    if not isinstance(instance, MEM_Pooling_BaseCase):
        return

    logger.info("[MEM_FIXTURE] request has instance: %s", hasattr(request, "instance"))
    logger.info("[MEM_FIXTURE] instance type: %s", type(instance).__name__)

    instance.mem_sdk_path = instance.MEM_SDK_PATH
    instance.mem_borrow_shm_path = instance.MEM_BORROW_SHM_PATH
    instance.c_path = instance.C_PATH

    instance.ubse_process_ops = ubse_process_ops
    instance.cli_api = cli_api
    instance.topo_common = topology
    instance.ub_common = topology

    if hasattr(instance, "nodes") and instance.nodes:
        instance.master_node = instance.nodes[0]
        instance.agent_node = instance.nodes[1] if len(instance.nodes) > 1 else instance.nodes[0]
    else:
        instance.master_node = None
        instance.agent_node = None

    logger.info(
        "MEM_Pooling_BaseCase initialized for %d nodes",
        len(instance.nodes) if hasattr(instance, "nodes") else 0,
    )


class MEM_Pooling_BaseCase(CMBaseCase):
    """Base class for MEM pooling management tests.

    Provides methods for:
    - Memory borrowing/lending operations
    - SDK interface execution
    - NUMA management
    - Memory status query

    外部依赖参数（父类CMBaseCase.fixture注入）:
        - nodes: list[Any] - 测试节点列表
        - resource: dict[str, Any] - 资源配置字典
        - custom_params: dict[str, Any] - 自定义参数字典

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
    C_PATH = "/home/autotest"

    def preTestCase(self) -> None:
        """Pre-test setup - verify MEM pooling environment."""
        super().preTestCase()
        logger.info("MEM pooling environment verified")

    def procedure(self) -> None:
        """Main test logic."""
        super().procedure()

    def postTestCase(self) -> None:
        """Post-test cleanup."""
        super().postTestCase()
        logger.info("MEM_Pooling_BaseCase postTestCase")

    def python_sdk_mem_public(
        self, node: Any, python_version: str, sdk_interface: str, sdk_path: Optional[str] = None
    ) -> str:
        """执行Python SDK内存公共接口.

        Args:
            node: 节点对象
            python_version: Python版本
            sdk_interface: SDK接口名称
            sdk_path: SDK路径（可选，默认使用mem_sdk_path）

        Returns:
            执行结果stdout字符串

        Example:
            result = self.python_sdk_mem_public(node, "python3", "mem_query")
            print(result)
        """
        if sdk_path is None:
            sdk_path = self.mem_sdk_path

        sdk_script = f"{sdk_path}/{sdk_interface}"
        cmd = f"{python_version} {sdk_script}"

        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("stdout", "")

    def c_sdk_mem_public(self, node: Any, sdk_interface: str) -> str:
        """执行C SDK内存公共接口.

        Args:
            node: 节点对象
            sdk_interface: SDK接口名称

        Returns:
            执行结果stdout字符串

        Example:
            result = self.c_sdk_mem_public(node, "mem_query")
            print(result)
        """
        cmd = f"{self.MEM_SDK_PATH}/{sdk_interface}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("stdout", "")

    def check_sdk_return_mem_value_status(self, data: str, status: str) -> bool:
        """检查SDK返回值的内存状态.

        Args:
            data: SDK返回数据
            status: 期望的状态值

        Returns:
            True表示找到匹配状态，False表示未找到

        Example:
            if self.check_sdk_return_mem_value_status(result, "ok"):
                print("Memory status is OK")
        """
        pattern = f"status.*{status}"
        return bool(re.search(pattern, data))

    def check_sdk_return_borrow_and_lent_value_status(self, data: str, status: str) -> bool:
        """检查SDK返回值的借用/借出状态.

        Args:
            data: SDK返回数据
            status: 期望的状态值

        Returns:
            True表示找到匹配状态，False表示未找到

        Example:
            if self.check_sdk_return_borrow_and_lent_value_status(result, "done"):
                print("Borrow/Lend operation completed")
        """
        pattern = f"(borrow_status|lend_status).*{status}"
        return bool(re.search(pattern, data))

    def mem_borrow(
        self,
        node: Any,
        bin_path: Optional[str] = None,
        masking: bool = True,
        option: str = "borrow",
        shm_name: Optional[str] = None,
        start: bool = False,
        **kwargs: Any,
    ) -> str:
        """执行内存借用操作.

        Args:
            node: 节点对象
            bin_path: 二进制路径（可选）
            masking: 是否掩码（默认True）
            option: 操作选项（默认'borrow'）
            shm_name: 共享内存名称（可选）
            start: 是否启动（默认False）

        Returns:
            执行结果stdout字符串

        Example:
            result = self.mem_borrow(node, option='borrow', shm_name='test_mem')
            print(result)
        """
        if bin_path is None:
            bin_path = f"{self.mem_sdk_path}/test/bin"

        cmd_parts = [f"{bin_path}/mem_borrow"]

        if option:
            cmd_parts.append(f"--{option}")
        if shm_name:
            cmd_parts.append(f"--name {shm_name}")

        for key, value in kwargs.items():
            cmd_parts.append(f"--{key} {value}")

        cmd = " ".join(cmd_parts)
        result = node.run({"command": [cmd], "timeout": 120})
        return result.get("stdout", "")

    def mem_fd_borrow(
        self,
        node: Any,
        masking: bool = True,
        option: str = "create",
        name: str = "mem_borrow_test",
        size: str = "256M",
        numa_num: int = 1,
        slot_ids: Optional[str] = None,
        params_dict: Optional[dict[str, Any]] = None,
        wait_time: int = 120,
    ) -> bool:
        """执行FD内存借用操作.

        Args:
            node: 节点对象
            masking: 是否掩码（默认True）
            option: 操作选项（'create'/'create_with_lender'/'create_with_candidate'/'fd_permission'）
            name: 内存名称（默认'mem_borrow_test'）
            size: 内存大小（默认'256M'）
            numa_num: NUMA数量（默认1）
            slot_ids: 借出节点范围（可选）
            params_dict: 参数字典（可选）
            wait_time: 等待超时时间（默认120）

        Returns:
            True表示操作成功，False表示失败

        Example:
            if self.mem_fd_borrow(node, name='test_fd', size='128M'):
                print("FD memory created successfully")
        """
        result = ""
        if params_dict is None:
            params_dict = {}

        if masking:
            node.run({"command": [f"cd {self.c_path}"]})
            node.run(
                {
                    "command": ["python3 ubse_mem_app.py"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )

            if option == "create":
                res = node.run(
                    {
                        "command": [f"fd_create {name} {size}"],
                        "waitstr": "ubse_mem_app>",
                        "returnCode": False,
                    }
                )
                result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
            elif option == "create_with_lender":
                if numa_num == 1:
                    res = node.run(
                        {
                            "command": [
                                f"fd_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size}"
                            ],
                            "waitstr": "ubse_mem_app>",
                            "returnCode": False,
                        }
                    )
                else:
                    res = node.run(
                        {
                            "command": [
                                f"fd_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size} --numa_id {params_dict.get('lender_numa_id1', '')} {params_dict.get('size1', '')}"
                            ],
                            "waitstr": "ubse_mem_app>",
                            "returnCode": False,
                        }
                    )
                result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
            elif option == "create_with_candidate":
                res = node.run(
                    {
                        "command": [f"fd_create {name} {size} --slot_ids {slot_ids}"],
                        "waitstr": "ubse_mem_app>",
                        "returnCode": False,
                        "timeout": wait_time,
                    }
                )
                result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
            elif option == "fd_permission":
                comm = f"fd_permission {name} {params_dict.get('owner_uid', '')} {params_dict.get('owner_gid', '')} {params_dict.get('mode', '')}"
                res = node.run({"command": [comm], "waitstr": "ubse_mem_app>", "returnCode": False})
                result = str(res.get("stdout", "")) + str(res.get("stderr", ""))

            node.run({"command": ["exit"]})

            return "Successfully created" in result or "Successfully modified" in result
        else:
            node.run({"command": [f"cd {self.c_path}"]})
            node.run(
                {
                    "command": ["python3 ubse_mem_app.py"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )
            res = node.run(
                {
                    "command": [f"fd_delete {name}"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                    "timeout": wait_time,
                }
            )
            result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
            node.run({"command": ["exit"]})

            return "Successfully deleted" in result

    def mem_numa_borrow(
        self,
        node: Any,
        masking: bool = True,
        option: str = "create",
        name: str = "mem_borrow_test",
        size: str = "256M",
        numa_num: int = 1,
        slot_ids: Optional[str] = None,
        params_dict: Optional[dict[str, Any]] = None,
        wait_time: int = 120,
    ) -> bool:
        """执行NUMA内存借用操作.

        Args:
            node: 节点对象
            masking: 是否掩码（默认True）
            option: 操作选项（'create'/'create_with_lender'/'create_with_candidate'）
            name: 内存名称（默认'mem_borrow_test'）
            size: 内存大小，单位Byte，范围[128M, 256G]（默认'256M'）
            numa_num: NUMA数量（默认1）
            slot_ids: 借出节点范围（可选）
            params_dict: lender_slot_id、lender_socket_id、lender_numa_id等参数字典（可选）
            wait_time: 等待超时时间（默认120）

        Returns:
            True表示操作成功，False表示失败

        Example:
            if self.mem_numa_borrow(node, name='test_numa', size='128M'):
                print("NUMA memory created successfully")
        """
        result = ""
        if params_dict is None:
            params_dict = {}
        if masking:
            node.run({"command": [f"cd {self.c_path}"]})
            node.run(
                {
                    "command": ["python3 ubse_mem_app.py"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )
            if option == "create":
                res = node.run(
                    {
                        "command": [f"numa_create {name} {size}"],
                        "waitstr": "ubse_mem_app>",
                        "returnCode": False,
                        "timeout": wait_time,
                    }
                )
                result = str(res.get("stdout")) + str(res.get("stderr"))
            elif option == "create_with_lender":
                if numa_num == 1:
                    res = node.run(
                        {
                            "command": [
                                f"numa_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size}"
                            ],
                            "waitstr": "ubse_mem_app>",
                            "returnCode": False,
                            "timeout": wait_time,
                        }
                    )
                else:
                    res = node.run(
                        {
                            "command": [
                                f"numa_create_with_lender {name} {params_dict.get('lender_slot_id', '')} {params_dict.get('lender_socket_id', '')} --numa_id {params_dict.get('lender_numa_id', '')} {size} --numa_id {params_dict.get('lender_numa_id1', '')} {params_dict.get('size1', '')}"
                            ],
                            "waitstr": "ubse_mem_app>",
                            "returnCode": False,
                            "timeout": wait_time,
                        }
                    )
                result = str(res.get("stdout")) + str(res.get("stderr"))
            elif option == "create_with_candidate":
                res = node.run(
                    {
                        "command": [f"numa_create {name} {size} --slot_ids {slot_ids}"],
                        "waitstr": "ubse_mem_app>",
                        "returnCode": False,
                        "timeout": wait_time,
                    }
                )
                result = str(res.get("stdout")) + str(res.get("stderr"))
            node.run({"command": ["exit"], "timeout": wait_time})
            return "Successfully created" in result
        else:
            node.run({"command": [f"cd {self.c_path}"]})
            node.run(
                {
                    "command": ["python3 ubse_mem_app.py"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )
            res = node.run(
                {
                    "command": [f"numa_delete {name}"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                    "timeout": wait_time,
                }
            )
            result = str(res.get("stdout")) + str(res.get("stderr"))
            node.run({"command": ["exit"], "timeout": wait_time})
            return "Successfully deleted" in result

    def mem_query(
        self, node: Any, bin_path: Optional[str] = None, option: str = "mem_query"
    ) -> str:
        """执行内存查询操作.

        Args:
            node: 节点对象
            bin_path: 二进制路径（可选，默认使用mem_sdk_path）
            option: 查询选项（默认'mem_query'）

        Returns:
            执行结果stdout字符串

        Example:
            result = self.mem_query(node)
            print(result)
        """
        if bin_path is None:
            bin_path = f"{self.mem_sdk_path}/test/bin"

        cmd = f"{bin_path}/mem_query --{option}"
        result = node.run({"command": [cmd], "timeout": 60})
        return result.get("stdout", "")

    def get_mem_pooling_info(self, node: Any, option: str = "numa_status") -> str:
        """获取内存池化信息.

        Args:
            node: 节点对象
            option: 查询选项（默认'numa_status'）

        Returns:
            内存池化信息JSON字符串

        Example:
            info = self.get_mem_pooling_info(node, option='numa_status')
            print(info)
        """
        curl_cmd = f'curl --unix-socket /var/run/scbus/rackAgentUds.socket "http://localhost/redfish/v1/Managers/1/MemPoolService" -d \'{{"option": "{option}"}}\''
        result = node.run({"command": [curl_cmd], "timeout": 30})
        return result.get("stdout", "")


    def get_node_memory_status(self, node_id: str, expect_value: str = "ok") -> str:
        """获取指定节点的内存状态.

        Args:
            node_id: 节点ID
            expect_value: 期望的状态值（默认"ok"）

        Returns:
            内存状态字符串

        Example:
            status = self.get_node_memory_status("Node0", expect_value="ok")
            if status == "ok":
                print("Memory status is OK")
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

        Args:
            node: 节点对象
            command: 包含所需参数的内存借用归还命令
            wait_time: 等待超时时间（默认120）

        Returns:
            True表示成功，False表示失败

        Example:
            if self.mem_borrow_common(node, 'fd_create test_mem 128M'):
                print("Memory borrow succeeded")
        """

        node.run({"command": [f"cd {self.c_path}"]})
        node.run(
            {
                "command": ["python3 ubse_mem_app.py"],
                "waitstr": "ubse_mem_app>",
                "returnCode": False,
            }
        )
        res = node.run(
            {
                "command": [f"{command}"],
                "waitstr": "ubse_mem_app>",
                "returnCode": False,
                "timeout": wait_time,
            }
        )
        result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        self.logInfo(result)
        if "ubse_mem_app" in result:
            node.run({"command": ["exit"]})
        return "INFO: Successfully" in result

    def mem_borrow_common_result(
        self, node: Any, command: str, borrow_app_path: Optional[str] = None, timeout: int = 10
    ) -> str:
        """通过内存借用工具执行不同方式的借用归还并返回结果.

        Args:
            node: 节点对象
            command: 包含所需参数的内存借用归还命令
            borrow_app_path: 借用工具路径（可选，默认/home/autotest）
            timeout: 超时时间（默认10）

        Returns:
            执行结果字符串

        Example:
            result = self.mem_borrow_common_result(node, 'fd_list')
            print(result)
        """
        ubse_mem_app_path = "/home/autotest" if borrow_app_path is None else borrow_app_path

        node.run({"command": [f"cd {ubse_mem_app_path}"], "timeout": 1})
        node.run(
            {
                "command": ["python3 ubse_mem_app.py"],
                "timeout": 1,
                "waitstr": "ubse_mem_app>",
                "returnCode": False,
            }
        )
        res = node.run(
            {
                "command": [f"{command}"],
                "timeout": timeout,
                "waitstr": "ubse_mem_app>",
                "returnCode": False,
            }
        )
        result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        if "ubse_mem_app>" in result:
            node.run({"command": ["exit"], "timeout": 1})
        return result

    def mem_borrow_common_by_specify_user(
        self,
        node: Any,
        command: str,
        user: str,
        user_password: str,
        is_ubse: bool = False,
        borrow_app_path: str = "/tmp",
    ) -> str:
        """通过内存借用工具执行不同方式的借用归还（指定用户）.

        Args:
            node: 节点对象
            command: 包含所需参数的内存借用归还命令
            user: 执行命令的用户名
            user_password: 用户密码
            is_ubse: 是否使用ubse用户执行（默认False）
            borrow_app_path: 借用工具路径（默认'/tmp'）

        Returns:
            执行结果字符串

        Example:
            result = self.mem_borrow_common_by_specify_user(node, 'fd_list', 'testuser', 'password')
            print(result)
        """
        test_file_path = getattr(self, "test_file_path", "/home/autotest")

        if is_ubse:
            node.run({"command": [f"cd {test_file_path}"]})
            node.run(
                {
                    "command": ["sudo -u ubse python3 ubse_mem_app.py"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )
            res = node.run(
                {"command": [f"{command}"], "waitstr": "ubse_mem_app>", "returnCode": False}
            )
            node.run({"command": ["exit"]})
        else:
            node.run(
                {
                    "command": [f"cd {borrow_app_path}"],
                    "username": f"{user}",
                    "password": f"{user_password}",
                }
            )
            node.run(
                {
                    "command": ["python3 ubse_mem_app.py"],
                    "username": f"{user}",
                    "password": f"{user_password}",
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )
            res = node.run(
                {
                    "command": [f"{command}"],
                    "username": f"{user}",
                    "password": f"{user_password}",
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                }
            )
            node.run({"command": ["exit"], "username": f"{user}", "password": f"{user_password}"})

        result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        return result

    def mem_shm_borrow(
        self,
        node: Any,
        option: str = "shm_create",
        name: str = "mem_borrow_test",
        size: str = "256M",
        slot_ids: Optional[str] = None,
        params_dict: Optional[dict[str, Any]] = None,
        proviers: Optional[str] = None,
        wait_time: int = 120,
    ) -> bool:
        """共享内存借用操作.

        Args:
            node: 节点对象
            option: 操作类型（'shm_create'/'shm_create_with_lender'/'shm_attach'/'shm_detach'/'shm_delete'）
            name: 共享内存名称（默认'mem_borrow_test'）
            size: 共享内存大小（默认'256M'）
            slot_ids: 共享内存的节点范围（可选）
            params_dict: 参数字典（可选）
            proviers: 资源提供方节点范围（可选）
            wait_time: 等待超时时间（默认120）

        Returns:
            True表示成功，False表示失败

        Example:
            if self.mem_shm_borrow(node, option='shm_create', name='test_shm'):
                print("Shared memory created successfully")
        """
        result = ""
        if params_dict is None:
            params_dict = {}
        node.run({"command": [f"cd {self.c_path}"]})
        node.run(
            {
                "command": ["python3 ubse_mem_app.py"],
                "waitstr": "ubse_mem_app>",
                "returnCode": False,
            }
        )

        if option == "shm_create":
            if proviers:
                res = node.run(
                    {
                        "command": [
                            f"shm_create {name} {size} --region={slot_ids} --provider={proviers}"
                        ],
                        "waitstr": "ubse_mem_app>",
                        "timeout": wait_time,
                        "returnCode": False,
                    }
                )
            elif slot_ids:
                res = node.run(
                    {
                        "command": [f"shm_create {name} {size} --region={slot_ids}"],
                        "waitstr": "ubse_mem_app>",
                        "returnCode": False,
                    }
                )
            else:
                res = node.run(
                    {
                        "command": [f"shm_create {name} {size}"],
                        "waitstr": "ubse_mem_app>",
                        "returnCode": False,
                    }
                )
            result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        elif option == "shm_create_with_lender":
            res = node.run(
                {
                    "command": [
                        f"shm_create_with_lender {name} {size} "
                        f"{params_dict.get('lender_slot_id', '')} "
                        f"--socket_id={params_dict.get('lender_socket_id', '')} "
                        f"--numa_id={params_dict.get('lender_numa_id', '')}"
                    ],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                    "timeout": wait_time,
                }
            )
            result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        elif option == "shm_attach":
            res = node.run(
                {
                    "command": [f"shm_attach {name}"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                    "timeout": wait_time,
                }
            )
            result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        elif option == "shm_detach":
            res = node.run(
                {
                    "command": [f"shm_detach {name}"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                    "timeout": wait_time,
                }
            )
            result = str(res.get("stdout", "")) + str(res.get("stderr", ""))
        elif option == "shm_delete":
            res = node.run(
                {
                    "command": [f"shm_delete {name}"],
                    "waitstr": "ubse_mem_app>",
                    "returnCode": False,
                    "timeout": wait_time,
                }
            )
            result = str(res.get("stdout", "")) + str(res.get("stderr", ""))

        self.logInfo(result)
        if "ubse_mem_app" in result:
            node.run({"command": ["exit"]})

        return (
            "Successfully created" in result
            or "Successfully attach" in result
            or "Successfully detach" in result
            or "Successfully delete" in result
        )

    def get_mem_desc_list(self, mem_desc: str) -> list[dict[str, str]]:
        """解析内存描述信息返回列表.

        Args:
            mem_desc: 内存描述字符串

        Returns:
            包含内存信息的字典列表

        Example:
            mem_list = self.get_mem_desc_list("(name=test, size=128M)")
            for mem in mem_list:
                print(f"Name: {mem.get('name')}, Size: {mem.get('size')}")
        """
        pattern = r"\([^)]*\)"
        matches = re.findall(pattern, mem_desc)
        mem_desc_list = []

        for item in matches:
            if "name" not in item:
                continue
            item = item.replace("(", "").replace(")", "").replace(",", "")
            data = item.split("\r\n")
            mem_info = [
                info.strip() for info in data if info != "" and "usr_info (hex)" not in info
            ]
            mem_info_key = [key_value.split("=")[0] for key_value in mem_info[:-1]]
            if "name" not in mem_info_key:
                continue
            mem_info_value = [key_value.split("=")[1] for key_value in mem_info[:-1]]
            mem_info_dict = dict(zip(mem_info_key, mem_info_value))
            mem_desc_list.append(mem_info_dict)

        return mem_desc_list

    def clear_all_borrow_mem(self) -> bool:
        """清理所有借用内存（FD、NUMA、共享内存）.

        Returns:
            True表示清理成功，False表示清理失败

        Example:
            if self.clear_all_borrow_mem():
                print("All borrowed memory cleared")
        """
        # 清理fd内存
        for node in self.nodes:
            res = self.mem_borrow_common_result(node, "fd_list")
            fd_list = self.get_mem_desc_list(res)
            for item in fd_list:
                res = self.mem_fd_borrow(node, masking=False, name=item.get("name", ""))

        # 清理numa内存
        for node in self.nodes:
            res = self.mem_borrow_common_result(node, "numa_list")
            numa_list = self.get_mem_desc_list(res)
            for item in numa_list:
                res = self.mem_numa_borrow(node, masking=False, name=item.get("name", ""))

        # 清理共享内存
        names = []
        res = self.mem_borrow_common_result(self.nodes[0], "shm_list")
        shm_list = self.get_mem_desc_list(res)
        for item in shm_list:
            names.append(item.get("name", ""))

        shm_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        for item in shm_borrow_details:
            if item.get("borrow_node", "").isdigit():
                res = self.mem_shm_borrow(
                    self.nodes[int(item.get("borrow_node", "")) - 1],
                    option="shm_detach",
                    name=item.get("name", ""),
                )

        shm_borrow_name = [item.get("name") for item in shm_borrow_details]
        update_shm_borrow_name = list(set(shm_borrow_name))
        master, _, _ = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        for name in update_shm_borrow_name:
            res = self.mem_shm_borrow(master, option="shm_delete", name=name)
            self.logInfo(f"清理结果: {res}")

        self.logStep("清理后账本信息")
        res = self.cli_api.display_memory(self.nodes[0])
        return len(res) == 0

    def get_file_permissions(self, node: Any, memid: str) -> Optional[int]:
        """获取共享内存设备文件权限。

        Args:
            node: 节点对象
            memid: 内存ID

        Returns:
            文件权限（八进制数字），文件不存在返回None

        Example:
            perms = self.get_file_permissions(node, '0')
            if perms:
                print(f"File permissions: {perms}")
        """
        file_path = f"/dev/obmm_shmdev{memid}"

        result = node.run({"command": [f"test -e {file_path} && echo EXISTS || echo NOTEXISTS"]})
        if "NOTEXISTS" in result.get("stdout", ""):
            return None

        result = node.run({"command": [f'stat -c "%a" {file_path}']})
        output = result.get("stdout", "").strip()

        try:
            permissions = int(output.split()[0])
            return permissions
        except ValueError:
            return None

    def get_consumer_by_share(
        self, account_list: list[dict[str, str]], share_name: str, query_item: str = "consumer"
    ) -> str:
        """获取共享内存的消费者或提供者节点列表。

        Args:
            account_list: 账本信息列表
            share_name: 共享内存名称
            query_item: 查询类型（'consumer'或'lender'）

        Returns:
            节点ID逗号分隔字符串

        Example:
            consumers = self.get_consumer_by_share(account_list, 'test_shm')
            print(f"Consumers: {consumers}")
        """
        res = []
        for item in account_list:
            if item.get("name") == share_name:
                if query_item == "consumer":
                    res.append(item.get("borrow_node", ""))
                else:
                    res.append(item.get("lend_node", ""))
        return ",".join(res)

    def check_obmm_files(self, node: Any, memid: str, uid: int, gid: int, perms: int) -> bool:
        """检查共享内存设备文件的权限信息。

        Args:
            node: 节点对象
            memid: 内存ID
            uid: 用户ID
            gid: 组ID
            perms: 权限值（八进制）

        Returns:
            True表示权限匹配，False表示不匹配或文件不存在

        Example:
            if self.check_obmm_files(node, '0', 1000, 1000, 755):
                print("File permissions match expected values")
        """
        file_path = f"/dev/obmm_shmdev{memid}"

        result = node.run({"command": [f"test -e {file_path} && echo EXISTS || echo NOTEXISTS"]})
        if "NOTEXISTS" in result.get("stdout", ""):
            return False

        result = node.run({"command": [f'stat -c "%u %g %a" {file_path}']})
        output = result.get("stdout", "").strip()
        try:
            parts = output.split()
            file_uid, file_gid, file_perms = parts[0], parts[1], parts[2]
        except ValueError:
            return False

        return file_uid == str(uid) and file_gid == str(gid) and file_perms == str(perms)

    def get_socket_info(self, node: Any) -> dict[str, list[str]]:
        """获取拓扑信息中的socket映射。

        Args:
            node: 节点对象

        Returns:
            Dict映射节点ID到socket列表

        Example:
            socket_info = self.get_socket_info(node)
            for node_id, sockets in socket_info.items():
                print(f"Node {node_id}: sockets={sockets}")
        """
        topo_info = cli_api.display_topo_cpu(node)
        result = {}
        for item in topo_info:
            node_val = item.get("node", "")
            socket_val = item.get("socket", "")
            peer_node_val = item.get("peer-node", "")
            peer_socket_val = item.get("peer-socket", "")

            if node_val not in result:
                result[node_val] = []
            result[node_val].append(socket_val)
            if peer_node_val not in result:
                result[peer_node_val] = []
            result[peer_node_val].append(peer_socket_val)
        new_result = {}
        for key, value in result.items():
            unique_values = set(value)
            new_key = key.split("(")[1].split(")")[0] if "(" in key and ")" in key else key
            new_result[new_key] = sorted(unique_values)
        return new_result

    def get_numa_info(self, node: Any) -> dict[str, list[str]]:
        """获取NUMA信息映射。

        Args:
            node: 节点对象

        Returns:
            Dict映射节点ID到NUMA列表

        Example:
            numa_info = self.get_numa_info(node)
            for node_id, numas in numa_info.items():
                print(f"Node {node_id}: NUMAs={numas}")
        """
        numa_info = cli_api.display_numa_status_info(node)
        numa_dicts = {}
        result = {}
        for item in numa_info:
            key = item.get("node", "")
            new_key = key.split("(")[1].split(")")[0] if "(" in key and ")" in key else key
            numa = item.get("numa", "")
            if new_key not in numa_dicts:
                numa_dicts[new_key] = []
            numa_dicts[new_key].append(numa)
        for key, value in numa_dicts.items():
            sort_value = sorted(value)
            result[key] = sort_value
        return result

    def build_numa_hierarchy(self, node_info: Any = None) -> dict[str, dict[str, list[str]]]:
        """构建NUMA层次结构。

        Args:
            node_info: 节点对象（可选，默认使用nodes[0]）

        Returns:
            Dict层次结构 {node: {socket: [numa1, numa2, ...]}}

        Example:
            hierarchy = self.build_numa_hierarchy()
            for node_id, socket_map in hierarchy.items():
                print(f"Node {node_id}: {socket_map}")
        """
        node = node_info if node_info else self.nodes[0]
        numa_info = self.get_numa_info(node)
        numa_info = {key: sorted(value, key=lambda x: int(x)) for key, value in numa_info.items()}
        socket_info = self.get_socket_info(node)
        socket_info = {
            key: sorted(value, key=lambda x: int(x)) for key, value in socket_info.items()
        }
        result = {}
        for node, sockets in socket_info.items():
            if node in numa_info:
                numas = numa_info[node]
                node_dict = {}
                for socket, numa in zip(sockets, numas):
                    node_dict[socket] = [numa]
                result[node] = node_dict
        return result

    def parse_sdk_numa_info(self, info: str) -> dict[str, dict[str, str]]:
        """解析SDK NUMA内存信息.

        Args:
            info: 包含ubse_numa_mem_info的输出字符串

        Returns:
            Dict映射numa id到NUMA信息字典：
            - 'numa id': NUMA节点ID
            - 'mem total': 总内存（GB）
            - 'huge pages 2M': 总2M大页数
            - 'free huge pages 2M': 空闲2M大页数

        Example:
            numa_info = self.parse_sdk_numa_info(sdk_output)
            for numa_id, info in numa_info.items():
                print(f"NUMA {numa_id}: total={info.get('mem total')}GB")
        """
        res = {}
        temp = {}
        keys = ["numa id", "mem total", "huge pages 2M", "free huge pages 2M"]
        for line in info.split("\r\n"):
            if "ubse_numa_mem_info" in line:
                if temp:
                    numa_id = temp.get("numa id")
                    if numa_id:
                        res[numa_id] = temp
                temp = {}
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                if key not in keys:
                    continue
                if key == "mem total":
                    value = value.split("bytes")[0].strip()
                    with contextlib.suppress(ValueError):
                        value = str(int(value) // 1024 // 1024 // 1024)
                else:
                    value = value.strip()
                temp[key] = value
        if temp:
            numa_id = temp.get("numa id")
            if numa_id:
                res[numa_id] = temp
        return res

    def get_env_numa_info(self, node: Any) -> dict[str, dict[str, str]]:
        """获取环境NUMA内存信息.

        Args:
            node: 节点对象

        Returns:
            Dict映射numa id到NUMA信息字典：
            - 'numa id': NUMA节点ID
            - 'mem total': 总内存（GB）
            - 'huge pages 2M': 总2M大页数
            - 'free huge pages 2M': 空闲2M大页数

        Example:
            numa_info = self.get_env_numa_info(node)
            for numa_id, info in numa_info.items():
                print(f"NUMA {numa_id}: {info}")
        """
        res = {}
        keys = {"size": "mem total"}
        numa_stat = node.run({"command": ["numactl -H"]}).get("stdout", "")
        info_list = numa_stat.replace("node distances", "").rstrip().split("\r\n")
        for line in info_list:
            items = line.split(":")
            if len(items) < 2:
                continue
            key = items[0].split(" ")
            if len(key) < 2:
                continue
            if "cpus" in items[0]:
                res.update({f"{key[1]}": {"numa id": key[1]}})
                continue
            if "size" in items[0] and len(key) >= 3:
                val_str = items[1].split("MB")[0].strip() if "MB" in items[1] else "0"
                try:
                    val = int(val_str)
                    res.get(key[1]).update({keys.get(key[2]): str(val // 1024)})
                except ValueError:
                    pass
        for i in list(res.keys()):
            total_2m = node.run(
                {
                    "command": [
                        f"cat /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages"
                    ]
                }
            )
            free_2m = node.run(
                {
                    "command": [
                        f"cat /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/free_hugepages"
                    ]
                }
            )
            res.get(i).update(
                {
                    "huge pages 2M": total_2m.get("stdout", "").split("\r\n")[0],
                    "free huge pages 2M": free_2m.get("stdout", "").split("\r\n")[0],
                }
            )
        return res
