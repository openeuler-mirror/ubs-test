"""
Migrated from legacy: tc_mem_numa_list_sdk_001
"""
import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemNumaListSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_numa_list_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口批量查询本节点numa形态远端内存成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_numa_create接口创建numa内存，参数合法
        S2.调用ubse_mem_numa_list，查看返回信息是否正确
        S3.调用ubse_mem_numa_create接口创建numa内存，参数合法
        S4.调用ubse_mem_numa_list，查看返回信息是否正确
        S5.调用ubse_mem_numa_delete接口删除指定numa远端内存,传入S1的name
        S6.调用ubse_mem_numa_list，查看返回信息是否正确
        S7.调用ubse_mem_numa_delete接口删除指定numa远端内存,传入S3的name
        S8.调用ubse_mem_numa_list，查看返回信息是否正确
    ExpectedResult:
        E1.内存创建成功
        E2.账本查看成功，存在1条借用信息
        E3.内存创建成功
        E4.账本查看成功，存在2条借用信息
        E5.内存删除成功
        E6.账本查看成功，存在1条借用信息
        E7.内存删除成功
        E8.账本查看成功，没有借用信息
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

    def test_tc_mem_numa_list_sdk_001(self):

        self.logStep("S1.调用ubse_mem_numa_create接口创建numa内存，参数合法")
        res = self.mem_numa_borrow(node=self.nodes[0], name="mem_numa_list_sdk_001_1")

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.调用ubse_mem_numa_list，查看返回信息是否正确")
        command = "numa_list"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E2.账本查看成功，存在1条借用信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn("Found 1 Numa-form memory resources", borrow_result)

        self.logStep("S3.调用ubse_mem_numa_create接口创建numa内存，参数合法")
        res = self.mem_numa_borrow(node=self.nodes[0], name="mem_numa_list_sdk_001_2")

        self.logStep("E3.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S4.调用ubse_mem_numa_list，查看返回信息是否正确")
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E4.账本查看成功，存在2条借用信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn("Found 2 Numa-form memory resources", borrow_result)

        self.logStep("S5.调用ubse_mem_numa_delete接口删除指定numa远端内存,传入S1的name")
        res = self.mem_numa_borrow(
            node=self.nodes[0], name="mem_numa_list_sdk_001_1", masking=False
        )

        self.logStep("E5.内存删除成功")
        self.assertTrue(res, "查看失败")

        self.logStep("S6.调用ubse_mem_numa_list，查看返回信息是否正确")
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E6.账本查看成功，存在1条借用信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn("Found 1 Numa-form memory resources", borrow_result)

        self.logStep("S7.调用ubse_mem_numa_delete接口删除指定numa远端内存,传入S3的name")
        res = self.mem_numa_borrow(node=self.nodes[0], name="mem_numa_list_sdk_001_2", masking=False)

        self.logStep("E7.内存删除成功")
        self.assertTrue(res, "内存删除失败")

        self.logStep("S8.调用ubse_mem_numa_list，查看返回信息是否正确")
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E8.账本查看成功，没有借用信息")
        self.assertIn("Successfully", borrow_result)
        self.assertIn("Found 0 Numa-form memory resources", borrow_result)
