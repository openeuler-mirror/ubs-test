import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemFdGetSdk002(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_fd_get_sdk_002
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口查询本节点fd形态远端内存信息成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.在节点1调用ubse_mem_fd_create接口，参数合法
        S2.在节点1调用ubse_mem_fd_get查询S1中创建的内存，检查是否查询成功
        S3.在节点2调用ubse_mem_fd_get查询S1中创建的内存，检查是否查询成功
        S4.在节点1调用ubse_mem_fd_delete接口删除指定fd远端内存,传入S1的name
        S5.在节点1调用ubse_mem_fd_get，传入S1的name，查看返回信息是否正确
    ExpectedResult:
        E1.内存创建成功
        E2.查询成功
        E3.查询失败，无S1中创建的内存
        E4.内存删除成功
        E5.账本不包含S1的内存

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

    def test_tc_fd_get_func_001(self):

        name = "mem_fd_get_sdk_002"
        self.logStep("S1.在节点1调用ubse_mem_fd_create创建内存，检查是否创建成功")
        res = self.mem_fd_borrow(self.nodes[0], name=name)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.在节点1调用ubse_mem_fd_get查询S1中创建的内存，检查是否查询成功")
        command = f"fd_get {name}"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)
        self.logStep("E2.查询成功")
        self.assertIn("Successfully", borrow_result, "账本查看失败")
        self.assertIn(name, borrow_result, "账本查看失败")

        self.logStep("S3.在节点2调用ubse_mem_fd_get查询S1中创建的内存，检查是否查询成功")
        command = f"fd_get {name}"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[1], command=command)
        self.logStep("E3.查询失败，无S1中创建的内存")
        self.assertIn("UBSE_ERR_NOT_EXIST", borrow_result,"账本查看成功")
        self.assertIn("Borrow relationship does not exist", borrow_result, "账本查看成功")

        self.logStep("S4.调用ubse_mem_fd_delete接口删除指定fd远端内存")
        res = self.mem_fd_borrow(self.nodes[0], masking=False, name=name)
        self.logStep("E4.内存删除成功")
        self.assertTrue(res, "内存删除失败")

        self.logStep("S5.在节点2调用ubse_mem_fd_get查询S1中创建的内存，检查是否查询成功")
        command = f"fd_get {name}"
        borrow_result = self.mem_borrow_common_result(node=self.nodes[0], command=command)

        self.logStep("E5.账本不包含S1的内存")
        self.assertIn("UBSE_ERR_NOT_EXIST", borrow_result,"账本中仍包含S1的内存")
        self.assertIn("Borrow relationship does not exist", borrow_result,"账本中仍包含S1的内存")
