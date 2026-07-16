"""
Migrated from legacy: test_virtual_vm_create_001
"""

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVirtualVmCreate001(OpenStackBaseCase):
    """
    CaseNumber: 
        test_virtual_vm_create_001
    RunLevel: 
        Level 1
    EnvType: 

    CaseName: 
        验证节点的内存超分上限为1.25上多个虚机占满创建成功
    PreCondition:
        P1.已按照资料配置nova的ram_allocation_ratio为1.25且重启服务生效
        P2.配置numa节点2M可用大页为20G
        P3.环境已安装使能memlink
    TestStep:
        S1.分别创建内存规格1U8G，1U2G的虚机各2个，创建内存规格2U4G，1U1G的虚机各1个
    ExpectedResult:
        E1.创建成功，虚拟机状态为ACTIVE
    Author: 
        fengqian 60061484
    """

    def teardown_method(self):
        self.clear_server()

    def test_virtual_vm_create_001(self, get_topo_path):

        self.logStep("S1.分别创建内存规格1U8G，1U2G的虚机各2个，创建内存规格2U4G，1U1G的虚机各1个")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_virtual_vm_create_001")))

        self.logStep("E1.创建成功，虚拟机状态为ACTIVE")
        for name in ["vm_01", "vm_02", "vm_03", "vm_04", "vm_05", "vm_06"]:
            server_detail = self.wait_server_target_status(
                name, {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host}
            )
            assert server_detail["OS-EXT-SRV-ATTR:host"] == self.node_dict["node1"].host
