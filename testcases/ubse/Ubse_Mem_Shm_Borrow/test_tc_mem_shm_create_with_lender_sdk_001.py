import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemShmCreateWithLenderSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_shm_create_with_lender_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口指定借出节点创建共享内存成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用shm_create_with_lender接口创建共享内存，参数合法
        S2.查看账本是否正确
        S3.归还内存，查看是否归还成功
    ExpectedResult:
        E1.内存借用成功
        E2.账本信息正确
        E3.内存归还成功，账本为空
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

    def test_tc_mem_shm_create_with_lender_sdk_001(self):

        self.logStep("S1.调用shm_create_with_lender接口创建共享内存，参数合法")
        name = "mem_shm_create_with_lender_sdk_001"
        node_hierarchy = self.build_numa_hierarchy()
        node_id = self.nodes[1].nodeId
        if node_id not in node_hierarchy or not node_hierarchy[node_id]:
            raise RuntimeError("获取numa_status失败")
        socket_id = next(iter(node_hierarchy[node_id].keys()))
        numa_ids = node_hierarchy[node_id][socket_id]
        if len(numa_ids) < 1:
            raise RuntimeError("获取numa_status失败")
        params_dict = {}
        params_dict["lender_slot_id"] = node_id
        params_dict["lender_socket_id"] = socket_id
        params_dict["lender_numa_id"] = numa_ids[0]
        mem_borrow = self.mem_shm_borrow(self.nodes[0], name=name,size="256M",
                                         option="shm_create_with_lender", params_dict=params_dict)

        self.logStep("E1.内存借用成功")
        self.assertTrue(mem_borrow, "创建共享内存失败")

        self.logStep("S2.查看账本是否正确")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E2.账本信息正确")
        self.assertTrue(any(d.get("name", "") == name for d in mem_borrow_details), f"不存在name为{name}的内存信息")

        self.logStep("S3.归还内存，查看是否归还成功")
        mem_borrow = self.mem_shm_borrow(self.nodes[0], option="shm_delete", name=name)
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E3.内存归还成功，账本为空")
        self.assertTrue(mem_borrow, "删除共享内存失败")
        self.assertFalse(any(d.get("name", "") == name for d in mem_borrow_details), f"仍存在name为{name}的内存信息")
