"""
Migrated from legacy: memory_pooling_third_migout_strategy_004
"""
import pytest
from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.libvirt as lv_api
import libs.ubturbo.api.mempooling_api as api
from libs.ubturbo.hooks import hook_mem_pooling
from libs.ubturbo.common import env

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemoryPoolingThirdMigoutStrategy004(ATBaseCase):
    """
    CaseNumber:
        memory_pooling_third_migout_strategy_004
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用内存迁出分配策略接口，仅有不同平面的远端NUMA，预期失败
    PreCondition:

    TestStep:
        1、给node1的numa0上分配13G大页，并成功创建1个1U2G虚机A
        2、调用第一层借用内存执行动作接口，借入方为node1的numa2，借出方为node0的numa2，借用内存256M（262144KB）
        3、给node1的远端numa2上分满大页256M
        4、调用第三层内存迁出策略接口，借入方为node1，迁出内存100M，虚机A的最大迁出比例都为10%
        5、调用内存归还接口，归还节点为node1
        6、调用第一层借用内存执行动作接口，借入方为node1的numa1，借出方为node0的numa1，借用内存256M（262144KB）
        7、给node1的远端numa3上分满大页
        8、调用第三层内存迁出策略接口，借入方为node1，迁出内存100M，虚机A的最大迁出比例都为10%
    ExpectedResult:
        E1、分配成功，虚机创建成功
        E2、接口响应200，node1存在远端numa2
        E3、分配成功
        E4、接口响应500
        E5、接口响应200，node1的远端numa2不存在
        E6、接口响应200，node1存在远端numa3
        E7、分配成功
        E8、接口响应200
    Author:
    """

    def setup_method(self):
        """Legacy: preTestCase"""
        mempooling_common.pre_test(self.nodemaster)
        if env.get_env_type(self.nodemaster) in [env.UB_simulation, env.UB_hardware]:
            mempooling_common.alloc_hugePage_with_check(self.nodemaster, 0, 8192)

    def test_memory_pooling_third_migout_strategy_004(self):
        """
        memory_pooling_third_migout_strategy_004
        """

        self.logStep("S1、给node1的numa0上分配13G大页，并成功创建1个1U2G虚机A")
        mempooling_common.alloc_hugePage(self.nodeagent, 0, 6656)
        api.create_vm_object(self.nodeagent, 'A')
        self.logStep("E1、创建虚机成功")

        self.logStep("S2、调用第一层借用内存执行动作接口，借入方为node1的numa2，借出方为node0的numa2，借用内存256M（262144KB）")
        destSocketId = mempooling_common.get_socketid(self.nodemaster, 1)
        srcSocketId = mempooling_common.get_socketid(self.nodeagent, 1)
        destParam = api.create_destparam([(0, destSocketId, 1, [1], [262144])])
        borrow_param = api.BorrowExecuteInputParameter(srcnid=1, srcsocketid=srcSocketId, srcnumaid=1, destparam=destParam)
        ret = api.function_borrow_execute(self.nodeagent, borrow_param)
        self.logStep("E2、接口响应200，node1上存在远端numa")
        self.assertEqual(ret, 200)
        borrowids, presentNumaId = api.parse_borrow_execute_response_full(self.nodeagent, ret)
        borrowId = borrowids[0]
        remote_numa_id = presentNumaId[0]

        self.logStep("S3、给node1的远端numa2上分满大页256M")
        mempooling_common.alloc_hugePage(self.nodeagent, remote_numa_id, 128)
        numaTotal = mempooling_common.getHugePageTotal(self.nodeagent, remote_numa_id)
        self.logStep("E3、分配大页成功")
        self.assertEqual(numaTotal, 128)

        self.logStep("S4、调用第三层内存迁出策略接口，借入方为node1，迁出内存100M，虚机A的最大迁出比例都为10%")
        destPid = lv_api.get_pid(self.nodeagent, "mempooling-A")
        ret = api.function_migrate_strategy(self.nodeagent, borrowinnode=1, borrowsize=102400,
                                            vminfolist=[{"pid": f"{destPid}", "ratio": 10}])
        self.logStep("E4、接口响应500")
        self.assertEqual(ret, 500)

        self.logStep("S5、调用内存归还接口，归还节点为node1")
        ret = api.function_return(self.nodeagent, 1)
        self.logStep("E5、接口响应200，node1的远端numa不存在")
        self.assertEqual(ret, 200)

        self.logStep("S6、调用第一层借用内存执行动作接口，借入方为node1的numa1，借出方为node0的numa1，借用内存256M（262144KB）")
        destSocketId = mempooling_common.get_socketid(self.nodemaster, 0)
        srcSocketId = mempooling_common.get_socketid(self.nodeagent, 0)
        destParam = api.create_destparam([(0, destSocketId, 1, [0], [262144])])
        borrow_param = api.BorrowExecuteInputParameter(srcnid=1, srcsocketid=srcSocketId, srcnumaid=0,
                                                       destparam=destParam)
        ret = api.function_borrow_execute(self.nodeagent, borrow_param)
        self.logStep("E6、接口响应200，node1存在远端numa")
        self.assertEqual(ret, 200)
        borrowids, presentNumaId = api.parse_borrow_execute_response_full(self.nodeagent, ret)
        borrowId = borrowids[0]
        remote_numa_id = presentNumaId[0]

        self.logStep("S7、给node1的远端numa上分满大页256M")
        mempooling_common.alloc_hugePage(self.nodeagent, remote_numa_id, 128)
        numaTotal = mempooling_common.getHugePageTotal(self.nodeagent, remote_numa_id)
        self.logStep("E7、分配大页成功")
        self.assertEqual(numaTotal, 128)

        self.logStep("S8、调用第三层内存迁出策略接口，借入方为node1，迁出内存100M，虚机A的最大迁出比例都为10%")
        ret = api.function_migrate_strategy(self.nodeagent, borrowinnode=1, borrowsize=102400,
                                            vminfolist=[{"pid": destPid, "ratio": 10}])
        self.logStep("E8、接口响应200")
        self.assertEqual(ret, 200)

    def teardown_method(self):
        """Legacy: postTestCase"""
        mempooling_common.delete_all_vms(self.nodeagent)
        mempooling_common.post_test(self.nodes)
