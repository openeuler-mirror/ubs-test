"""
Migrated from legacy: memory_pooling_white_list_001
"""

import pytest
import time
from typing import Any, Dict, List
from libs.core.basecase.ubturbo.mempooling_basecase import MempoolingBaseCase, mem_return
import libs.ubturbo.api.mempooling as mempooling_common
import libs.ubturbo.api.mempooling_api as api
from libs.ubturbo.api import rack_manager, system
from libs.ubturbo.api.rack_manager import RACK_CONF
from libs.ubturbo.common import basic
from libs.ubturbo.common.string_utils import STR_ENTER
from libs.ubturbo.api.mempooling import RACK_INSTALL_PATH

@pytest.mark.smoke
@pytest.mark.mempooling
class TestMemoryPoolingWhiteList001(MempoolingBaseCase):
    """
    CaseNumber: 
        memory_pooling_white_list_001
    RunLevel: 
        Level 2
    EnvType: 
        
    CaseName: 
        白名单配置测试
    PreCondition:
        1.两台带有RDMA网卡的节点
        2.网络正常，ip可以ping通
        3.HCOM动态库存在且加载环境变量
    TestStep:
        S1.修改两个节点的rackmanager.conf配置文件，新增两行：group=computer01,computer02 provider=computer01
        S2.重启两个节点rack：systemctl restart scbus-daemon
        S3.computer01节点注入overCommitment1.0
        S4.调用内存借用策略接口，借入节点Node0的numa0，借用内存128M
        S5.调用内存借用执行函数，借入节点Node0的numa0，借用内存128M，destParam为node1
        S6.调用内存借用策略接口，借入节点Node1的numa0，借用内存128M
        S7.调用内存借用执行函数，借入节点Node1的numa0，借用内存128M
    ExpectedResult:
        S4.接口响应成功，返回码500（白名单限制）
        S5.接口响应成功，返回码500（白名单限制）
        S6.接口响应成功，返回码200
        S7.接口响应成功，返回码200
    Author: 
        tongjinhui
    """
    def setup_method(self):
        """Legacy: preTestCase"""
        for node in self.nodes:
            mempooling_common.upload_sh_files(node)
        mempooling_common.alloc_hugePage(self.nodes[0], self.socket2numa[self.socket[0]][0], 5120)
        mempooling_common.alloc_hugePage(self.nodes[1], self.socket2numa[self.socket[0]][0], 5120)

    def test_memory_pooling_white_list_001(self):
        """Legacy: procedure"""
        self.logStep("S1、修改两个节点的rackmanager.conf配置文件，新增两行：group=computer01,computer02 provider=computer01,S2、重启两个节点rack：systemctl restart scbus-daemon")
        self.hostnames = [
            basic.run(node, "hostname").stdout.strip(STR_ENTER)
            for node in self.nodes
        ]

        mempooling_common.restart_rack_with_ReconfigureConf(
            self.nodes,
            group_value=",".join(self.hostnames),
            provider_value=self.hostnames[0]  #第一个节点
        )
        
        self.logStep("S3、computer01节点注入overCommitment1.0")
        self.assertEqual(mempooling_common.check_memborrow_mode(self.nodes), True, "场景注入失败")
        
        self.logStep("S4、调用内存借用策略接口，借入节点Node0的numa0，借用内存128M")
        ret = api.function_borrow_strategy(self.nodes[0], 0, mempooling_common.get_socketid(self.nodes[0], 0), 0, 131072)
        self.assertEqual(ret, 500, f"内存借用策略接口预期返回500，实际返回{ret}")
        
        self.logStep("S5、调用内存借用执行函数，借入节点Node0的numa0，借用内存128M，destParam为node1，numa为与Node0numa0同平面的numa")
        destParam = api.create_destparam([(1, mempooling_common.get_socketid(self.nodes[1], 0), 1, [0], [131072])])
        borrow_param = api.BorrowExecuteInputParameter(srcnid=0, srcsocketid=mempooling_common.get_socketid(self.nodes[0], 0), srcnumaid=0, destparam=destParam)
        ret1 = api.function_borrow_execute(self.nodes[0], borrow_param)
        self.assertEqual(ret1, 500, f"node0调用内存借用执行函数预期返回500,实际返回{ret1}")
        
        self.logStep("S6、调用内存借用策略接口，借入节点Node1的numa0，借用内存128M")
        ret2 = api.function_borrow_strategy(self.nodes[1], 1, mempooling_common.get_socketid(self.nodes[1], 0), 0, 131072)
        self.assertEqual(ret2, 200, f"node0调用内存借用执行函数预期返回200,实际返回{ret2}")
        
        self.logStep("S7、调用内存借用执行函数，借入节点Node1的numa0，借用内存128M，destParam来自步骤4的返回值")
        destParam1 = api.create_destparam([(0, mempooling_common.get_socketid(self.nodes[0], 0), 1, [0], [131072])])
        borrow_param1 = api.BorrowExecuteInputParameter(srcnid=1, srcsocketid=mempooling_common.get_socketid(self.nodes[1], 0), srcnumaid=0, destparam=destParam1)
        ret3 = api.function_borrow_execute(self.nodes[1], borrow_param1)
        self.assertEqual(ret3, 200, f"node0调用内存借用执行函数预期返回200,实际返回{ret3}")

    def teardown_method(self):
        """Legacy: postTestCase"""
        self.logStep("P1、销毁虚机、归还内存、重置节点反亲和性、恢复大页")
        for node in self.nodes:
            mempooling_common.clean_config_file(node)
            mempooling_common.delete_all_vms(node)
            basic.run(node, "numastat -cvm")
            system.update_conf_file(node, path=f"{RACK_INSTALL_PATH}/{RACK_CONF}", key='group', mode='delete')
            system.update_conf_file(node, path=f"{RACK_INSTALL_PATH}/{RACK_CONF}", key='provider', mode='delete')
            system.update_conf_file(node, path=f"{RACK_INSTALL_PATH}/{RACK_CONF}", key='group', mode='set', value=",".join(self.hostnames))
            system.update_conf_file(node, path=f"{RACK_INSTALL_PATH}/{RACK_CONF}", key='provider', mode='set', value=",".join(self.hostnames))
            system.update_conf_file(node, path=f"{RACK_INSTALL_PATH}/{RACK_CONF}", key='group', mode='comment')
            system.update_conf_file(node, path=f"{RACK_INSTALL_PATH}/{RACK_CONF}", key='provider', mode='comment')
        mem_return(self.nodes)
        time.sleep(15)
        mempooling_common.reset_anti_affinity(self.nodes, self.nodes[0])
        rack_manager.restart_cluster_scbus(self.nodes, sync=False)
        success, master = rack_manager.wait_for_master_consistency(self.nodes, timeout_minutes=10, interval_seconds=10)
        if success:
            basic.logger.info(f"一致成功，master节点是 {master}")
        else:
            raise Exception(f"10分钟内主节点未一致")
        mempooling_common.alloc_hugePage(self.nodes[0], self.socket2numa[self.socket[0]][0], 4096)
        mempooling_common.alloc_hugePage(self.nodes[1], self.socket2numa[self.socket[0]][0], 4096)
