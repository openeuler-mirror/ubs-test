"""
Migrated from legacy: memory_pooling_third_migout_execute_003
"""
import pytest
from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
from libs.ubturbo.common import basic, env
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.libvirt as lv_api
import libs.ubturbo.api.mempooling_api as api
import json
from libs.ubturbo.hooks import hook_mem_pooling

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemoryPoolingThirdMigoutExecute003(ATBaseCase):
    """
    CaseNumber:
        memory_pooling_third_migout_execute_003
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用内存迁出分配执行接口，虚机迁出后相同内存段再次新建虚机
    PreCondition:

    TestStep:
        S1、给node1的numa0上分配16G大页，并成功创建1个1U2G虚机A
        S2、调用第一层借用内存执行动作接口，借入方为node1的numa2，借出方为node0的numa2，借用内存128M（131072KB）
        S3、给node1的远端numa2上分满大页128M；
        S4、调用第三层内存迁出执行接口，借入方为node1，迁出内存100M，迁到numa2上，其余入参来自步骤2
        S5、调用内存归还接口，归还节点为node1
        S6、调用第一层借用内存执行动作接口，借入方为node1的numa1，借出方为node0的numa1，借用内存128M（131072KB）
        S7、给node1的远端numa3上分满大页；
        S8、调用第三层内存迁出执行接口，借入方为node1，迁出内存100M，迁到numa3上，其余入参来自步骤2
        S9、调用内存归还接口，归还节点为node1
    ExpectedResult:
        E1、创建虚机成功
        E2、接口响应200，node1上存在远端numa2
        E3、分配大页成功
        E4、接口响应500
        E5、接口响应200，numa2不存在
        E6、接口响应200，node1存在远端numa3
        E7、分配大页成功
        E8、接口响应200
        E9、接口响应200，numa3不存在
    Author:
    """

    # No __init__ method - dependencies injected via fixture

    def setup_method(self):
        """Legacy: preTestCase"""
        mempooling_common.pre_test(self.nodemaster)
        if env.get_env_type(self.nodemaster) in [env.UB_simulation, env.UB_hardware]:
            mempooling_common.alloc_hugePage_with_check(self.nodemaster, 0, 8192)

    def test_memory_pooling_third_migout_execute_003(self):
        """
        memory_pooling_third_migout_execute_003
        """
        self.logStep("S1、给node1的numa0上分配16G大页，并成功创建1个1U2G虚机A")
        mempooling_common.alloc_hugePage(self.nodeagent, 0, 5888)
        api.create_vm_object(self.nodeagent, 'A')
        self.logStep("E1、分配大页成功，虚机A创建成功")

        self.logStep(
            "S2、调用第一层借用内存执行动作接口，借入方为node1的numa0，借出方为node0的numa0，借用内存1.25G（1310720KB）")
        destSocketId = mempooling_common.get_socketid(self.nodemaster, 0)
        srcSocketId = mempooling_common.get_socketid(self.nodeagent, 0)
        destParam = api.create_destparam([(0, destSocketId, 1, [0], [1310720])])
        borrowParam = api.BorrowExecuteInputParameter(srcnid=1, srcnumaid=0, srcsocketid=srcSocketId,
                                                      destparam=destParam)
        ret = api.function_borrow_execute(self.nodeagent, borrowParam)
        self.logStep("E2、接口响应200，node1存在远端numa")
        self.assertEqual(ret, 200)
        borrowids, presentNumaId = api.parse_borrow_execute_response_full(self.nodeagent, ret)
        borrowId = borrowids[0]
        remote_numa_id = presentNumaId[0]

        self.logStep("S3、给node1的远端numa上分满大页1280M")
        mempooling_common.alloc_hugePage(self.nodeagent, remote_numa_id, 640)
        numaTotal = mempooling_common.getHugePageTotal(self.nodeagent, remote_numa_id)
        self.logStep("E3、分配大页成功")
        self.assertEqual(numaTotal, 640)

        self.logStep(
            "S4、调用第三层内存迁出执行接口，借入方为node1，迁出内存512M，虚机A的最大迁出比例为50%，其余入参来自步骤2")
        destPid = lv_api.get_pid(self.nodeagent, "mempooling-A")
        payload = {
            "borrowInNode": str(1 + 1),
            "borrowIds": [borrowId],
            "vmInfoList": [
                {
                    "pid": destPid,
                    "memSize": 524288,
                    "destNumaId": remote_numa_id
                }
            ],
            "waitingTime": 51000
        }
        migrate_execute = f"python3 /home/mempooling-test/sdk/call_virt.py call_migrate_execute '{json.dumps(payload)}'"
        ret = basic.run(self.nodeagent, migrate_execute, timeout=120).stdout
        self.logStep("E4、接口响应200，虚机A的512M分布在node1的numa0、512M分布在numa2上")
        self.assertEqual(int([x for x in ret.splitlines() if x.strip()][-1]), 200)
        # check

        self.logStep("S5、在numa0上成功创建1个1U1G虚机B")
        api.create_vm_object(self.nodeagent, 'B')
        self.logStep("E5、虚机B创建成功")

    def teardown_method(self):
        """Legacy: postTestCase"""
        mempooling_common.delete_all_vms(self.nodeagent)
        mempooling_common.post_test(self.nodes)
