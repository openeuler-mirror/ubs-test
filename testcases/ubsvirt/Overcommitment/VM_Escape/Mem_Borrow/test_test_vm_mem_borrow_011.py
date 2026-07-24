

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemBorrow011(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_mem_borrow_011
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不同节点上多虚拟机同时加压后内存借用成功
    PreCondition:
        P1.环境中存在4个及以上节点
        P2.OpenStack/RackManager功能正常无异常
        P3.Node0、Node1上配置20G可用大页内存
        P4.已完成不同节点内存规格4G虚拟机VM1、8G虚拟机VM2的创建
    TestStep:
        S1.登录VM1/VM2，对VM1/VM2加压，使得内存超过第二水位线92%，查看水位线告警、借用策略、借入借出点水位线告警变化情况
    ExpectedResult:
        E1.两个节点存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，内存借入点水位线会降低，内存借出点水线会上涨。
    Author:
        fengqian 60061484
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_borrow_011(self, get_topo_path):

        self.logStep("P4.已完成不同节点内存规格4G虚拟机VM1、8G虚拟机VM2的创建")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_borrow_011")))

        self.logStep(
            "S1.登录VM1/VM2，对VM1/VM2加压，使得内存超过第二水位线92%，查看水位线告警、借用策略、借入借出点水位线告警变化情况"
        )
        for vm in self.vms:
            self.add_stress_to_vm(vm, 96)

        self.logStep(
            "E1.两个节点存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，内存借入点水位线会降低，内存借出点水线会上涨。"
        )
        self.assertTrue(self.check_borrowed_numa_size("node1", 1000, 1024), "Mem borrow 1024M failed")
        self.assertTrue(self.check_borrowed_numa_size("node2", 1000, 1024), "Mem borrow 1024M failed")
