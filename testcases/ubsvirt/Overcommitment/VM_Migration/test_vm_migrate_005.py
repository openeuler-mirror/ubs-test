from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate005(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_005
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证目的节点存在多个可迁移节点，虚机优先迁移至内存风险更小（空闲大页内存/总大页内存）的节点
    PreCondition:
        P1.环境中存在4个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置4G可用大页内存
        P4.已完成内存规格4G虚拟机VM1的创建
        P5.配置目标节点Node2的numa0可用5G大页，Node3的numa1可用6G大页
    TestStep:
        S1.登录VM1,对VM1加压到3.5G，使得内存超过第一水位线85%（3.4G），查看水位线告警、逃生策略
    ExpectedResult:
        E1.存在水位线告警，预期虚拟机迁移成功，虚拟机绑定numa1
    """

    def setup_method(self):
        self.logStep("P1.环境中存在4个及以上节点")
        ubse_node_count = len(self.ubse_node_list)
        self.assertGreaterEqual(ubse_node_count, 4, "环境中不存在4个及以上节点")

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_005(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_005")))

        self.logStep("S1.登录VM1,对VM1加压到3.5G，使得内存超过第一水位线85%（3.4G），查看水位线告警、逃生策略")
        start_time = client.get_date_timestamp(self.controller)
        self.add_stress_to_vm(self.vm_list[0], 88)
        self.logStep("E1.存在水位线告警，预期虚拟机迁移成功，虚拟机绑定numa1")
        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)
        self.assertEqual(escape_decision, "True", "Ubs scheduler action type is not migrate.")

        self.logInfo("查看虚机迁移状态")
        res = self.check_vm_migrate_to_dest_node(self.controller, self.vm_list[0].name, self.node_dict["node3"].host, 4000)
        self.assertTrue(res, "VM1 migrate error")