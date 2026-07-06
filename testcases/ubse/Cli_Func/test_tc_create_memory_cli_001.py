"""
Migrated from legacy: tc_memory_sdk_cli_002
"""

import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.smoke
class TestTcCreateMemoryCli001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_create_memory_cli_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证cli创建内存后，内存sdk功能正常
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubsectl create memory分别创建fd、numa、共享内存
        S2.调用ubsectl display memory，检查账本是否正常
    ExpectedResult:
        E1.内存创建成功
        E2.账本正常
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

    def test_tc_create_memory_cli_001(self):

        self.logStep("S1.使用cli分别创建fd、numa、共享内存")
        # 创建FD内存
        res_fd, mem_info = self.cli_api.create_fd_memory(self.nodes[0], size="128M", name="create_memory_cli_001_fd")
        # 创建NUMA内存
        res_numa, mem_info = self.cli_api.create_numa_memory(self.nodes[0], size="128M", name="create_memory_cli_001_numa")
        # 创建共享内存
        res_shm, mem_info = self.cli_api.create_shm_memory(self.nodes[0], size="128M",
                                                 name="create_memory_cli_001_shm", region="1,2")

        self.logStep("E1.内存创建成功")
        self.assertTrue(res_fd, "创建FD内存失败")
        self.assertTrue(res_numa, "创建NUMA内存失败")
        self.assertTrue(res_shm, "创建共享内存失败")


        self.logStep("S2.调用ubsectl display memory，检查账本是否正常")
        accounts = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E2.账本正常")
        fd_found = any(acc.get("name") == "create_memory_cli_001_fd" for acc in accounts)
        self.assertTrue(fd_found, "FD内存账本记录缺失")

        numa_found = any(acc.get("name") == "create_memory_cli_001_numa" for acc in accounts)
        self.assertTrue(numa_found, "NUMA内存账本记录缺失")

        shm_found = any(acc.get("name") == "create_memory_cli_001_shm" for acc in accounts)
        self.assertTrue(shm_found, "共享内存账本记录缺失")