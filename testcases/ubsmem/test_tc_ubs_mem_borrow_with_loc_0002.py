#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import UBSM_SHMEM_OK, UBSMemLocation

import pytest


@pytest.mark.smoke
class TestTcUbsMemBorrowWithLoc0002(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_BORROW_WITH_LOC_0002
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        002验证指定numa进行fd借用1024M
    PreCondition:
        P1.四节点环�?
        P2.UBS-Engine进程正常拉起
        P3.MMI组件加载正常
        P4.UBS-Memory服务加载正常
    TestStep:
        S1.节点0执行sudo -u ubse ubsectl display topo -t cpu查询节点cpu拓扑
        S2.调用接口ubsmem_lease_malloc_with_location loc 1024*1024*1024 0 1进行fd借用
        S3.执行sudo -u ubse ubsectl display memory -t borrow_detail查询账本信息
        S4.调用接口ubsmem_lease_free addr释放借用内存
    ExpectedResult:
        E1.拓扑查询成功
        E2.内存借用成功
        E3.内存从指定的numa进行借出
        E4.内存释放成功
    Author:
        yangdonglin 00919887
    """

    def setup_method(self):
        self.logStep("P1.四节点环�?)

        self.logStep("P2.UBS-Engine进程正常拉起")

        self.logStep("P3.MMI组件加载正常")

        self.logStep("P4.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_borrow_with_loc_0002(self):
        size = 1024 * 1024 * 1024
        self.logStep("S1.节点0执行sudo -u ubse ubsectl display topo -t cpu查询节点cpu拓扑")
        topo = self.host_nodes[0].get_node_cpu_topo()
        self.logStep("E1.拓扑查询成功")
        self.assertNotEqual(len(topo), 0)
        self.logStep("S2.调用接口ubsmem_lease_malloc_with_location(loc, 1024*1024*1024, 0, 1)进行fd借用")
        node1_topo = topo[self.host_nodes[1].host_name][-1]
        local_numa_list = self.host_nodes[1].get_loacl_numa()
        loc = UBSMemLocation(
            node1_topo.slot_id, node1_topo.socket, local_numa_list[-1], node1_topo.port_id)
        addr_desc = self.host_nodes[0].apps[0].ubsmem_lease_malloc_with_location(loc, size, 0, 1)
        self.logStep("E2.内存借用成功")
        self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)
        self.logStep("S3.执行sudo -u ubse ubsectl display memory -t borrow_detail查询账本信息")
        account_list = self.host_nodes[0].get_borrow_account(self.host_nodes[0].host_name)
        self.assertEqual(len(account_list), 1)
        self.logStep("E3.内存从指定的numa进行借出")
        self.assertEqual(account_list[0].lend_node, node1_topo.slot_id)
        self.assertEqual(account_list[0].lend_numa, local_numa_list[-1])
        self.logStep("S4.调用接口ubsmem_lease_free addr释放借用内存")
        rc = self.host_nodes[0].apps[0].ubsmem_lease_free(addr_desc.addr)
        self.logStep("E4.内存释放成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
