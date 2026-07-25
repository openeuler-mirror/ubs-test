

import pytest
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemReturn004(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_mem_return_004
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证非numa0上4G虚拟机清除压力后内存归还成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/RackManager功能正常无异常
        P3.Node0上配置4G可用大页内存
        P4.已完成基于numa2内存规格4G虚拟机VM1的创建
        P5.对VM1加压触发了内存借用操作
    TestStep:
        S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况
    ExpectedResult:
        E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。
    Author:
        chensijiang 00930421
    """

    def teardown_method(self):
        self.clear_server()

    @pytest.mark.case_info(level='P1', type='Functional')
    def test_vm_mem_return_004(self, get_topo_path):

        self.logStep("P4.已完成基于numa2内存规格4G虚拟机VM1的创建")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_test_vm_mem_return_004")))

        self.logStep("P5.对VM1加压触发了内存借用操作")
        self.add_stress_to_vm(self.vm_list[0], 95)
        self.assertTrue(self.check_borrowed_numa_size("node1", 2000, 1024), "Mem borrow 1024M failed")

        self.logStep("S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况")
        start_time = client.get_date_timestamp(self.master)
        self.clean_vm_stress(self.vm_list[0])
        vm_decision = self.get_decision(start_time)
        self.assertIn(vm_decision[0], [1, 2], "vm_decision is not 1 or 2")
        flag_return = self.check_return_mem("node1", 1200)

        self.logStep(
            "E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。"
        )
        self.assertTrue(flag_return, "VM failed to return the borrowed memory")
