import logging
import random
import string
import time

import pytest
from typing import Any, Dict, List

from libs import TestCase
from libs.core.basecase.ubturbo.smap_params import EnableNodeMsg, RemoveMsg, MigrateOutMsg, MigrateOutPayload

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_smap_basecase_dependencies(
        request: Any,
        nodes: List[Any],
        resource: Dict[str, Any],
        custom_params: Dict[str, Any]
) -> None:
    """注入MSmapBaseCase外部依赖参数.
    
    只对SmapBaseCase及其子类执行注入。
    """
    if isinstance(request.instance, SmapCase):
        request.instance._setup_with_fixtures(nodes, resource, custom_params)


class SmapCase(TestCase):

    def _setup_with_fixtures(self, nodes, resource, custom_params):

        from libs.core.basecase.ubturbo.smap_cli import SmapCli
        from libs.core.basecase.ubturbo.smap_host import SmapHost

        self.nodes = nodes if nodes else []
        self.resource = resource
        self._package_path = custom_params.get("package_path", "/home/ubturbo-test/smap")
        self.smap_period_config = custom_params.get("smap_period_config", "/opt/ubturbo/conf/smap/period.config")
        self.smap_log = custom_params.get("smap_log", "/var/log/smap_log")
        self.cli: List[SmapCli] = [SmapCli(self._package_path, node) for node in self.nodes]
        self.hosts: List[SmapHost] = [SmapHost(self._package_path, node, i) for i, node in
                                      enumerate(self.nodes, start=0)]
        self.remote_numa_list: List[int] = []
        self.local_numa_list: List[int] = []

    @staticmethod
    def generate_string(length: int) -> str:
        letters = string.ascii_letters  # 包含所有大小写字母
        return ''.join(random.choice(letters) for _ in range(length))

    def recover_smap_env_pre(self):
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)

        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

        rc = self.cli[0].set_smap_remote_numa_info(0, self.remote_numa_list[0], 0)
        self.assertEqual(rc, 0)
        rc = self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        self.assertEqual(rc, 0)

    def safe_delete_vms(self):
        """
        尝试安全移除虚机，用于用例后处理，将虚机远端内存迁回 并移除smap纳管
        1、通过SmapQueryProcessConfig 查询被纳管的虚机
        2、在水线模式下将所有纳管虚机的远端内存迁回
        3、移除虚机纳管
        """
        if len(self.remote_numa_list) == 0:
            return

        # vm_pid -> remote_numa 字典映射
        vm_remote_numa_map = dict()
        for remote_numa in self.remote_numa_list:
            pids = map(lambda config: config.pid, self.cli[0].smap_query_process_config(remote_numa, 1, 96, 1).payload)
            for pid in pids:
                if pid not in vm_remote_numa_map:
                    vm_remote_numa_map[pid] = set()
                vm_remote_numa_map[pid].add(remote_numa)

        # vm_pid -> vm_instance 字典映射
        vm_instance_map = dict()
        for vm_nodes in [getattr(self.hosts[0], name) for name in dir(self.hosts[0]) if name.startswith('vm_nodes')]:
            for vm_node in vm_nodes:
                if vm_node.in_use():
                    vm_instance_map[vm_node.get_pid()] = vm_node

        # 需要按比例迁回，设置为水线模式
        self.cli[0].smap_set_runmode(0)

        for vm_instance in vm_instance_map.values():
            vm_pid = vm_instance.get_pid()
            if vm_remote_numa_map.get(vm_pid) is None:
                continue
            vm_local_numa = vm_instance.get_unique_numa_node()
            self.logger.info(f"found vm:{vm_pid} local_numa:{vm_local_numa} remote_numa:{vm_remote_numa_map[vm_pid]}")
            for remote_numa in vm_remote_numa_map[vm_pid]:
                self.cli[0].set_smap_remote_numa_info(vm_local_numa, remote_numa, 0)
                self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, vm_pid, 0)]), 1)
                self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 0, 180, True)
            self.cli[0].smap_remove(RemoveMsg([vm_pid]), 1)

    def postTestCase(self):
        time.sleep(1)
        self.logger.info("This is Post Test Case~ ")
        try:
            self.performCleanUp()
        except Exception as error:
            raise Exception("An Exception Occurred during The Post-TestCase:\n%s" % error)
        return

    def preTestCase(self):
        return