from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.common.service_common import exec_service
from libs.modules.ubsvirt.model.model import VMResource


class TestVirtualMsAgent010(OpenStackBaseCase):
    """
    CaseNumber:
        test_virtual_ms_agent_010
    RunLevel:
        Level 2
    EnvType:
        None
    CaseName:
        验证Ubs Scheduler Agent执行内存借用，UBSE服务异常导致执行内存借用失败
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.OpenStack/UBSE功能正常无异常
        P3.碎片场景
        P4.node1分配13G大页，node2分配4G大页，node1创建8G虚机
    TestStep:
        S1.构造UBSE服务异常
        S2.node1匀一匀创建5G虚机
        S3.UBSE恢复后，node1匀一匀创建5G虚机
    ExpectedResult:
        E1.日志记录失败信息，Ubs Scheduler Agent组件状态正常
        E2.虚机创建失败
        E3.虚机创建成功，发生内存借用
    """

    def setup_method(self):
        self.logStep("P1.环境中存在2个及以上节点")
        ubse_node_count = len(self.ubse_node_list)
        self.assertGreaterEqual(ubse_node_count, 2, "环境中不存在2个及以上节点")

        self.wait_time = 600
        self.ubs_agent_log_path = '/var/log/ubs_scheduler/ubs-scheduler-agent.log'
        self.ubs_agent_error_log = 'Get node info failed'

    def teardown_method(self):
        exec_service(self.agent, "restart", "ubse")
        self.wait_ubse_status(self.master, self.wait_time, 30)

        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_virtual_ms_agent_010(self, get_topo_path):
        self.prepare_topo(str(get_topo_path("test_virtual_ms_agent_010")))

        self.logStep("S1.构造UBSE服务异常")
        log_start_time = client.get_date_timestamp(self.agent)
        exec_service(self.agent, "stop", "ubse")

        self.logStep("E1.日志记录失败信息，Ubs Scheduler Agent组件状态正常")
        log = client.get_ms_log_info(self.agent, log_start_time, self.ubs_agent_error_log,
                                     self.ubs_agent_log_path, "50")
        self.assertIsNotNone(log, "get_ms_log_info returned None, expected log containing error message")
        self.assertIn(self.ubs_agent_error_log, log)

        service_status = self.get_service_status(self.agent, "ubs-scheduler-agent")
        self.assertEqual(service_status, "running", "ubs-scheduler-agent service is not running")

        self.logStep("S2.node1匀一匀创建5G虚机")
        vm_5g_01 = VMResource("vm_5g_01", "openEuler-22.03-everything", 5120, "node1",
                           False, 2, False, True, 25)
        self.create_server(vm_5g_01, "ERROR")

        self.logStep("E2.虚机创建失败")
        status_detail = self.wait_server_target_status('vm_5g_01', {'status': 'ERROR'})
        self.assertEqual(status_detail['status'], 'ERROR')

        self.logStep("S3.UBSE恢复后，node1匀一匀创建5G虚机")
        exec_service(self.agent, "restart", "ubse")
        self.wait_ubse_status(self.master, self.wait_time, 30)

        vm_5g_02 = VMResource("vm_5g_02", "openEuler-22.03-everything", 5120, "node1",
                           False, 2, False, True, 25)
        self.create_server(vm_5g_02, "ACTIVE")

        self.logStep("E3.虚机创建成功，发生内存借用")
        status_detail = self.wait_server_target_status('vm_5g_02', {'status': 'ACTIVE'})
        self.assertEqual(status_detail['status'], 'ACTIVE')

        flag = self.check_borrowed_numa_size("node1", 1000, "100")
        self.assertTrue(flag, "Mem borrow failed")
