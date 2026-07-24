#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import UBSM_SHMEM_OK, UbsMemInstance

import pytest


@pytest.mark.smoke
class TestTcUbsMemBorrow0003(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_BORROW_0003
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        003验证借用4M内存后进行先读后写操�?
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.调用接口ubsmem_lease_malloc region 4*1024*1024 0 0
        S2.随机取一个字符并写入得到的地址�?
        S3.检查内存内容是否与写入的一�?
        S4.调用接口ubsmem_lease_free addr释放借用内存
    ExpectedResult:
        E1.内存申请成功，有相应的obmm设备呈现
        E2.内存写入成功
        E3.内存检查结果一�?
        E4.内存归还成功
    Author:
        wanghaojie 60117672
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_borrow_0007(self):
        alloc_size = 4 * 1024 * 1024
        self.logStep("S1.调用接口ubsmem_lease_malloc region 4*1024*1024 0 0")
        addr_desc = self.host_nodes[0].apps[0].ubsmem_lease_malloc(
            self.default_region, alloc_size, UbsMemInstance.DISTANCE_DIRECT_NODE, 0)
        self.logStep("E1.内存申请成功，有相应的obmm设备呈现")
        self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)
        obmm_device_count = self.host_nodes[0].get_obmm_device_count()
        self.assertGreater(obmm_device_count, 0)

        expect_char = get_random_char()
        self.logStep("S2.随机取一个字符并写入得到的地址�?)
        rc = self.host_nodes[0].apps[0].mem_write(addr_desc.addr, alloc_size, expect_char)
        self.logStep("E2.内存写入成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S3.检查内存内容是否与写入的一�?)
        rc = self.host_nodes[0].apps[0].mem_check(addr_desc.addr, alloc_size, expect_char)
        self.logStep("E3.内存检查结果一�?)
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S4.调用接口ubsmem_lease_free addr释放借用内存")
        result = self.host_nodes[0].apps[0].ubsmem_lease_free(addr_desc.addr)
        self.logStep("E4.内存归还成功")
        self.assertEqual(result, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
