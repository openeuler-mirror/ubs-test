import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcDisplayMemoryCli(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        tc_display_memory_cli
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证查询池化信息CLI可用长短选项下发
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
        P3.存在numa，fd，共享内存
    TestStep:
        S1.下发ubsectl display memory -t node_borrow命令，检查是否查询成功，检查借出节点信息是否正确，借出总量是否正确
        S2.下发ubsectl display memory -t borrow_detail命令，检查是否查询成功，检查各返回字段信息是否正确
        S3.下发ubsectl display memory -t node_lend命令，检查是否查询成功，检查借入节点信息是否正确，借入总量是否正确
        S4.下发ubsectl display memory --type node_borrow命令，检查是否查询成功,检查借出节点信息是否正确，借出总量是否正确
        S5.下发ubsectl display memory --type borrow_detail命令，检查是否查询成功，检查各返回字段信息是否正确
        S6.下发ubsectl display memory --type node_lend命令，检查是否查询成功,检查借入节点信息是否正确，借入总量是否正确
        S7.下发ubsectl display memory -t config命令，检查是否查询成功，检查各返回字段信息是否正确
        S8.下发ubsectl display memory --type config命令，检查是否查询成功，检查各返回字段信息是否正确
        S9.下发ubsectl display memory -t numa_status命令，检查是否查询成功，检查各返回字段信息是否正确
        S10.下发ubsectl display memory --type numa_status命令，检查是否查询成功，检查各返回字段信息是否正确
    ExpectedResult:
        E1.查询成功，借出节点信息正确，总量正确
        E2.查询成功，各返回字段信息正确
        E3.查询成功，借入节点信息正确，总量正确
        E4.查询成功，借出节点信息正确，总量正确
        E5.查询成功，各返回字段信息正确
        E6.查询成功，借入节点信息正确，总量正确
        E7.各返回字段信息是否正确
        E8.各返回字段信息是否正确
        E9.各返回字段信息是否正确
        E10.各返回字段信息是否正确
    """

    def setup_method(self):
        self.logStep("P1.ubse进程已启动")
        self.master_node, self.standby_node, _ = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)

        self.logStep("P2.节点集群状态为ok")
        for node in self.nodes:
            node_status = self.get_node_memory_status(node.nodeId)
            self.assertEqual(node_status, "ok", "内存状态未就绪")
        self.clear_all_borrow_mem()

        self.logStep("P3.存在numa，fd，共享内存")
        self.slot_ids = ",".join([node.nodeId for node in self.nodes])
        res = self.mem_fd_borrow(self.master_node, name="display_memory_cli_fd", size="256M")
        res &= self.mem_numa_borrow(self.master_node, name="display_memory_cli_numa", size="256M")
        res &= self.mem_shm_borrow(
            self.master_node,
            name="display_memory_cli_shm",
            size="256M",
            slot_ids=self.slot_ids,
            proviers=self.master_node.nodeId,
        )
        self.assertEqual(res, True)

    def teardown_method(self):
        self.logStep("清除所有内存")
        self.clear_all_borrow_mem()

    def test_tc_display_memory_cli(self):

        total_borrow_size = 256 * 2
        self.logStep(
            "S1.下发ubsectl display memory -t node_borrow命令，检查是否查询成功，检查借出节点信息是否正确，借出总量是否正确"
        )
        node_borrows = self.cli_api.display_memory(self.nodes[0], "node_borrow")
        self.assertEqual(int(node_borrows[0].get("size")), total_borrow_size)
        self.logStep("E1.查询成功，借出节点信息正确，总量正确")

        self.logStep(
            "S2.下发ubsectl display memory -t borrow_detail命令，检查是否查询成功，检查各返回字段信息是否正确"
        )
        borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        self.assertEqual(len(borrow_details), 3)
        for borrow_detail in borrow_details:
            self.assertEqual(int(borrow_detail.get("lend_size")), 256)
            self.assertEqual(borrow_detail.get("status"), "done")
        self.logStep("E2.查询成功，各返回字段信息正确")

        self.logStep(
            "S3.下发ubsectl display memory -t node_lend命令，检查是否查询成功，检查借入节点信息是否正确，借入总量是否正确"
        )
        node_lends = self.cli_api.display_memory(self.nodes[0], "node_lend")
        self.assertEqual(int(node_lends[0].get("size")), total_borrow_size)
        self.logStep("E3.查询成功，借入节点信息正确，总量正确")

        self.logStep(
            "S4.下发ubsectl display memory --type node_borrow命令，检查是否查询成功,检查借出节点信息是否正确，借出总量是否正确"
        )
        node_borrows = self.cli_api.display_memory(
            self.nodes[0], "node_borrow", is_use_long_option=True
        )
        self.assertEqual(int(node_borrows[0].get("size")), total_borrow_size)
        self.logStep("E4.查询成功，借出节点信息正确，总量正确")

        self.logStep(
            "S5.下发ubsectl display memory --type borrow_detail命令，检查是否查询成功，检查各返回字段信息是否正确"
        )
        borrow_details = self.cli_api.display_mem_borrow_detail(
            self.nodes[0], is_use_long_option=True
        )
        self.assertEqual(len(borrow_details), 3)
        for borrow_detail in borrow_details:
            self.assertEqual(int(borrow_detail.get("lend_size")), 256)
            self.assertEqual(borrow_detail.get("status"), "done")
        self.logStep("E5.查询成功，各返回字段信息正确")

        self.logStep(
            "S6.下发ubsectl display memory --type node_lend命令，检查是否查询成功,检查借入节点信息是否正确，借入总量是否正确"
        )
        node_lends = self.cli_api.display_memory(
            self.nodes[0], "node_lend", is_use_long_option=True
        )
        self.assertEqual(int(node_lends[0].get("size")), total_borrow_size)
        self.logStep("E6.查询成功，借入节点信息正确，总量正确")

        self.logStep(
            "S7.下发ubsectl display memory -t config命令，检查是否查询成功，检查各返回字段信息是否正确"
        )
        islenders = self.cli_api.display_memory(self.nodes[0], "config")
        for islender in islenders:
            self.assertEqual(islender.get("isLender"), "true")
        self.logStep("E7.各返回字段信息是否正确")

        self.logStep(
            "S8.下发ubsectl display memory --type config命令，检查是否查询成功，检查各返回字段信息是否正确"
        )
        islenders = self.cli_api.display_memory(self.nodes[0], "config", is_use_long_option=True)
        for islender in islenders:
            self.assertEqual(islender.get("isLender"), "true")
        self.logStep("E8.各返回字段信息是否正确")

        self.logStep(
            "S9.下发ubsectl display memory -t numa_status命令，检查是否查询成功，检查各返回字段信息是否正确"
        )
        numa_statuses = self.cli_api.display_memory(self.nodes[0], "numa_status")
        self.assertNotEqual(numa_statuses, [])
        self.logStep("E9.各返回字段信息是否正确")

        self.logStep(
            "S10.下发ubsectl display memory --type numa_status命令，检查是否查询成功，检查各返回字段信息是否正确"
        )
        numa_statuses = self.cli_api.display_memory(
            self.nodes[0], "numa_status", is_use_long_option=True
        )
        self.assertNotEqual(numa_statuses, [])
        self.logStep("E10.各返回字段信息是否正确")
