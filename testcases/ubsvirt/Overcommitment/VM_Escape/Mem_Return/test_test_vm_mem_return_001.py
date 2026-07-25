

import time

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemReturn001(OpenStackBaseCase):
    """
    Legacy test case: test_vm_mem_return_001
    """

    def teardown_method(self):
        self.clear_server()

    def test_test_vm_mem_return_001(self, get_topo_path):
        """
        Test for test_vm_mem_return_001
        """

        self.logStep("P1、创建虚拟机")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_return_001")))

        self.logStep("P5.对VM1加压触发了内存借用操作")
        for vm in self.vms:
            self.add_stress_to_vm(vm, 95)
        self.assertTrue(self.check_borrowed_numa_size("node1", 600, 1024 * 0.9), "the borrowed size is 0")
        node2_numa_used_size = self.get_node_numa_used("node2", "Node 0")
        self.assertGreater(node2_numa_used_size, 256, "Node2 numa0 is not used")

        self.logStep("登录VM1,停止VM1的加压进程，查看借用策略、借入借出点的水位线告警变化情况")
        time.sleep(30)
        for vm in self.vms:
            self.clean_vm_stress(vm)

        self.assertTrue(self.check_return_mem("node1", 600), "the borrowed size is not returned")
