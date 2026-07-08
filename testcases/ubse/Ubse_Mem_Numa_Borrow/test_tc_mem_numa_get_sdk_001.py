import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemNumaGetSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_numa_get_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口查询本节点numa形态远端内存信息成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_numa_create接口，参数合法
        S2.调用ubse_mem_numa_get，传入S1的name，查看返回信息是否正确
        S3.调用ubse_mem_numa_delete接口删除指定numa远端内存
        S4.调用ubse_mem_numa_get，传入S1的name，查看返回信息是否正确
    ExpectedResult:
        E1.内存创建成功
        E2.账本查看成功
        E3.内存删除成功
        E4.账本不包含S1的内存

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

    def test_tc_mem_numa_get_sdk_001(self):

        self.logStep("S1.调用ubse_mem_numa_create接口，参数正常")
        name = "mem_numa_get_sdk_001"
        res = self.mem_numa_borrow(node=self.nodes[0], name=name)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.调用ubse_mem_numa_get，传入S1的name，查看返回信息是否正确")
        command = "numa_get mem_numa_get_sdk_001"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E2.账本查看成功")
        self.assertIn("Successfully", borrow_result,"账本查看失败")
        self.assertIn(name, borrow_result, "账本查看失败")

        self.logStep("S3.调用ubse_mem_numa_delete接口删除指定numa远端内存")
        res = self.mem_numa_borrow(node=self.nodes[0], masking=False, name=name)

        self.logStep("E3.内存删除成功")
        self.assertTrue(res, "内存删除失败")

        self.logStep("S4.调用ubse_mem_numa_get，传入S1的name，查看返回信息是否正确")
        command = "numa_get mem_numa_get_sdk_001"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E4.账本不包含S1的内存")
        self.assertIn("UBSE_ERR_NOT_EXIST", borrow_result,"账本中仍包含S1的内存")
        self.assertIn("Borrow relationship does not exist", borrow_result,"账本中仍包含S1的内存")
