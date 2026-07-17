from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate016(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_016
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证借用Node2远端内存虚机迁移Node3成功
    PreCondition:
        P1.环境中存在3个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置8G可用大页内存，Node2的numa0配置可用4G内存
        P4.已完成内存规格8G虚拟机VM1的创建
    TestStep:
        S1.登录VM1,对VM1加压使得内存超过第二水位线92%，查看水位线告警、逃生策略
        S2.配置node3的numa0可用大页内存为10G
        S3.继续加压，对VM1加压使得内存超过第一水位线85%，查看水位线告警、逃生策略
    ExpectedResult:
        E1.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，
        E2.配置成功
        E3.存在水位线告警，预期虚拟机迁移成功
    """

    def setup_method(self):
        self.logStep("P1.环境中存在3个及以上节点")
        ubse_node_count = len(self.ubse_node_list)
        self.assertGreaterEqual(ubse_node_count, 3, "环境中不存在3个及以上节点")

        self.ubs_restart_flag = False

    def teardown_method(self):
        if self.ubs_restart_flag:
            self.logInfo("启动加压节点ubs scheduler agent")
            start_res = self.start_ubs_scheduler_agent(self.master)
            self.assertTrue(start_res, '启动master ubs scheduler agent进程失败')
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_016(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_016")))

        self.logStep("S1.登录VM1,对VM1加压使得内存超过第二水位线92%，查看水位线告警、逃生策略")
        self.logInfo("停止加压节点ubs scheduler agent")
        stop_master_res = self.stop_ubs_scheduler_agent(self.master)
        self.assertTrue(stop_master_res, '停止master ubs scheduler agent进程失败')
        self.ubs_restart_flag = True

        result = client.echo_hugePage(self.agent_list[0], 0, 2048)
        if not result:
            raise RuntimeError("set hugePage fail")
        self.restart_service(self.agent_list[0], "nova-compute")
        self.add_stress_to_vm(self.vm_list[0], 98)

        self.logStep("E1.存在水位线告警，预期借用1G内存，触发内存借用操作，")
        flag = self.check_borrowed_numa_size('node1', 600, 900)
        self.assertEqual(flag, True, "Borrow Memory failed")

        self.logStep("S2.配置Node3的numa0可用大页内存为10G")
        result = client.echo_hugePage(self.agent_list[1], 0, 5376)
        if not result:
            raise RuntimeError("set hugePage fail")
        self.restart_service(self.agent_list[1], "nova-compute")

        self.logStep("E2.配置成功")
        self.waitServiceStatus(self.agent_list[1], "openstack-nova-compute", 600)

        self.logStep("S3.继续加压，对VM1加压使得内存超过第一水位线85%，查看水位线告警、逃生策略")
        start_time = client.get_date_timestamp(self.controller)

        self.logInfo("启动加压节点ubs scheduler agent")
        start_res = self.start_ubs_scheduler_agent(self.master)
        self.assertTrue(start_res, '启动master ubs scheduler agent进程失败')
        self.ubs_restart_flag = False

        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)
        self.assertEqual(escape_decision, "True", "Action type is not migrate")

        self.logStep("E3.存在水位线告警，预期虚拟机迁移成功")
        vm_migrate_result = self.check_vm_migrate_to_dest_node(self.controller, self.vm_list[0].name,
                                                               self.agent_list[1].getHostname(), 8000)
        self.assertEqual(vm_migrate_result, True, "VM test_vm_migrate_016_01 migrate failed")