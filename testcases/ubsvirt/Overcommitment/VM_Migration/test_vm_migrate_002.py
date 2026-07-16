from datetime import datetime

from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestVmMigrate002(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_002
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证8G虚拟机迭代拷贝热迁移
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.Node1上配置4096个2M大页，Node2上配置10000个2M大页
        P4.Node1上创建4U8G大小的虚机
    TestStep:
        S1.向虚机加压，使其内存占比超过85%
        S2.查看告警水线、逃生策略
        S3.根据逃生策略查看逃生策略执行情况
    ExpectedResult:
        E1.虚机登录成功，成功加压
        E2.水线超过85%，实际逃生策略为0
        E3.触发虚机迁移，虚机被迁移至Node2，此时虚机状态正常（状态为running，可以正常登录该虚机，虚机内部压力依然存在）
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")

        self.logStep("P2.OpenStack/ubse功能正常无异常")

        self.logStep("P3.Node1上配置4096个2M大页，Node2上配置10000个2M大页")

        self.logStep("P4.Node1上创建4U8G大小的虚机")

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_vm_migrate_002(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_002")))

        self.logStep("S1.向虚机加压，使其内存占比超过85%")
        start_time = client.get_date_timestamp(self.controller)
        for vm in self.vm_list:
            self.add_stress_to_vm(vm, 86)

        self.logInfo("E1.虚机登录成功，成功加压")
        self.logInfo("查看当前环境信息")
        expect_numa_size = 0.85 * self.vm_list[0].ram
        self.wait_stress('node1', 'Node 0', expect_numa_size)

        self.logStep("S2.查看告警水线、逃生策略")
        escape_decision = self.get_decision(timestamp=start_time, ubs_scheduler_decision=True)

        self.logInfo("E2.水线超过85%，实际逃生策略为0")
        self.assertEqual(escape_decision, "True", "Ubs scheduler action type is not migrate")

        self.logStep("S3.根据逃生策略查看逃生策略执行情况")
        timestamp = client.get_date_timestamp(self.controller)
        log_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.logInfo(f"虚机迁移前时间: {log_time}")
        except_acitonType = 0
        migrate_actionType = self.get_migrate_actionType(self.master, start_time)
        self.assertEqual(migrate_actionType, except_acitonType,
                         f"migrate_actionType is {migrate_actionType},not {except_acitonType}")

        self.logInfo("E3.触发虚机迁移，虚机被迁移至Node2，此时虚机状态正常（状态为running，可以正常登录该虚机，虚机内部压力依然存在）")
        migrate_result = self.check_vm_migrate_to_dest_node(self.controller, self.vm_list[0].name,
                                                            self.node_dict['node2'].host, 8000)
        self.assertTrue(migrate_result, "vm_01 migrate failed")

        flag = self.check_stress_in_vm(self.vm_list[0], first_enter=False)
        self.assertTrue(flag, "迁移后虚机stress异常")

        timestamp2 = client.get_date_timestamp(self.controller)
        log_time2 = datetime.fromtimestamp(timestamp2).strftime("%Y-%m-%d %H:%M:%S")
        self.logInfo(f"虚机迁移后时间: {log_time2}")
