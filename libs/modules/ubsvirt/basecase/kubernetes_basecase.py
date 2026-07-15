#!/usr/local/python
# -*- coding: utf-8 -*-
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

        if self.master is None:
            raise RuntimeError("No master node found in node list")

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
            return False

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
        numa_count = self.get_node_numa_num(node)
        for i in range(0, numa_count):
            numa_clr_cmd = f"echo 0 > /sys/devices/system/node/node{i}/hugepages/hugepages-2048kB/nr_hugepages"
            node.run({'command': [numa_clr_cmd]})
        node.run({'command': ['echo 3 > /proc/sys/vm/drop_caches']})
        node.run({'command': ['numastat -cvm']})

    def change_hugepage(self, node_name: str, numa_name: str, extra_huge_size: int) -> None:
        """修改节点NUMA的大页数量

        参数说明：
            node_name: 节点名称
            numa_name: NUMA名称（如node0）
            extra_huge_size: 大页数量
        """
        node = self.node_dict[node_name]
        cmd = f"echo {extra_huge_size} > /sys/devices/system/node/{numa_name}/hugepages/hugepages-2048kB/nr_hugepages"
        node.run({'command': [cmd]})

    def clear_drop_cache(self, node_name: str) -> None:
        """清理节点缓存

        参数说明：
            node_name: 节点名称
        """
        node = self.node_dict[node_name]
        cmd = "echo 3 > /proc/sys/vm/drop_caches"
        node.run({'command': [cmd]})

    def set_label_numa(self) -> None:
        """设置NUMA策略标签"""
        cmd = "kubectl label nodes --all watermark-escape-strategy=numa --overwrite"
        self.master.run({'command': [cmd]})

    def set_label_node(self) -> None:
        """设置Node策略标签"""
        cmd = "kubectl label nodes --all watermark-escape-strategy=node --overwrite"
        self.master.run({'command': [cmd]})

    def get_node_number(self) -> int:
        """获取集群节点数量

        返回值说明：
            int: 节点数量
        """
        cmd = "kubectl get nodes -o jsonpath='{.items[*].metadata.name}'"
        res = self.master.run({'command': [cmd]})
        node_names = res.get("stdout", "").split("root@#>")[0]
        all_node = node_names.split()
        return len(all_node)

    def watch_pod_for_status(self, name_space: str = "kube-system", pod_name: str = "",
                             status: str = "Running", timeout: int = 60) -> bool:
        """等待Pod达到指定状态

        参数说明：
            name_space: 命名空间
            pod_name: Pod名称
            status: 目标状态
            timeout: 超时时间（秒）

        返回值说明：
            bool: 是否达到目标状态
        """
        search_cmd = f"kubectl get pod -n {name_space} | grep {pod_name} | awk '{{print $3}}'"
        wait_time = 0
        flag = False
        while wait_time < timeout:
            res = self.master.run({'command': [search_cmd], 'waitstr': '#'}).get('stdout')
            if status in res:
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        return flag

    def get_node_numa_free(self, node_name: str, numa_name: str) -> float:
        """获取节点NUMA的空闲内存

        参数说明：
            node_name: 节点名称
            numa_name: NUMA名称（如Node 0）

        返回值说明：
            float: 空闲内存大小（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        numa_infos = get_numaInfo(self.node_dict[node_name])
        for numa in numa_infos:
            if numa['name'] == numa_name:
                return float(numa['MemFree'])
        return 0.0

    def get_node_numa_total(self, node_name: str, numa_name: str) -> float:
        """获取节点NUMA的总内存

        参数说明：
            node_name: 节点名称
            numa_name: NUMA名称（如Node 0）

        返回值说明：
            float: 总内存大小（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        node = self.node_dict.get(node_name)
        if node is not None:
            numa_infos = get_numaInfo(node)
            for numa in numa_infos:
                if numa['name'] == numa_name:
                    return float(numa['MemTotal'])
        return 0.0

    def get_node_numa_used(self, node_name: str, numa_name: str) -> float:
        """获取节点NUMA的使用内存（通过大页计算）

        参数说明：
            node_name: 节点名称
            numa_name: NUMA名称（如Node 0）

        返回值说明：
            float: 使用内存大小（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        numa_infos = get_numaInfo(self.node_dict[node_name])
        res = 0.0
        for numa in numa_infos:
            if numa['name'] == numa_name:
                res = res + float(numa['HugePages_Total']) - float(numa['HugePages_Free'])
        return round(res, 2)

    def get_node_container_numa_affinity_by_name(self, node_name: str, pod_name: str = "pod-for-mem",
                                                  container_name: str = "numa") -> int:
        """通过名称获取Pod容器的NUMA亲和性

        参数说明：
            node_name: 节点名称
            pod_name: Pod名称
            container_name: 容器名称

        返回值说明：
            int: NUMA亲和性编号（失败返回-1）
        """
        name_space = "kube-system"
        uid_cmd = f"kubectl get pod -n {name_space} {pod_name} -o go-template='{{{{.metadata.uid}}}}'"
        test_node_uid = self.master.run({'command': [uid_cmd], 'waitstr': '#'}).get('stdout').replace("root@#>", "")

        node = self.node_dict[node_name]
        res = node.run({'command': ['cat /root/kubernetes/var/lib/kubelet/memory_manager_state']}).get(
            "stdout").replace("root@#>", "")
        if container_name not in res:
            logger.info("can not find container in mem manager state")
            return -1

        data = json.loads(res)
        numa_affinity = data['entries'][test_node_uid][container_name][0]['numaAffinity'][0]
        logger.info(f"pod numa affinity is {numa_affinity}")
        return numa_affinity

    def set_node_reserved_size(self, node_list: List[str], reserved_size_all: float) -> None:
        """设置节点预留内存大小

        参数说明：
            node_list: 节点列表
            reserved_size_all: 预留大小（MB）
        """
        for node_name in node_list:
            node = self.node_dict[node_name]
            node_numa_num = self.get_node_numa_num(node)
            reserved_size = reserved_size_all / int(node_numa_num)
            for numa_num in range(0, node_numa_num):
                numa_name = f"node{numa_num}"
                numa_name_for_search = f"Node {numa_num}"
                self.change_hugepage(node_name, numa_name, 0)
                time.sleep(2)
                mem_free = self.get_node_numa_free(node_name, numa_name_for_search)
                mem_reserved = reserved_size
                mem_hugepage = mem_free - mem_reserved
                if mem_hugepage > 0:
                    hugepage_count = int(mem_hugepage / 2)
                    self.change_hugepage(node_name, numa_name, hugepage_count)
                    time.sleep(2)
                else:
                    raise ValueError(f"set_node_reserved_size, mem_hugepage value error for {node_name} numa{numa_num}")

    def set_numa_reserved_size(self, numa_affinity_num: int, reserved_size_all: float, run_node_name: str) -> None:
        """设置NUMA预留内存大小

        参数说明：
            numa_affinity_num: NUMA亲和性编号
            reserved_size_all: 预留大小（MB）
            run_node_name: 运行节点名称
        """
        if numa_affinity_num not in [0, 1, 2, 3]:
            raise ValueError(f"numa affinity is invalid, num is {numa_affinity_num}")
        numa_name = f"Node {numa_affinity_num}"
        numa_node_for_huagepage = f"node{numa_affinity_num}"
        self.change_hugepage(run_node_name, numa_node_for_huagepage, 0)
        mem_free = self.get_node_numa_free(run_node_name, numa_name)
        mem_hugepage = mem_free - reserved_size_all
        if mem_hugepage > 0:
            hugepage_count = int(mem_hugepage / 2)
            self.change_hugepage(run_node_name, numa_node_for_huagepage, hugepage_count)
            time.sleep(10)
        else:
            logger.info("Remaining memory is less than the set_numa_reserved_size")

    def clear_all_huge_size(self, node_list: List[str]) -> None:
        """清理所有节点的大页

        参数说明：
            node_list: 节点列表
        """
        for node_name in node_list:
            node = self.node_dict[node_name]
            for numa_name in [f'node{i}' for i in range(0, 4)]:
                self.change_hugepage(node_name, numa_name, 0)
                time.sleep(2)

    def start_redis_server(self, node_name: str, pod_name: str = "pod-for-mem") -> None:
        """启动Redis服务器

        参数说明：
            node_name: 节点名称
            pod_name: Pod名称
        """
        node = self.node_dict[node_name]
        server_cmd = f"kubectl exec -n kube-system {pod_name} -- /redis/redis-server /redis/redis.conf &"
        ssh_node = get_new_sshconnect(self.master)
        ssh_node.run({'command': [server_cmd], 'waitstr': '#', 'timeout': 30, 'shnormal': True})
        wait_time = 0
        flag = False
        cmd = "ps axf | grep redis-server | grep -v grep | awk '{print $1}'"
        while wait_time < 60:
            server_pid = node.run({'command': [cmd], 'waitstr': '#'}).get("stdout").split("\r\n")[0]
            if server_pid:
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        if not flag:
            raise RuntimeError("redis server create failed")

    def stress_redis(self, stress_type: str = "numa", pod_name: str = "pod-for-mem") -> None:
        """使用Redis进行压力测试

        参数说明：
            stress_type: 压力类型（numa/node）
            pod_name: Pod名称
        """
        stress_map = {
            "numa": 2850000,
            "node": 6500000
        }
        stress_val = stress_map.get(stress_type, 2850000)
        server_cmd = [
            f"nohup kubectl exec -n kube-system {pod_name} -- /redis/redis-benchmark -t set,get -n 20000000 -c 128 -r {stress_val} -h 127.0.0.1 -p 6379 -d 2048 --threads 64 > /dev/null 2>&1 &"]
        ssh_node = get_new_sshconnect(self.master)
        ssh_node.run({'command': server_cmd, 'waitstr': 'avg_msec'})

    def stress_redis_by_value(self, stress_num_value: int, pod_name: str = "pod-for-mem") -> None:
        """使用Redis按指定值进行压力测试

        参数说明：
            stress_num_value: 压力数值
            pod_name: Pod名称
        """
        server_cmd = [
            f"nohup kubectl exec -n kube-system {pod_name} -- /redis/redis-benchmark -t set,get -n 20000000 -c 128 -r {stress_num_value} -h 127.0.0.1 -p 6379 -d 2048 --threads 64 > /dev/null 2>&1 &"]
        ssh_node = get_new_sshconnect(self.master)
        ssh_node.run({'command': server_cmd, 'waitstr': 'avg_msec'})

    def clear_redis_stress(self, pod_name: str) -> None:
        """清理Redis压力测试进程

        参数说明：
            pod_name: Pod名称
        """
        ssh_pod = get_new_sshconnect(self.master)
        client_kill_cmd = f"kubectl exec -n kube-system {pod_name} -- pkill -9 redis-benchmark"
        ssh_pod.run({'command': [client_kill_cmd], "timeout": 30})

        server_kill_cmd = f"kubectl exec -n kube-system {pod_name} -- pkill -9 redis-server"
        ssh_pod.run({'command': [server_kill_cmd], "timeout": 30})

    def add_huge_page_stress(self, node: Any, numa_id: int, percent: float) -> None:
        """添加大页压力

        参数说明：
            node: 节点SSH对象
            numa_id: NUMA编号
            percent: 压力百分比
        """
        node.run({'command': ['echo 3 > /proc/sys/vm/drop_caches']})
        from libs.modules.ubsvirt.api.client import get_numaInfo
        node_numa = get_numaInfo(node)
        numa_node = next((numa for numa in node_numa if numa['name'] == f'Node {numa_id}'), None)
        if not numa_node:
            raise ValueError(f"Node {numa_id} not found")

        request_huge_mem = int(numa_node["MemTotal"]) - (
                (int(numa_node["MemTotal"]) - int(numa_node["MemFree"]) + 7200) * 100 / percent)
        extra_huge_size = request_huge_mem / 2
        extra_stress_cmd = f"echo {int(extra_huge_size)} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
        res = node.run({'command': [extra_stress_cmd], 'waitstr': 'root@#>'}).get('stdout')
        if "error" in res:
            raise RuntimeError("tuning huge pages failed")

    def add_stress(self, pod: PodResource, percent: float, node_name: str, bind_numa: bool = True) -> None:
        """添加压力测试

        参数说明：
            pod: PodResource对象
            percent: 压力百分比
            node_name: 节点名称
            bind_numa: 是否绑定NUMA
        """
        self.start_redis_server(node_name, pod.pod_name)
        if bind_numa:
            self.add_huge_page_stress(pod.node, pod.numa_affinity, percent)
        self.stress_redis("numa", pod.pod_name)

    def get_node_matrix_log_path(self, node_name: str) -> str:
        """获取节点matrix-agent日志路径

        参数说明：
            node_name: 节点名称

        返回值说明：
            str: 日志路径
        """
        get_name_cmd = f"kubectl get pod -n kube-system -owide | grep kube-matrix-agent | grep {node_name} | awk '{{print $1}}'"
        matrix_node_name = self.master.run({'command': [get_name_cmd], 'waitstr': '#'}).get('stdout')
        matrix_node_name = matrix_node_name.replace("root@#>", "").replace("\r\n", "").strip()

        get_uid_cmd = f"kubectl get pod -n kube-system {matrix_node_name} -o go-template='{{{{.metadata.uid}}}}'"
        matrix_node_uid = self.master.run({'command': [get_uid_cmd], 'waitstr': '#'}).get('stdout')
        matrix_node_uid = matrix_node_uid.replace("root@#>", "").replace("\r\n", "").strip()

        log_path = f"/var/log/pods/kube-system_{matrix_node_name}_{matrix_node_uid}/kube-matrix-agent/"

        path_Exist = self.node_dict[node_name].doesPathExist(log_path)
        if not path_Exist:
            raise RuntimeError("can not get node matrix log path")
        return log_path

    def get_latest_log_name_list(self, node: Any, log_path: str) -> List[str]:
        """获取最新的日志文件列表

        参数说明：
            node: 节点SSH对象
            log_path: 日志路径

        返回值说明：
            List[str]: 日志文件名列表
        """
        cmd = f"ls -t {log_path}| head -n 2"
        res = node.run({'command': [cmd]})
        if res.get("stderr"):
            logger.error(res.get("stderr"))
            return []
        file_list = res.get("stdout", "").split("\r\n")
        return [f for f in file_list if ".log" in f]

    def get_decision_from_log(self, node: Any, log_path: str, current_time: int,
                              expect_des: str, log_name: str) -> str:
        """从日志中获取决策信息

        参数说明：
            node: 节点SSH对象
            log_path: 日志路径
            current_time: 当前时间戳
            expect_des: 期望的描述关键字
            log_name: 日志文件名

        返回值说明：
            str: 决策日志行（未找到返回None）
        """
        from datetime import datetime
        pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        cmd_str = f"zgrep -a '{expect_des}' {log_path}{log_name} | tail -n 20"
        res = node.run({'command': [cmd_str], 'waitstr': '#'})
        if res['stdout'] is None:
            return None
        server = res.get("stdout").replace("root@#>", "")
        lines = server.split('\n')
        decisions = []
        for index in range(0, len(lines) - 1, 1):
            line = lines[index]
            match = re.search(pattern, line)
            if not match:
                continue
            log_time = match.group()
            timestamp = datetime.strptime(log_time, "%Y-%m-%dT%H:%M:%S").timestamp()
            if timestamp <= current_time or (index + 1) >= len(lines):
                continue
            decisions.append(lines[index])
        formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"{formatted_time}时间点后的日志信息有{decisions}")
        if not decisions:
            return None
        else:
            return decisions[0]

    def get_matrix_agent_decision(self, timestamp: int, node_name: str, expect_des: str,
                                  timeout: int = 120) -> bool:
        """获取matrix-agent决策日志

        参数说明：
            timestamp: 时间戳
            node_name: 节点名称
            expect_des: 期望的描述关键字
            timeout: 超时时间（秒）

        返回值说明：
            bool: 是否找到决策日志
        """
        start_time = time.time()
        exec_node = self.node_dict[node_name]
        matrix_log = self.get_node_matrix_log_path(exec_node.getHostname())
        while (time.time() - start_time) < timeout:
            matrix_log_name_list = self.get_latest_log_name_list(exec_node, matrix_log)
            for matrix_log_name in matrix_log_name_list:
                decisions = self.get_decision_from_log(exec_node, matrix_log, timestamp, expect_des, matrix_log_name)
                if decisions:
                    return True
            time.sleep(10)
        return False

    def get_node_borrowing_numa(self, node_name: str) -> float:
        """获取节点借用的NUMA内存总量

        参数说明：
            node_name: 节点名称

        返回值说明：
            float: 借用内存总量（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        numa_infos = get_numaInfo(self.node_dict[node_name])
        borrowing_mem = 0.0
        for numa in numa_infos:
            if numa['name'] in {f'Node {i}' for i in range(self.node_numa_num, self.node_numa_num + 18)}:
                borrowing_mem = borrowing_mem + float(numa['MemTotal'])
        return round(borrowing_mem, 2)

    def get_node_borrowing_mem_used(self, node_name: str) -> float:
        """获取节点已借用内存的使用量

        参数说明：
            node_name: 节点名称

        返回值说明：
            float: 已借用内存使用量（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        numa_infos = get_numaInfo(self.node_dict[node_name])
        used_mem = 0.0
        for numa in numa_infos:
            if numa['name'] in {f'Node {i}' for i in range(4, 10)}:
                used_mem = used_mem + (float(numa['MemTotal']) - float(numa['HugePages_Free']))
        return round(used_mem, 2)

    def get_node_borrowing_mem_free(self, node_name: str) -> float:
        """获取节点已借用内存的空闲量

        参数说明：
            node_name: 节点名称

        返回值说明：
            float: 已借用内存空闲量（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        numa_infos = get_numaInfo(self.node_dict[node_name])
        used_mem = 0.0
        for numa in numa_infos:
            if numa['name'] in {f'Node {i}' for i in range(4, 10)}:
                used_mem = used_mem + float(numa['HugePages_Free'])
        return round(used_mem, 2)

    def get_node_mem_free_total(self, node_name: str) -> float:
        """获取节点所有本地NUMA的空闲内存总量

        参数说明：
            node_name: 节点名称

        返回值说明：
            float: 空闲内存总量（MB）
        """
        from libs.modules.ubsvirt.api.client import get_numaInfo
        numa_infos = get_numaInfo(self.node_dict[node_name])
        free_mem = 0.0
        for numa in numa_infos:
            if numa['name'] in {f'Node {i}' for i in range(0, 4)}:
                free_mem = free_mem + float(numa['MemFree'])
        return free_mem

    def check_numa_borrow_size(self, node_name: str, size: float, timeout: int = 120) -> bool:
        """检查NUMA借用内存大小

        参数说明：
            node_name: 节点名称
            size: 期望的借用大小（MB）
            timeout: 超时时间（秒）

        返回值说明：
            bool: 是否达到期望的借用大小
        """
        wait_time = 0
        flag = False
        while wait_time < timeout:
            borrow_num = self.get_node_borrowing_numa(node_name)
            if borrow_num >= size:
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        return flag

    def check_numa_accurate_borrow_size(self, node_name: str, size: float, timeout: int = 120) -> bool:
        """检查NUMA借用内存准确值

        参数说明：
            node_name: 节点名称
            size: 期望的借用大小（MB）
            timeout: 超时时间（秒）

        返回值说明：
            bool: 是否达到期望的借用大小
        """
        wait_time = 0
        flag = False
        while wait_time < timeout:
            borrow_num = self.get_node_borrowing_numa(node_name)
            if borrow_num == size:
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        return flag

    def check_numa_mem_return(self, node_name: str, timeout: int = 120) -> bool:
        """检查NUMA内存归还

        参数说明：
            node_name: 节点名称
            timeout: 超时时间（秒）

        返回值说明：
            bool: 是否归还成功
        """
        wait_time = 0
        while wait_time < timeout:
            flag1 = self.check_numa_accurate_borrow_size(node_name, 0, timeout=10)
            if flag1 is True:
                return True
            wait_time = wait_time + 5
            time.sleep(5)
        return False

    def get_latest_borrow_event(self, node_name: str) -> str:
        """获取最新的借用事件时间

        参数说明：
            node_name: 节点名称

        返回值说明：
            str: 事件时间字符串
        """
        borrow_event = f"kubectl get events -A --field-selector involvedObject.name={node_name},reason=EscapeAlarm --sort-by='.metadata.creationTimestamp' | grep 'mem borrow success' |tail -n 1"
        res = self.master.run({'command': [borrow_event], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0]
            if node_name in result:
                parts = result.split()
                time_field = parts[1]
                logger.info(f"time field is {time_field}")
                return time_field
        return ""

    def get_latest_return_event(self, node_name: str) -> str:
        """获取最新的归还事件时间

        参数说明：
            node_name: 节点名称

        返回值说明：
            str: 事件时间字符串
        """
        borrow_event = f"kubectl get events -A --field-selector involvedObject.name={node_name},reason=MemReturnAlarm --sort-by='.metadata.creationTimestamp' | grep 'mem return success' |tail -n 1"
        res = self.master.run({'command': [borrow_event], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0]
            if node_name in result:
                parts = result.split()
                time_field = parts[1]
                logger.info(f"time field is {time_field}")
                return time_field
        return ""

    def to_seconds(self, time_str: str) -> int:
        """将Kubernetes事件时间转换为秒

        参数说明：
            time_str: 时间字符串（如2m30s）

        返回值说明：
            int: 秒数
        """
        if 'm' in time_str:
            parts = re.split('m', time_str)
            minutes = int(parts[0])
            seconds = int(parts[1].rstrip('s')) if 's' in parts[1] else 0
            logger.info(f"time to second is {minutes * 60 + seconds}")
            return minutes * 60 + seconds
        else:
            return int(time_str.rstrip('s'))

    def set_watermark(self, return_line: int, first_line: int, second_line: int) -> bool:
        """设置内存借用水线阈值

        参数说明：
            return_line: 归还水线（百分比）
            first_line: 第一水线（百分比）
            second_line: 第二水线（百分比）

        返回值说明：
            bool: 是否设置成功

        示例：
            set_watermark(70, 85, 90) 表示：
            - 归还水线：70%
            - 第一借用水线：85%
            - 第二借用水线：90%
        """
        cmd = (
            f"kubectl patch cm -n kube-system watermark-config "
            f"--type merge "
            f"-p '{{\"data\":{{\"firstLine\":\"{first_line}\","
            f"\"returnLine\":\"{return_line}\","
            f"\"secondLine\":\"{second_line}\"}}}}'"
        )
        res = self.master.run({'command': [cmd], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0]
            if "configmap/watermark-config patched" in result:
                logger.info(f"水线设置成功: return_line={return_line}, first_line={first_line}, second_line={second_line}")
                return True
        logger.error("水线设置失败")
        return False

    def config_hugepage_with_mem_hugepage(self, node_name: str, numa_num: int, mem_reserved: float) -> None:
        """配置大页与预留内存

        参数说明：
            node_name: 节点名称
            numa_num: NUMA编号
            mem_reserved: 需要预留的内存大小（MB）
        """
        numa_name = f"Node {numa_num}"
        numa_node_for_huagepage = f"node{numa_num}"
        self.change_hugepage(node_name, numa_node_for_huagepage, 0)
        mem_free = self.get_node_numa_free(node_name, numa_name)
        mem_hugepage = mem_free - mem_reserved
        hugepage_count = int(mem_hugepage / 2)
        self.change_hugepage(node_name, numa_node_for_huagepage, hugepage_count)

    def set_node_label(self, bind_numa: bool = True) -> None:
        """设置节点标签

        参数说明：
            bind_numa: 是否绑定NUMA策略（True为numa，False为node）
        """
        self.master.run({'command': [f"kubectl label nodes --all remote-mem-allocation-ratio=25"]})
        if bind_numa:
            self.master.run({'command': [f"kubectl label nodes --all watermark-escape-strategy=numa --overwrite"]})
        else:
            self.master.run({'command': [f"kubectl label nodes --all watermark-escape-strategy=node --overwrite"]})

    def create_pod(self, pod_yaml: str) -> PodResource:
        """创建Pod并返回PodResource对象

        参数说明：
            pod_yaml: Pod yaml文件路径

        返回值说明：
            PodResource: Pod资源对象
        """
        tmp_pod_file = "/tmp/pod.yaml"
        with open(pod_yaml, encoding='utf-8') as fd:
            data = fd.read()

        self.upload_file("master", {"source_file": pod_yaml, "destination_file": tmp_pod_file})

        lines = data.split('\n')
        pod_name = ""
        name_space = "kube-system"
        node_name = ""
        container_name = ""

        for line in lines:
            line = line.strip()
            if line.startswith("name:"):
                if pod_name == "":
                    pod_name = line.split(":")[1].strip()
            elif line.startswith("namespace:"):
                name_space = line.split(":")[1].strip()
            elif line.startswith("nodeName:"):
                node_name = line.split(":")[1].strip()

        if container_name == "":
            container_name = pod_name

        pod_resource = PodResource(
            pod_name=pod_name,
            name_space=name_space,
            node=self.node_dict.get(node_name),
            container=container_name
        )

        create_cmd = f"kubectl apply -f {tmp_pod_file}"
        self.master.run({'command': [create_cmd], 'waitstr': '#'})

        self.master.run({'command': [f"rm -f {tmp_pod_file}"], 'waitstr': '#'})

        search_cmd = f"kubectl get pod -n {name_space} | grep {pod_name} | awk '{{print $3}}'"
        wait_time = 0
        flag = False
        while wait_time < 60:
            res = self.master.run({'command': [search_cmd], 'waitstr': '#'}).get('stdout')
            if "Running" in res:
                flag = True
                break
            wait_time = wait_time + 5
            time.sleep(5)
        self.assertTrue(flag, "pod create failed")

        self.get_node_container_numa_affinity(pod_resource)
        self.pod_list.append(pod_resource)

        return pod_resource

    def delete_pod(self, pod: PodResource) -> None:
        """删除Pod

        参数说明：
            pod: PodResource对象
        """
        search_cmd = f"kubectl get pod -n {pod.name_space} {pod.pod_name} -owide"
        res = self.master.run({'command': [search_cmd], 'waitstr': '#'}).get("stdout")
        self.assertNotIn("not found", res, "can not find pod in kube")

        del_cmd = f"kubectl delete pod -n {pod.name_space} {pod.pod_name}"
        self.master.run({'command': [del_cmd], 'waitstr': '#'})

    def clear_test_pod(self) -> None:
        """清理所有测试Pod"""
        for pod in self.pod_list[:]:
            self.delete_pod(pod)
            search_cmd = f"kubectl get pod -n {pod.name_space} {pod.pod_name} -owide"
            self.master.run({'command': [search_cmd], 'waitstr': '#'})
            self.pod_list.remove(pod)

    def get_node_container_numa_affinity(self, pod: PodResource) -> None:
        """获取Pod容器的NUMA亲和性

        参数说明：
            pod: PodResource对象
        """
        uid_cmd = f"kubectl get pod -n {pod.name_space} {pod.pod_name} -o go-template='{{{{.metadata.uid}}}}'"
        test_node_uid = self.master.run({'command': [uid_cmd], 'waitstr': '#'}).get('stdout').replace("root@#>", "")

        res = pod.node.run({'command': ['cat /root/kubernetes/var/lib/kubelet/memory_manager_state']}).get(
            "stdout").replace("root@#>", "")
        if pod.container_name not in res:
            logger.info("can not find container in mem manager state")
            pod.numa_affinity = 0
            return

        data = json.loads(res)
        numa_affinity = data['entries'][test_node_uid][pod.container_name][0]['numaAffinity'][0]
        logger.info(f"pod numa affinity is {numa_affinity}")
        pod.numa_affinity = numa_affinity

    def get_latest_borrow_failed_event(self, node_name: str) -> str:
        """获取最新的借用失败事件

        参数说明：
            node_name: 节点名称

        返回值说明：
            str: 时间字段
        """
        borrow_event = (
            f"kubectl get events -A  --field-selector involvedObject.name={node_name},reason=EscapeAlarm  --sort-by='.metadata.creationTimestamp'  | grep 'mem borrow failed' | tail -n 1")
        res = self.master.run({'command': [borrow_event], 'waitstr': '#'})
        if res.get("stdout"):
            result = res.get("stdout").split("root@#>")[0]
            if node_name in result:
                parts = result.split()
                time_field = parts[1]
                logger.info(f"time field is {time_field}")
                return time_field
        return ""

