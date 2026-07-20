from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate018(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_018
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证多虚机决策逃生不同节点
    PreCondition:
        P1.环境中存在4个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置10G可用大页内存，配置Node2 Node3可用4G大页
        P4.已完成内存规格8G虚拟机VM1和2G虚拟机VM2的创建
    TestStep:
        S1.登录VM1/VM2,对VM1/VM2加压到9.5G，使得内存超过第二水位线92%（9.2G），查看水位线告警、借用策略、水位线告警变化情况
    ExpectedResult:
        E1.存在水位线告警，预期VM1借用收益1G，借用账本借用量1G，触发内存借用操作，VM2触发迁移操作，借用节点和迁移节点不同。
    """

    def setup_method(self):
        self.logStep("P1.环境中存在4个及以上节点")
        ubse_node_count = len(self.ubse_node_list)
        self.assertGreaterEqual(ubse_node_count, 4, "环境中不存在4个及以上节点")

        self.ubs_restart_flag = False

    def teardown_method(self):
        if self.ubs_restart_flag:
            self.logInfo("启动加压节点ubs-scheduler-agent")
            start_res = self.start_ubs_scheduler_agent(self.master)
            self.assertTrue(start_res, '启动master ubs-scheduler-agent进程失败')
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_018(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_018")))

        self.logStep(
            "S1.登录VM1/VM2,对VM1/VM2加压到9.5G，使得内存超过第二水位线92%（9.2G），查看水位线告警、借用策略、水位线告警变化情况")
        self.logInfo("停止加压节点ubs-scheduler-agent")
        self.master.stopService("ubs-scheduler-agent")
        self.ubs_restart_flag = True

        self.logInfo("登录VM1/VM2,对VM1/VM2加压，使得内存超过第二水位线92%")
        start_time = client.get_date_timestamp(self.controller)
        self.add_stress_to_vm(self.vm_list[1], 96)
        self.add_stress_to_vm(self.vm_list[0], 96)

        except_numa_size = 0.8 * self.vm_list[0].ram + 0.8 * self.vm_list[1].ram
        self.wait_stress("node1", "Node 0", except_numa_size)

        self.logStep(
            "E1.存在水位线告警，预期VM1借用收益1G，借用账本借用量1G，触发内存借用操作，VM2触发迁移操作，借用节点和迁移节点不同。")
        flag = self.check_borrowed_numa_size("node1", 900, 1024)
        self.assertTrue(flag, "The borrowed size is not 1G")

        self.logInfo("启动加压节点ubs-scheduler-agent")
        self.master.startService("ubs-scheduler-agent")
        self.waitServiceStatus(self.master, "ubs-scheduler-agent", 900)
        self.ubs_restart_flag = False

        self.logInfo("获取加压节点ms迁移策略")
        ubs_scheduler_decision = self.get_decision(start_time, ubs_scheduler_decision=True)
        self.assertEqual(ubs_scheduler_decision, "True", "Ubs scheduler action type is not migrate")

        node2_used = self.get_node_numa_used("node2", "Node 0")
        node3_used = self.get_node_numa_used("node3", "Node 0")
        if node2_used > 256:
            self.logInfo(f"node2_used is {node2_used}")
            self.logInfo(f"node3_used is {node3_used}")
            target_node = "node3"
            self.logInfo(f"target_node is {target_node}")
        elif node3_used > 256:
            self.logInfo(f"node2_used is {node2_used}")
            self.logInfo(f"node3_used is {node3_used}")
            target_node = "node2"
            self.logInfo(f"target_node is {target_node}")
        else:
            self.logInfo(f"node2_used is {node2_used}")
            self.logInfo(f"node3_used is {node3_used}")
            raise RuntimeError("node2 node3 used size is all less than 256M")

        res = self.check_vm_migrate_to_dest_node(self.controller, "test_vm_migrate_018_01",
                                                 self.node_dict[target_node].host, 3000)
        self.assertTrue(res, "VM test_vm_migrate_018_01 migrate failed")