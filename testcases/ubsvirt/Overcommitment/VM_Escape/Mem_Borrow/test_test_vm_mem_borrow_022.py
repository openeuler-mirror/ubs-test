

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemBorrow022(OpenStackBaseCase):
    """
    P1.环境中存在2个及以上节点
        P2.OpenStack/RackManager功能正常无异常
        P3.Node0上配置4G可用大页内存
        P4.已完成内存规格4G虚拟机VM1和1G虚拟机的VM2的创建

        S1.登录VM1，执行加压命令对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况（obmm占用256M内存，虚拟机自身进程占用8-10%大页内存）
        S2.登录VM2，执行加压命令对VM2加压，使得内存超过第二水位线92%（0.92G）,查看虚机状态
        E1.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，内存接入点水位线会降低，内存借出点水线会上涨
        E2.虚机的状态为ACTIVE，虚机内部OS正常，无异常crash
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_borrow_022(self, get_topo_path):
        """
        Test for test_vm_mem_borrow_022
        """

        self.logStep("P4、已完成内存规格4G虚拟机VM1和1G虚拟机的VM2的创建。")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_borrow_022")))

        self.logStep(
            "S1、登录VM1，执行加压命令对VM1加压，使得内存超过第二水位线92%（3.68G），"
            "查看水位线告警、借用策略、借入借出点水位线告警变化情况（obmm占用256M内存，虚拟机自身进程占用8-10%大页内存）"
        )
        self.add_stress_to_vm(self.vms[0], 98)
        self.logStep(
            "S2、登录VM2，执行加压命令对VM2加压，使得内存超过第二水位线92%（0.92G）,查看虚机状态"
        )
        self.add_stress_to_vm(self.vms[1], 98)

        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 1024), "the borrowed size is 1G")

        server_detail = self.wait_server_target_status(
            "vm_02", {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host}
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node1"].host)
