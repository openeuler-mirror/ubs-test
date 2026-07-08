import pytest
from typing import Any, Dict, List

from libs.modules.ubse.basecase.mem_pooling_basecase import MEM_Pooling_BaseCase
from libs.modules.ubse.basecase.ub_pooling_basecase import UB_Pooling_BaseCase
from libs.utils.logger_compat import Log

@pytest.mark.hook("libs.modules.ubse.hook.mem_pooling_hook.MEM_Pooling_Hook")
@pytest.mark.smoke
class TestTcUbsTopoLinkListSdk001(MEM_Pooling_BaseCase, UB_Pooling_BaseCase):
    """
    CaseNumber:
        tc_ubs_topo_link_list_sdk_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证sdk接口查询所有CPU类型节点的拓扑信息成功
    PreCondition:
        P1.ubse进程已启动
        P2.节点集群状态为ok
    TestStep:
        S1.调用ubse_node_cpu_topo_list接口查询本节点信息
    ExpectedResult:
        E1.返回成功
    Author:
        zhangyufang 30058350
    """
    def setup_method(self):

        self.logStep("P1.ubse进程已启动")
        self.master_node, self.standby_node, _ = self.ubse_process_ops.return_nodes_by_all_role(self.nodes)
        self.logStep("P2.节点集群状态为ok")
        for node in self.nodes:
            node_status = self.get_node_memory_status(node.nodeId)
            self.assertEqual(node_status, "ok", "内存状态未就绪")

    def teardown_method(self):
        
        pass

    def test_tc_ubs_topo_link_list_sdk_001(self):

        lcne_result = []
        self.logStep("S1.调用ubse_node_cpu_topo_list接口查询本节点信息")
        for node in self.nodes:
            info = self.mem_borrow_common_result(node, "cpu_topo")
            res = info.split("\r\nubse_mem_app>")[0]
            result = res.split("Successfully get cpu topo info\r\n")[1]
            result = self.get_cpu_topo_info(result)
            self.logInfo("result:" + str(result))

            if len(self.nodes) > 1:
                dict_slot_all_nodes, bindWitch_dict_all_nodes, chipType_dict_all_nodes = (
                    self.get_bindWitch_chipType_from_lcne()
                )
                socketId_os = self.change_lcne_socketId_os()
                dict_slot_all_nodes = self.replace_socketId(dict_slot_all_nodes, socketId_os)
                one_step = {}
                for key, value in dict_slot_all_nodes.items():
                    one_step[key] = sorted(value)
                sorted_by_key = dict(sorted(one_step.items()))
                topology_info = self.get_topo_info_from_lcne(self.nodes, sorted_by_key)
                lcne_result = [
                    {k: v for k, v in item.items() if k != "link-id"} for item in topology_info
                ]
            lcne_info = self.process_cpu_topo_dict(lcne_result)

            sorted_list1 = sorted(result, key=lambda x: x["socket"])
            sorted_list2 = sorted(lcne_info, key=lambda x: x["socket"])

            print("sorted_list1:", sorted_list1)
            print("sorted_list2:", sorted_list2)

            res = self.compare_dicts_list(sorted_list1, sorted_list2, "port")
            self.logStep("E1.返回成功")
            self.assertTrue(res)
