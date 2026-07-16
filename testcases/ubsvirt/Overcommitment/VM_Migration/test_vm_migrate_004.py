from datetime import datetime
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate004(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_004
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证单个目的节点存在多个可迁移numa，虚机优先迁移至内存风险更小的numa
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置4G可用大页内存
        P4.已完成内存规格4G虚拟机VM1的创建
        P5.配置目标节点的numa0可用5G大页，numa1可用6G大页
    TestStep:
        S1.登录VM1,对VM1加压到3.5G，使得内存超过第一水位线85%（3.4G），查看水位线告警、逃生策略
    ExpectedResult:
        E1.存在水位线告警，预期虚拟机迁移成功，虚拟机绑定numa1
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")
        self.logStep("P2.OpenStack/ubse功能正常无异常")
        self.logStep("P3.Node1上配置4G可用大页内存")
        self.logStep("P4.已完成内存规格4G虚拟机VM1的创建")

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_004(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_004")))

        self.logStep("P5.配置目标节点的numa0可用5G大页，numa1可用6G大页")
        result = client.echo_hugePage(self.node_dict['node2'].ssh_node, 1, 3072)
        if not result:
            raise RuntimeError("set hugePage fail")
        self.restart_service(self.node_dict['node2'].ssh_node, "nova-compute")

        self.logStep("S1.登录VM1,对VM1加压到3.5G，使得内存超过第一水位线85%（3.4G），查看水位线告警、逃生策略")
        start_time = client.get_date_timestamp(self.controller)
        self.add_stress_to_vm(self.vm_list[0], 87)
        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)

        self.logStep("E1.存在水位线告警，预期虚拟机迁移成功，虚拟机绑定numa1")
        self.assertEqual(escape_decision, "True", "Ubs scheduler action type is not migrate")

        timestamp = client.get_date_timestamp(self.controller)
        log_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.logInfo(f"虚机迁移前时间: {log_time}")

        self.logInfo("虚机开始迁移")
        vm_migrate_result = self.check_vm_migrate_to_dest_node(self.controller, self.vm_list[0].name,
                                                               self.node_dict['node2'].host, 4000)
        self.assertTrue(vm_migrate_result, "VM test_vm_migrate_004_01 migrate failed")

        timestamp2 = client.get_date_timestamp(self.controller)
        log_time2 = datetime.fromtimestamp(timestamp2).strftime("%Y-%m-%d %H:%M:%S")
        self.logInfo(f"虚机迁移后时间: {log_time2}")

        self.logInfo("查看虚机是否绑定numa1")
        node2_numa1_mem_used_size = self.get_node_numa_used("node2", "Node 1")
        if not node2_numa1_mem_used_size > 2000:
            self.assertEqual(False, True, "VM test_vm_migrate_004_01 is not on node2 numa1")