from datetime import datetime
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate021(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_021
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证8G虚拟机的逃生决策迁移
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置8G，Node2配置12G可用大页内存
        P4.已完成内存规格8G虚拟机VM1的创建
    TestStep:
        S1.登录VM1,对VM1加压，使得内存超过第二水位线85%，查看水位线告警、逃生策略
    ExpectedResult:
        E1.存在水位线告警，预期虚拟机迁移成功
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")
        self.logStep("P2.OpenStack/ubse功能正常无异常")
        self.logStep("P3.Node1上配置8G，Node2配置12G可用大页内存")
        self.logStep("P4.已完成内存规格8G虚拟机VM1的创建")

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_021(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_021")))

        self.logStep("S1.登录VM1,对VM1加压，使得内存超过第二水位线85%，查看水位线告警、逃生策略")
        start_time = client.get_date_timestamp(self.controller)
        self.add_stress_to_vm(self.vm_list[0], 87)
        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)
        self.assertEqual(escape_decision, "True", "MS action type is not migrate")
        flag = self.check_vm_migrate_to_dest_node(self.controller, self.vm_list[0].name, self.node_dict["node2"].host,
                                                  12000)
        self.logStep("E1.存在水位线告警，预期虚拟机迁移成功")
        self.assertTrue(flag, "VM1 migrate error!")