"""VMxmlBaseCase - Base class for VM XML-based test cases.

Migrated from: legency/RackController_Automation/lib/basecase/virtualization/vmxml/VMxmlBaseCase.py
Provides common initialization logic for VM creation tests using XML configuration.

Legacy inheritance: VMxmlBaseCase(CMBaseCase)
Pytest adaptation: VMxmlBaseCase(CMBaseCase) - 使用fixture注入依赖

CRITICAL CHANGE (2026-05-29):
- 移除__init__方法，解决pytest无法收集带__init__测试类的硬限制
- 使用@pytest.fixture(autouse=True)注入外部依赖参数(nodes, resource, custom_params)
- 业务参数在fixture中初始化
"""

import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

import pytest

from libs.modules.ubsvirt.basecase.ubsvirt_basecase import UBSVirtBaseCase
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.common.node_manager import get_new_sshconnect
from libs.modules.ubsvirt.model.model import WrapperNode
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_vmxml_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any],
) -> None:
    """注入VMxmlBaseCase外部依赖参数.
    
    只对VMxmlBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.modules.ubsvirt.basecase.vmxml_basecase import VMxmlBaseCase
    if not isinstance(instance, VMxmlBaseCase):
        return
    
    instance.nodes = nodes if nodes else []
    instance.resource = resource
    instance.customParam = custom_params or {}
    
    instance.controller = None
    instance.agent_list = []
    instance.master = None
    instance.agent = None
    instance.node_list = instance._load_nodes() if nodes else []
    instance.numa_num = instance.get_numa_num(instance.master) if instance.master else 0
    instance.node_dict = {}
    
    instance.logger = Log.getLogger(instance.__class__.__name__)
    
    logger.info(f"VMxmlBaseCase initialized: {len(nodes)} nodes, class={instance.__class__.__name__}")


class VMxmlBaseCase(UBSVirtBaseCase):
    """Base class for VM XML-based test cases.
    
    提供基于XML创建虚拟机测试的基础设施：
    - Node list管理 (self.node_list, self.node_dict)
    - VM创建/删除操作（基于XML配置）
    - 大页配置
    - SSH连接管理
    
    Pytest模式（当前）:
        class MyTest(VMxmlBaseCase):
            # 无__init__方法！
            
            def setup_method(self):
                # 业务参数在此初始化
                pass
            
            def test_xxx(self):
                # 使用self.master, self.agent等
                pass
            
            def teardown_method(self):
                # 清理逻辑
                pass
    
    外部依赖参数（fixture注入）:
        - nodes: List[Any] - 测试节点列表
        - resource: Dict[str, Any] - 资源配置字典
        - custom_params: Dict[str, Any] - 自定义参数字典
    
    公共属性:
        - master: Any - master节点对象
        - agent: Any - agent节点对象
        - node_list: List[WrapperNode] - 节点列表
        - numa_num: int - NUMA节点数量
    """
    
    def get_scbus_role(self, ssh_node: Any) -> str:
        """获取节点软总线角色 (master/agent).
        
        Args:
            ssh_node: 节点SSH对象
            
        Returns:
            str: 'master' 或 'agent'
        """
        rack_role = ssh_node.run(
            {'command': ['sudo -u ubse /usr/bin/ubsectl display cluster | grep master | awk -F \'[()]\' \'{print $2}\''
                         ]}).get("stdout", "").replace("root@#>", "").strip()
        slot_ids = ssh_node.run({'command': [
            "ubsectl display cluster | grep ` cat /etc/hostname  | grep -v '#'` | awk 'BEGIN{ FS=\"(\" ; RS=\")\" } NF>1 { print $NF }'"]}).get(
            "stdout", "")
        if not slot_ids:
            return "agent"
        node_role = slot_ids[0]
        return "master" if node_role == rack_role else "agent"
    
    def _load_nodes(self) -> List[WrapperNode]:
        """加载节点列表并设置master/agent角色.
        
        Returns:
            List[WrapperNode]: 节点列表
        """
        node_list = []
        self.agent_list = []
        for ssh_node in self.nodes:
            host_name = ssh_node.getHostname()
            wrapper_node = WrapperNode(host_name, ssh_node)
            node_list.append(wrapper_node)
            if host_name == 'controller':
                wrapper_node.add_tag('controller')
                self.controller = ssh_node
            node_role = self.get_scbus_role(ssh_node)
            wrapper_node.add_tag(node_role)
            if node_role == 'master':
                self.master = ssh_node
                self.logger.info(f"{wrapper_node.hostname}---------->master")
            else:
                self.agent = ssh_node
                self.agent_list.append(ssh_node)
                self.logger.info(f"{wrapper_node.hostname}---------->agent")
        return node_list
    
    def get_numa_num(self, node: Any) -> int:
        """获取NUMA节点数量.
        
        Args:
            node: 节点SSH对象
            
        Returns:
            int: NUMA节点数量
        """
        if not node:
            return 0
        res = node.run({'command': ["lscpu | grep 'NUMA node(s)' | awk '{print $NF}'"]}).get("stdout")
        if res:
            res_clean = res.replace("root@#>", "").replace("@#>", "").strip()
            match = re.search(r'\d+', res_clean)
            if match:
                return int(match.group())
        return 0
    
    def get_numa_cpulist(self, node: Any, numa_id: int) -> List[str]:
        """获取指定NUMA节点的CPU列表.
        
        Args:
            node: 节点SSH对象
            numa_id: NUMA节点ID
            
        Returns:
            List[str]: CPU ID列表
        """
        res = node.run({'command': [f"cat /sys/devices/system/node/node{numa_id}/cpulist"]})
        cpulist_str = res.get('stdout', '').split("root@#>")[0].strip()
        return self._parse_cpu_list(cpulist_str)
    
    def _parse_cpu_list(self, cpulist_str: str) -> List[str]:
        """解析CPU列表字符串.
        
        Args:
            cpulist_str: CPU列表字符串，格式如 "0-3,8-11"
            
        Returns:
            List[str]: 展开后的CPU ID列表
        """
        cpu_list = []
        cpu_array = cpulist_str.split(',')
        for cpu in cpu_array:
            cpus = cpu.split('-')
            cpu_list.append(cpus[0])
            if len(cpus) > 1:
                for i in range(int(cpus[0]) + 1, int(cpus[1]) + 1):
                    cpu_list.append(str(i))
        return cpu_list
    
    def upload_xml_to_device(self, node: Any, source_path: str, filepath: str, xml_name: str) -> None:
        """上传XML文件到目标节点.
        
        Args:
            node: 节点SSH对象
            source_path: 本地XML文件所在目录
            filepath: 目标节点存放路径
            xml_name: XML文件名
        """
        cmd_command = f"mkdir -p {filepath}"
        node.run({'command': [cmd_command]})
        node.putFile(f"{source_path}/{xml_name}", f"{filepath}/{xml_name}")
    
    def modify_xml_on_device(self, node: Any, filepath: str, xml_name: str, 
                             modifications: Optional[Dict[str, Any]] = None) -> None:
        """在目标节点修改XML文件.
        
        Args:
            node: 节点SSH对象
            filepath: XML文件路径
            xml_name: XML文件名
            modifications: 修改配置字典
        """
        if not modifications:
            return
        for mod_type, mod_value in modifications.items():
            if mod_type == "vcpupin":
                for vcpu, cpuset in mod_value.items():
                    vcpu_id = vcpu.replace("vcpu", "")
                    node.run({'command': [
                        f"sed -i 's/<vcpupin vcpu=\"{vcpu_id}\" cpuset=\"[^\"]*\"/<vcpupin vcpu=\"{vcpu_id}\" cpuset=\"{cpuset}\"/g' {filepath}/{xml_name}"
                    ]})
            elif mod_type == "emulatorpin":
                node.run({'command': [
                    f"sed -i 's/<emulatorpin cpuset=\"[^\"]*\"/<emulatorpin cpuset=\"{mod_value}\"/g' {filepath}/{xml_name}"
                ]})
            elif mod_type == "memory":
                node.run({'command': [
                    f"sed -i 's/<memory unit=\"GiB\">[^\"]*</<memory unit=\"GiB\">{mod_value}</g' {filepath}/{xml_name}"
                ]})
            elif mod_type == "numatune_memory_nodeset":
                node.run({'command': [
                    f"sed -i \"s/<memory mode='strict' nodeset='[0-9]*'/<memory mode='strict' nodeset='{mod_value}'/g\" {filepath}/{xml_name}"
                ]})
            elif mod_type == "numatune_memnode_nodeset":
                node.run({'command': [
                    f"sed -i \"s/<memnode cellid='[0-9]*' mode='strict' nodeset='[0-9]*'/<memnode cellid='0' mode='strict' nodeset='{mod_value}'/g\" {filepath}/{xml_name}"
                ]})
    
    def create_vm_from_xml_file(self, node: Any, filepath: str, xml_name: str, 
                                 need_define: bool = False) -> bool:
        """从XML文件创建虚拟机.
        
        Args:
            node: 节点SSH对象
            filepath: XML文件路径
            xml_name: XML文件名
            need_define: 是否需要先定义再启动
            
        Returns:
            bool: 创建是否成功
        """
        vm_name = xml_name.replace(".xml", "")
        node.run({'command': [f"virsh destroy {vm_name} 2>/dev/null || true"]})
        node.run({'command': [f"virsh undefine {vm_name} 2>/dev/null || true"]})
        time.sleep(1)
        if need_define:
            vm_name = xml_name[:-4]
            cmd_command1 = f"virsh define {filepath}/{xml_name}"
            cmd_command2 = f"virsh start {vm_name}"
            res = node.run({'command': [cmd_command1]})
            res = node.run({'command': [cmd_command2]})
            stdout = res.get("stdout", "")
            if stdout and "started" in stdout.split("root@#>")[0]:
                return True
            return False
        cmd_command = f"virsh create {filepath}/{xml_name}"
        res = node.run({'command': [cmd_command]})
        stdout = res.get("stdout", "")
        if stdout and "created" in stdout.split("root@#>")[0]:
            return True
        return False
    
    def create_vm_from_xml(self, node: Any, source_path: str, filepath: str, 
                           xml_name: str, xml_modifications: Optional[Dict[str, Any]] = None,
                           need_define: bool = False) -> bool:
        """从XML文件创建虚拟机（完整流程）.
        
        Args:
            node: 节点SSH对象
            source_path: 本地XML文件目录
            filepath: 目标节点XML文件路径
            xml_name: XML文件名
            xml_modifications: XML修改配置
            need_define: 是否需要先定义再启动
            
        Returns:
            bool: 创建是否成功
        """
        self.upload_xml_to_device(node, source_path, filepath, xml_name)
        if xml_modifications:
            self.modify_xml_on_device(node, filepath, xml_name, xml_modifications)
        return self.create_vm_from_xml_file(node, filepath, xml_name, need_define)
    
    def wait_vm_state(self, node: Any, vm_name: str, expected_state: str,
                       timeout: int = 30, interval: int = 3) -> bool:
        """等待虚拟机达到期望状态.
        
        Args:
            node: 节点SSH对象
            vm_name: 虚拟机名称
            expected_state: 期望状态 (如 'running', 'shutdown' 等)
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
            
        Returns:
            bool: 是否在超时前达到期望状态
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            vm_state = node.run({'command': [f"virsh domstate {vm_name}"]}).get("stdout", "")
            if not vm_state:
                return False
            if expected_state in vm_state:
                return True
            time.sleep(interval)
        return False
    
    def verify_hugepage_config(self, node: Any, numa: int, expected_size_mb: int,
                                timeout: int = 60) -> int:
        """验证大页配置.
        
        Args:
            node: 节点SSH对象
            numa: NUMA节点ID
            expected_size_mb: 期望大页大小（MB）
            timeout: 超时时间（秒）
            
        Returns:
            int: 实际大页总大小（MB）
        """
        time.sleep(2)
        numa_info = client.get_numaInfo(node)
        if numa >= len(numa_info):
            self.assertTrue(False, f"numa {numa} out of range, available range: 0-{len(numa_info) - 1}")
        actual_total = int(numa_info[numa].get("HugePages_Total", 0))
        actual_free = int(numa_info[numa].get("HugePages_Free", 0))
        expected_hugepages = expected_size_mb // 2
        self.logInfo(f"NUMA{numa} hugepages - Total: {actual_total}, Free: {actual_free}, Expected: {expected_hugepages} ({expected_size_mb}MB)")
        self.assertEqual(actual_total, expected_size_mb,
                         f"hugepage config mismatch on node{numa}: expected {expected_hugepages}, got {actual_total}")
        return actual_total * 2
    
    def distribute_huge_page(self, node: Any, number: int, numa: int) -> None:
        """配置大页内存.
        
        Args:
            node: 节点SSH对象
            number: 大页数量
            numa: NUMA节点ID
        """
        node.run({'command': [f"echo {number} > /sys/devices/system/node/node{numa}/"
                              f"hugepages/hugepages-2048kB/nr_hugepages"]})
    
    def _get_vm_ssh(self, node: Any, name: str) -> Any:
        """获取虚拟机SSH连接.
        
        Args:
            node: 节点SSH对象
            name: 虚拟机名称
            
        Returns:
            Any: 虚拟机SSH连接对象
        """
        vm_ssh_node = get_new_sshconnect(node)
        res = client.enter_vm(vm_ssh_node, name)
        self.assertEqual(res.get('rc'), 0, f"登录虚拟机失败: {res}")
        return vm_ssh_node
    
    def add_stress_to_vm(self, node: Any, name: str, percent: int) -> Any:
        """对虚拟机增加内存压力.
        
        Args:
            node: 节点SSH对象
            name: 虚拟机名称
            percent: 内存压力百分比
            
        Returns:
            Any: 虚拟机SSH连接对象
        """
        vm_ssh_node = self._get_vm_ssh(node, name)
        memory_dict = client.get_memory(vm_ssh_node)
        total_mem = int(memory_dict.get('total', 0))
        used_mem = int(memory_dict.get('used', 0))
        add_stress = total_mem * percent / 100 - used_mem
        client.vm_stree(vm_ssh_node, str(int(add_stress)) + "M")
        return vm_ssh_node
