"""
Migrated from legacy: tc_memory_sdk_cli_001
"""

import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.smoke
class TestTcAttachMemorySdkCli001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_attach_memory_cli_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证导入共享内存cli功能正常
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubsectl create memory创建共享内存
        S2.调用ubsectl display memory，检查账本是否正常
        S3.调用ubsectl attach memory 映射共享内存，检查是否成功
        S4.调用ubsectl display memory，检查账本是否正常
        S5.调用ubsectl detach memory 解除映射，检查是否成功
        S6.调用ubsectl display memory，检查账本是否正常
    ExpectedResult:
        E1.内存创建成功
        E2.账本正常
        E3.映射成功
        E4.账本正常
        E5.解除映射成功
        E6.账本正常
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

    def test_tc_attach_memory_cli_001(self):

        name = "attach_memory_cli_001"
        self.logStep("S1.调用ubsectl create memory创建共享内存")
        res_shm = self.cli_api.create_shm_memory(self.nodes[0], size="128M", name=name,region="1,2")

        self.logStep("E1.内存创建成功")
        self.assertTrue(res_shm, "创建共享内存失败")

        self.logStep("S2.调用ubsectl display memory，检查账本是否正常")
        accounts = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E2.账本正常")
        shm_found = any(acc.get("name") == name for acc in accounts)
        self.assertTrue(shm_found, "共享内存账本记录缺失")
        self.logStep("E2.账本正常")

        self.logStep("S3.调用ubsectl attach memory 映射共享内存，检查是否成功")
        res_attach = self.cli_api.attach_shm_memory(self.nodes[0], name=name)
        self.assertTrue(res_attach, "映射共享内存失败")
        self.logStep("E3.映射成功")

        self.logStep("S4.调用ubsectl display memory，检查账本是否正常")
        accounts = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E4.账本正常")
        target_account = next((acc for acc in accounts if acc.get("name") == name), None)
        self.assertIsNotNone(target_account, f"未找到name为{name}的账本记录")
        self.assertTrue(target_account.get("borrow_node"), f"name为{name}的账本borrow_node为空")

        self.logStep("S5.调用ubsectl detach memory 解除映射，检查是否成功")
        res_detach = self.cli_api.detach_shm_memory(self.nodes[0], name=name)

        self.logStep("E5.解除映射成功")
        self.assertTrue(res_detach, "解除映射失败")

        self.logStep("S6.调用ubsectl display memory，检查账本是否正常")
        accounts = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E6.账本正常")
        target_account = next((acc for acc in accounts if acc.get("name") == name), None)
        self.assertIsNotNone(target_account, f"未找到name为{name}的账本记录")
        self.assertFalse(target_account.get("borrow_node"),f"name为{name}的账本borrow_node不为空")