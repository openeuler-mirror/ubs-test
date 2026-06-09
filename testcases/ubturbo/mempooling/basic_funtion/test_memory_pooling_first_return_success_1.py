"""
Migrated from legacy: memory_pooling_first_return_success_1
"""

import pytest
import time
from typing import Any, Dict, List
from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
from libs.ubturbo.common import basic, env
import libs.ubturbo.api.mempooling as mempooling_common
from libs.ubturbo.api.mempooling import get_pid, REMOTE_VM_XML_PATH, VM_2U2G_A_CONFIG_FILE, VM_2U2G_B_CONFIG_FILE
import libs.ubturbo.api.mempooling_api as api
from libs.ubturbo.hooks import hook_mem_pooling



@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemoryPoolingFirstReturnSuccess1(ATBaseCase):
    """
    CaseNumber: 
        memory_pooling_first_return_success_1
    RunLevel: 
        Level 2
    EnvType: 
        
    CaseName: 
        第一层借用内存成功后归还成功
    PreCondition:
        1.两台带有RDMA网卡的节点
        2.网络正常，ip可以ping通
        3.HCOM动态库存在且加载环境变量
    TestStep:
        1.创建虚机大页内存不足，调用第一层借用内存策略接口借用2228224KB内存
        2.调用第一层借用内存执行动作接口
        3.分配大页，调用第三层内存迁出策略接口
        4.调用第三层内存迁出执行接口
        5.调用内存归还接口归还内存
    ExpectedResult:
        1.接口响应成功，返回码200
        2.接口响应成功，返回码200
        3.接口响应成功，返回码200
        4.接口响应成功，返回码200
        5.接口响应成功，返回码200
    Author: 
        tongjinhui
    """

    def setup_method(self):
        """Legacy: preTestCase"""
        self._nodeagent = self.nodeagent
        self.srcSocketId = mempooling_common.get_socketid(self.nodeagent, 0)
        self.destSocketId = mempooling_common.get_socketid(self.nodemaster, 0)
        mempooling_common.pre_test(self.nodemaster)
        mempooling_common.pre_test(self._nodeagent)
        
        res = False
        if env.get_env_type(self._nodeagent) in [env.UB_simulation, env.UB_hardware]:
            res = mempooling_common.alloc_hugePage_with_check(self._nodeagent, 0, 6656)
        if not res:
            basic.logger.error("大页分配失败")
            raise Exception("大页分配失败")
        
        if env.get_env_type(self._nodeagent) == env.HCCS:
            basic.run(self._nodeagent, "virsh create " + REMOTE_VM_XML_PATH + VM_2U2G_A_CONFIG_FILE)
            basic.run(self._nodeagent, "virsh create " + REMOTE_VM_XML_PATH + VM_2U2G_B_CONFIG_FILE)
        
        if env.get_env_type(self._nodeagent) in [env.UB_simulation, env.UB_hardware]:
            api.create_vm_object(self._nodeagent, 'A')
            api.create_vm_object(self._nodeagent, 'B')

    def test_memory_pooling_first_return_success_1(self):
        """Legacy: procedure"""
        self.logStep("1-创建虚机大页内存不足，调用第一层借用内存策略接口借用2228224KB内存")
        res_1 = api.function_borrow_strategy(self.nodeagent, 1, self.srcSocketId, 0, 2228224)
        if res_1 != 200:
            mempooling_common.save_error_log_for_failed_case(self.nodemaster, type(self).__name__)
            mempooling_common.save_error_log_for_failed_case(self._nodeagent, type(self).__name__)
            raise Exception("1-创建虚机大页内存不足，调用第一层借用内存策略接口借用2228224KB内存失败。")
        
        self.logStep("2-调用第一层借用内存执行动作接口")
        time.sleep(3)
        borrow_param = api.BorrowExecuteInputParameter(srcnid=1, srcnumaid=0, srcsocketid=self.srcSocketId)
        borrow_param.destParam = api.create_destparam([(0, self.destSocketId, 1, [0], [2228224])])
        res_2 = api.function_borrow_execute(self.nodeagent, borrow_param, timeout=120)
        if res_2 != 200:
            mempooling_common.save_error_log_for_failed_case(self.nodemaster, type(self).__name__)
            mempooling_common.save_error_log_for_failed_case(self._nodeagent, type(self).__name__)
            raise Exception("2-调用第一层借用内存执行动作接口失败。")
        borrowIds, presentNumaId = api.parse_borrow_execute_response_full(self.nodeagent, 200)
        
        self.logStep("3-分配大页，调用第三层内存迁出策略接口（borrowSize表示待迁出内存）")
        if env.get_env_type(self._nodeagent) == env.UB_simulation:
            mempooling_common.alloc_hugePage(self.nodeagent, presentNumaId[0], 1088)
        pid_A = get_pid(self._nodeagent, "mempooling-A")
        pid_B = get_pid(self._nodeagent, "mempooling-B")
        time.sleep(5)
        res_3 = api.function_migrate_strategy(self.nodeagent, 1, 102400, [{"pid": int(pid_A), "ratio": 4}, {"pid": int(pid_B), "ratio": 4}])
        if res_3 != 200:
            mempooling_common.save_error_log_for_failed_case(self._nodeagent, type(self).__name__)
            raise Exception("3-分配大页，调用第三层内存迁出策略接口-borrowSize表示待迁出内存失败。")
        
        self.logStep("4-调用第三层内存迁出执行接口")
        time.sleep(4)
        if env.get_env_type(self._nodeagent) == env.UB_simulation:
            vmInfoList = api.parse_migrate_strategy_response(self._nodeagent)
            res_4 = api.function_migrate_execute(self.nodeagent, 1, borrowIds, vmInfoList, 52000)
            if res_4 != 200:
                mempooling_common.save_error_log_for_failed_case(self.nodemaster, type(self).__name__)
                mempooling_common.save_error_log_for_failed_case(self._nodeagent, type(self).__name__)
                raise Exception("4-调用第三层内存迁出执行接口失败。")
        
        self.logStep("5、numastat -p vm_name化")
        numastat_vmname = "numastat -p mempooling-A"
        basic.run(self._nodeagent, numastat_vmname)
        time.sleep(30)
        
        self.logStep("6、调用内存归还接口归还内存")
        res_6 = api.function_return(self.nodeagent, 1)
        if res_6 != 200:
            mempooling_common.save_error_log_for_failed_case(self.nodemaster, type(self).__name__)
            mempooling_common.save_error_log_for_failed_case(self._nodeagent, type(self).__name__)
            raise Exception("6-调用内存归还接口归还内存失败。")

    def teardown_method(self):
        """Legacy: postTestCase"""
        mempooling_common.delete_all_vms(self._nodeagent)
        mempooling_common.post_test(self.nodes)