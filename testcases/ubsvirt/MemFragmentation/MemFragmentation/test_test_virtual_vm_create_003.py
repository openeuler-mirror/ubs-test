"""
Migrated from legacy: test_virtual_vm_create_003
"""

import os
from libs.modules.ubsvirt.model.model import VMResource
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVirtualVmCreate003(OpenStackBaseCase):
    """
    Legacy test case: test_virtual_vm_create_003
    """

    def setup_method(self):
        """Legacy: preTestCase"""
        self.CUR_PATH = os.path.abspath(os.path.dirname(__file__))

        pass

    def teardown_method(self):
        """Legacy: postTestCase"""
        self.clear_server()

    def test_test_virtual_vm_create_003(self, get_topo_path):
        """
        Test for test_virtual_vm_create_003
        """

        self.logStep("S1、创建内存规格4U20G的虚机VM0")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_virtual_vm_create_003")))

        self.logStep("S2、创建1U1G虚机失败")
        vm_1g = VMResource('vm_1g', 'openEuler-22.03-everything', 1024, 'node1',
                           False, 1, False, True, 25,
                           True, 25)
        vm_status = self.create_server(vm_1g, expect_status="ERROR")
        self.assertEqual(vm_status, "ERROR", "创建失败")