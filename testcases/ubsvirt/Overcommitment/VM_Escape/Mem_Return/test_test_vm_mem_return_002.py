

import time

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemReturn002(OpenStackBaseCase):
    """
    Legacy test case: test_vm_mem_return_002
    """

    def teardown_method(self):
        self.clear_server()

    def test_test_vm_mem_return_002(self, get_topo_path):
        """
        Test for test_vm_mem_return_002
        """

        self.logStep("P1、创建虚拟机")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_return_002")))

        self.logStep("P5.对VM1加压触发了内存借用操作")
        for vm in self.vms:
            self.add_stress_to_vm(vm, 95)
        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 0.1), "the borrowed size is 0")
        node2_numa_used_size = self.get_node_numa_used("node2", "Node 0")
        self.assertGreater(node2_numa_used_size, 256, "Node1 numa0 is not used")

        self.logStep("删除VM1，查看借用策略、借入借出点的水位线告警变化情况")
        time.sleep(30)
        self.clear_server()
        self.assertTrue(self.check_return_mem("node1", 600), "the borrowed size is not returned")
