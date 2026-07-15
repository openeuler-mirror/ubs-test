#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2025. All rights reserved.
"""KubernetesBaseCase - Kubernetes容器共享内存测试用例基类。
Pytest适配: KubernetesBaseCase(UBSVirtBaseCase) - 使用fixture注入
"""

import json
import logging
import re
import threading
import time

import pytest

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from libs.modules.ubsvirt.basecase.ubsvirt_basecase import UBSVirtBaseCase
from libs.modules.ubsvirt.common.node_manager import get_new_sshconnect
from libs.modules.ubsvirt.model.model import WrapperNode
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)
lock = threading.Lock()

class PodResource:
    """Pod资源容器类。"""

    def __init__(self, pod_name: str, name_space: str, node: Any, container: str):
        self.pod_name = pod_name
        self.name_space = name_space
        self.node = node
        self.container_name = container
        self.numa_affinity = 0

@pytest.fixture(autouse=True)
def inject_kubernetes_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any],
) -> None:
    """注入KubernetesBaseCase外部依赖。

    仅对KubernetesBaseCase及其子类进行注入。
    """
    if not hasattr(request, 'instance'):
        return

    instance = request.instance

    from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase

    if not isinstance(instance, KubernetesBaseCase):
        return

    instance.nodes = nodes if nodes else []
    instance.resource = resource
    instance.customParam = custom_params or {}

    instance.node_dict = {}
    instance.pod_list = []
    instance.controller = None
    instance.master = None
    instance.node_list = instance._load_nodes() if nodes else []

    instance.node_numa_num = instance.get_node_numa_num(instance.master) if instance.master else 0

    instance.logger = Log.getLogger(instance.__class__.__name__)

    instance.init_shm_test_tool()

    logger.info(f"KubernetesBaseCase已初始化: {len(nodes)}个节点, 类={instance.__class__.__name__}")

class KubernetesBaseCase(UBSVirtBaseCase):
    """Kubernetes容器共享内存测试用例基类。

    提供以下操作：
    - Pod管理（创建、删除、等待）
    - 共享内存操作（分配、映射、解除映射、释放）
    - CR资源管理
    - CSI驱动管理
    """

    def _load_nodes(self) -> List[WrapperNode]:
        """加载节点列表并设置master角色

        返回值说明：
            List[WrapperNode]: 节点列表
        """
        node_list = []
        for ssh_node in self.nodes:
            host_name = ssh_node.getHostname()
            wrapper_node = WrapperNode(host_name, ssh_node)
            node_list.append(wrapper_node)
            self.node_dict[host_name] = ssh_node
            if host_name == "controller":
                wrapper_node.add_tag('controller')
                self.controller = ssh_node
            elif host_name == "master":
                wrapper_node.add_tag('master')
                self.master = ssh_node
        return node_list

    def init_shm_test_tool(self) -> None:
        """初始化共享内存测试工具

        将shm_tool和shm_demo上传到master和worker1节点的/tmp/memborrow目录
        """
        resource_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt"
        file_path = '/tmp/memborrow'
        shm_test_tool_files = ['shm_tool', 'shm_demo']
        run_nodes = ["master", "worker1"]

        for node_name in run_nodes:
            if node_name not in self.node_dict:
                continue
            node = self.node_dict[node_name]
            node.run({'command': [f"mkdir -p {file_path}"]})
            for tool_file in shm_test_tool_files:
                source_file = str(resource_path / tool_file)
                destination_file = f"{file_path}/{tool_file}"
                res = node.run({'command': [f"ls -l {destination_file}"]})
                stdout = res.get("stdout") or ""
                parts = stdout.split("root@#>")
                first_part = parts[0] if parts else ""
                if "-r-xr-xr-x" in first_part:
                    continue
                params = {
                    "source_file": source_file,
                    "destination_file": destination_file
                }
                self.upload_file(node_name, params)
                node.run({'command': [f"chmod 555 {destination_file}"]})

    def get_node_numa_num(self, node: Any) -> int:
        """获取节点的NUMA数量

        参数说明：
            node: 节点SSH对象

        返回值说明：
            int: NUMA节点数量
        """
        res = node.run({'command': ["ls /sys/devices/system/node/ | grep node | wc -l"]}).get('stdout')
        if res:
            numa_num = res.split("root@#>")[0].strip()
            return int(numa_num)
        return 0

    def get_pod_list_by_name(self, pod_name: str, namespace: str = "kube-system", 
                              filter_running: bool = False) -> List[str]:
        """查询指定名称的pod列表，支持正则匹配

        参数说明：
            pod_name: Pod名称（支持正则）
            namespace: 命名空间（默认kube-system）
            filter_running: 是否过滤running状态的pod

        返回值说明：
            List[str]: Pod名称列表
        """
        cmd = f"kubectl get pods -n {namespace} --no-headers -o custom-columns=NAME:.metadata.name"
        if filter_running:
            cmd = f"{cmd} --field-selector='status.phase==Running'"

        res = self.master.run({'command': [cmd]})
        name = res.get("stdout", "").split("root@#>")[0]
        all_pods = name.splitlines()
        if res.get("stderr") is not None:
            logger.error(res.get("stderr"))

        pattern = re.compile(pod_name)
        matched_pods = [name for name in all_pods if pattern.search(name)]

        return matched_pods

    def create_dir(self, node_name: str, path: str) -> None:
        """在节点上创建目录

        参数说明：
            node_name: 节点名称
            path: 目录路径
        """
        cmd = f"mkdir -p {path}"
        node = self.node_dict[node_name]
        node.run({'command': [cmd]})

    def upload_file(self, node_name: str, params: Dict[str, str]) -> None:
        """上传文件到节点

        参数说明：
            node_name: 节点名称
            params: {'source_file': 本地路径, 'destination_file': 远程路径}
        """
        node = self.node_dict[node_name]
        if node:
            s_file = params.get('source_file')
            d_file = params.get('destination_file')
            if s_file and d_file:
                node.putFile(s_file, d_file)
            else:
                raise ValueError("Missing source_file or destination_file")
        else:
            raise ValueError("Node not found in node_dict")

    def create_resource_by_yaml(self, file_path: str) -> bool:
        """通过yaml文件创建资源

        参数说明：
            file_path: YAML文件路径

        返回值说明：
            bool: 是否成功
        """
        res = self.master.run({'command': [f"kubectl apply -f {file_path}"]})
        stdout = res.get("stdout", "")
        if "created" in stdout.split("root@#>")[0] or "unchanged" in stdout.split("root@#>")[0]:
            return True
        return False

    def delete_resource_by_yaml(self, file_path: str) -> bool:
        """通过yaml文件删除资源

        参数说明：
            file_path: YAML文件路径

        返回值说明：
            bool: 是否成功
        """
        res = self.master.run({'command': [f"kubectl delete -f {file_path}"]})
        stdout = res.get("stdout", "")
        if "deleted" in stdout.split("root@#>")[0]:
            return True
        return False

    def create_pod_by_name(self, file_name: str) -> bool:
        """通过yaml文件名创建pod

        参数说明：
            file_name: YAML文件名（位于/tmp/memborrow/）

        返回值说明：
            bool: 是否成功
        """
        res = self.master.run({'command': [f"kubectl apply -f /tmp/memborrow/{file_name}"]})
        if "created" in res.get("stdout", "").split("root@#>")[0]:
            return True
        return False

    def create_pod_and_wait_running(self, file_name: str, pod_name: str) -> bool:
        """创建pod并等待运行

        参数说明：
            file_name: YAML文件名
            pod_name: Pod名称

        返回值说明：
            bool: 是否成功
        """
        create_result = self.create_pod_by_name(file_name)
        if create_result:
            if not self.wait_for_pod_running(pod_name):
                return False
        return create_result

    def delete_pod_by_name(self, pod_name: str) -> bool:
        """根据名称删除pod

        参数说明：
            pod_name: Pod名称

        返回值说明：
            bool: 是否成功
        """
        res = self.master.run({'command': [f"kubectl delete pod {pod_name} -n kube-system"]})
        stdout = res.get("stdout")

        if stdout is None:
            return True

        if "deleted" in stdout.split("root@#>")[0]:
            return True
        return False

    def delete_pod_and_wait(self, pod_name: str) -> bool:
        """删除pod并等待删除完成

        参数说明：
            pod_name: Pod名称

        返回值说明：
            bool: 是否成功
        """
        self.delete_pod_by_name(pod_name)
        return self.wait_for_pod_deleted(pod_name)

    def wait_for_pod_running(self, pod_name: str, replica_num: int = 1) -> bool:
        """等待pod运行

        参数说明：
            pod_name: Pod名称（支持正则）
            replica_num: 期望的副本数

        返回值说明：
            bool: 是否成功
        """
        wait_time = 0
        while wait_time < 60:
            pod_list = self.get_pod_list_by_name(pod_name, "kube-system", True)
            if len(pod_list) == replica_num:
                return True
            wait_time = wait_time + 5
            time.sleep(5)
        return False

    def wait_for_pod_deleted(self, pod_name: str) -> bool:
        """等待pod删除完成

        参数说明：
            pod_name: Pod名称（支持正则）

        返回值说明：
            bool: 是否成功
        """
        wait_time = 0
        while wait_time < 60:
            pod_list = self.get_pod_list_by_name(pod_name, "kube-system", False)
            if len(pod_list) == 0:
                return True
            wait_time = wait_time + 5
            time.sleep(5)
        return False

    def exec_pod_cmd(self, pod_name: str, command: str) -> List[str]:
        """在pod中执行命令

        参数说明：
            pod_name: Pod名称
            command: 要执行的命令

        返回值说明：
            List[str]: 命令输出结果列表
        """
        server_cmd = f"kubectl exec -i -n kube-system {pod_name} -- {command}"
        ssh_node = get_new_sshconnect(self.master)
        res = ssh_node.run({'command': [server_cmd], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0].split('\r\n')
            return result
        return []

    def check_shm_demo_file(self, pod_name: str) -> List[str]:
        """检查pod中是否存在shm_demo文件

        参数说明：
            pod_name: Pod名称

        返回值说明：
            List[str]: 命令执行结果
        """
        wait_time = 0
        res = []
        while wait_time < 3:
            res = self.exec_pod_cmd(pod_name, "ls /ko | grep \"shm_demo\"")
            if self.get_key_from_result(res, "shm_demo"):
                break
            time.sleep(1)
            wait_time += 1
        return res

    def check_shm_tool_file(self, pod_name: str) -> List[str]:
        """检查pod中是否存在shm_tool文件

        参数说明：
            pod_name: Pod名称

        返回值说明：
            List[str]: 命令执行结果
        """
        wait_time = 0
        res = []
        while wait_time < 3:
            res = self.exec_pod_cmd(pod_name, "ls /ko | grep \"shm_tool\"")
            if self.get_key_from_result(res, "shm_tool"):
                break
            time.sleep(1)
            wait_time += 1
        return res

    def start_shm_tool_server(self, pod_name: str) -> bool:
        """在pod中启动shm_tool服务

        参数说明：
            pod_name: Pod名称

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(pod_name, "/ko/shm_tool server")
        for result in results:
            if "Daemon started" in result:
                return True
        return False

    def allocate_shm(self, pod_name: str, name: str, size: int, 
                     mode: int = 0o660, region_name: str = "default") -> bool:
        """申请共享内存

        参数说明：
            pod_name: Pod名称
            name: 共享内存名称
            size: 共享内存大小
            mode: 权限模式
            region_name: 区域名称

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name, 
            f"/ko/shm_demo ubsm_shmem_allocate {region_name} {name} {size} {mode} | grep \"shm_demo\""
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def allocate_shm_with_tool(self, pod_name: str, name: str, size: int,
                                mode: int = 0o660, region_name: str = "default") -> bool:
        """使用shm_tool申请共享内存

        参数说明：
            pod_name: Pod名称
            name: 共享内存名称
            size: 共享内存大小
            mode: 权限模式
            region_name: 区域名称

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client ubsm_shmem_allocate {region_name} {name} {size} {mode}"
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def map_shm(self, pod_name: str, length: int, prot: str, 
                flags: str, name: str) -> bool:
        """映射共享内存

        参数说明：
            pod_name: Pod名称
            length: 内存长度
            prot: 保护标志
            flags: 映射标志
            name: 共享内存名称

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_demo ubsm_shmem_map {length} {prot} {flags} {name} | grep \"shm_demo\""
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def map_shm_with_tool(self, pod_name: str, length: int, prot: str,
                          flags: str, name: str) -> str:
        """使用shm_tool映射共享内存

        参数说明：
            pod_name: Pod名称
            length: 内存长度
            prot: 保护标志
            flags: 映射标志
            name: 共享内存名称

        返回值说明：
            str: 内存地址（失败返回空字符串）
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client ubsm_shmem_map {length} {prot} {flags} {name}"
        )
        text = "\n".join(results) if isinstance(results, list) else str(results)

        match = re.search(r"at\s+(0x[0-9a-fA-F]+)", text)
        if match:
            return match.group(1)
        return ""

    def unmap_shm(self, pod_name: str, length: int, prot: str,
                  flags: str, name: str) -> List[str]:
        """解除共享内存映射

        注意：由于ubsm SDK限制，需要先映射才能解除映射

        参数说明：
            pod_name: Pod名称
            length: 内存长度
            prot: 保护标志
            flags: 映射标志
            name: 共享内存名称

        返回值说明：
            List[str]: 命令执行结果
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_demo ubsm_shmem_unmap {length} {prot} {flags} {name} | grep \"shm_demo\""
        )
        return results

    def unmap_shm_with_tool(self, pod_name: str, ptr: str, length: int) -> bool:
        """使用shm_tool解除共享内存映射

        参数说明：
            pod_name: Pod名称
            ptr: 内存地址指针
            length: 内存长度

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client ubsm_shmem_unmap {ptr} {length}"
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def deallocate_shm(self, pod_name: str, name: str) -> bool:
        """释放共享内存

        参数说明：
            pod_name: Pod名称
            name: 共享内存名称

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_demo ubsm_shmem_deallocate {name} | grep \"shm_demo\""
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def deallocate_shm_with_tool(self, pod_name: str, name: str) -> bool:
        """使用shm_tool释放共享内存

        参数说明：
            pod_name: Pod名称
            name: 共享内存名称

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client ubsm_shmem_deallocate {name}"
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def write_shm(self, pod_name: str, length: int, prot: str, flags: str,
                  name: str, file_length: int, input_file_path: str) -> List[str]:
        """写共享内存

        参数说明：
            pod_name: Pod名称
            length: 内存长度
            prot: 保护标志
            flags: 映射标志
            name: 共享内存名称
            file_length: 文件长度
            input_file_path: 输入文件路径

        返回值说明：
            List[str]: 命令执行结果
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_demo append {length} {prot} {flags} {name} {file_length} {input_file_path} | grep \"shm_demo\""
        )
        return results

    def read_shm(self, pod_name: str, length: int, prot: str, flags: str,
                 name: str, file_length: int, output_file_path: str) -> List[str]:
        """读共享内存

        参数说明：
            pod_name: Pod名称
            length: 内存长度
            prot: 保护标志
            flags: 映射标志
            name: 共享内存名称
            file_length: 文件长度
            output_file_path: 输出文件路径

        返回值说明：
            List[str]: 命令执行结果
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_demo read {length} {prot} {flags} {name} {file_length} {output_file_path} | grep \"shm_demo\""
        )
        return results

    def gen_file_for_shm(self, pod_name: str, file_path: str, size: str) -> List[str]:
        """在pod中生成测试文件

        参数说明：
            pod_name: Pod名称
            file_path: 文件路径
            size: 文件大小（支持4K, 10M, 1G等格式）

        返回值说明：
            List[str]: 命令执行结果
        """
        result = self.exec_pod_cmd(
            pod_name,
            f"bash -c \"tr -dc 'a-zA-Z' < /dev/urandom | head -c {size} > {file_path}\""
        )
        self.logInfo(f"生成shm测试文件结果 {result}")
        results = self.exec_pod_cmd(pod_name, f"ls -l {file_path} | wc -l")
        return results

    def set_shm_ownership_with_tool(self, pod_name: str, shm_name: str, 
                                     ptr: str, length: int, prot: int = 3) -> bool:
        """使用shm_tool设置共享内存权限

        参数说明：
            pod_name: Pod名称
            shm_name: 共享内存名称
            ptr: 内存地址指针
            length: 内存长度
            prot: 保护级别

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client ubsm_shmem_set_ownership {shm_name} {ptr} {length} {prot}"
        )
        for result in results:
            if "Success" in result:
                return True
        return False


    def write_shm_with_tool(self, pod_name: str, ptr: str, 
                            length: int, file_length: int) -> bool:
        """使用shm_tool写共享内存

        参数说明：
            pod_name: Pod名称
            ptr: 内存地址指针
            length: 内存长度
            file_length: 文件长度

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client append {ptr} {length} {file_length}"
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def read_shm_with_tool(self, pod_name: str, ptr: str,
                           length: int, file_length: int) -> bool:
        """使用shm_tool读共享内存

        参数说明：
            pod_name: Pod名称
            ptr: 内存地址指针
            length: 内存长度
            file_length: 文件长度

        返回值说明：
            bool: 是否成功
        """
        results = self.exec_pod_cmd(
            pod_name,
            f"/ko/shm_tool client read {ptr} {length} {file_length}"
        )
        for result in results:
            if "Success" in result:
                return True
        return False

    def get_file_md5(self, pod_name: str, file_path: str) -> str:
        """获取文件MD5值

        参数说明：
            pod_name: Pod名称
            file_path: 文件路径

        返回值说明：
            str: MD5值
        """
        results = self.exec_pod_cmd(pod_name, f"md5sum {file_path}")
        if results and len(results) > 0:
            return results[0].split()[0]
        return ""

    def get_cr_status(self, cr_name: str) -> List[str]:
        """获取CR(ShareMemory)状态

        参数说明：
            cr_name: CR名称

        返回值说明：
            List[str]: YAML输出内容列表
        """
        server_cmd = f"kubectl get smv -n kube-system {cr_name} -o yaml"
        ssh_node = get_new_sshconnect(self.master)
        res = ssh_node.run({'command': [server_cmd], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0].split('\r\n')
            return result
        return []

    def get_key_from_result(self, results: List[str], key_word: str) -> bool:
        """从结果中查找关键字

        参数说明：
            results: 结果列表
            key_word: 要查找的关键字

        返回值说明：
            bool: 是否找到关键字
        """
        for result in results:
            if key_word in result:
                self.logInfo(f"在结果中找到关键字 {result}")
                return True
        return False

    def get_shm_dev_nums(self, results: List[str]) -> int:
        """统计obmm设备数量

        参数说明：
            results: 结果列表

        返回值说明：
            int: 设备数量
        """
        num = 0
        for result in results:
            if "obmm" in result:
                self.logInfo(f"在结果中找到obmm设备 {result}")
                num += 1
        return num

    def get_shm_dev_num_with_tool(self, pod_name: str) -> int:
        """获取pod中/dev目录下的obmm设备数量

        参数说明：
            pod_name: Pod名称

        返回值说明：
            int: 设备数量
        """
        results = self.exec_pod_cmd(pod_name, "ls -l /dev/")
        return self.get_shm_dev_nums(results)

    def get_tmp_dev_num(self, pod_name: str, cr_name: str = "sharememory") -> List[str]:
        """获取tmpdev文件数量

        参数说明：
            pod_name: Pod名称
            cr_name: CR名称

        返回值说明：
            List[str]: 命令执行结果
        """
        server_cmd = f"ls -l /root/kubernetes/var/lib/kubelet/plugins/tmpdev/{cr_name}/{pod_name} | wc -l"
        ssh_node = get_new_sshconnect(self.master)
        res = ssh_node.run({'command': [server_cmd], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0].split('\r\n')
            return result
        return []

    def stop_shm_pod(self) -> bool:
        """停止shm-csi-driver pods

        返回值说明：
            bool: 是否成功
        """
        stop_cmd = """kubectl patch ds/shm-csi-driver -n kube-system -p '{"spec": {"template": {"spec": {"nodeSelector": {"aa": "bb"}}}}}'"""
        self.master.run({'command': [stop_cmd], 'waitstr': '#'})
        wait_time = 0
        flag = False
        while wait_time < 60:
            pod_list = self.get_pod_list_by_name("shm-csi-driver")
            if len(pod_list) == 0:
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        return flag

    def restart_shm_pod(self) -> bool:
        """重启shm-csi-driver pods

        返回值说明：
            bool: 是否成功
        """
        restart_cmd = """kubectl patch ds/shm-csi-driver -n kube-system --type='json' -p='[{"op": "remove", "path": "/spec/template/spec/nodeSelector"}]'"""
        self.master.run({'command': [restart_cmd], 'waitstr': '#'})
        wait_time = 0
        flag = False
        while wait_time < 60:
            pod_list = self.get_pod_list_by_name("shm-csi-driver", "kube-system", True)
            if len(pod_list) == self.get_node_number():
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        time.sleep(10)
        return flag

    def change_shm_driver_timer(self, ds_name: str, value: str) -> List[str]:
        """修改shm-csi-driver定时器值

        参数说明：
            ds_name: DaemonSet名称
            value: 定时器值

        返回值说明：
            List[str]: 命令执行结果
        """
        patch = [
            {
                "op": "replace",
                "path": "/spec/template/spec/containers/1/env/3/value",
                "value": value
            }
        ]
        server_cmd = f"kubectl patch ds {ds_name} -n kube-system --type='json' -p='{json.dumps(patch)}'"
        ssh_node = get_new_sshconnect(self.master)
        res = ssh_node.run({'command': [server_cmd], 'waitstr': '#'})
        if res.get("stdout"):
            wait_result = self.wait_ds_rollout(ds_name)
            return wait_result
        return []

    def wait_ds_rollout(self, ds_name: str, timeout: int = 60) -> List[str]:
        """等待daemonset滚动更新完成

        参数说明：
            ds_name: DaemonSet名称
            timeout: 超时时间（秒）

        返回值说明：
            List[str]: 命令执行结果
        """
        server_cmd = f"kubectl rollout status ds {ds_name} -n kube-system --timeout={timeout}s"
        ssh_node = get_new_sshconnect(self.master)
        res = ssh_node.run({'command': [server_cmd], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0].split('\r\n')
            return result
        return []

    def check_shm_driver_timer_clean(self, cr_name: str, shm_name: str) -> bool:
        """检查shm driver定时器是否清理了CR状态

        参数说明：
            cr_name: CR名称
            shm_name: 共享内存名称

        返回值说明：
            bool: 是否清理完成
        """
        wait_time = 0
        while wait_time < 20:
            cr_result = self.get_cr_status(cr_name)
            if not self.get_key_from_result(cr_result, shm_name):
                return True
            wait_time += 1
            time.sleep(3)
        return False

    def clear_huge_pages(self, node: Any) -> None:
        """清理节点上的所有大页

        参数说明：
            node: 节点SSH对象
        """
        for i in range(0, 4):
            numa_clr_cmd = f"echo 0 > /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages"
            node.run({'command': [numa_clr_cmd]})
        node.run({'command': ['echo 3 > /proc/sys/vm/drop_caches']})
        node.run({'command': ['numastat -cvm']})

