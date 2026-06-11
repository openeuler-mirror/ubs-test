"""
Migrated from legacy: RMRS_Fragment_SamePlane_Priority_004
"""

import json
import pytest
from libs.ubturbo.common import basic
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.mempooling_api as api

@pytest.mark.smoke
@pytest.mark.mempooling
@pytest.mark.mempooling_sameplane_priority
class TestRmrsFragmentSameplanePriority004(MempoolingBaseCase):
    """
    CaseNumber:
        RMRS_Fragment_SamePlane_Priority_004
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        2节点，创建虚机，跨平面借用512M，调用迁出策略接口，预期成功，返回策略
    PreCondition:
        P1、每个节点为2socket2numa（socket0_id=36,socket1_id=216）；
        P2、每个节点OBMM内存池的扩展上限mempool_size=16G；
        P3、2节点UBSE组网，记为Node0~Node1（UBSE的节点标识符为1~2）；
        P4、修改rmrs.fragment.mustSamePlane为false（优先同平面）；
        P5、Node1的NUMA1分配8G+512M大页内存，NUMA0不分配，并等待OBMM内存池扩充完成（8G/numa）；
        P6、Node0的NUMA0分配10G大页内存，等待OBMM内存池扩充完成（8G/numa）后，创建1个1U2G虚机；
    TestStep:
        S1、调用内存借用执行北向接口，参数为srcParam.srcNid=1,srcParam.srcSocketId=36,srcParam.srcNumaId=0,destParam.destNid=2,
            destParam.destSocketId=216,destParam.destNumaNum=1,destParam.destNumaId=[1],destParam.memSize=[524288]；
        S2、调用内存迁移策略北向接口，参数为borrowInNode=1,borrowSize=524288,vmInfoList.pid=<vm_pid>,vmInfoList.ratio=25
    ExpectedResult:
        E1、返回码200，且成功从Node1借到512G内存；
        E2、返回码200，且成功给出虚机pid迁移策略；
    Author:
    """

    # No __init__ method - dependencies injected via fixture

    def setup_method(self):
        """Legacy: preTestCase"""
        self.logStep("P1、碎片场景正常设置")
        super().preTestCase()

    def test_rmrs_fragment_sameplane_priority_004(self):
        """
        RMRS_Fragment_SamePlane_Priority_004
        """
        self.logStep("P5、Node1的NUMA1分配8G+512M大页内存，NUMA0不分配，并等待OBMM内存池扩充完成（8G/numa）")
        for socket_id in self.socket:
            for numa in self.socket2numa[socket_id]:
                mempooling_common.alloc_hugePage(self.nodes[1], numa, 0)
        mempooling_common.alloc_hugePage(self.nodes[1], self.socket2numa[self.socket[1]][0], 4096 + 512)
        self.logStep("P6、Node0的NUMA0分配10G大页内存，等待OBMM内存池扩充完成（8G/numa）后，创建1个1U2G虚机")
        for socket_id in self.socket:
            for numa in self.socket2numa[socket_id]:
                mempooling_common.alloc_hugePage(self.nodes[0], numa, 0)
        mempooling_common.alloc_hugePage(self.nodes[0], self.socket2numa[self.socket[0]][0], 4096 + 1024)
        vm = api.create_vm_object(self.nodes[0], 'A')
        pidA = vm.get_pid()
        self.logStep("P-E6、创建虚机成功")
        self.assertNotEqual(pidA, None, "创建虚机A失败")

        self.logStep("S1、调用内存借用执行北向接口，参数为srcParam.srcNid=1,srcParam.srcSocketId=36,srcParam.srcNumaId=0,"
                     "destParam.destNid=2,destParam.destSocketId=216,destParam.destNumaNum=1,destParam.destNumaId=[1],destParam.memSize=[524288]")
        payload = {
            "srcParam": {
                "srcNid": "1",
                "srcSocketId": self.socket[0],
                "srcNumaId": self.socket2numa[self.socket[0]][0]
            },
            "borrowSize": 524288,
            "destParam": [
                {
                    "destNid": "2",
                    "destSocketId": self.socket[1],
                    "destNumaNum": 1,
                    "destNumaId": [self.socket2numa[self.socket[1]][0]],
                    "memSize": [524288]
                }
            ]
        }
        ret = api.function_borrow_execute(self.nodes[0], payload)
        self.logStep("E1、接口响应成功，返回码200")
        self.assertEqual(ret, 200, "E1、node0调用内存借用执行函数失败")
        presentnumaid = api.parse_presentnumaid_from_borrow_execute_response(self.nodemaster, ret)
        self.assertEqual(self.get_numa_info_tuple(self.nodemaster, presentnumaid[0])[1], 512, f"借用大小不符合预期")

        self.logStep("S2、调用内存迁移策略北向接口，参数为borrowInNode=1,borrowSize=524288,vmInfoList.pid=<vm_pid>,vmInfoList.ratio=25")
        payload = {
            "borrowInNode": "1",
            "borrowSize": 524288,
            "vmInfoList": [
                {
                    "pid": pidA,
                    "ratio": 25
                }
            ]
        }
        migrate_strategy1 = f"python3 /home/mempooling-test/sdk/call_virt.py call_migrate_strategy '{json.dumps(payload)}'"
        ret = basic.run(self.nodemaster, migrate_strategy1, timeout=500).stdout
        self.logStep("E2、迁出策略接口响应成功，返回码200")
        self.assertEqual(int([x for x in ret.splitlines() if x.strip()][-1]), 200, "E2、调用迁出策略函数失败")

    def teardown_method(self):
        """Legacy: postTestCase"""
        super().postTestCase()
