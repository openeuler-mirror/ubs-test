"""VMHotPlugBaseCase - Base class for VM hot-plug test cases.

"""

import pytest
import re
import time

from typing import Any, Dict, List, Optional
from libs.modules.ubsvirt.basecase.ubsvirt_basecase import UBSVirtBaseCase
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.common import node_manager
from libs.modules.ubsvirt.model.model import WrapperNode
from libs.utils.logger_compat import Log


@pytest.fixture(autouse=True)
def inject_vmhotplug_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any],
) -> None:
    """注入VMHotPlugBaseCase外部依赖参数.

    只对VMHotPlugBaseCase及其子类执行注入。
    """
    if not hasattr(request, "instance"):
        return

    instance = request.instance

    from libs.modules.ubsvirt.basecase.vmhotplug_basecase import VMHotPlugBaseCase

    if not isinstance(instance, VMHotPlugBaseCase):
        return

    # 注入外部依赖参数（从父类fixture继承）
    instance.nodes = nodes
    instance.resource = resource
    instance.customParam = custom_params

    # 初始化业务参数
    instance.node_list = instance._load_nodes()
    instance.node_dict = {}
    instance.is_Simulation = resource.get('global', {}).get('is_simulation', False)
    instance.resource_dict = {}
    instance.volume_use_list = []
    # TODO: Update_Common需要单独迁移到 libs/rackcontrol/update_common.py
    # instance.update_aw = Update_Common
    instance.node_numa_numa = {}
    
    # 初始化NUMA数量（需要master节点）
    if hasattr(instance, "master") and instance.master:
        instance.numa_num = instance.get_numa_num(instance.master)
    else:
        instance.numa_num = 0  # 默认值，后续在setup_method中更新

    instance.logger = Log.getLogger(instance.__class__.__name__)


class VMHotPlugBaseCase(UBSVirtBaseCase):
    """Base class for VM hot-plug test cases.

    提供所有VM热插拔测试的基础设施：
    - Node list管理 (self.nodes, self.node_list, self.node_dict)
    - VM管理 (self.master, self.agent, self.controller)
    - NUMA信息管理 (self.numa_num, self.node_numa_numa)
    - 内存热插拔操作 (hot_plug_mem, hot_plug_delete等)

    Legacy模式（已废弃）:
        class MyTest(VMHotPlugBaseCase):
            def __init__(self, parameters):
                super().__init__(parameters)

    Pytest模式（当前）:
        class MyTest(VMHotPlugBaseCase):
            # 无__init__方法！
            # 外部依赖参数通过父类fixture自动注入

            def setup_method(self):
                # 业务参数在此初始化
                pass

            def test_xxx(self):
                # 使用self.nodes, self.node_list等
                pass

    外部依赖参数（fixture注入）:
        - nodes: List[Any] - 测试节点列表
        - resource: Dict[str, Any] - 资源配置字典
        - custom_params: Dict[str, Any] - 自定义参数字典

    业务参数（fixture初始化）:
        - node_list: List[WrapperNode] - 包装节点列表
        - node_dict: Dict[str, NodeResource] - 节点字典
        - numa_num: int - NUMA节点数量
        - master: SSH node - 主节点
        - agent: SSH node - 代理节点
        - controller: SSH node - 控制节点
    """

    def get_numa_num(self, node: Any) -> int:
        """获取节点的NUMA数量.

        Args:
            node: SSH节点对象

        Returns:
            NUMA节点数量

        Raises:
            RuntimeError: 获取NUMA数量失败
        """
        res = node.run(
            {"command": ["lscpu | grep 'NUMA node(s)' | awk '{print $NF}'"]}
        ).get("stdout")
        if res:
            return int(res.replace("root@#>", ""))
        else:
            raise RuntimeError("get numa num failed")

    def upload_xml_to_device(self, node: Any, source_path: str, filepath: str, xml_name: str) -> None:
        """上传XML文件到目标节点.

        Args:
            node: SSH节点对象
            source_path: 本地XML文件所在目录
            filepath: 目标节点存放路径
            xml_name: XML文件名
        """
        cmd_command = f"mkdir -p {filepath}"
        node.run({"command": [cmd_command]})
        src_file = f"{source_path}/{xml_name}"
        dst_file = f"{filepath}/{xml_name}"
        node.putFile(src_file, dst_file)

    def modify_xml_on_device(self, node: Any, filepath: str, xml_name: str,
                             xml_modifications: Optional[Dict[str, Any]] = None) -> None:
        """在目标节点修改XML文件.

        Args:
            node: SSH节点对象
            filepath: XML文件路径
            xml_name: XML文件名
            xml_modifications: 修改配置字典
        """
        if not xml_modifications:
            return
        for mod_type, mod_value in xml_modifications.items():
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

    def create_vm_from_xml_file(self, node: Any, filepath: str, xml_name: str) -> bool:
        """从XML文件创建虚拟机.

        Args:
            node: SSH节点对象
            filepath: XML文件路径
            xml_name: XML文件名

        Returns:
            bool: 创建是否成功
        """
        cmd_command = f"virsh create {filepath}/{xml_name}"
        res = node.run({"command": [cmd_command]})
        stdout = res.get("stdout", "") if res else ""
        if stdout and "created" in stdout.split("root@#>")[0]:
            return True
        return False

    def create_vm_from_xml(
        self, node: Any, source_path: str, filepath: str, xml_name: str,
        xml_modifications: Optional[Dict[str, Any]] = None
    ) -> bool:
        """从XML文件创建虚拟机（完整流程）.

        Args:
            node: SSH节点对象
            source_path: 本地XML文件目录
            filepath: 目标节点XML文件路径
            xml_name: XML文件名
            xml_modifications: XML修改配置（可选）

        Returns:
            bool: 创建是否成功
        """
        self.upload_xml_to_device(node, source_path, filepath, xml_name)
        if xml_modifications:
            self.modify_xml_on_device(node, filepath, xml_name, xml_modifications)
        return self.create_vm_from_xml_file(node, filepath, xml_name)

    def get_scbus_role(self, ssh_node: Any) -> str:
        """获取软总线角色.

        Args:
            ssh_node: SSH节点对象

        Returns:
            "master" 或 "agent"
        """
        self.logger.info(
            "读取软总线配置， 当软总线配置为主，设置为self.master，软总线设置为其他，则设置为agent"
        )
        res = ssh_node.run(
            {
                "command": [
                    "sudo -u ubse /usr/bin/ubsectl display cluster | grep master | awk -F '[()]' '{print $2}'"
                ]
            }
        ).get("stdout", "")
        rack_role = res.replace("root@#>", "").strip() if res else ""
        command = (
            'curl -X GET "http://127.0.0.1:34256/restconf/data/huawei-vbussw-inventory:vbussw-inventory/logic-entity-mappings" '
            '-H "Accept: application/yang-data+xml" -H "Content-Type: application/yang-data+xml" -v 2>&1 | grep slot'
        )
        res = ssh_node.run({"command": [command]}).get("stdout", "")
        res_clean = res.replace("root@#>", "").strip() if res else ""
        slot_ids = re.findall(r"<slot-id>(\d+)</slot-id>", res_clean)
        if not slot_ids:
            self.logger.warn(f"No slot-id found in curl response, defaulting to agent")
            return "agent"
        node_role = slot_ids[0]
        return "master" if node_role == rack_role else "agent"

    def reset_hugepage(self, node_list: List[Any], node_dict: Dict[str, Any]) -> None:
        """重置大页内存.

        Args:
            node_list: 节点列表
            node_dict: 节点字典
        """
        keys = node_dict.keys()
        for node in node_list:
            for key in keys:
                if "agent" not in node.tags:
                    node.add_tag("expect_node")
                    continue
                elif node.hostname == node_dict[key].host:
                    node.add_tag("expect_node")
                    continue
        for node in node_list:
            if "expect_node" not in node.tags:
                numa_info_dict = {0: 384}
                result = client.refresh_hugePage(node.ssh_connect, numa_info_dict)
                if not result:
                    raise RuntimeError("set hugePage fail")

    def get_node_borrowing_numa(self, node: Any) -> float:
        """获取节点的借用NUMA内存.

        Args:
            node: SSH节点对象

        Returns:
            借用内存大小（MB）
        """
        numa_infos = client.get_numaInfo(node)
        borrowing_mem = 0.0
        for numa in numa_infos:
            match = re.search(r"Node\s+(\d+)", numa["name"])
            if match:
                node_number = match.group(1)
                number = int(node_number)
                if number >= self.numa_num and number <= 17:
                    borrowing_mem = borrowing_mem + float(numa["MemTotal"])
        return round(borrowing_mem, 2)

    def add_stress_to_vm(self, node: Any, name: str, ram: int) -> None:
        """为VM添加压力测试.

        Args:
            node: SSH节点对象
            name: VM名称
            ram: 内存大小（MB）
        """
        vm_ssh_node = self._get_vm_ssh(node, name)
        client.vm_stree(vm_ssh_node, str(ram) + "M")

    def free_mem_within_time(self, node: Any, free_time: int) -> None:
        """检查内存是否在指定时间内归还.

        Args:
            node: SSH节点对象
            free_time: 等待时间（秒）
        """
        is_borrowed_mem = self.check_is_borrow_mem(node, free_time, 5)
        self.assertFalse(is_borrowed_mem, f"在{free_time}时间内，内存归还失败")

    def get_ubse_status(self, node: Any) -> Dict[str, str]:
        """获取UBSE状态.

        Args:
            node: SSH节点对象

        Returns:
            状态字典
        """
        status_dict = {}
        res = node.run({"command": ["sudo -u ubse ubsectl check memory"]}).get("stdout")
        if res:
            lines = res.splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith(("-", "root")) and "node" not in line:
                    parts = line.split()
                    node_str = parts[0]
                    status = parts[1]
                    base_node = node_str.split("(")[0] if "(" in node_str else node_str
                    status_dict[base_node] = status
        return status_dict

    def wait_ubse_status(self, node: Any, timeout: int, wait_interval: int) -> None:
        """等待UBSE状态就绪.

        Args:
            node: SSH节点对象
            timeout: 超时时间（秒）
            wait_interval: 等待间隔（秒）
        """
        start_time = time.time()
        while time.time() - start_time <= timeout:
            flag = True
            status_dict = self.get_ubse_status(node)
            for ssh_node in self.nodes:
                host_name = ssh_node.getHostname()
                if host_name == "controller":
                    continue
                if status_dict.get(host_name) != "ok":
                    flag = False
                    break
            if flag:
                time.sleep(30)  # ubse进程恢复后再等待30s，提高用例稳定性
                return
            time.sleep(wait_interval)
        self.assertTrue(False, "进程重启后节点状态未就绪")

    def wait_vm_used_mem_match_expect(
        self,
        vm_ssh: Any,
        operate: str,
        value: int,
        timeout: int = 1800,
        wait_time: int = 30,
    ) -> bool:
        """等待VM已用内存匹配预期值.

        Args:
            vm_ssh: VM SSH节点
            operate: 操作类型（"greater" 或 "less"）
            value: 预期值
            timeout: 超时时间（秒）
            wait_time: 等待间隔（秒）

        Returns:
            匹配成功返回True，超时返回False
        """
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            vm_mem = client.get_memory(vm_ssh).get("used")
            if not vm_mem:
                continue
            elif operate == "greater" and int(vm_mem) > value:
                return True
            elif operate == "less" and int(vm_mem) < value:
                return True
            time.sleep(wait_time)
        return False

    def check_is_borrow_mem(
        self, node: Any, wait_time: int = 3000, interval: int = 10
    ) -> bool:
        """检查是否借用内存.

        Args:
            node: SSH节点对象
            wait_time: 等待时间（秒）
            interval: 检查间隔（秒）

        Returns:
            是否借用内存
        """
        is_borrow_mem = True
        start_time = time.time()
        while (time.time() - start_time) < wait_time:
            borrow_mem = self.get_node_borrowing_numa(node)
            if not borrow_mem:
                is_borrow_mem = False
                break
            time.sleep(interval)
        return is_borrow_mem

    def distribute_huge_page(self, node: Any, number: int, numa: int) -> None:
        """分配大页内存.

        Args:
            node: SSH节点对象
            number: 大页数量
            numa: NUMA节点编号
        """
        node.run(
            {
                "command": [
                    f"echo {number} > /sys/devices/system/node/node{numa}/"
                    f"hugepages/hugepages-2048kB/nr_hugepages"
                ]
            }
        )

    def hot_plug_mem(
        self,
        node: Any,
        vm_name: str,
        mem_size: int,
        guest_numa: int,
        slot: int,
        time_out: int,
    ) -> None:
        """热插拔内存.

        Args:
            node: SSH节点对象
            vm_name: VM名称
            mem_size: 内存大小
            guest_numa: Guest NUMA节点
            slot: Slot编号
            time_out: 超时时间
        """
        res = node.run(
            {
                "command": [
                    f"hot_plug add {vm_name} -size {mem_size} -gnode {guest_numa} -slot {slot}"
                ],
                "timeout": time_out,
            }
        ).get("stdout")
        if not res:
            self.logger.warn(f"No output found from hot_plug command for {vm_name}.")
            return
        expected_msgs = [
            "Memory hot plug finished",
            "Local hot plug completed successfully",
            "Validate success",
            "Device attached successfully",
        ]
        self.assertTrue(
            any(msg in res for msg in expected_msgs),
            f"hot plug failure, out put does not contain any of:{expected_msgs}",
        )

    def get_vm_xml_hot_plug_section(
        self, node: Any, vm_name: str, slot: int, mem_size: int
    ) -> None:
        """获取VM XML热插拔部分.

        Args:
            node: SSH节点对象
            vm_name: VM名称
            slot: Slot编号
            mem_size: 内存大小
        """
        res = None
        retry = 0
        while not res and retry < 3:
            res = node.run(
                {
                    "command": [
                        f"virsh dumpxml {vm_name} | grep \"<address type='dimm' slot='{slot}'\" -B 5 |grep \"<size unit='KiB'>{mem_size}</size>\""
                    ]
                }
            ).get("stdout")
            retry = retry + 1
            time.sleep(5)

        self.assertIsNotNone(res, "vm xml is wrong.")

    def get_vm_xml_hot_plug_section_new(
        self, node: Any, vm_name: str, slot: int, mem_size: int
    ) -> None:
        """获取VM XML热插拔部分（新版本）.

        Args:
            node: SSH节点对象
            vm_name: VM名称
            slot: Slot编号
            mem_size: 内存大小
        """
        res_text = ""
        retry = 0

        cmd_spec = {
            "command": [f"virsh dumpxml {vm_name}"],
            "checkrc": 0,
            "timeout": 60,  # 适当增加超时
        }

        while retry < 5:
            ret = node.run(cmd_spec)
            if not ret:
                self.logger.warn(f"Retry {retry}: node.run returned None")
            else:
                stdout = ret.get("stdout", "")
                if isinstance(stdout, list):
                    stdout = "".join(stdout)

                if f"slot='{slot}'" in stdout and str(mem_size) in stdout:
                    res_text = stdout
                    break
                else:
                    self.logger.warn(f"Retry {retry}: Target slot/size not found in XML")

            retry += 1
            time.sleep(3)

        self.assertIsNotNone(
            res_text if res_text else None,
            f"Failed to fetch XML for {vm_name} after {retry} retries.",
        )

    def hot_plug_delete(self, node: Any, vm_name: str, time_out: int) -> None:
        """删除热插拔VM.

        Args:
            node: SSH节点对象
            vm_name: VM名称
            time_out: 超时时间
        """
        res = node.run(
            {"command": [f"hot_plug delete {vm_name}"], "timeout": time_out}
        ).get("stdout")
        expected_msgs = [
            f"Domain '{vm_name}' destroyed",
            f"VM {vm_name} delete task finished",
        ]
        self.assertTrue(
            any(msg in res for msg in expected_msgs),
            f"hot plug delete failure, out put does not contain any of:{expected_msgs}",
        )

    def _load_nodes(self) -> List[WrapperNode]:
        """加载节点列表.

        Returns:
            包装节点列表
        """
        node_list = []
        self.agent_list = []
        self.master = None
        self.agent = None
        for ssh_node in self.nodes:
            host_name = ssh_node.getHostname()
            wrapper_node = WrapperNode(host_name, ssh_node)
            node_list.append(wrapper_node)
            if host_name == "controller":
                wrapper_node.add_tag("controller")
                self.controller = ssh_node
                continue
            node_role = self.get_scbus_role(ssh_node)
            wrapper_node.add_tag(node_role)
            if node_role == "master":
                self.master = ssh_node
                self.logger.info(f"{wrapper_node.hostname}---------->master")
            else:
                self.agent = ssh_node
                self.agent_list.append(ssh_node)
                self.logger.info(f"{wrapper_node.hostname}---------->agent")
        if self.master is None and self.nodes:
            self.master = self.nodes[0]
            self.logger.warning(f"No master found via scbus role, using first node as master")
        return node_list

    def _get_vm_ssh(self, node: Any, name: str) -> Any:
        """获取VM SSH连接.

        Args:
            node: SSH节点对象
            name: VM名称

        Returns:
            VM SSH节点
        """
        vm_ssh_node = node_manager.get_new_sshconnect(node)
        res = client.enter_vm(vm_ssh_node, name)
        rc = res.get("rc", -1) if isinstance(res, dict) else -1
        self.assertEqual(rc, 0, "登录虚拟机失败")
        return vm_ssh_node