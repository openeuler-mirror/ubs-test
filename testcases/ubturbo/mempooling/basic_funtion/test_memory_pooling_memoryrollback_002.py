"""
Migrated from legacy: memory_pooling_memoryRollback_002
"""
import pytest
import json
from libs.ubturbo.common import basic, env
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.libvirt as lv_api
import libs.ubturbo.api.mempooling_api as api
from libs.ubturbo.hooks import hook_mem_pooling

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemoryPoolingMemoryrollback002(MempoolingBaseCase):
    """
    CaseNumber:
        memory_pooling_memoryRollback_002
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        内存碎片_借用内存来源于单node多numa，迁出内存成功，调用内存回滚函数，预期回滚成功
    PreCondition:

    TestStep:
        S1、主节点numa0分配5G大页，创建2个2u2g虚机A、B / 13g大页，1u2g虚机(UB)
        S2、node0调用内存借用执行函数借4G+4G,借入方node0的numa0、1 / 128M+128M(UB)
        S3、主节点远端numa分配1G大页 / 256M(UB)
        S4、调用内存迁移策略函数,内存借入节点为node0，两个虚机的预设迁出最大比例均为60%，匀出本地内存大小为1G / 130M(UB)
        S5、调用内存迁出执行函数，内存借入节点为node0，等待时间设置8000ms
        S6、调用内存回滚函数，回滚节点为node0
        S7、检查大页信息，判断内存是否回滚成功
    ExpectedResult:
        E1、内存借用执行成功
        E2、迁移策略执行成功
        E3、迁移执行成功
        E4、回滚成功
    Author:
    """

    # No __init__ method - dependencies injected via fixture

    def setup_method(self):
        """Legacy: preTestCase"""
        mempooling_common.pre_test(self.nodemaster)
        if env.get_env_type(self.nodemaster) in [env.UB_simulation, env.UB_hardware]:
            mempooling_common.alloc_hugePage_with_check(self.nodemaster, 0, 8192)

    def test_memory_pooling_memoryrollback_002(self):
        """
        memory_pooling_memoryRollback_002
        """
        self.srcSocketId = mempooling_common.get_socketid(self.nodeagent, 1)
        self.destSocketId = mempooling_common.get_socketid(self.nodemaster, 1)
        self.logStep("S1、给node1的numa1分12G大页，成功创建2个1U2G虚机")
        # 分配大页，起虚机
        mempooling_common.alloc_hugePage(self.nodeagent, 0, 6144)
        api.create_vm_object(self.nodeagent, 'A')
        api.create_vm_object(self.nodeagent, 'B')

        self.logStep(
            "S2、调用内存借用执行函数，借入方为node1的numa1,借出方为node0的numa1，借用256M+128M，打印并检查函数出参")
        destParam = api.create_destparam([(0, int(self.destSocketId), 1, [0], [393216])])
        borrow_param = api.BorrowExecuteInputParameter(srcnid=1, srcsocketid=self.srcSocketId, srcnumaid=0,
                                                       destparam=destParam)
        ret = api.function_borrow_execute(self.nodeagent, borrow_param)
        self.assertEqual(ret, 200, "node0调用内存借用执行函数失败")
        borrowIds, presentNumaId = api.parse_borrow_execute_response_full(self.nodeagent, 200)
        self.logStep("S3、给node1的远端numa分384M大页")
        mempooling_common.alloc_hugePage(self.nodeagent, presentNumaId[0], 192)

        self.logStep("S4、调用内存迁出执行函数，内存借入节点为node1，等待时间设置8000ms")
        pid_A = lv_api.get_pid(self.nodeagent, "mempooling-A")
        pid_B = lv_api.get_pid(self.nodeagent, "mempooling-B")
        vmInfoList = [{"pid": int(pid_A), "memSize": 153600, "destNumaId": presentNumaId[0]},
                      {"pid": int(pid_B), "memSize": 153600, "destNumaId": presentNumaId[0]}]
        ret = api.function_migrate_execute(self.nodeagent, 1, borrowIds, vmInfoList, 52000)
        self.logStep("E3、迁移执行成功")
        self.assertEqual(ret, 200, "调用内存迁移执行函数失败")

        self.logStep("S5、调用内存回滚函数，回滚节点为node1")
        payload = {
            "borrowInNode": "2",
            "borrowIds": [borrowIds[0]]
        }
        mem_roolback = f"python3 /home/mempooling-test/sdk/call_virt.py call_mem_roolback '{json.dumps(payload)}'"
        ret = basic.run(self.nodeagent, mem_roolback, timeout=1200).stdout
        self.logStep("E4、回滚成功")
        self.assertEqual(int([x for x in ret.splitlines() if x.strip()][-1]), 200, "调用内存回滚函数失败")

    def teardown_method(self):
        """Legacy: postTestCase"""
        mempooling_common.delete_all_vms(self.nodeagent)
        mempooling_common.post_test(self.nodes)
