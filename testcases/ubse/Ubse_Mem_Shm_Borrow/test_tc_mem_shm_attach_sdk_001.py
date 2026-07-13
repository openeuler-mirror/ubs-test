import pytest
from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemShmAttachSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_shm_attach_sdk_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        验证sdk接口映射共享内存name合法映射成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_shm_create接口创建共享内存，参数合法
        S2.查看内存账本信息：ubsectl display memory -t borrow_detail
        S3.各节点均调用ubse_mem_shm_attach接口映射共享内存，传入name为S1创建的name
        S4.查看内存账本信息：ubsectl display memory -t borrow_detail
    ExpectedResult:
        E1.内存创建成功
        E2.查到创建的内存信息，consumer为空
        E3.内存映射成功
        E4.账本信息正常，consumer包含各已映射节点
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

    def test_tc_mem_shm_attach_sdk_001(self):
        
        self.logStep("S1.调用ubse_mem_shm_create接口创建共享内存，参数合法")
        region = ",".join([node.nodeId for node in self.nodes])
        name = "mem_shm_attach_sdk_001"
        res = self.mem_shm_borrow(node=self.nodes[0], option="shm_create", name=name, slot_ids=region)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.查看内存账本信息：ubsectl display memory -t borrow_detail")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        consumer = self.get_consumer_by_share(account_list=mem_borrow_details, share_name=name)

        self.logStep("E2.账本查看成功，consumer为空")
        self.assertEqual(consumer, "", "consumer不为空")

        self.logStep("S3.各节点均调用ubse_mem_shm_attach接口映射共享内存，传入name为S1创建的name")
        results = []
        for node in self.nodes:
            res = self.mem_shm_borrow(node=node, name=name, option="shm_attach")
            results.append((node.nodeId, res))

        self.logStep("E3.内存映射成功")
        for node_id, result in results:
            self.assertTrue(result, f"节点{node_id} attach失败")

        self.logStep("S4.查看内存账本信息：ubsectl display memory -t borrow_detail")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])
        consumer = self.get_consumer_by_share(account_list=mem_borrow_details, share_name=name)

        self.logStep("E4.账本信息正常，consumer包含各已映射节点")
        for node in self.nodes:
            self.assertIn(node.nodeId, consumer, f"未包含节点{node.nodeId}信息")