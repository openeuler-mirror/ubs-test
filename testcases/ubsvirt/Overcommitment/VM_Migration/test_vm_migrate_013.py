import time
from datetime import datetime

from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate013(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_013
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证多个虚机迁移满足要求时，优先迁移内存使用量小的虚机
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置10G可用大页内存
        P4.已完成内存规格6G/2G/2G虚拟机VM1/VM2/VM3的创建
    TestStep:
        S1.登录虚机，对虚机内存进行加压，使得node1上内存超过第二水位线85%，VM3内存占用超过VM2
        S2.查看告警水线、逃生策略
        S3.根据逃生策略查看逃生策略执行情况
    ExpectedResult:
        E1.虚机登录成功，成功加压
        E2.水线超过85%，实际逃生策略为0
        E3.触发虚机迁移，VM2虚机被迁移至Node2，此时虚机状态正常（状态为running，可以正常登录该虚机，虚机内部压力依然存在）
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")
        self.logStep("P2.OpenStack/ubse功能正常无异常")
        self.logStep("P3.Node1上配置10G可用大页内存")
        self.logStep("P4.已完成内存规格6G/2G/2G虚拟机VM1/VM2/VM3的创建")

    def teardown_method(self):
        if self.ubs_restart_flag:
            self.logInfo("启动加压节点ubs scheduler agent")
            start_res = self.start_ubs_scheduler_agent(self.master)
            self.assertTrue(start_res, '启动master ubs scheduler agent进程失败')
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_013(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_013")))

        self.logStep("S1.登录虚机，对虚机内存进行加压，使得Node1上内存超过第二水位线85%，VM3内存占用超过VM2")
        self.logInfo("停止加压节点ubs scheduler agent")
        stop_master_res = self.stop_ubs_scheduler_agent(self.master)
        self.assertTrue(stop_master_res, '停止master ubs scheduler agent进程失败')
        self.ubs_restart_flag = True

        start_time = client.get_date_timestamp(self.controller)
        self.add_stress_to_vm(self.vm_list[0], 92)
        self.add_stress_to_vm(self.vm_list[1], 75)
        self.add_stress_to_vm(self.vm_list[2], 91)

        self.logStep("E1.虚机登录成功，成功加压")
        wait_time = 0
        flag = False
        while wait_time < 1200:
            node1_numa0_mem_used_size = self.get_node_numa_used("node1", "Node 0")
            if node1_numa0_mem_used_size > 8777:
                flag = True
                break
            else:
                wait_time = wait_time + 30
                time.sleep(30)
        self.assertEqual(flag, True, "Node1 numa0 used mem is unexpected")

        self.logInfo("启动加压节点ubs scheduler agent")
        start_res = self.start_ubs_scheduler_agent(self.master)
        self.assertTrue(start_res, '启动master ubs scheduler agent进程失败')
        self.ubs_restart_flag = False

        self.logStep("S2.查看告警水线、逃生策略")
        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)

        self.logStep("E2.水线超过85%，实际逃生策略为0")
        self.assertEqual(escape_decision, "True", "Ubs Scheduler actionType is not migrate")

        self.logStep("S3.根据逃生策略查看逃生策略执行情况")
        self.logStep(
            "E3.触发虚机迁移，VM2虚机被迁移至Node2，此时虚机状态正常（状态为running，可以正常登录该虚机，虚机内部压力依然存在）")
        wait_time = 0
        flag = False
        while wait_time < 4000:
            server_detail_vm02 = client.get_server_detail(self.controller, self.vm_list[1].name)
            server_detail_vm03 = client.get_server_detail(self.controller, self.vm_list[2].name)
            if server_detail_vm02['OS-EXT-SRV-ATTR:host'] == self.node_dict['node2'].host:
                flag = True
                break
            elif server_detail_vm03['status'] == "MIGRATING":
                self.logError("test_vm_migrate_013_03 migrate is unexpected")
                break
            else:
                wait_time = wait_time + 30
                time.sleep(30)
        self.assertEqual(flag, True, "test_vm_migrate_013_02 migrate failed")