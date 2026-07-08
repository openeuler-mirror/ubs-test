import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcUbseMemNumaStatGetSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_ubse_mem_numastat_get_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口查询指定节点numa信息成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubs_mem_numastat_get接口查询，传入node_id 1.
        S2.调用ubs_mem_numastat_get接口查询，传入node_id 1000.
    ExpectedResult:
        E1.返回成功
        E2.返回成功,uma信息为空
    """


    def setup_method(self):

        self.logStep("P1.ubse进程已启动")
        self.master_node, self.standby_node, _ = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        self.logStep("P2.节点集群状态为ok")
        for node in self.nodes:
            node_status = self.get_node_memory_status(node.nodeId)
            self.assertEqual(node_status, "ok", "内存状态未就绪")
        self.clear_all_borrow_mem()
    def teardown_method(self):
        
        pass

    def test_tc_ubse_mem_numastat_get_sdk_001(self):

        self.logStep("S1.调用ubs_mem_numastat_get接口查询，传入node_id 1.")
        for node in self.nodes:
            sdk_res = {}
            info = self.mem_borrow_common_result(node, f"numa_info {node.nodeId}")
            if "Successfully get numa info" in info:
                sdk_res = self.parse_sdk_numa_info(info.split("Successfully get numa info")[1])
            env_res = self.get_env_numa_info(node)
            self.logInfo(f"node{node.nodeId} sdk:{sdk_res}")
            self.logInfo(f"node{node.nodeId} env:{env_res}")
            self.assertEqual(sdk_res, env_res)
        self.logStep("E1.返回成功")

        self.logStep("S2.调用ubs_mem_numastat_get接口查询，传入node_id 1000.")
        res = self.mem_borrow_common_result(self.master_node, f"numa_info 1000")
        self.logStep("E2.返回成功,uma信息为空")
        self.assertNotIn("ubse_numa_mem_info", res)
