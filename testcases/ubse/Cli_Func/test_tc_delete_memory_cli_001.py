import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.smoke
class TestTcDeleteMemoryCli001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_delete_memory_cli_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证归还内存CLI可用长短选项下发
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
        P3.已存在内存借用
    TestStep:
        S1.调用ubsectl delete memory -n 命令，检查是否删除成功
        S2.调用ubsectl delete memory --name 命令，检查是否删除成功
        S3.查询是否不存在内存借用账本
    ExpectedResult:
        E1.删除成功
        E2.删除成功
        E3.无内存借用账本
    """

    def setup_method(self):

        self.logStep("P1.ubse进程已启动")
        self.master_node, self.standby_node, _ = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)

        self.logStep("P2.节点集群状态为ok")
        for node in self.nodes:
            node_status = self.get_node_memory_status(node.nodeId)
            self.assertEqual(node_status, "ok", "内存状态未就绪")
        self.clear_all_borrow_mem()

        self.logStep("P3.已存在内存借用")
        res = self.mem_fd_borrow(self.master_node, name="delete_memory_cli_001_fd")
        self.assertEqual(res, True)
        res = self.mem_numa_borrow(self.master_node, name="delete_memory_cli_001_numa")
        self.assertEqual(res, True)
        region = ",".join([node.nodeId for node in self.nodes])
        res = self.mem_shm_borrow(self.master_node, name="delete_memory_cli_001_shm", slot_ids=region)
        self.assertEqual(res, True)

    def teardown_method(self):
        
        self.logStep("清理内存")
        self.clear_all_borrow_mem()

    def test_tc_delete_memory_cli_001(self):

        self.logStep("S1.调用ubsectl delete memory -n 命令，检查是否删除成功")
        res = self.cli_api.delete_memory(self.master_node, name="delete_memory_cli_001_fd", mem_type="fd")

        self.logStep("E1.删除成功")
        self.assertEqual(res, True)

        self.logStep("S2.调用ubsectl delete memory --name 命令，检查是否删除成功")
        res = self.cli_api.delete_memory(self.master_node, name="delete_memory_cli_001_numa",
                                         is_use_long_option=True)

        self.logStep("E2.删除成功")
        self.assertEqual(res, True)
        res = self.cli_api.delete_memory(self.master_node, name="delete_memory_cli_001_shm", mem_type="share")
        self.assertEqual(res, True)

        self.logStep("S3.查询是否不存在内存借用账本")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E3.无内存借用账本")
        self.assertEqual(mem_borrow_details, [], "内存借用账本未清空")

