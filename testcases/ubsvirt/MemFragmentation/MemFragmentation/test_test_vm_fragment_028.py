"""
Migrated from legacy: test_vm_fragment_028

验证UBS Scheduler服务启停和进程拉起功能
"""

import time
import pytest

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmFragment028(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_fragment_028
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证UBS Scheduler服务启停和进程拉起功能
    PreCondition:
        P1、多节点环境，openstack部署成功
        P2、Ubs Scheduler服务正常部署
    TestStep:
        S1、启动服务验证状态
        S2、停止服务验证停止成功
        S3、重启服务验证运行成功
        S4、kill -9 进程后验证服务自动拉起
    ExpectedResult:
        E1、服务启动成功状态为running
        E2、服务停止成功状态为None
        E3、服务重启成功状态为running
        E4、进程被kill后服务自动拉起状态为running
    """

    def setup_method(self):
        self.logStep("P1、多节点环境，openstack部署成功")
        self.logStep("P2、Ubs Scheduler服务正常部署")

    def teardown_method(self):
        self.clear_server()

    def test_vm_fragment_028(self, get_topo_path):
        self.logStep("S1、启动服务：systemctl start ubs-scheduler-agent/ubs-scheduler-controller")
        ubs_scheduler_controller_status = self.get_service_status(self.controller, "ubs-scheduler-controller")
        self.assertEqual(ubs_scheduler_controller_status, "running", "ubs-scheduler-controller is not running")
        ubs_scheduler_agent1_status = self.get_service_status(self.master, "ubs-scheduler-agent")
        self.assertEqual(ubs_scheduler_agent1_status, "running", "ubs-scheduler-agent is not running on master")
        ubs_scheduler_agent2_status = self.get_service_status(self.agent, "ubs-scheduler-agent")
        self.assertEqual(ubs_scheduler_agent2_status, "running", "ubs-scheduler-agent is not running on agent")

        self.logStep("S2、停止服务：systemctl stop ubs-scheduler-controller/ubs-scheduler-agent")
        self.controller.run({'command': ['systemctl stop ubs-scheduler-controller']})
        self.master.run({'command': ['systemctl stop ubs-scheduler-agent']})
        self.agent.run({'command': ['systemctl stop ubs-scheduler-agent']})
        
        wait_time = 0
        while wait_time < 600:
            ubs_scheduler_controller_status = self.get_service_status(self.controller, "ubs-scheduler-controller")
            ubs_scheduler_agent1_status = self.get_service_status(self.master, "ubs-scheduler-agent")
            ubs_scheduler_agent2_status = self.get_service_status(self.agent, "ubs-scheduler-agent")
            if ubs_scheduler_controller_status is None and \
               ubs_scheduler_agent1_status is None and \
               ubs_scheduler_agent2_status is None:
                break
            else:
                wait_time = wait_time + 5
                time.sleep(5)
        
        self.logStep("E2、服务停止成功状态为None")
        self.assertIsNone(ubs_scheduler_controller_status, "ubs-scheduler-controller is still running")
        self.assertIsNone(ubs_scheduler_agent1_status, "ubs-scheduler-agent on master is still running")
        self.assertIsNone(ubs_scheduler_agent2_status, "ubs-scheduler-agent on agent is still running")

        self.logStep("S3、重启服务：systemctl restart ubs-scheduler-controller/ubs-scheduler-agent")
        self.controller.run({'command': ['systemctl restart ubs-scheduler-controller']})
        self.master.run({'command': ['systemctl restart ubs-scheduler-agent']})
        self.agent.run({'command': ['systemctl restart ubs-scheduler-agent']})
        
        wait_time = 0
        while wait_time < 600:
            self.logInfo("查看服务状态：systemctl status ubs-scheduler-controller/ubs-scheduler-agent")
            ubs_scheduler_controller_status = self.get_service_status(self.controller, "ubs-scheduler-controller")
            ubs_scheduler_agent1_status = self.get_service_status(self.master, "ubs-scheduler-agent")
            ubs_scheduler_agent2_status = self.get_service_status(self.agent, "ubs-scheduler-agent")
            if ubs_scheduler_controller_status == "running" and \
               ubs_scheduler_agent1_status == "running" and \
               ubs_scheduler_agent2_status == "running":
                break
            else:
                wait_time = wait_time + 5
                time.sleep(5)
        
        self.logStep("E3、服务重启成功状态为running")
        self.assertEqual(ubs_scheduler_controller_status, "running", "ubs-scheduler-controller is not running")
        self.assertEqual(ubs_scheduler_agent1_status, "running", "ubs-scheduler-agent on master is not running")
        self.assertEqual(ubs_scheduler_agent2_status, "running", "ubs-scheduler-agent on agent is not running")

        self.logStep(
            "S4、关闭进程（kill -9 【进程号】），"
            "查看进程（ps -ef | grep ubs-scheduler-controller/ubs-scheduler-agent），验证服务是否自动拉起进程"
        )
        controller_pid = self.get_ms_controller_pid(self.controller)
        master_pid = self.get_ms_agent_pid(self.master)
        agent_pid = self.get_ms_agent_pid(self.agent)
        
        self.controller.run({'command': [f'kill -9 {controller_pid}']})
        self.master.run({'command': [f'kill -9 {master_pid}']})
        self.agent.run({'command': [f'kill -9 {agent_pid}']})
        
        wait_time = 0
        while wait_time < 600:
            self.logInfo("查看服务状态：systemctl status ubs-scheduler-controller/ubs-scheduler-agent")
            ubs_scheduler_controller_status = self.get_service_status(self.controller, "ubs-scheduler-controller")
            ubs_scheduler_agent1_status = self.get_service_status(self.master, "ubs-scheduler-agent")
            ubs_scheduler_agent2_status = self.get_service_status(self.agent, "ubs-scheduler-agent")
            if ubs_scheduler_controller_status == "running" and \
               ubs_scheduler_agent1_status == "running" and \
               ubs_scheduler_agent2_status == "running":
                break
            else:
                wait_time = wait_time + 5
                time.sleep(5)
        
        self.logInfo("服务状态：systemctl status ubs-scheduler-controller/ubs-scheduler-agent")
        self.assertEqual(ubs_scheduler_controller_status, "running", "ubs-scheduler-controller is not running after kill")
        self.assertEqual(ubs_scheduler_agent1_status, "running", "ubs-scheduler-agent on master is not running after kill")
        self.assertEqual(ubs_scheduler_agent2_status, "running", "ubs-scheduler-agent on agent is not running after kill")