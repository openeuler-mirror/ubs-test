

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.model.model import VMResource


@pytest.mark.smoke
class TestVirtualVmCreate002(OpenStackBaseCase):

    def teardown_method(self):
        self.clear_server()

    def test_virtual_vm_create_002(self, get_topo_path):

        self.logStep("S1、创建内存规格2U5G的虚机VM0")
        self.vms = self.prepare_topo(str(get_topo_path("test_virtual_vm_create_002")))

        self.logStep("S2、创建1U1G虚机失败")
        vm1 = VMResource('vm_02', 'openEuler-22.03-everything', 1024, 'node1', False, 2)
        vm_status = self.create_server(vm1, expect_status="ERROR")
        assert vm_status == "ERROR", "超过超分比创建虚机成功"
