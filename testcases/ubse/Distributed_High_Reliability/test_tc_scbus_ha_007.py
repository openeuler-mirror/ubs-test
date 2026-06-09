"""
Migrated from legacy: tc_scbus_ha_007
"""
import pytest
import time
from typing import Any, Dict, List

from libs.modules.ubse.basecase.distributed_high_reliability_basecase import (
    Distributed_High_Reliability_BaseCase
)
from libs.utils.logger_compat import Log

@pytest.mark.smoke
class TestTcScbusHa007(Distributed_High_Reliability_BaseCase):
    """
    CaseNumber:
        test_tc_scbus_ha_007
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        验证8P场景4节点同时启动有唯一主
    PreCondition:
        P1.所有节点节点scbus-daemon进程均退出
    TestStep:
        S1.同时启动4节点进程
        S2.检查集群中是否存在唯一主备
    ExpectedResult:
        E2.是
    """

    def setup_method(self):
        
        self.logStep("P1.所有节点scbus-daemon进程均退出")
        res = self.ubse_process_ops.stop_all_ubse_without_waiting(self.nodes)
        self.assertTrue(res)

    def teardown_method(self):
        
        pass

    def test_tc_scbus_ha_007(self):

        self.logStep("S1.同时启动4节点进程")
        res = self.ubse_process_ops.start_all_ubse_without_waiting(self.nodes)
        self.assertTrue(res)

        self.logStep("S2.检查集群中是否存在唯一主备")
        self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        self.logInfo("E2.是")
