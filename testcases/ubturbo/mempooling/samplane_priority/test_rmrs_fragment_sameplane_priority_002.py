"""
Migrated from legacy: RMRS_Fragment_SamePlane_Priority_002
"""

import time
import pytest
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase, mem_return
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.mempooling_api as api

@pytest.mark.smoke
@pytest.mark.mempooling
@pytest.mark.mempooling_sameplane_priority
class TestRmrsFragmentSameplanePriority002(MempoolingBaseCase):
    """
    CaseNumber: 
        RMRS_Fragment_SamePlane_Priority_002
    RunLevel: 
        Level 2
    EnvType: 
        
    CaseName: 
        RMRS碎片同平面优先级测试-优先同平面(顺序调整)
    PreCondition:
        P4.修改rmrs.fragment.mustSamePlane为false（优先同平面）
        P5.Node1的NUMA1分配10G大页内存，NUMA0不分配
    TestStep:
        S1.调用内存借用策略北向接口
        E1.验证借出节点为同平面节点
    ExpectedResult:
        E1.借出节点nodeId预期为2，借出节点socketId与实际一致
    Author: 
        tongjinhui
    """

    def setup_method(self):
        """Legacy: preTestCase"""
        self.logStep("P4、修改rmrs.fragment.mustSamePlane为false（优先同平面）；")
        self.logger.info("Hook已实现")
        self.logStep("P5、Node1的NUMA1分配10G大页内存，NUMA0不分配，并等待OBMM内存池扩充完成（8G/numa）；")
        for socket_id in self.socket:
            for numa in self.socket2numa[socket_id]:
                mempooling_common.alloc_hugePage(self.nodeagent, numa, 0)
        mempooling_common.alloc_hugePage(self.nodeagent, self.socket2numa[self.socket[1]][0], 5120)
        time.sleep(5)

    def test_rmrs_fragment_sameplane_priority_002(self):
        """Legacy: procedure"""
        self.logStep("调用内存借用执行北向接口，参数为srcParam.srcNid=1,srcParam.srcSocketId=36,srcParam.srcNumaId=0,destParam.destNid=2,destParam.destSocketId=216,destParam.destNumaNum=1,destParam.destNumaId=[1],destParam.memSize=[1048576]；")
        payload = {
            "srcParam": {
                "srcNid": "1",
                "srcSocketId": self.socket[0],
                "srcNumaId": self.socket2numa[self.socket[0]][0]
            },
            "borrowSize": 1048576,
            "destParam": [
                {
                    "destNid": "2",
                    "destSocketId": self.socket[1],
                    "destNumaNum": 1,
                    "destNumaId": [self.socket2numa[self.socket[1]][0]],
                    "memSize": [1048576]
                }
            ]
        }
        ret = api.function_borrow_execute(self.nodemaster, payload)
        self.logStep("E1、调用内存借用策略北向接口，参数为srcParam.srcNid=1,srcParam.srcSocketId=36,srcParam.srcNumaId=0,borrowSize=1048576；")
        self.assertEqual(ret, 200, f"内存借用策略接口预期返回200，实际返回{ret}")
        presentnumaid = api.parse_presentnumaid_from_borrow_execute_response(self.nodemaster, ret)
        self.assertEqual(self.get_numa_info_tuple(self.nodemaster, presentnumaid[0])[1], 1024, f"借用大小不符合预期")

    def teardown_method(self):
        """Legacy: postTestCase"""
        # todo: 优化内存归还
        mem_return(self.nodes)
