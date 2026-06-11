"""
Migrated from legacy: mempooling_001
"""

import pytest
from typing import Any, Dict, List
from libs.ubturbo.hooks import hook_mem_pooling
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase
from libs.ubturbo.common import basic
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.mempooling_api as api

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMempooling001(MempoolingBaseCase):
    """
    CaseNumber: 
        mempooling_001
    RunLevel: 
        Level T
    EnvType: 
        
    CaseName: 
        内存碎片_借用内存成功（策略+执行），迁出内存成功（策略+执行），本地内存充足，内存归还成功
    PreCondition:
        P1、软总线已经正常运行，内存子系统模块成功加载，SMAP正常启动。
        P2、内存调度管理模块成功加载。
        P3、4p环境
        P4、所有节点的每个numa初始配置8G空闲大页
    TestStep:
        S1、给node0的numa0分配13G大页，并成功创建2个1u2g虚机
        S2、调用内存借用策略函数，借用内存为256M，借入方为node0的numa0，打印并检查函数出参
        S3、调用内存借用执行函数，借用内存为256M，借入方为node0的numa0，借出方为node1的numa（根据实际情况选择与node0的numa0同平面的numa）
        S4、给node0的步骤3借来的远端numa分满大页
        S5、调用内存迁移策略函数，内存借入节点为node0，两个虚机的预设迁出最大比例均为60%，总共匀出本地内存大小为100M（102400kb），打印并检查函数出参
        S6、调用内存迁出执行函数，内存借入节点为node0，迁出内存到步骤3的借来的远端numa上，等待时间设置8000ms，虚机信息列表由步骤5得到，内存描述符列表由步骤3出参得到
        S7、执行指令：numastat -cvm
        S8、执行指令：numastat -p 
        S9、调用内存归还函数，内存借入节点为node0
    ExpectedResult:
        E1、分配大页成功、创建两个虚机成功
        E2、返回码200，预期策略返回从node1的与node0的numa0同平面的numa借用256M内存
        E3、返回码200；
        E4、分配大页成功
        E5、返回码200；
        E6、返回码200；需要检查迁出前后两个虚机功能正常
        E7、node0的numa0空闲大页在步骤1之后减少4G,在步骤6之后增加100M
        E8、两个虚机共计有100M大页分布在步骤3借来的远端numa上
        E9、
        1）返回码200；
        2）通过步骤7检查：
        主节点numa0上的HugePages_Total等于13312
        主节点numa0上的HugePages_Free等于1024
        没有远端numa
    Author: 
        huangdewei 00889334
    """

    # No __init__ method - dependencies injected via fixture

    def setup_method(self):
        """Legacy: preTestCase"""
        super().preTestCase()

    def teardown_method(self):
        """Legacy: postTestCase"""
        for node in self.nodes:
            mempooling_common.delete_all_vms(node)
        mempooling_common.post_test(self.nodes)

    def test_mempooling_001(self):
        """
        mempooling_001
        """
        self.logStep("S1、给node0的numa0分配13G大页，并成功创建2个1u2g虚机")
        mempooling_common.alloc_hugePage_with_check(self.nodemaster, 0, int(13 * 1024 / 2))
        mempooling_common.alloc_hugePage_with_check(self.nodeagent, 0, int(13 * 1024 / 2))
        free_hugepages_node0_numa0 = api.parse_node_numa_attribute(self.nodemaster, 0, 'HugePages_Free')
        vm_A = api.create_vm_object(self.nodemaster, 'A')
        vm_B = api.create_vm_object(self.nodemaster, 'B')
        s1_free_hugepages_node0_numa0 = api.parse_node_numa_attribute(self.nodemaster, 0, 'HugePages_Free')
        self.assertEqual(free_hugepages_node0_numa0 - s1_free_hugepages_node0_numa0, int(4 * 1024),
                         f"numa0大页占用不符合预期，预期减少4G, 实际减少{(free_hugepages_node0_numa0 - s1_free_hugepages_node0_numa0) / 1024}G")
        self.logStep("E1、分配大页成功、创建两个虚机成功")

        self.logStep("S2、调用内存借用策略函数，借用内存为256M，借入方为node0的numa0，打印并检查函数出参")
        res_2 = api.function_borrow_strategy(self.nodemaster, 0, mempooling_common.get_socketid(self.nodemaster, 0), 0,
                                             262144)
        self.assertEqual(res_2, 200, f"调用内存借用策略函数预期返回200，实际返回{res_2}")
        borrow_strategy_response = api.parse_borrow_strategy_response(self.nodemaster, res_2)
        destNumaId = borrow_strategy_response["destParam"][0]["destNumaId"][0]

        node0_numa0_plane0 = api.create_member_of_borrow_topology(0, 0, 0)
        same_plane_topology_member_in_node1_as_node0_plane0_numa0 = \
            api.get_same_plane_topology_members_list_from_dest_nodeid(node0_numa0_plane0, 1)[0]
        dest_numax_id = same_plane_topology_member_in_node1_as_node0_plane0_numa0.numaId
        self.assertEqual(destNumaId, dest_numax_id, f"决策numaId: {destNumaId}, 预期numaId: {dest_numax_id}")
        self.logStep("E2、返回码200，预期策略返回从node1的与node0的numa0同平面的numa借用256M内存")

        self.logStep(
            "S3、调用内存借用执行函数，借用内存为256M，借入方为node0的numa0，借出方为node1的numa（根据实际情况选择与node0的numa0同平面的numa）")
        res_3 = api.function_borrow_execute(self.nodemaster, borrow_strategy_response)
        self.assertEqual(res_3, 200, f"调用内存借用执行函数预期返回200，实际返回{res_3}")
        borrowIds, presentNumaId = api.parse_borrow_execute_response_full(self.nodemaster, res_3)
        remote_numa_id = presentNumaId[0]
        self.logStep("E3、返回码200")

        self.logStep("S4、给node0的步骤3借来的远端numa分满大页")
        mempooling_common.alloc_hugePage_with_check(self.nodemaster, remote_numa_id, int(256 / 2) + 1)
        self.logStep("E4、分配大页成功")

        self.logStep(
            "S5、调用内存迁移策略函数，内存借入节点为node0，两个虚机的预设迁出最大比例均为60%，总共匀出本地内存大小为100M（102400kb），打印并检查函数出参")
        vm_list = [(mempooling_common.get_pid(self.nodemaster, vm_A.vm_name), 60),
                   (mempooling_common.get_pid(self.nodemaster, vm_B.vm_name), 60)]
        vm_info_list = api.get_vm_infolist(vm_list, used_for_strategy=True)
        res_5 = api.function_migrate_strategy(self.nodemaster, 0, 102400, vm_info_list)
        self.assertEqual(res_5, 200, f"调用迁移策略函数预期返回200，实际返回{res_5}")
        real_vm_info_list = api.parse_migrate_strategy_response(self.nodemaster)
        self.logStep("E5、返回码200")

        self.logStep(
            "S6、调用内存迁出执行函数，内存借入节点为node0，迁出内存到步骤3的借来的远端numa上，等待时间设置50000ms，虚机信息列表由步骤5得到，内存描述符列表由步骤3出参得到")
        res_6 = api.function_migrate_execute(self.nodemaster, 0, borrowIds, real_vm_info_list, 50000)
        self.assertEqual(res_6, 200, f"调用迁移策略函数预期返回200，实际返回{res_6}")
        vm_A.init_login()
        vm_B.init_login()
        api.check_vm_function(vm_A)
        api.check_vm_function(vm_B)
        self.logStep("E6、返回码200；需要检查迁出前后两个虚机功能正常")

        self.logStep("S7、执行指令：numastat -cvm")
        basic.run(self.nodemaster, "numastat -cvm")
        s7_free_hugepages_node0_numa0 = api.parse_node_numa_attribute(self.nodemaster, 0, 'HugePages_Free')
        self.assertEqual(s7_free_hugepages_node0_numa0 - s1_free_hugepages_node0_numa0, 100,
                         f"numa0大页占用不符合预期，预期增加100M, 实际增加{s7_free_hugepages_node0_numa0 - s1_free_hugepages_node0_numa0}M")
        self.logStep("E7、node0的numa0空闲大页在步骤1之后减少4G,在步骤6之后增加100M")

        self.logStep("S8、执行指令：numastat -p")
        basic.run(self.nodemaster, f"numastat -p {mempooling_common.get_pid(self.nodemaster, vm_A.vm_name)}")
        basic.run(self.nodemaster, f"numastat -p {mempooling_common.get_pid(self.nodemaster, vm_B.vm_name)}")
        used_hugepages_remote_numa = api.parse_node_numa_attribute(self.nodemaster, remote_numa_id,
                                                                   'HugePages_Total') - api.parse_node_numa_attribute(
            self.nodemaster, remote_numa_id, 'HugePages_Free')
        self.assertEqual(used_hugepages_remote_numa, 100,
                         f"远端numa大页使用不符合预期，预期使用100M, 实际使用{used_hugepages_remote_numa}M")
        self.logStep("E8、两个虚机共计有100M大页分布在步骤3借来的远端numa上")

        self.logStep("S9、调用内存归还函数，内存借入节点为node0")
        res_9 = api.function_return(self.nodemaster, 0)
        self.assertEqual(res_9, 200, f"调用内存归还预期返回200，实际返回{res_9}")
        s9_total_hugepages_node0_numa0 = api.parse_node_numa_attribute(self.nodemaster, 0,
                                                                       'HugePages_Total')
        self.assertEqual(s9_total_hugepages_node0_numa0, 13312,
                         f"numa0大页总量预期13312，实际{s9_total_hugepages_node0_numa0}")
        s9_free_hugepages_node0_numa0 = api.parse_node_numa_attribute(self.nodemaster, 0, 'HugePages_Free')
        self.assertEqual(s9_free_hugepages_node0_numa0, 1024,
                         f"numa0大页空闲预期1024，实际{s9_free_hugepages_node0_numa0}")

        self.logStep("E9、"
                     "1）返回码200；"
                     "2）通过步骤7检查："
                     "主节点numa0上的HugePages_Total等于13312"
                     "主节点numa0上的HugePages_Free等于1024"
                     "没有远端numa")
