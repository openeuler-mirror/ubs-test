import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemShmDeleteSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_shm_delete_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口删除共享内存成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_shm_create接口创建共享内存，参数合法
        S2.调用ubse_mem_shm_delete接口删除共享内存,传入S1的name
        S3.再次调用ubse_mem_shm_delete接口删除共享内存,传入S1的name
    ExpectedResult:
        E1.内存创建成功
        E2.内存删除成功
        E3.内存删除失败
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
        
        self.logStep("清理内存")
        self.clear_all_borrow_mem()

    def test_tc_mem_shm_delete_sdk_001(self):

        self.logStep("S1.调用ubse_mem_shm_create接口创建共享内存，参数合法")
        region = ",".join([node.nodeId for node in self.nodes])
        name = "mem_shm_delete_sdk_001"
        res = self.mem_shm_borrow(node=self.nodes[0], option="shm_create", name=name, slot_ids=region)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.调用ubse_mem_shm_delete接口删除共享内存,传入S1的name")
        res = self.mem_shm_borrow(node=self.nodes[0], option="shm_delete", name=name)

        self.logStep("E2.内存删除成功")
        self.assertTrue(res, "内存删除失败")

        self.logStep("S3.再次调用ubse_mem_shm_delete接口删除共享内存,传入S1的name")
        res = self.mem_shm_borrow(node=self.nodes[0], option="shm_delete", name=name)

        self.logStep("E3.内存删除失败")
        self.assertFalse(res, "内存删除成功")
