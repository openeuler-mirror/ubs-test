from libs.modules.ubsvirt.model.model import VMResource
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVirtualVmCreate003(OpenStackBaseCase):
    """
    预置条件：
    P1、已按照资料配置nova的ram_allocation_ratio为1且重启服务生效
    P2、配置numa节点2M可用大页为20G+512M（obmm占用512M）

    测试步骤：
    S1、创建内存规格20G的虚机
    S2、创建内存规格1G的虚机

    预期结果：
    E1、创建成功
    E2、创建失败
    """

    def setup_method(self):
        self.logStep("P1、已按照资料配置nova的ram_allocation_ratio为1且重启服务生效")

        self.logStep(" P2、配置numa节点2M可用大页为20G+512M（obmm占用512M）")

    def teardown_method(self):
        """Legacy: postTestCase"""
        self.clear_server()

    def test_virtual_vm_create_003(self, get_topo_path):
        """
        Test for test_virtual_vm_create_003
        """

        self.logStep("S1、创建内存规格20G的虚机")
        self.vms = self.prepare_topo(str(get_topo_path("test_virtual_vm_create_003")))

        self.logStep("E1、创建成功")

        self.logStep("S2、创建内存规格1G的虚机")
        vm_1g = VMResource('vm_1g', 'openEuler-22.03-everything', 1024, 'node1',
                           False, 1, False, True, 25,
                           True, 25)
        vm_status = self.create_server(vm_1g, expect_status="ERROR")

        self.logStep("E2、创建失败")
        self.assertEqual(vm_status, "ERROR", "创建失败")