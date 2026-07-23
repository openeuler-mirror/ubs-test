#!/usr/local/python
# -*- coding: utf-8 -*-

"""VAS (虚拟化感知调度器) 基础测试类。

本模块提供VAS线性调度测试用例的基础功能。
包括虚拟机管理、CPU绑核检查、VAS服务操作等。
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

import pytest

from libs.core.base import TestCase

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_vas_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any],
) -> None:
    """注入VasBaseCase外部依赖。

    仅对VasBaseCase及其子类进行注入。
    """
    if not hasattr(request, 'instance'):
        return

    instance = request.instance

    if not isinstance(instance, VasBaseCase):
        return

    instance.nodes = nodes if nodes else []
    instance.resource = resource
    instance.customParam = custom_params or {}

    if nodes:
        instance.node = nodes[0]
        instance.cluster_size = instance.get_cluster_size()
        instance.numa_cpu_size = instance.get_numa_cpu_size()
        instance.cpu_list = instance.load_cpus()

        instance.command_check("setenforce 0", "setenforce failed")
        instance.ensure_dir_exist("/home/images", "Failed to ensure images dir exist")

    logger.info(f"VasBaseCase已初始化: {len(nodes)}个节点, 类={instance.__class__.__name__}")


class VasBaseCase(TestCase):
    """VAS线性调度测试用例基类。

    提供以下功能：
    - VAS服务管理（启动/停止/重启）
    - 虚拟机创建与销毁
    - CPU绑核查询与验证
    - Cluster和NUMA拓扑处理

    属性:
        node: SSH连接到测试节点（Linux实例）
        config_file: vas-daemon.service配置文件路径
        cluster_size: 每个Cluster的CPU数量
        numa_cpu_size: 每个NUMA节点的CPU数量
        cpu_list: 每个NUMA节点的CPU范围列表
    """

    node: Any = None
    config_file: str = "/usr/lib/systemd/system/vas-daemon.service"
    cluster_size: int = 16
    numa_cpu_size: int = 96
    cpu_list: List[str] = []

    def load_cpus(self) -> List[str]:
        """加载每个NUMA节点的CPU信息。

        执行lscpu命令并解析NUMA节点CPU分配。

        返回:
            每个NUMA节点的CPU范围字符串列表。
            示例：2个NUMA节点时返回 ['0-15,32-47', '16-31,48-63']。
        """
        if not self.node:
            self.logError("节点未初始化")
            return []

        command = "lscpu | grep 'NUMA node[0-9] CPU(s)'"
        result = self.node.run({'command': [command]})
        stdout = result.get('stdout', '')

        if not stdout:
            self.logError("获取NUMA CPU信息失败")
            return []

        cpu_list: List[str] = []
        numa_pattern = r'NUMA node(\d+) CPU\(s\):\s+([\d,-]+)'
        matches = re.findall(numa_pattern, stdout)

        for node_num, cpu_range in matches:
            idx = int(node_num)
            while len(cpu_list) <= idx:
                cpu_list.append('')
            cpu_list[idx] = cpu_range.strip()

        return cpu_list

    def get_cluster_size(self) -> int:
        """获取Cluster中的CPU数量。

        从/sys/devices/system/cpu/cpu0/topology/cluster_cpus_list读取。

        返回:
            每个Cluster的CPU数量。
        """
        if not self.node:
            return self.cluster_size

        command = "cat /sys/devices/system/cpu/cpu0/topology/cluster_cpus_list"
        result = self.node.run({'command': [command]})
        stdout = result.get('stdout', '')

        if not stdout:
            self.logWarn("获取Cluster大小失败，使用默认值")
            return self.cluster_size

        pattern = r'0-(\d+)'
        match = re.search(pattern, stdout)
        if match:
            return int(match.group(1)) + 1

        return self.cluster_size

    def get_numa_cpu_size(self) -> int:
        """获取NUMA节点0的CPU数量。

        返回:
            NUMA节点0的CPU数量。
        """
        if not self.node:
            return self.numa_cpu_size

        command = "lscpu | grep 'NUMA node[0] CPU(s)'"
        result = self.node.run({'command': [command]})
        stdout = result.get('stdout', '')

        if not stdout:
            self.logWarn("获取NUMA CPU大小失败，使用默认值")
            return self.numa_cpu_size

        pattern = r'0-(\d+)'
        match = re.search(pattern, stdout)
        if match:
            return int(match.group(1)) + 1

        return self.numa_cpu_size

    def stop_vas(self, timeout: int = 30) -> None:
        """停止vas-daemon服务。

        参数:
            timeout: 等待服务停止的最大时间（秒）。

        异常:
            AssertionError: 服务停止失败时抛出。
        """
        command = "systemctl stop vas-daemon"
        result = self.node.run({'command': [command]})
        self.assertIsNotNone(result.get('stdout'), "停止vas-daemon失败")

        query_cmd = "ps -ef | grep vas_daemon | grep -v grep"
        for _ in range(timeout):
            res = self.node.run({'command': [query_cmd]})
            if res.get("stdout") is None:
                break
            time.sleep(1)
        else:
            self.assertTrue(False, "vas-daemon在超时时间内未停止")

    def start_vas(self, timeout: int = 30) -> None:
        """启动vas-daemon服务。

        参数:
            timeout: 等待服务启动的最大时间（秒）。

        异常:
            AssertionError: 服务启动失败时抛出。
        """
        command = "systemctl start vas-daemon"
        result = self.node.run({'command': [command]})
        self.assertIsNotNone(result.get('stdout'), "启动vas-daemon失败")
        self.wait_service_status("vas-daemon", timeout)

    def restart_vas(self, timeout: int = 30) -> None:
        """重启vas-daemon服务。

        参数:
            timeout: 等待服务重启的最大时间（秒）。
        """
        command = "systemctl restart vas-daemon"
        result = self.node.run({'command': [command]})
        self.assertIsNotNone(result.get('stdout'), "重启vas-daemon失败")
        self.wait_service_status("vas-daemon", timeout)

    def reload_daemon(self) -> None:
        """重新加载systemd守护进程配置。"""
        command = "systemctl daemon-reload"
        result = self.node.run({'command': [command]})
        self.assertIsNotNone(result.get('stdout'), "systemctl daemon-reload失败")

    def wait_service_status(self, service_name: str, timeout: int, expect_status: str = "running") -> None:
        """等待服务达到预期状态。

        参数:
            service_name: 服务名称。
            timeout: 最大等待时间（秒）。
            expect_status: 预期状态（'running'或'stopped'）。

        异常:
            AssertionError: 服务未达到预期状态时抛出。
        """
        wait_time = 0
        flag = False

        while wait_time < timeout:
            res = self.node.getServiceStatus(service_name)
            if res == expect_status:
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)

        time.sleep(2)
        self.assertTrue(flag, f"{service_name}未达到{expect_status}状态")

    def command_check(self, command: str, msg: str = "命令执行错误") -> None:
        """执行命令并检查是否成功。

        参数:
            command: 要执行的命令。
            msg: 命令失败时的错误信息。

        异常:
            AssertionError: 命令执行失败时抛出。
        """
        result = self.node.run({'command': [command]})
        self.assertTrue(
            result.get('stdout') is not None and result.get('rc') == 0,
            msg
        )

    def ensure_dir_exist(self, dir_path: str, msg: str = "目录创建错误") -> None:
        """确保镜像目录存在。

        参数:
            dir_path: 目录路径。
            msg: 创建失败时的错误信息。
        """
        cmd = f"mkdir -p {dir_path}"
        self.command_check(cmd, msg)

    def execute_command_with_return(self, command: str) -> Dict[str, Any]:
        """执行命令并返回结构化结果。

        参数:
            command: 要执行的命令。

        返回:
            包含以下键的字典：
                - 'stdout': 命令标准输出（已清理）
                - 'stderr': 命令标准错误输出（已清理）
                - 'return_code': 成功为True，失败为False
        """
        result = self.node.run({'command': [command]})

        stdout = None
        stderr = None

        if result.get('stdout'):
            stdout = result.get('stdout').split("root@#>")[0].split('\r\n')[0]
        if result.get('stderr'):
            stderr = result.get('stderr').split("root@#>")[0].split('\r\n')[0]

        return_code = result.get('rc') == 0 and stderr is None

        return {
            'stdout': stdout,
            'stderr': stderr,
            'return_code': return_code
        }

    def create_vm(self, vm_name: str = "VM1", vcpus: int = 4, vmemory: int = 8,
                  numa_num: int = 0, cpuset_s: int = 0, cpuset_e: int = 0) -> None:
        """创建指定CPU和内存配置的虚拟机。

        参数:
            vm_name: 虚拟机名称。
            vcpus: 虚拟CPU数量。
            vmemory: 内存大小（GB）。
            numa_num: CPU绑核的NUMA节点编号。
            cpuset_s: CPU集范围的起始值（0表示自动）。
            cpuset_e: CPU集范围的结束值（0表示自动）。

        异常:
            AssertionError: 虚拟机创建失败时抛出。
        """
        base_disk_size = 200
        vmemory_mb = vmemory * 1024
        iso_path = "/home/openEuler-24.03-LTS-SP2-everything-aarch64-dvd.iso"
        images_dir = "/home/images"
        disk_path = f"{images_dir}/{vm_name}.img"

        if cpuset_s == 0 and cpuset_e == 0:
            cpuset_value = self.cpu_list[numa_num] if numa_num < len(self.cpu_list) else ""
            command = f"virt-install \
                --name={vm_name} \
                --vcpus={int(vcpus)},cpuset={cpuset_value} \
                --ram={int(vmemory_mb)} \
                --virt-type=kvm \
                --nographics \
                --noreboot \
                --disk path={disk_path},format=qcow2,size={base_disk_size},bus=virtio,cache=none \
                --location={iso_path} \
                --network network:default,model=virtio \
                --os-variant=centos8 \
                --noautoconsole"
        else:
            command = f"virt-install \
                --name={vm_name} \
                --vcpus={int(vcpus)},cpuset={cpuset_s}-{cpuset_e} \
                --ram={int(vmemory_mb)} \
                --virt-type=kvm \
                --nographics \
                --noreboot \
                --disk path={disk_path},format=qcow2,size={base_disk_size},bus=virtio,cache=none \
                --location={iso_path} \
                --network network:default,model=virtio \
                --os-variant=centos8 \
                --noautoconsole"

        self.command_check(command, f"创建{vm_name}失败")

    def destroy_vm(self, vm_name: str) -> None:
        """销毁并取消定义虚拟机。

        参数:
            vm_name: 要销毁的虚拟机名称。
        """
        command = f"virsh destroy {vm_name} && virsh undefine {vm_name} --nvram"
        self.command_check(command, f"销毁{vm_name}失败")

    def destroy_all(self) -> None:
        """销毁除VM0外的所有虚拟机。"""
        command = "virsh list --all | grep -v VM0 | wc -l"
        result = self.node.run({'command': [command]}).get('stdout', '')

        if result:
            count_str = result.split("root@#>")[0].split('\r\n')[0]
            if count_str == "0":
                return

        command = "virsh list --all | grep -v VM0"
        result = self.node.run({'command': [command]}).get('stdout', '')

        if not result:
            return

        pattern = r'(VM\d+)'
        matches = re.findall(pattern, result)

        for vm in matches:
            cmd1 = f"virsh destroy {vm}"
            cmd2 = f"virsh undefine {vm} --nvram"
            self.node.run({'command': [cmd1]})
            self.node.run({'command': [cmd2]})

    def get_vm_id(self, vm_name: str = "VM1") -> str:
        """根据名称获取虚拟机UUID。

        参数:
            vm_name: 虚拟机名称。

        返回:
            虚拟机的UUID字符串。

        异常:
            AssertionError: 获取虚拟机ID失败时抛出。
        """
        result = self.execute_command_with_return(f'virsh domuuid {vm_name}')
        self.assertTrue(result["return_code"], "获取虚拟机ID失败")
        return result['stdout']

    def check_vm(self, vm_name: str) -> bool:
        """检查虚拟机是否在运行。

        参数:
            vm_name: 虚拟机名称。

        返回:
            虚拟机运行中返回True，否则返回False。
        """
        command = f"virsh list --all|grep running |grep {vm_name}| wc -l"
        result = self.node.run({'command': [command]}).get('stdout', '')

        if result:
            count = result.split("root@#>")[0].split('\r\n')[0]
            return count == "1"

        return False

    def check_query_affinity(self, vm_name: str, start: Optional[int], end: Optional[int]) -> bool:
        """使用vasctl query检查虚拟机CPU绑核情况。

        参数:
            vm_name: 虚拟机名称，或'all'表示所有虚拟机。
            start: 预期的CPU范围起始值（None表示无绑核）。
            end: 预期的CPU范围结束值（None表示无绑核）。

        返回:
            绑核信息符合预期范围返回True。
        """
        if vm_name != "all":
            vm_id = self.get_vm_id(vm_name)
        else:
            vm_id = "all"

        command = f"vasctl query affinity --scope {vm_id}"
        result = self.node.run({'command': [command]}).get('stdout', '')

        if not result:
            return False

        pattern = r'"cpuIdx":(\d+)'
        matches = re.findall(pattern, result)

        if start is not None and end is not None:
            if not matches:
                return False
            for cpu_idx in matches:
                if int(cpu_idx) < int(start) or int(cpu_idx) > int(end):
                    return False
            return True
        elif start is None and end is None:
            return len(matches) == 0
        else:
            return False

    def get_layerId(self, vm_name: str, layer_id: int) -> bool:
        """检查虚拟机是否在指定层级。

        参数:
            vm_name: 虚拟机名称，或'all'。
            layer_id: 预期的层级ID。

        返回:
            虚拟机在指定层级返回True。
        """
        if vm_name != "all":
            vm_id = self.get_vm_id(vm_name)
        else:
            vm_id = "all"

        command = f"vasctl query affinity --scope {vm_id}"
        result = self.node.run({'command': [command]}).get('stdout', '')

        if not result:
            return False

        pattern = r'"layerId":(\d+)'
        match = re.search(pattern, result)

        if not match:
            return False

        return int(match.group(1)) == layer_id