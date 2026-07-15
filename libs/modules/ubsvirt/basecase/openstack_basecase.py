"""OpenStackBaseCase - Base class for OpenStack/Virtualization test cases.

Migrated from: legency/testcase/ubsvirt/lib/basecase/virtualization/openstack/BaseCase.py
"""

import json
import logging
import re
import threading
import time
import ast
from typing import Any, Dict, List, Optional

import pytest

from libs.modules.ubsvirt.basecase.ubsvirt_basecase import UBSVirtBaseCase
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.common import string_util, node_manager
from libs.modules.ubsvirt.model.model import ResourceTopo, NodeResource, VMResource, ResourceItem, Volume, WrapperNode
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)
lock = threading.Lock()


@pytest.fixture(autouse=True)
def inject_openstack_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any],
) -> None:
    """Inject OpenStackBaseCase dependencies via fixture.

    Only injects for OpenStackBaseCase and its subclasses.
    """
    if not hasattr(request, 'instance'):
        return

    instance = request.instance

    from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
    if not isinstance(instance, OpenStackBaseCase):
        return

    # Inject base dependencies
    instance.nodes = nodes if nodes else []
    instance.resource = resource
    instance.customParam = custom_params or {}

    # Initialize OpenStack-specific attributes
    instance.is_Simulation = resource.get('global', {}).get('is_simulation', False)
    instance.controller = None
    instance.agent_list = []
    instance.master = None
    instance.agent = None
    instance.node_list = instance._load_nodes() if nodes else []
    instance.numa_num = instance.get_numa_num(instance.master) if instance.master else 0
    instance.obmm_default_num = 1024 // instance.numa_num if instance.numa_num != 0 else 512
    instance.default_page_num = instance.obmm_default_num // 2
    instance.ubse_node_list = [instance.master] + instance.agent_list
    instance.node_dict = {}
    instance.resource_dict = {}
    instance.volume_use_list = []

    # Initialize logger
    instance.logger = Log.getLogger(instance.__class__.__name__)

    logger.info(f"OpenStackBaseCase initialized: {len(nodes)} nodes")


class OpenStackBaseCase(UBSVirtBaseCase):
    """Base class for OpenStack/Virtualization test cases.

    Provides methods for:
    - VM creation and management
    - Memory stress testing
    - NUMA info retrieval
    - Decision validation

    Pytest adaptation: Uses fixture injection instead of __init__.
    """

    def _load_nodes(self) -> List[WrapperNode]:
        """Load nodes from self.nodes and categorize them."""
        node_list = []
        self.agent_list = []

        for ssh_node in self.nodes:
            host_name = ssh_node.getHostname()
            wrapper_node = WrapperNode(host_name, ssh_node)
            node_list.append(wrapper_node)

            if host_name == 'controller':
                wrapper_node.add_tag('controller')
                self.controller = ssh_node
                if self.is_Simulation:
                    continue

            wrapper_node.add_tag('compute')
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

    def get_scbus_role(self, ssh_node: Any) -> str:
        """Get scbus role (master/agent) for a node."""
        rack_role = ssh_node.run({'command': [
            'sudo -u ubse /usr/bin/ubsectl display cluster | grep master | awk -F \'[()]\' \'{print $2}\''
        ]}).get("stdout", "").replace("root@#>", "").strip()

        slot_ids = ssh_node.run({'command': [
            "ubsectl display cluster | grep ` cat /etc/hostname | grep -v '#'` | awk 'BEGIN{ FS=\"(\" ; RS=\")\" } NF>1 { print $NF }'"
        ]}).get("stdout", "")

        if not slot_ids:
            return "agent"

        node_role = slot_ids[0] if slot_ids else ""
        return "master" if node_role == rack_role else "agent"

    def get_numa_num(self, node: Any) -> int:
        """Get NUMA node count."""
        res = node.run({'command': ["lscpu | grep 'NUMA node(s)' | awk '{print $NF}'"]}).get("stdout")
        if res:
            return int(res.replace("root@#>", "").strip())
        return 0

    def get_service_status(self, node: Any, service_name: str) -> Optional[str]:
        """Get service status on a node."""
        return client.get_service_status(node, service_name)

    def get_mem_fragment_algorithm_decision(self, node: Any) -> Optional[Dict[str, Any]]:
        """Get memory fragment algorithm decision from controller log."""
        res = node.run(
            {'command': [f'grep -a "Algorithm_result" /var/log/ubs_scheduler/ubs-scheduler-controller.log | tail -n 1'], 'waitstr': '#'})
        if res.get('stdout') is None:
            self.logError("Get mem fragment algorithm decision failed")
            return None

        algorithm_decision_str = res.get("stdout").replace("root@#>", "").split('\n')[0]
        start_index = algorithm_decision_str.find("Algorithm_result: ") + len("Algorithm_result: ")
        algorithm_decision_dict_str = algorithm_decision_str[start_index:].strip()[:-1]
        if algorithm_decision_dict_str:
            algorithm_decision_dict = eval(algorithm_decision_dict_str)
            return algorithm_decision_dict
        else:
            return None

    def get_ms_controller_pid(self, node: Any) -> str:
        """Get ubs-scheduler-controller process PID."""
        res = node.run({'command': ["ps -ef | grep 'ubs_scheduler_controller.py' | grep -v grep | awk '{print $2}'"]}).get('stdout')
        res = res.replace("root@#>", "").replace("\r", "").replace("\n", "")
        return res

    def get_ms_agent_pid(self, node: Any) -> str:
        """Get ubs-scheduler-agent process PID."""
        res = node.run({'command': ["ps -ef | grep 'ubs_scheduler_agent.py' | grep -v grep | awk '{print $2}'"]}).get('stdout')
        res = res.replace("root@#>", "").replace("\r", "").replace("\n", "")
        return res

    def check_vm_migrate_to_dest_node(self, node: Any, vm_name: str, dest_node: str, reserved_time: int) -> bool:
        """Check if VM has migrated to destination node."""
        wait_time = 0
        flag = False
        src_node = client.get_server_detail(node, vm_name)['OS-EXT-SRV-ATTR:host']
        while wait_time < reserved_time:
            server_detail = client.get_server_detail(node, vm_name)
            if server_detail['OS-EXT-SRV-ATTR:host'] == dest_node:
                flag = True
                break
            elif server_detail['OS-EXT-SRV-ATTR:host'] != src_node:
                self.logError("VM migrate to unexpected dest_node")
                break
            elif server_detail['OS-EXT-STS:vm_state'] == 'error':
                self.logError("VM state is error")
                break
            elif server_detail['OS-EXT-STS:vm_state'] == 'stopped':
                self.logError("VM state is stopped")
                break
            else:
                wait_time = wait_time + 30
                time.sleep(30)
        return flag

    def check_borrowed_numa_size(self, node, reserved_time, size):
        flag = False
        wait_time = 0
        while wait_time < reserved_time:
            numa_borrowed_size = self.get_node_borrowing_numa(node)
            self.logInfo(f"借用了{numa_borrowed_size}M")
            if numa_borrowed_size >= float(size):
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)
        return flag

    def check_return_mem(self, node, reserved_time):
        """
        功能：检测借用的内存是否归还
        参数：
        nodes: 执行节点
        """
        flag = False
        wait_time = 0
        while wait_time < reserved_time:
            numa_borrowed_size = self.get_node_borrowing_numa(node)
            self.logInfo(f"借用了{numa_borrowed_size}M")
            if numa_borrowed_size == 0:
                self.logInfo("借用的内存成功归还")
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)
        return flag

    def wait_mem_match_expect(self, node, operate, value, timeout=300):
        start_time = time.time()
        percent = 0
        while (time.time() - start_time) < timeout:
            percent = self.get_node_numa_percent(node)
            if operate == 'greater' and percent > value:
                break

            if operate == 'less' and percent < value:
                break
            time.sleep(10)
        return percent

    def restart_service(self, node, service):
        service_commands = {
            "nova-compute": "systemctl restart openstack-nova-compute",
            "nova-scheduler": "systemctl restart openstack-nova-scheduler",
            "ubse": "systemctl restart ubse"
        }

        if service in service_commands:
            command = service_commands[service]
            node.run({'command': [command]})
        else:
            self.logInfo(f"服务输入错误: {service}")

    def waitServiceStatus(self, node, service_name, timeout, expect_status="running"):
        wait_time = 0
        flag = False
        while wait_time < timeout:
            res = node.getServiceStatus(service_name)
            if res == expect_status:
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)
        self.assertEqual(flag, True, f"{service_name} is not {expect_status}")

    def ensure_admin_openrc_on_controller(self):
        openrc_content_lines = [
            "export OS_USERNAME=admin",
            "export OS_PASSWORD=123456",
            "export OS_PROJECT_NAME=admin",
            "export OS_USER_DOMAIN_NAME=Default",
            "export OS_PROJECT_DOMAIN_NAME=Default",
            "export OS_AUTH_URL=http://controller:5000/v3",
            "export OS_IDENTITY_API_VERSION=3",
            "export OS_IMAGE_API_VERSION=2"
        ]

        openrc_path = "/root/.admin-openrc"
        create_file_cmd = f"touch {openrc_path}"
        self.controller.run({'command': [create_file_cmd], 'is_roc_node': True})
        for line in openrc_content_lines:
            check_cmd = f"grep -qxF '{line}' {openrc_path}"
            result = self.controller.run({'command': [check_cmd], 'is_roc_node': True})
            if result.get('exit_code') != 0:
                append_cmd = f"echo \"{line}\" >> {openrc_path}"
                self.controller.run({'command': [append_cmd], 'is_roc_node': True})
        source_cmd = f"source {openrc_path}"
        self.controller.run({'command': [source_cmd], 'is_roc_node': True})
        profile_cmd = "grep -q 'source ~/.admin-openrc' /etc/profile || echo 'source ~/.admin-openrc' >> /etc/profile"
        self.controller.run({'command': [profile_cmd], 'is_roc_node': True})

    def prepare_topo(self, topo_file: str) -> List[VMResource]:
        self.ensure_admin_openrc_on_controller()
        """Prepare test topology from JSON file."""
        if not topo_file:
            return []

        with open(topo_file, encoding='utf-8') as fd:
            data = json.load(fd)
        resource_topo = ResourceTopo.from_dict(data)

        self._match_node(resource_topo.nodes)
        self.clear_server()
        self.reset_hugepage(self.node_list, self.node_dict)

        for node in resource_topo.nodes:
            huge_page = node.hugePage
            if isinstance(huge_page, int):
                numa_info_dict = {int(node.numa): int(huge_page)}
            else:
                numa_info_dict = {int(numa): int(pages) for numa, pages in huge_page.items()}

            if node.name in self.node_dict:
                result = client.refresh_hugePage(self.node_dict[node.name].ssh_node, numa_info_dict, numa_total=self.numa_num)
                if not result:
                    raise RuntimeError("set hugePage fail")
        res = self.check_nova_compute_status(self.node_list)
        self.assertTrue(res, "等待nova-compute服务重启状态没全部拉起")

        self.volume_use_list = []
        for vm in resource_topo.vms:
            self.create_server(vm)

        return resource_topo.vms

    def _match_node(self, plan_nodes: List[NodeResource]) -> None:
        """Match plan nodes to actual nodes."""
        matched_list = []
        for plan_node in plan_nodes:
            role = plan_node.role
            for node in self.node_list:
                if node in matched_list:
                    continue
                if 'compute' not in node.tags or role not in node.tags:
                    continue
                self.node_dict[plan_node.name] = plan_node
                plan_node.host = node.hostname
                plan_node.ssh_node = node.ssh_connect
                matched_list.append(node)
                self.logger.info(f"{plan_node.name}---------->{node.hostname}")
                break

    def clear_server(self) -> None:
        """Clear all servers."""
        if not self.controller:
            return
        servers = client.list_servers(self.controller)
        if not servers:
            return
        for server in servers:
            client.delete_server(self.controller, server['ID'])

    def add_stress_to_vm(self, vm: VMResource, percent: int) -> None:
        """Add memory stress to VM."""
        vm_ssh_node = self._get_vm_ssh(vm)
        memory_dict = client.get_memory(vm_ssh_node)
        add_stress = int(vm.ram) * percent / 100 - (int(vm.ram) - int(memory_dict['total'])) - int(memory_dict['used'])
        client.vm_stree(vm_ssh_node, str(add_stress) + "M")

    def clean_vm_stress(self, vm: VMResource, first_enter: bool = True) -> None:
        """Clean VM stress."""
        vm_ssh_node = self._get_vm_ssh(vm, first_enter)
        client.kill_stress(vm_ssh_node)

    def check_nova_compute_status(self, node):
        """
            功能：控制节点查看计算节点的nova-compute状态是否正常，因仿真环境下，计算节点重启后控制节点会较慢感知到计算节点状态
            参数：
                node: 节点列表（self.node_list）
                包括控制节点和计算节点
            返回值：true or false
        """
        node_num = len(node) - 1 if self.is_Simulation else len(node)
        self.logger.info(f"check_nova_compute_status: is_Simulation={self.is_Simulation}, node_num={node_num}, total_nodes={len(node)}")
        for _ in range(60):
            command = "openstack compute service list | grep nova-compute | awk '$12 == \"up\"' | wc -l"
            res = self.controller.run({'command': [command]}).get("stdout")
            self.logger.info(f"nova-compute status check: res={res}")
            if not res:
                continue
            elif int(res.split("\r\n")[0]) == node_num:
                return True
            time.sleep(10)
        return False

    def _get_vm_ssh(self, vm: VMResource, first_enter: bool = True) -> Any:
        """Get SSH connection to VM."""
        server_detail = client.get_server_detail(self.controller, vm.name)
        host_name = server_detail['OS-EXT-SRV-ATTR:host']

        if host_name != self.node_dict[vm.node].host:
            for node_name, node_info in self.node_dict.items():
                if node_info.host == host_name:
                    vm.node = node_name
            vm.ssh_node = None

        vm_ssh_node = vm.ssh_node
        if not vm_ssh_node:
            ssh_node = self.node_dict[vm.node].ssh_node
            vm_ssh_node = node_manager.get_new_sshconnect(ssh_node)
            vm.ssh_node = vm_ssh_node
            res = client.enter_vm(vm_ssh_node, vm.instance, not vm.ub_instance, first_enter)
            self.assertEqual(res["rc"], 0, "登录虚拟机失败")

        return vm_ssh_node

    def get_decision(self, timestamp: int, timeout: int = 900, **kwargs) -> Optional[str]:
        """Get escape decision."""
        start_time = time.time()
        exec_node = kwargs.get('ubs_scheduler_decision', False) and self.controller or self.master

        while (time.time() - start_time) < timeout:
            decision = client.get_decision(exec_node, timestamp, **kwargs)
            if decision is not None:
                return decision
            time.sleep(10)
        return None

    def get_node_numa_percent(self, node_name: str) -> float:
        """Get NUMA memory usage percent."""
        numa_infos = client.get_numaInfo(self.node_dict[node_name].ssh_node)
        match = next((numa for numa in numa_infos if numa['name'] == 'Node 0'), None)
        if match:
            total = int(match['HugePages_Total'])
            free = int(match['HugePages_Free'])
            if total != 0:
                return round((total - free) / total * 100, 2)
        return 0

    def get_node_borrowing_numa(self, node_name: str) -> float:
        """Get borrowing NUMA memory."""
        numa_infos = client.get_numaInfo(self.node_dict[node_name].ssh_node)
        borrowing_mem = 0.0
        for numa in numa_infos:
            match = re.search(r"Node\s+(\d+)", numa['name'])
            if match:
                number = int(match.group(1))
                if number >= self.numa_num and number <= 17:
                    borrowing_mem += float(numa['MemTotal'])
        return round(borrowing_mem, 2)

    def get_node_numa_used(self, node_name, numa_name):
        """Get used NUMA memory for a specific node and numa."""
        numa_infos = client.get_numaInfo(self.node_dict[node_name].ssh_node)
        res = 0.0
        for numa in numa_infos:
            if numa['name'] == numa_name:
                res = res + float(numa['HugePages_Total']) - float(numa['HugePages_Free'])
        return round(res, 2)

    def wait_server_target_status(self, vm, expect_dict, timeout=600, sleep_time=10):
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            found = True
            detail = client.get_server_detail(self.controller, vm)
            for key, value in expect_dict.items():
                if detail[key] != value:
                    found = False
                    break
            if found:
                return detail
            time.sleep(sleep_time)

    def create_server(self, vm: VMResource, expect_status='ACTIVE'):
        lock.acquire()
        volume = self._create_volume(vm.image)
        lock.release()
        flavor = self._get_flavor(vm)
        if vm.enable_remote_memory == '' and vm.enable_remote_create == '':
            client.create_server_with_volume(self.controller, vm.name, flavor.name, volume.name,
                                             host=self.node_dict[vm.node].host)
        else:
            client.create_server_with_volume(self.controller, vm.name, flavor.name, volume.name)

        while True:
            detail = client.get_server_detail(self.controller, vm.name)
            if detail['status'] not in ['creating', 'BUILD']:
                break
            time.sleep(20)
        if expect_status == 'ACTIVE':
            if detail['status'] != 'ACTIVE':
                raise RuntimeError("create server fail")
        else:
            if detail['status'] == expect_status:
                return detail['status']

        volume.status = 'in-use'
        if detail['OS-EXT-SRV-ATTR:host'] != self.node_dict[vm.node].host:
            client.migrate_server(self.controller, vm.name, self.node_dict[vm.node].host)
            detail = self.wait_server_target_status(vm.name, {'status': 'ACTIVE'})
        vm.instance = detail['OS-EXT-SRV-ATTR:instance_name']
        vm.ip = detail['addresses']['vm_net'][0]

    def _create_volume(self, image):
        if not self.resource_dict.get('volume'):
            self._load_volumes()
        volumes = self.resource_dict.get('volume')
        match = next((volume for volume in volumes if
                      volume.image == image and volume.status == 'available' and volume not in self.volume_use_list),
                     None)
        if match:
            self.volume_use_list.append(match)
            return match

        name = "volume_" + string_util.generate_random_string(5)
        ret = client.create_volume_with_image(self.controller, name, image)
        volume = Volume('volume', ret['id'], name, None, None)
        volume.image = image
        while True:
            detail = client.show_volume(self.controller, name)
            if detail['status'] not in ['creating', 'downloading']:
                break
            time.sleep(10)
        if detail['status'] != 'available':
            return None
        volume.status = 'available'
        volumes.append(volume)
        self.volume_use_list.append(volume)
        return volume

    def _load_volumes(self):
        items = client.get_volume_available_list(self.controller)
        volumes = [Volume('volume', item['ID'], item['Name'], item['Properties'], item['Status']) for item
                   in items]

        for volume in volumes:
            detail = client.show_volume(self.controller, volume.id)
            if not detail:
                continue
            volume.image = detail['volume_image_metadata']['image_name']
        self.resource_dict['volume'] = volumes

    def _get_flavor(self, vm: VMResource):
        if not self.resource_dict.get('flavor'):
            self._load_flavor()
        flavor_list = self.resource_dict['flavor']
        ext_properties = {}

        need_flavor = "flavor_" + str(vm.ram) + "_" + str(vm.cpu)
        if vm.ub_instance:
            need_flavor = need_flavor + "_ub"
        if not vm.removable:
            need_flavor = need_flavor + "_" + vm.node
        if vm.enable_remote_create != '':
            need_flavor = need_flavor + "_remote_create"
            ext_properties["ubs:enable_remote_create"] = vm.enable_remote_create
            need_flavor = need_flavor + "_" + str(vm.remote_create_memory_ratio)
            ext_properties["ubs:remote_create_memory_ratio"] = vm.remote_create_memory_ratio
        if vm.enable_remote_memory != '':
            need_flavor = need_flavor + "_remote_memory"
            ext_properties["ubs:enable_remote_memory"] = vm.enable_remote_memory
            need_flavor = need_flavor + "_" + str(vm.max_remote_memory_ratio)
            ext_properties["ubs:max_remote_memory_ratio"] = vm.max_remote_memory_ratio
        if vm.dpu:
            need_flavor = need_flavor + "_dpu"
            ext_properties["hw:dpu"] = vm.dpu
        if not vm.core_binding:
            need_flavor = need_flavor + "_notcorebinding"
        match = next((flavor for flavor in flavor_list if flavor.name == need_flavor), None)
        if not match:
            self._create_flavor(need_flavor, vm.ram, None if vm.removable else vm.node, vm.cpu, vm.ub_instance,
                                ext_properties, vm.core_binding)
            match = ResourceItem('flavor', None, need_flavor, None)
            flavor_list.append(match)
        elif not vm.removable:
            self._update_aggregate(vm.node + '_only', vm.node)
        return match

    def _load_flavor(self):
        flavors = client.list_flavors(self.controller)
        flavor_list = [ResourceItem('flavor', flavor['ID'], flavor['Name'], flavor['Properties']) for flavor in
                       flavors]
        self.resource_dict['flavor'] = flavor_list

    def _create_flavor(self, name, ram, bound_node, cpu, ub_instance, ext_properties: dict = None, core_binding=True):
        client.create_flavor(self.controller, name, ram, 50, cpu)
        if bound_node:
            aggregate = self._get_aggregate(bound_node)
            properties = {"hw:mem_page_size": "2048", "custom": aggregate.name, "hw:numa_node": "1"}
        else:
            properties = {"hw:mem_page_size": "2048", "hw:numa_node": "1"}
        if core_binding:
            properties["hw:cpu_policy"] = "dedicated"
        if ub_instance:
            properties["hw:ub_instance"] = "true"
        if ext_properties:
            del properties["hw:numa_node"]
            properties.update(ext_properties)
        client.add_metadata_to_flavor(self.controller, name, properties)

    def _get_aggregate(self, node_name):
        if not self.resource_dict.get('aggregate'):
            aggregates = client.list_aggregate(self.controller)
            aggregate_list = [ResourceItem('aggregate', flavor['ID'], flavor['Name'], flavor['Properties']) for flavor
                              in aggregates]
            self.resource_dict['aggregate'] = aggregate_list

        aggregate_list = self.resource_dict['aggregate']
        match = next((aggregate for aggregate in aggregate_list if aggregate.name == node_name + '_only'), None)
        if not match:
            client.create_aggregate(self.controller, node_name + '_only', {'custom': node_name + '_only'},
                                    [self.node_dict[node_name].host])
            resource = ResourceItem('aggregate', None, node_name + '_only', None)
            aggregate_list.append(resource)
            match = resource
        else:
            match_hosts = client.show_aggregate(self.controller, match.name)['hosts']
            if match_hosts[0] != self.node_dict[node_name].host:
                client.remove_aggregate_host(self.controller, match.name, match_hosts)
                client.add_aggregate_host(self.controller, match.name, [self.node_dict[node_name].host])
        return match

    def _update_aggregate(self, aggregate_name, node_name):
        match_hosts = client.show_aggregate(self.controller, aggregate_name)['hosts']
        if not match_hosts:
            return
        if match_hosts[0] != self.node_dict[node_name].host:
            client.remove_aggregate_host(self.controller, aggregate_name, match_hosts)
            client.add_aggregate_host(self.controller, aggregate_name, [self.node_dict[node_name].host])

    def reset_hugepage(self, node_list, node_dict):
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
                numa_info_dict = {0: self.default_page_num}
                result = client.refresh_hugePage(node.ssh_connect, numa_info_dict, numa_total=self.numa_num)
                if not result:
                    raise RuntimeError("set hugePage fail")

    def create_server_only(self, vm):
        lock = threading.Lock()
        lock.acquire()
        volume = self._create_volume(vm.image)
        lock.release()
        flavor = self._get_flavor(vm)
        client.create_server_with_volume(self.controller, vm.name, flavor.name, volume.name)

    def clear_huge_pages(self, node):
        for i in range(0, self.numa_num):
            numa_clr_cmd = "echo 0 > /sys/devices/system/node/node{}/hugepages/hugepages-2048kB/nr_hugepages".format(i)
            node.run({'command': numa_clr_cmd})
        node.run({'command': ['echo 3 > /proc/sys/vm/drop_caches']})
        node.run({'command': ['numastat -cvm']})

    def get_overcommitment(self, node):
        command = "python /usr/lib/python3.11/site-packages/ubse/ubs_virt_case_conf.py"
        res = node.run({'command': [command]}).get('stdout')
        parts = res.split("#####")
        if len(parts) < 2:
            self.logError(f"get_overcommitment: unexpected output format: {res}")
            return None
        case_conf_dict = ast.literal_eval(parts[1])
        overcommitment = [case_conf_dict['migrate_water_line'], case_conf_dict['over_commitment']]
        return overcommitment

    def wait_ubse_status(self, node, timeout, wait_interval):
        start_time = time.time()
        while time.time() - start_time < timeout:
            flag = True
            status_dict = self.get_ubse_status(node)
            for ssh_node in self.nodes:
                host_name = ssh_node.getHostname()
                if host_name == 'controller' and self.is_Simulation:
                    continue
                if status_dict.get(host_name) != 'ok':
                    flag = False
                    break
            if flag:
                time.sleep(30) # ubse进程恢复后再等待30s，提高用例稳定性
                return
            time.sleep(wait_interval)
        self.assertTrue(False, "进程重启后节点状态未就绪")

    def get_ubse_status(self, node):
        status_dict = {}
        res = node.run({'command': [f'sudo -u ubse ubsectl check memory']}).get('stdout')
        if res:
            lines = res.splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('-', 'root')) and 'node' not in line:
                    parts = line.split()
                    node_str = parts[0]
                    status = parts[4].rstrip(';')
                    base_node = node_str.split('(')[0] if '(' in node_str else node_str
                    status_dict[base_node] = status
        return status_dict

    def get_ubse_node_id(self, node):
        res = node.run({'command': [
            "ubsectl display cluster | grep ` cat /etc/hostname | grep -v '#'` | awk 'BEGIN{ FS=\"(\" ; RS=\")\" } NF>1 { print $NF }'"
        ]}).get("stdout")
        if not res:
            return False
        else:
            return str(res[0])

    def wait_stress(self, node_name, numa_name, expect_numa_size, timeout=900):
        if self.is_Simulation is False:
            self.logInfo("环境为非仿真环境，跳过加压等待时间")
            return True
        wait_time = 0
        flag = True
        numa_used_size = None
        while wait_time < timeout:
            numa_used_size = self.get_node_numa_used(node_name, numa_name)
            if numa_used_size > expect_numa_size:
                flag = True
                break
            else:
                wait_time = wait_time + 5
                time.sleep(5)
        self.assertTrue(flag, f"numa{numa_name} numa_used_size is {numa_used_size}, not {expect_numa_size}")

    def get_migrate_actionType(self, exec_node, timestamp, timeout=1800):
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            decision = client.get_migrate_actionType(exec_node, timestamp)
            if decision is not None:
                return int(decision)
            time.sleep(10)
        return None

    def check_stress_in_vm(self, vm, first_enter=True):
        vm_ssh_node = self._get_vm_ssh(vm, first_enter)
        return client.check_vm_stress(vm_ssh_node)

    def stop_ubs_scheduler_agent(self, node):
        command = f"systemctl stop ubs-scheduler-agent.service"
        query_cmd = f"ps -ef |grep ubs_scheduler_agent.py | grep -v grep"
        res = node.run({'command': [command]})
        for _ in range(15):
            res = node.run({'command': [query_cmd]})
            if res.get("stdout") is None:
                break
            time.sleep(3)
        return True if res.get("stdout") is None else False

    def start_ubs_scheduler_agent(self, node):
        command = f"systemctl start ubs-scheduler-agent.service"
        query_cmd = f"ps -ef |grep ubs_scheduler_agent.py | grep -v grep"
        res = node.run({'command': [command]})
        for _ in range(15):
            res = node.run({'command': [query_cmd]})
            if res.get("stdout") is not None:
                break
            time.sleep(3)
        return True if res.get("stdout") is not None else False

    def stop_scbus(self, node):
        command = f"systemctl stop ubse"
        query_cmd = f"ps -ef |grep /usr/bin/ubse | grep -v grep"
        res = node.run({'command': [command]})
        for _ in range(5):
            res = node.run({'command': [query_cmd]})
            if res.get("stdout") is None:
                break
            time.sleep(1)
        return True if res.get("stdout") is None else False

    def start_scbus(self, node):
        command = f"systemctl start ubse"
        query_cmd = f"ps -ef |grep /usr/bin/ubse | grep -v grep"
        res = node.run({'command': [command]})
        for _ in range(5):
            res = node.run({'command': [query_cmd]})
            if res.get("stdout") is not None:
                break
            time.sleep(1)
        return True if res.get("stdout") is not None else False

    def stop_all_scbus(self):
        for node in self.ubse_node_list:
            res = self.stop_scbus(node)
            self.assertTrue(res, '停止ubse进程失败')

    def start_all_scbus(self):
        for node in self.ubse_node_list:
            res = self.start_scbus(node)
            self.assertTrue(res, '启动ubse进程失败')

    def change_overcommitment(self, nova_conf_path, set_value=1.25):
        change_overcommitment_res = True

        for node in self.ubse_node_list:
            try:
                overcommitment = self.get_overcommitment(node)
                if set_value != overcommitment[1]:
                    change_overcommitment_res = False
                    break
            except Exception:
                change_overcommitment_res = False
                break

        if change_overcommitment_res is True:
            self.logStep("超分比例不需要修改")
            return change_overcommitment_res

        self.stop_all_scbus()
        self.controller.stopService("openstack-nova-scheduler")
        for node in self.ubse_node_list:
            node.stopService("openstack-nova-compute")

        set_value_str = str(set_value)
        for node in self.nodes:
            client.set_conf_file(node, nova_conf_path, 'ram_allocation_ratio', set_value_str)

        self.master.run({'command': ['rm -rf /var/lib/ubse/data']})
        for agent in self.agent_list:
            agent.run({'command': ['rm -rf /var/lib/ubse/data']})

        self.start_all_scbus()
        self.wait_ubse_status(self.master, 900, 10)

        self.controller.startService("openstack-nova-scheduler")
        for node in self.ubse_node_list:
            node.startService("openstack-nova-compute")

        self.waitServiceStatus(self.controller, "openstack-nova-scheduler", 900)
        for node in self.ubse_node_list:
            self.waitServiceStatus(node, "openstack-nova-compute", 900)

        for node in self.ubse_node_list:
            overcommitment = self.get_overcommitment(node)
            self.assertEqual(overcommitment[1], set_value, "overcommitment is not set value")

        self.controller.stopService("ubs-scheduler-controller")
        for node in self.ubse_node_list:
            node.stopService("ubs-scheduler-agent")

        self.controller.startService("ubs-scheduler-controller")
        for node in self.ubse_node_list:
            node.startService("ubs-scheduler-agent")

        self.waitServiceStatus(self.controller, "ubs-scheduler-controller", 900)
        for node in self.ubse_node_list:
            self.waitServiceStatus(node, "ubs-scheduler-agent", 900)

        change_overcommitment_res = True
        return change_overcommitment_res

    def get_keystone_token(self):
        self.ensure_admin_openrc_on_controller()
        res = (self.controller.run({"command": ["openstack token issue -f value -c id"]}).get("stdout") or "")
        return res.replace("\r", "").replace("\n", "").replace("root@#>", "")