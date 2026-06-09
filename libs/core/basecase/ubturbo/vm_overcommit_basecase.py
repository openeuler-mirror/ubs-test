"""VMOvercommitBaseCase - Base class for VM overcommit test cases.

Migrated from legacy lib/basecase/VMOvercommitBaseCase.py
Inherits from ATBaseCase (already migrated).

CRITICAL: This class NO LONGER has __init__ method.
pytest cannot collect test classes with __init__ (even with default args).

Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
"""

import os
import re
import json
import math
import time
import inspect
import logging
from typing import List, Dict, Any
from pathlib import Path

import pytest

from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
from libs.ubturbo.common import basic, env, connect
from libs.ubturbo.api import numa, virtualization, openstack, smap_tool
from libs.ubturbo.model import Ledger, LedgerEntry
from libs.ubturbo.model.openstack_model import ResourceTopo, NodeResource, VMResource, ResourceItem, Volume

logger = logging.getLogger(__name__)

MAX_REMOTE_NUMA_IDX = 32
QMP_PORT = {'Node0': 51000, 'Node1': 51001, 'Node2': 51002, 'Node3': 51003}


@pytest.fixture(autouse=True)
def inject_vm_overcommit_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入VMOvercommitBaseCase依赖参数.
    
    只对VMOvercommitBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.ubturbo.vm_overcommit_basecase import VMOvercommitBaseCase
    if not isinstance(instance, VMOvercommitBaseCase):
        return
    
    instance.env_type = env.get_env_type(instance.node)
    instance.topo_file = ''
    instance.resource_dict = {}
    instance.node_dict = {}
    instance.numa = []
    instance.local_numa_counts = 2
    instance.local_numa = []
    instance.numa_id2vms: Dict[int, list] = {}
    instance.qmp_port = QMP_PORT.copy()
    instance.ledger = Ledger()
    
    instance.phy_address = None
    instance.agent_list = []
    instance.master = None
    instance.fault_nodes = []
    
    instance.numa_id2topo_path: Dict[int, str] = {}
    
    if VMOvercommitBaseCase in instance.__class__.__mro__[1:]:
        subclass_file_folder = os.path.dirname(inspect.getfile(instance.__class__))
        for fn in os.listdir(subclass_file_folder):
            numa_search = re.findall(r'topo_numa(\d+)\.json', fn)
            if numa_search:
                instance.numa_id2topo_path[int(numa_search[0])] = os.path.join(subclass_file_folder, fn)
    
    logger.info(f"VMOvercommitBaseCase initialized: class={instance.__class__.__name__}")


class VMOvercommitBaseCase(ATBaseCase):
    """Base class for VM overcommit test cases.
    
    继承 ATBaseCase (libs.core.basecase.ubturbo.at_basecase.ATBaseCase)，
    提虚拟机超分测试的基础功能。
    
    环境支持：
    - UB仿真环境 (env.UB_simulation)
    - HCCS物理环境 (env.HCCS)
    
    节点角色：
    - self.master: OpenStack controller节点
    - self.agent_list: OpenStack compute节点列表
    
    使用示例：
        class MyVMTest(VMOvercommitBaseCase):
            def setup_method(self):
                super().setup_method()
                self.prepare_topo("topo_numa0.json")
            
            def test_vm_overcommit(self):
                vms = self.numa_id2vms[0]
                self.add_stress_to_vm(vms[0], 50)
    """
    
    def setup_method(self):
        """Pre-test setup hook (legacy: preTestCase)."""
        self.logStep("setup_method、匹配/连接环境节点")
        self.init_nodes()
        
        self.logStep("setup_method1、停止RackManager（scbus），清理数据后重新启动")
        self.clear_server()
        
        self.logStep("setup_method2、确认OpenStack超分比例")
        self.confirm_scene_config()
        
        self.logStep("setup_method3、根据topo文件创建虚机")
        for numa_id, topo_path in self.numa_id2topo_path.items():
            vms = self.prepare_topo(topo_path)
            self.numa_id2vms[numa_id] = vms
            for vm in vms:
                self.confirm_vm_ready(vm, timeout=30 * 60)
    
    def teardown_method(self):
        """Post-test cleanup hook (legacy: postTestCase)."""
        self.logStep("teardown_method、清理虚机")
        self.clear_server()
    
    def init_nodes(self):
        """初始化节点连接."""
        self.logger.info("匹配环境节点")
        for ssh_node in self.nodes:
            res = ssh_node.run({'command': ['hostname']}).get("stdout").replace("root@#>", "").strip()
            if res == 'controller':
                self.master = ssh_node
                if self.env_type == env.UB_hardware:
                    self.agent_list.append(ssh_node)
            elif 'compute' in res:
                self.agent = ssh_node
                self.agent_list.append(ssh_node)
            if ssh_node.nodeId == env.UB_simulation:
                self.simulation_host = ssh_node

        self.init_numa_info(self.agent_list[0] if self.agent_list else self.nodes[0])

    def init_numa_info(self, node):
        """初始化NUMA信息."""
        self.local_numa_counts = numa.get_numa_count_with_cpu(node)
        self.logInfo(f"=====本地numa数量为: {self.local_numa_counts}=====")
        for i in range(self.local_numa_counts):
            numa_name = f"Node {i}"
            self.local_numa.append(numa_name)
        for i in range(MAX_REMOTE_NUMA_IDX):
            numa_name = f"Node {i}"
            self.numa.append(numa_name)
        if self.env_type == env.HCCS:
            self.local_numa.append("Node 63")
        self.local_numa.append("Total")
    
    def prepare_topo(self, topo_file, do_match=True):
        """根据topo文件准备环境."""
        openstack.ensure_admin_openrc_on_controller(self.master)
        if not topo_file:
            return []
        
        with open(topo_file, encoding='utf-8') as fd:
            data = json.load(fd)
        resource_topo = ResourceTopo.from_dict(data)
        
        if do_match:
            self._match_node(resource_topo.nodes)
        for node in resource_topo.nodes:
            huge_page = node.hugePage
            result = openstack.refresh_hugePage(self.node_dict[node.name].ssh_node, resource_topo.numa, int(huge_page))
            if not result:
                raise RuntimeError("set hugePage fail")
            service_status = openstack.confirm_service_ready(self.master, self.node_dict[node.name].host)
            if not service_status:
                raise RuntimeError("wait service ready timeout")
        for vm in resource_topo.vms:
            self.create_server(vm)
        return resource_topo.vms

    def clear_server(self):
        """清理所有虚机."""
        openstack.ensure_admin_openrc_on_controller(self.master)
        servers = openstack.list_servers(self.master)
        for server in servers:
            openstack.delete_server(self.master, server['ID'])
        if self.env_type == env.UB_simulation:
            time.sleep(30)
    
    def create_server(self, vm: VMResource):
        """创建虚机."""
        volume = self._create_volume(vm.image)
        flavor = self._get_flavor(vm)
        detail = openstack.create_server_with_volume(self.master, vm.name, flavor.name, volume.name,
                                                     host=self.node_dict[vm.node].host)
        retry_times = 0
        while detail['status'] != 'ACTIVE':
            if retry_times < 2 and self.env_type == env.UB_simulation:
                openstack.delete_server(self.master, vm.name)
                time.sleep(20)
                retry_times += 1
                detail = openstack.create_server_with_volume(self.master, vm.name, flavor.name, volume.name,
                                                             host=self.node_dict[vm.node].host)
            else:
                raise RuntimeError("create server fail")
        
        volume.status = 'in-use'
        if detail['OS-EXT-SRV-ATTR:host'] != self.node_dict[vm.node].host:
            openstack.migrate_server(self.master, vm.name, self.node_dict[vm.node].host)
            detail = self.wait_server_target_status(vm.name, {'status': 'ACTIVE'})
        vm.instance = detail['OS-EXT-SRV-ATTR:instance_name']
    
    def confirm_vm_ready(self, vm: VMResource, timeout=1800):
        """确认虚机启动完成."""
        self._auth_fixed = False
        
        def condition():
            log = self.get_console_log(vm)
            if 'login' in log:
                return True
            if "Missing value auth-url required for auth plugin password" in log:
                if not self._auth_fixed:
                    openstack.ensure_admin_openrc_on_controller(self.master)
                    self._auth_fixed = True
            return False
        
        return basic.wait_until(condition, 20, timeout)

    def confirm_ssh_node(self, vm: VMResource):
        ssh_node = self._get_vm_ssh(vm)

        def condition():
            # ---------- 1. 先判断是否“真的能执行命令”（是否已登录） ----------
            check = basic.run(ssh_node, "echo OK", timeout=5)
            check_stdout = (check.stdout or "").strip()

            # 可能出现卡在虚机登录输入账户密码的状态
            if check_stdout != "OK":
                basic.logger.info(f"[SSH未就绪] echo返回异常: {check_stdout}")
                return 0

            # ---------- 2. 再判断是否进入虚机 ----------
            res = basic.run(
                ssh_node,
                "command -v virsh >/dev/null 2>&1 && echo 1 || echo 0",
                timeout=10
            )

            val = (res.stdout or "").strip()

            # 避免 "Login incorrect\n...\n0" 这种误判
            if val == "0":
                return 1

            basic.logger.info(f"[仍在宿主机] virsh检测返回: {val}")
            return 0

        result = basic.wait_until(
            condition,
            check_sep=5,
            timeout=60,
            expect_times=1,
            msg="等待确认已进入虚机（能执行命令 + 检测命令的返回是0）"
        )

        # ---------- 3. 判断是否“真正成功” ----------
        if result >= 1:
            return

        # ---------- 4. 失败后重连virsh console----------
        basic.logger.warn("确认进入虚机失败，重新建立 SSH 连接")
        vm.ssh_node.disConnect()
        vm.ssh_node = None
        self._get_vm_ssh(vm, auth=False)

    def get_console_log(self, vm: VMResource):
        """获取虚机console日志."""
        return basic.run(self.master, f'openstack console log show {vm.name}').stdout
    
    def confirm_scene_config(self):
        """确认超分场景配置."""
        for node in self.agent_list:
            res = basic.run(node, " cat /etc/nova/nova.conf")
            if self.env_type == env.HCCS:
                self.assertIn('1.175', res.stdout, "HCCS overcommit ratio incorrect")
            else:
                self.assertIn('1.25', res.stdout, "UB overcommit ratio incorrect")
    
    def get_node_borrowing_numa(self, node_name, numa_name='all', field_name='MemTotal'):
        """获取借用内存NUMA信息."""
        numa_infos = openstack.get_numaInfo(self.node_dict[node_name].ssh_node)
        borrowing_mem = 0.0
        
        if numa_name == 'all':
            for numa_info in numa_infos:
                if numa_info['name'] not in self.local_numa:
                    borrowing_mem += float(numa_info.get(field_name, 0))
        else:
            for numa_info in numa_infos:
                if numa_info['name'] == numa_name:
                    borrowing_mem += float(numa_info.get(field_name, 0))
                    break
        
        return round(borrowing_mem, 2)
    
    def get_node_borrowing_mem_used(self, node_name):
        """获取已借用内存使用量."""
        numa_infos = openstack.get_numaInfo(self.node_dict[node_name].ssh_node)
        used_mem = 0.0
        for current_numa in numa_infos:
            if current_numa['name'] not in self.local_numa:
                used_mem = used_mem + (float(current_numa['MemTotal']) - float(current_numa['HugePages_Free']))
        return round(used_mem, 2)
    
    def get_node_borrowing_mem_free(self, node_name, numa_idx=None):
        """获取已借用内存空闲量."""
        numa_infos = openstack.get_numaInfo(self.node_dict[node_name].ssh_node)
        used_mem = 0.0
        
        for numa_info in numa_infos:
            if numa_idx is None:
                if numa_info['name'] not in self.local_numa:
                    used_mem = used_mem + float(numa_info['HugePages_Free'])
            else:
                if numa_idx == numa_info['name']:
                    used_mem = used_mem + float(numa_info['HugePages_Free'])
        return round(used_mem, 2)
    
    def wait_borrow_status(self, node_name, numa_idx=None, target_mem=0, timeout=600):
        """等待借用状态."""
        if numa_idx is None:
            numa_idx_str = 'all'
        else:
            numa_idx_str = self.numa[numa_idx]
        
        def condition():
            cur_mem = int(self.get_node_borrowing_numa(node_name, numa_idx_str))
            self.logger.debug(f"=============等待借用内存大小：{target_mem}=============")
            self.logger.debug(f"=============当前借用内存大小：{cur_mem}=============")
            if cur_mem == target_mem:
                return True
            return False
        
        res = basic.wait_until(condition, 20, timeout)
        self.assertEqual(res, 1, '内存借用/归还失败')
    
    def get_node_numa_percent(self, node_name):
        """获取节点NUMA使用百分比."""
        numa_infos = openstack.get_numaInfo(self.node_dict[node_name].ssh_node)
        match = next((numa for numa in numa_infos if numa['name'] == 'Node 0'), None)
        total = int(match['HugePages_Total'])
        free = int(match['HugePages_Free'])
        if total != 0:
            return round((total - free) / total * 100, 2)
        else:
            return 0
    
    def log_node_mem_info(self):
        """打印节点NUMA内存信息."""
        numastat_info = {}
        for node in self.node_dict:
            if node in self.fault_nodes:
                continue
            numa_info = self.get_node_numa_percent(node)
            borrowing_numa = self.get_node_borrowing_numa(node)
            numastat_info[node] = [numa_info, borrowing_numa]
        self.logInfo("================print env node numa status by numastat ==================")
        for key, value in numastat_info.items():
            self.logInfo(f"[numastat] {key} numa memory persent is {value[0]}")
            self.logInfo(f"[numastat] {key} borrow memory is {value[1]}")
        self.logInfo("================print env node numa status end==================")

    def wait_server_target_status(self, vm, expect_dict, timeout=600):
        """等待虚机达到目标状态."""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            found = True
            detail = openstack.get_server_detail(self.master, vm)
            for key, value in expect_dict.items():
                if detail[key] != value:
                    found = False
                    break
            if found:
                return detail
            time.sleep(10)

    def set_huge_page(self, node_name, numa_idx, pages, restart_service=False):
        """
        设置大页数 并决定是否重启服务
        :param node_name: 节点名称
        :param numa_idx: numa
        :param pages: 大页数量
        :param restart_service: 是否重启服务
        :return:
        """
        openstack.refresh_hugePage(self.node_dict[node_name].ssh_node, numa_idx, pages, restart_service)

    def add_stress_to_target(self, vm, host_target):
        """
        :param vm: 虚拟机
        :param host_target: 通过给当前虚拟机加压，实现host侧大页内存占用值，单位：MB
        :return:
        """
        self.confirm_ssh_node(vm)
        vm_node = self.node_dict[vm.node].ssh_node  # 获取虚机所在节点的ssh连接
        mem_info = numa.get_numa_huge_mem(vm_node, vm.numa)
        stress_mb = int(host_target - mem_info['total'] + mem_info['free'])
        return self.add_stress_value_to_vm(vm, stress_mb)

    def add_stress_value_to_vm(self, vm, stress_mb):
        """直接使用具体值(MB)施加内存压力"""
        self.confirm_ssh_node(vm)
        vm_ssh_node = self._get_vm_ssh(vm)
        return self._apply_memory_stress(vm_ssh_node, stress_mb)

    def clean_vm_stress(self, vm):
        """
        撤掉虚机内部所有内存压力
        :param vm:
        :return:
        """
        self.confirm_ssh_node(vm)
        vm_ssh_node = self._get_vm_ssh(vm)
        openstack.kill_stress_memtester(vm_ssh_node)

    def update_ledger(self):
        """查询环境账本，更新维护的ledger，并返回变动的账目信息"""
        self.logger.info(f'当前故障节点为: {self.fault_nodes}')
        working_nodes = []
        for node_name in self.node_dict:
            if node_name in self.fault_nodes:
                continue
            working_nodes.append(self.node_dict[node_name].ssh_node)
        return Ledger.update_ledger(working_nodes, self.ledger)

    def concatenate_entry_src_node(self, entry: LedgerEntry):
        src_node_id = str(entry.src_node)
        if 'Node' in src_node_id:
            return src_node_id
        return f'Node{int(src_node_id) - 1}'

    def confirm_mig_out_complete(self, node_name, dest_numa=None, expect_free=400, timeout=300):
        """
        迁出完成检查（增强版）
        - 自动更新账本
        - 自动解析远端内存numa
        - 自动打印节点内存信息
        - 完成原迁出稳定 + hugepage_free 检查

        :param node_name: 节点名
        :param dest_numa: 可选；若未传入则自动从账本获取
        :param expect_free: hugepage 预期空闲最小值
        :param timeout: 最大等待时间
        """
        # 更新账本
        diff_entry_tuple = self.update_ledger()

        # 获取远端内存numa
        if dest_numa is None:
            borrow_list = diff_entry_tuple.borrow_list
            if not borrow_list:
                raise ValueError(
                    f"update_ledger().borrow_list 为空，无法自动确定 {node_name} 的 dest_numa"
                )
            dest_numa = borrow_list[0].src_remote_numa
            self.logger.info(f"节点{node_name}要检测迁移是否完成的numa是：{dest_numa}=============")

        # 等待迁出过程稳定
        vm_node = self.node_dict[node_name].ssh_node
        res = smap_tool.wait_mig_out_complete(vm_node, dest_numa, 15, timeout=timeout)
        self.assertEqual(res, 1, f'节点 {node_name} 迁移超时')

        # hugepage free 校验
        self.log_node_mem_info()
        self.logger.info(f"节点{node_name}要检测迁移是否完成的numa是：{dest_numa}=============")
        hugepage_free_state = self.confirm_mig_hugepage_free(node_name, dest_numa, expect_free)
        self.assertTrue(hugepage_free_state, '迁移稳定后 hugepage free 仍不符合预期')

    def confirm_mig_hugepage_free(self, node_name, dest_numa, expect_free, timeout=600):
        """
        等待借用的内存迁出已稳定
        :param node_name: 节点名
        :param dest_numa: 可选；若未传入则自动从账本获取
        :param expect_free: hugepage free 预期空闲最小值
        :param timeout: 最大等待时间
        """
        def condition():
            numa_free = self.get_node_borrowing_mem_free(node_name, f"Node {dest_numa}")
            return expect_free > numa_free > 1.00

        try:
            result = basic.wait_until(condition, 20, timeout)
            return bool(result)
        except Exception as e:
            self.logger.warn(f"wait hugepage free failed: node={node_name}, numa={dest_numa}, err={e}")
            return False

    def _match_node(self, plan_nodes: List[NodeResource]):
        """匹配节点SSH连接."""
        self.logger.info("===将节点的ssh连接与topo文件做匹配===")
        matched_list = []
        for plan_node in plan_nodes:
            role = plan_node.role
            for ssh_node in self.nodes:
                if ssh_node in matched_list:
                    continue
                res = ssh_node.run({'command': ['hostname']}).get("stdout").replace("root@#>", "").strip()
                if (res != 'controller') and ('compute' not in res):  # openstack集群回显只有controller,computeX
                    continue
                if 'compute' not in res and self.env_type == env.UB_simulation:  # UB仿真环境只有computeX能建虚机
                    continue

                plan_node.ssh_node = ssh_node
                plan_node.host = res
                self.node_dict[plan_node.name] = plan_node
                matched_list.append(ssh_node)
                break

    def _create_volume(self, image):
        """创建卷."""
        if not self.resource_dict.get('volume'):
            self._load_volumes()
        volumes = self.resource_dict.get('volume')
        match = next((volume for volume in volumes if volume.image == image and volume.status == 'available'), None)
        if match:
            return match

        name = "volume_" + basic.generate_random_string(5)
        size = 10 if self.env_type == env.UB_simulation else 50
        ret = openstack.create_volume_with_image(self.master, name, image, size)
        volume = Volume('volume', ret['id'], name, None, None)
        volume.image = image
        while True:
            detail = openstack.show_volume(self.master, name)
            if detail['status'] not in ['creating', 'downloading']:
                break
            time.sleep(10)
        if detail['status'] != 'available':
            return None
        volume.status = 'available'
        volumes.append(volume)
        return volume

    def _load_volumes(self):
        """加载可用卷列表."""
        items = openstack.get_volume_available_list(self.master)
        volumes = [
            Volume('volume', item['ID'], item['Name'], item['Properties'], item['Status'])
            for item in items
        ]

        for volume in volumes:
            detail = openstack.show_volume(self.master, volume.id)
            if not detail:
                continue
            volume.image = detail['volume_image_metadata']['image_name']
        self.resource_dict['volume'] = volumes
        return volumes

    def _get_flavor(self, vm: VMResource):
        """获取flavor."""
        if not self.resource_dict.get('flavor'):
            self._load_flavor()
        flavor_list = self.resource_dict['flavor']

        need_flavor = "os_flavor_" + str(vm.ram) + "_" + str(vm.cpu)
        if vm.ub_instance:
            need_flavor = need_flavor + "_ub"
        if not vm.removable:
            need_flavor = need_flavor + "_" + vm.node
        match = next((flavor for flavor in flavor_list if flavor.name == need_flavor), None)
        if not match:
            self._create_flavor(need_flavor, vm.ram, None if vm.removable else vm.node, vm.cpu, vm.ub_instance)
            match = ResourceItem('flavor', None, need_flavor, None)
            flavor_list.append(match)
        return match

    def _load_flavor(self):
        """加载flavor列表."""
        flavors = openstack.list_flavors(self.master)
        flavor_list = [
            ResourceItem('flavor', flavor['ID'], flavor['Name'], flavor['Properties'])
            for flavor in flavors
        ]
        self.resource_dict['flavor'] = flavor_list

    def _create_flavor(self, name, ram, bound_node, cpu, ub_instance):
        """创建flavor."""
        disk_size = 10 if self.env_type == env.UB_simulation else 50
        openstack.create_flavor(self.master, name, ram, disk_size, cpu)
        if bound_node:
            aggregate = self._get_aggregate(bound_node)
            properties = {"hw:mem_page_size": "2048", "custom": aggregate.name, "hw:cpu_policy": "dedicated",
                          "hw:numa_nodes": "1"}
        else:
            properties = {"hw:mem_page_size": "2048", "hw:cpu_policy": "dedicated", "hw:numa_nodes": "1"}
        if ub_instance:
            properties["hw:ub_instance"] = "true"
        openstack.add_metadata_to_flavor(self.master, name, properties)

    def _get_aggregate(self, node_name):
        """获取aggregate."""
        aggregate_name = 'OS_' + node_name + '_only'
        if not self.resource_dict.get('aggregate'):
            aggregates = openstack.list_aggregate(self.master)
            aggregate_list = [
                ResourceItem('aggregate', flavor['ID'], flavor['Name'], flavor['Properties'])
                for flavor in aggregates
            ]
            self.resource_dict['aggregate'] = aggregate_list

        aggregate_list = self.resource_dict['aggregate']
        match = next((aggregate for aggregate in aggregate_list if aggregate.name == aggregate_name), None)
        if not match:
            openstack.create_aggregate(self.master, aggregate_name, {'custom': aggregate_name},
                                       [self.node_dict[node_name].host])
            resource = ResourceItem('aggregate', None, aggregate_name, None)
            aggregate_list.append(resource)
            match = resource
        return match

    def _get_vm_ssh(self, vm: VMResource, auth=True):
        vm_ssh_node = vm.ssh_node
        if not vm_ssh_node:
            ssh_node = self.node_dict[vm.node].ssh_node
            vm_ssh_node = ssh_node.copy()
            vm.ssh_node = vm_ssh_node
            res = openstack.enter_vm(vm_ssh_node, vm.instance, auth=auth)
            # if res['rc'] != 0:
            if res['returnCode'] != 0:
                vmlog = self.get_console_log(vm)
                self.logError("vm log is {}".format(vmlog))
            # self.assertEqual(res['rc'], 0, "登录虚拟机失败")
            self.assertEqual(res['returnCode'], 0, "登录虚拟机失败")
        return vm_ssh_node

    def _apply_memory_stress(self, vm_ssh_node, stress_mb):
        """内部方法：应用指定内存压力"""
        memory_init = openstack.get_memory(vm_ssh_node)
        openstack.vm_stree_memtester(vm_ssh_node, f"{stress_mb}M")
        openstack.wait_stress_complete(vm_ssh_node, memory_init, stress_mb)
        return f"memtester {stress_mb}M"
