from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate019(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_019
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证带远端内存借用Node2,迁移Node2其他numa成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置8G可用大页内存，Node2的numa0配置可用4G内存
        P4.已完成内存规格8G虚拟机VM1的创建
    TestStep:
        S1.登录VM1,对VM1加压使得内存超过第二水na位线92%，查看水位线告警、逃生策略
        S2.配置Node2的numa1可用大页内存为10G
        S3.继续加压，对VM1加压使得内存超过第一水位线85%，查看水位线告警、逃生策略
    ExpectedResult:
        E1.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，
        E2.配置成功
        E3.存在水位线告警，预期虚拟机迁移成功
    """

    def setup_method(self):
        self.agent = self.agent_list[0]
        self.ubs_restart_flag = False

    def teardown_method(self):
        if self.ubs_restart_flag:
            self.logInfo("启动加压节点ubs scheduler agent")
            start_res = self.start_ubs_scheduler_agent(self.master)
            self.assertTrue(start_res, '启动ubs scheduler agent进程失败')
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_019(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_019")))

        self.logStep("S1.登录VM1,对VM1加压使得内存超过第二水na位线92%，查看水位线告警、逃生策略")
        self.logInfo("停止加压节点ubs scheduler agent")
        stop_master_res = self.stop_ubs_scheduler_agent(self.master)
        self.assertTrue(stop_master_res, '停止ubs scheduler agent进程失败')
        self.ubs_restart_flag = True

        self.add_stress_to_vm(self.vm_list[0], 98)

        self.logStep("E1.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，")
        flag = self.check_borrowed_numa_size('node1', 600, 900)
        self.assertTrue(flag, "Borrow Memory failed")

        self.logStep("S2.配置Node2的numa1可用大页内存为10G")
        result = client.echo_hugePage(self.agent, 1, 5376)
        if not result:
            raise RuntimeError("set hugePage fail")
        self.restart_service(self.agent, "nova-compute")

        self.logStep("E2.配置成功")
        self.waitServiceStatus(self.agent, "openstack-nova-compute", 600)

        self.logStep("S3.继续加压，对VM1加压使得内存超过第一水位线85%，查看水位线告警、逃生策略")
        start_time = client.get_date_timestamp(self.controller)

        self.logInfo("启动加压节点ubs scheduler agent")
        start_res = self.start_ubs_scheduler_agent(self.master)
        self.assertTrue(start_res, '启动ubs scheduler agent进程失败')
        self.ubs_restart_flag = False

        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)
        self.assertEqual(escape_decision, "True", "MS action type is not migrate")

        self.logStep("E3.存在水位线告警，预期虚拟机迁移成功")
        vm_migrate_result = self.check_vm_migrate_to_dest_node(self.controller, self.vm_list[0].name,
                                                               self.agent.getHostname(), 8000)
        self.assertTrue(vm_migrate_result, "VM test_vm_migrate_019_01 migrate failed")