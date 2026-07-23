
import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemBorrow012(OpenStackBaseCase):
    """
    P1.环境中存在2个及以上节点
        P2.OpenStack/RackManager功能正常无异常
        P3.Node0上配置4G可用大页内存
        P4.已完成内存规格4G虚拟机VM1的创建
        P5.对VM1加压后触发了内存借用操作

        S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况
        S2.登录VM1,在对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况

        E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。
        E2.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，水位线会降低，内存借出点水线会上涨。
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_borrow_012(self, get_topo_path):
        """
        Test for test_vm_mem_borrow_012
        """

        self.logStep("P4、已完成内存规格4G虚拟机VM1的创建。")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_borrow_012")))

        self.logStep("P5.对VM1加压后触发了内存借用操作")
        self.add_stress_to_vm(self.vms[0], 93)
        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 1024), "the borrowed size is not 1G")

        self.logStep("S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况")
        for vm in self.vms:
            self.clean_vm_stress(vm)

        self.assertTrue(self.check_return_mem("node1", 600), "the borrowed size is not returned")

        node1_numa_after_stress = self.get_node_numa_percent("node1")
        self.logInfo("node1 numa percent is " + str(node1_numa_after_stress))
        node1_percent = self.wait_mem_match_expect("node1", "less", 85)
        self.assertLess(node1_percent, 85, "内存水线下降到85%")

        self.logStep(
            "S2.登录VM1,在对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况"
        )
        self.add_stress_to_vm(self.vms[0], 93)
        node1_numa_after_stress = self.get_node_numa_percent("node1")
        self.logInfo("node1 numa percent is " + str(node1_numa_after_stress))
        self.logInfo("获取加压后借用值")
        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 1024), "the borrowed size is not 1G")
        node1_percent = self.wait_mem_match_expect("node1", "less", 92)
        self.assertLess(node1_percent, 92, "内存水线下降到92%")
