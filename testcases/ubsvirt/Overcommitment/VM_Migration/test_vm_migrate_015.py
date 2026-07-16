import time
import pytest

from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.model.model import VMResource


@pytest.mark.hook("libs.modules.ubsvirt.hook.migrate_hook.MigrateHook")
class TestVmMigrate015(OpenStackBaseCase):
    """
    CaseId:
        test_vm_migrate_015
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证决策多个VM迁移，同时只有一个VM迁移
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/ubse功能正常无异常
        P3.修改high.watermark为70，low.watermark为60
        P4.Node1上numa0配置8G可用大页内存,numa1配置4G可用大页
        P5.已完成内存规格4G虚拟机VM1、8G虚拟机VM2的创建
    TestStep:
        S1.同时对VM1/VM2进行加压触发虚机迁移操作
    ExpectedResult:
        E1.环境中VM1、VM2存在串行迁移操作
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")
        self.logStep("P2.OpenStack/ubse功能正常无异常")
        self.logStep("P3.修改high.watermark为70，low.watermark为60")
        self.logInfo("hook里已执行")
        self.logStep("P4.Node1上numa0配置8G可用大页内存,numa1配置4G可用大页")
        self.logStep("P5.已完成内存规格4G虚拟机VM1、8G虚拟机VM2的创建")
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

    def test_vm_migrate_015(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_migrate_015")))

        test_vm_migrate_015_02 = VMResource('test_vm_migrate_015_02', 'openEuler-22.03-everything',
                                            4096, 'node1', True, 2)
        self.create_server(test_vm_migrate_015_02)
        self.vm_list.append(test_vm_migrate_015_02)

        result = client.echo_hugePage(self.agent, 0, 5376)
        if not result:
            raise RuntimeError("set hugePage fail")
        self.restart_service(self.agent, "nova-compute")
        self.waitServiceStatus(self.agent, "openstack-nova-compute", 600)

        self.logStep("S1.同时对VM1/VM2进行加压触发虚机迁移操作")
        self.logInfo("停止加压节点ubs scheduler agent")
        stop_master_res = self.stop_ubs_scheduler_agent(self.master)
        self.assertTrue(stop_master_res, '停止master ubs scheduler agent进程失败')
        self.ubs_restart_flag = True

        self.add_stress_to_vm(self.vm_list[1], 72)
        self.add_stress_to_vm(self.vm_list[0], 72)
        wait_time = 0
        flag = False
        while wait_time < 900:
            node1_numa0_mem_used_size = self.get_node_numa_used("node1", "Node 0")
            node1_numa1_mem_used_size = self.get_node_numa_used("node1", "Node 1")
            if node1_numa0_mem_used_size > 5735 and node1_numa1_mem_used_size > 2868:
                flag = True
                break
            else:
                wait_time = wait_time + 30
                time.sleep(30)
        self.assertEqual(flag, True, "Node1 numa0 or Node1 numa1 used mem is unexpected")

        self.logInfo("启动加压节点ubs scheduler agent")
        start_res = self.start_ubs_scheduler_agent(self.master)
        self.assertTrue(start_res, '启动master ubs scheduler agent进程失败')
        self.ubs_restart_flag = False

        self.logStep("E1.环境中VM1、VM2存在串行迁移操作")
        wait_time = 0
        flag = False
        agent_hostname = self.agent.getHostname()
        while wait_time < 2400:
            server_detail_vm01 = client.get_server_detail(self.controller, self.vm_list[0].name)
            server_detail_vm02 = client.get_server_detail(self.controller, self.vm_list[1].name)
            if server_detail_vm02['OS-EXT-SRV-ATTR:host'] == agent_hostname:
                flag = True
                break
            elif server_detail_vm01['status'] == "MIGRATING":
                self.logError("test_vm_migrate_015_01 migrate is unexpected")
                break
            else:
                wait_time = wait_time + 30
                time.sleep(30)
        self.assertEqual(flag, True, "test_vm_migrate_015_01 migrate failed")