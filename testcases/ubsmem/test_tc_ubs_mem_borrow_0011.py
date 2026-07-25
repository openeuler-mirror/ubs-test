#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import UBSM_FLAG_MALLOC_WITH_NUMA, UbsMemInstance, UBSM_SHMEM_OK

import pytest


@pytest.mark.smoke
class TestTcUbsMemBorrow0011(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_BORROW_0011
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        011验证numa借用128内存后进行先写后读操作
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.调用接口ubsmem_lease_malloc name 128*1024*1024 0 64
        S2.随机取一个字符并写入得到的地址中
        S3.检查内存内容是否与写入的一致
        S4.调用接口ubsmem_lease_free addr释放借用内存
    ExpectedResult:
        E1.内存申请成功，有相应的远端numa呈现
        E2.内存写入成功
        E3.内存检查结果一致
        E4.内存归还成功
    Author:
        yangdonglin 00919887
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_tc_ubs_mem_borrow_0011(self):
        size = 128 * 1024 * 1024
        self.logStep("S1.调用接口ubsmem_lease_malloc name 128*1024*1024 0 64")
        addr_desec = self.host_nodes[0].apps[0].ubsmem_lease_malloc(
            self.default_region, size, UbsMemInstance.DISTANCE_DIRECT_NODE, UBSM_FLAG_MALLOC_WITH_NUMA)
        self.logStep("E1.内存申请成功，有相应的远端numa呈现")
        self.assertNotEqual(addr_desec.addr, "")
        remote_numa = self.host_nodes[0].get_remote_numa()
        self.assertNotEqual(len(remote_numa), 0)
        expect_char = get_random_char()
        self.logStep("S2.随机取一个字符并写入得到的地址中")
        rc = self.host_nodes[0].apps[0].mem_write(addr_desec.addr, size, expect_char)
        self.logStep("E2.内存写入成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S3.检查内存内容是否与写入的一致")
        rc = self.host_nodes[0].apps[0].mem_check(addr_desec.addr, size, expect_char)
        self.logStep("E3.内存检查结果一致")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S4.调用接口ubsmem_lease_free addr释放借用内存")
        rc = self.host_nodes[0].apps[0].ubsmem_lease_free(addr_desec.addr)
        self.logStep("E4.内存归还成功")
        self.assertEqual(rc, 0)

    def teardown_method(self):
        super().teardown_method()
