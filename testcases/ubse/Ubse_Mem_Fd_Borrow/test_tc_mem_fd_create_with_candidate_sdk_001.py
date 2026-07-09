import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemFdCreateWithCandidateSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_fd_create_with_candidate_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口指定候选节点创建fd形态的远端内存成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_fd_create_with_candidate接口，参数合法
        S2.查看内存账本信息：ubsectl display memory -t borrow_detail
S3.调用ubse_mem_fd_delete接口删除指定fd远端内存
        S4.查看内存账本信息：ubsectl display memory -t borrow_detail
    ExpectedResult:
        E1.内存创建成功
        E2.查到创建的内存信息
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

    def test_tc_fd_create_with_candidate_test_name_001(self):

        self.logStep("S1.调用ubse_mem_fd_create_with_candidate接口，参数合法")
        name = "mem_fd_create_with_candidate_sdk_001"
        res = self.mem_fd_borrow(node=self.nodes[0], option="create_with_candidate",
                                   name=name, slot_ids="1,2")
        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.查看内存账本信息：ubsectl display memory -t borrow_detail")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        self.logInfo(f"mem_borrow_details={mem_borrow_details}")

        self.logStep("E2.查到创建的内存信息")
        self.assertTrue(any(d.get("name") == name for d in mem_borrow_details), f"不存在name为{name}的内存信息")

        self.logStep("S3.调用ubse_mem_fd_delete接口删除指定numa远端内存")
        res = self.mem_fd_borrow(node=self.nodes[0], name=name, masking=False)

        self.logStep("E3.内存删除成功")
        self.assertTrue(res, "内存删除失败")

        self.logStep("S4.查看内存账本信息：ubsectl display memory -t borrow_detail")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        self.logInfo(f"mem_borrow_details={mem_borrow_details}")

        self.logStep("E4.账本不包含S1的内存")
        self.assertFalse(any(d.get("name") == name for d in mem_borrow_details), f"仍存在name为{name}的内存信息")
