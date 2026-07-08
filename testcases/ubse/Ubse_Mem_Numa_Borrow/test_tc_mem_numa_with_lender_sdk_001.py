import pytest
import random
import string
from typing import Any, Dict, List

from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase
from libs.utils.logger_compat import Log


@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcMemNumaWithLenderSdk001(MEM_Pooling_BaseCase):
    """
    CaseNumber:
        test_tc_mem_numa_with_lender_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口指定借出信息numa形态的远端内存创建成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_mem_numa_create_with_lender接口，参数合法
        S2.查看内存账本信息：ubsectl display memory -t borrow_detail
        S3.调用ubse_mem_numa_delete接口删除指定numa远端内存
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

    def test_tc_mem_numa_with_lender_sdk_001(self):

        self.logStep("S1.调用ubse_mem_numa_create_with_lender接口，参数正常")
        name = "mem_numa_with_lender_sdk_001"
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
        res = self.mem_numa_borrow(self.nodes[0], name=name,
                                   option="create_with_lender", params_dict=params_dict)

        self.logStep("E1.内存创建成功")
        self.assertTrue(res, "内存创建失败")

        self.logStep("S2.查看内存账本信息：ubsectl display memory -t borrow_detail")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E2.查到创建的内存信息")
        self.assertTrue(any(d.get("name") == name for d in mem_borrow_details), f"不存在name为{name}的内存信息")

        self.logStep("S3.调用ubse_mem_numa_delete接口删除指定numa远端内存")
        res = self.mem_numa_borrow(self.nodes[0], masking=False, name=name)

        self.logStep("E3.内存删除成功")
        self.assertTrue(res, "内存删除失败")

        self.logStep("S4.查看内存账本信息：ubsectl display memory -t borrow_detail")
        mem_borrow_details = self.cli_api.display_mem_borrow_detail(self.nodes[0])

        self.logStep("E4.账本不包含S1的内存")
        self.assertFalse(any(d.get("name") == name for d in mem_borrow_details), f"仍存在name为{name}的内存信息")

