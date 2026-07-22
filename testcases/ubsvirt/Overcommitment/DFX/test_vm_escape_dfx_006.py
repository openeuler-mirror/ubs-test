from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
import libs.modules.ubsvirt.common.file_common as file_aw


class TestVmEscapeDfx006(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_escape_dfx_006
    RunLevel:
        Level 2
    EnvType:
        None
    CaseName:
        验证第一次内存借用失败恢复后，第二次借用成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/UBSE功能正常无异常
        P3.Node0上配置4G可用大页内存
        P4.已完成内存规格4G虚拟机VM1的创建
    TestStep:
        S1.登录VM1,在对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况
        S2.执行UBSE重启操作
        S3.登录VM1,在对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况
    ExpectedResult:
        E1.存在水位线告警，触发内存借用失败
        E2.操作成功
        E3.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作
    Author:
        chenyuying 00816141
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")
        ubse_node_count = len(self.ubse_node_list)
        self.assertGreaterEqual(ubse_node_count, 2, "环境中不存在2个及以上节点")

        self.vm_plugin_conf = "/etc/ubse/ubse_plugin_admission.conf"
        self.vm_plugin_key = "virt_agent"

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)
        file_aw.uncomment_config(self.master, self.vm_plugin_conf, self.vm_plugin_key)
        self.restart_service(self.master, "ubse")
        self.wait_ubse_status(self.master, 1200, 30)

    def test_vm_escape_dfx_006(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vms = self.prepare_topo(str(get_topo_path("test_vm_escape_dfx_006")))

        self.logStep(
            "S1.登录VM1,在对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况")
        file_aw.comment_config(self.master, self.vm_plugin_conf, self.vm_plugin_key)
        self.restart_service(self.master, "ubse")
        self.wait_ubse_status(self.master, 1200, 30)

        self.add_stress_to_vm(self.vms[0], 92)
        start_time = client.get_date_timestamp(self.master)
        except_numa_size = 0.92 * self.vms[0].ram
        self.wait_stress("node1", "Node 0", except_numa_size)

        self.logStep("E1.存在水位线告警，触发内存借用失败")
        numa_borrowed_size = self.get_node_borrowing_numa("node1")
        self.assertEqual(numa_borrowed_size, 0, "the borrowed size is not 0")

        self.logStep("S2.执行UBSE重启操作")
        file_aw.uncomment_config(self.master, self.vm_plugin_conf, self.vm_plugin_key)
        self.restart_service(self.master, "ubse")

        self.logStep("E2.操作成功")
        self.wait_ubse_status(self.master, 1200, 30)


        self.logStep(
            "S3.登录VM1,在对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况")
        vm_decision = self.get_decision(start_time)
        self.assertIn(vm_decision[0], [0, 2], "actionType is not 0 or 2")

        flag = self.check_borrowed_numa_size("node1", 1000, "1024")
        self.assertTrue(flag, "Mem borrow 1024M failed")

        self.logStep("E3.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作")
        node1_percent = self.wait_mem_match_expect("node1", "less", 92)
        self.assertLess(node1_percent, 92, "内存水线未下降到92%")
