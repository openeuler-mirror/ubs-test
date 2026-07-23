import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemShmListSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_shm_list_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口查询共享内存列表
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_shm_create接口创建共享内存，参数合法
        S2.再次调用ubse_mem_shm_create接口创建共享内存，参数合法
        S3.调用ubse_mem_shm_list，查看返回信息是否正确
        S4.调用ubse_mem_shm_attach接口映射共享内存，传入name为S1创建的name
        S5.调用ubse_mem_shm_list，查看返回信息是否正确
        S6.调用ubse_mem_shm_delete接口删除共享内存,传入name为S2创建的name
        S7.调用ubse_mem_shm_list，查看返回信息是否正确
    ExpectedResult:
        E1.内存创建成功
        E2.内存创建成功
        E3.账本查看成功，存在2条借用信息
        E4.内存映射成功
        E5.账本查看成功，映射的内存账本中存在import信息
        E6.内存删除成功
        E7.账本查看成功，存在1条借用信息

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

    def test_tc_mem_shm_list_sdk_001(self):

        self.logStep("S1.调用ubse_mem_shm_create接口创建共享内存，参数合法")
        region = ",".join([node.nodeId for node in self.nodes])
        name1 = "mem_shm_list_sdk_001_01"
        res1 = self.mem_shm_borrow(node=self.nodes[0], option="shm_create", name=name1, slot_ids=region)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res1, "内存创建失败")

        self.logStep("S2.再次调用ubse_mem_shm_create接口创建共享内存，参数合法")
        name2 = "mem_shm_list_sdk_001_02"
        res2 = self.mem_shm_borrow(node=self.nodes[0], option="shm_create", name=name2, slot_ids=region)

        self.logStep("E2.内存创建成功")
        self.assertTrue(res2, "内存创建失败")

        self.logStep("S3.调用ubse_mem_shm_list，查看返回信息是否正确")
        command = "shm_list"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E3.账本查看成功，存在2条借用信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn("Found 2 shm memory resources", borrow_result)

        self.logStep("S4.调用ubse_mem_shm_attach接口映射共享内存，传入name为S1创建的name")
        res = self.mem_shm_borrow(self.nodes[0], option="shm_attach", name=name1)

        self.logStep("E4.内存映射成功")
        self.assertEqual(res, True, "共享内存attach失败")

        self.logStep("S5.调用ubse_mem_shm_list，查看返回信息是否正确")
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E5.账本查看成功，映射的内存账本中存在import信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn(f"import_node={self.nodes[0].nodeId}", borrow_result)

        self.logStep("S6.调用ubse_mem_shm_delete接口删除共享内存,传入name为S2创建的name")
        res = self.mem_shm_borrow(node=self.nodes[0], option="shm_delete", name=name2)

        self.logStep("E6.内存删除成功")
        self.assertTrue(res, "查看失败")

        self.logStep("S7.调用ubse_mem_shm_list，查看返回信息是否正确")
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E7.账本查看成功，存在1条借用信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn("Found 1 shm memory resources", borrow_result)

