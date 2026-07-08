import pytest
from typing import Any, Dict, List

from libs.modules.ubse.basecase.distributed_high_reliability_basecase import (
    Distributed_High_Reliability_BaseCase
)
from libs.utils.logger_compat import Log

@pytest.mark.smoke
class TestTcScbusHa026(Distributed_High_Reliability_BaseCase):
    """
    CaseNumber:
        test_tc_scbus_ha_026
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        验证主节点进程异常退出备升级为主
    PreCondition:
        P1.所有节点ubse进程已启动，主备已经完成仲裁
    TestStep:
        S1.停止主节点进程
        S2.备节点通过命令行ubsectl display cluster查询，master角色是否为原备节点
        S3.启动原主节点的进程，检查是否以agent角色加入集群
    ExpectedResult:
        E2.是
        E3.是
    """

    def setup_method(self):
        
        self.tcStep("P1.所有节点ubse进程已启动，主备已经完成仲裁")
        self.master_node, self.standby_node, self.agent_nodes = (
            self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        )
        self.logInfo(f"主节点nodeId为：{self.master_node.nodeId}")
        self.logInfo(f"备节点nodeId为：{self.standby_node.nodeId}")
        self.logInfo(f"从节点nodeId为： {[node.nodeId for node in self.agent_nodes]}")

    def teardown_method(self):
        
        pass

    def test_tc_scbus_ha_026(self):

        self.tcStep("S1.停止主节点进程")
        res = self.ubse_process_ops.stop_ubse(self.master_node)
        self.assertEqual(res, True)

        self.tcStep("S2.备节点通过命令行ubsectl display cluster查询，master角色是否为原备节点")
        self.master_nodeId = self.wait_master_standby_loaded(
            self.standby_node, "master", self.standby_node.nodeId
        )
        self.assertEqual(self.master_nodeId, self.standby_node.nodeId)
        self.logInfo("E2.是")

        self.tcStep("S3.启动原主节点的进程，检查是否以agent角色加入集群")
        pid = self.ubse_process_ops.start_ubse(self.master_node)
        self.assertNotEqual(pid, False)
        self.new_master_node, self.new_standby_node, self.new_agent_nodes = (
            self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        )
        self.assertIn(self.master_node, self.new_agent_nodes)
        self.logInfo("E3.是")
        self.logInfo(f"新主节点nodeId为：{self.new_master_node.nodeId}")
        self.logInfo(f"新备节点nodeId为：{self.new_standby_node.nodeId}")
        self.logInfo(f"新从节点nodeId为： {[node.nodeId for node in self.new_agent_nodes]}")
