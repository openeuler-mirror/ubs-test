#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    UBSM_FLAG_MMAP_HUGETLB_PMD,
    UBSM_SHMEM_OK,
    UbsMemInstance,
)

import pytest


@pytest.mark.smoke
class TestTcUbsMemBorrow0051(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_BORROW_0051
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        051验证单次最大借用512G内存
    PreCondition:
        P1.环境�?G大页导出内存
        P2.UBS-Engine进程正常拉起
        P3.MMI组件加载正常
        P4.UBS-Memory服务加载正常
    TestStep:
        S1.调用接口ubsmem_lease_malloc region_name 512*1024*1024*1024 0 32进行fd借用
        S2.调用接口ubsmem_lease_free addr释放借用的内�?
        S3.查看借用信息，如果存在缓存，则释放掉借用环境
    ExpectedResult:
        E1.内存借用成功
        E2.内存释放成功
        E3.内存缓存清空
    Author:
        zhulinhao 30063494
    """

    def setup_method(self):
        self.logStep("P1.环境�?G大页导出内存")

        self.logStep("P2.UBS-Engine进程正常拉起")

        self.logStep("P3.MMI组件加载正常")

        self.logStep("P4.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_borrow_0051(self):
        size = 512 * 1024 * 1024 * 1024
        self.logStep("S1.调用接口ubsmem_lease_malloc region_name 512*1024*1024*1024 0 32进行fd借用")
        addr_desc = self.host_nodes[0].apps[0].ubsmem_lease_malloc(
            self.default_region, size, UbsMemInstance.DISTANCE_DIRECT_NODE, UBSM_FLAG_MMAP_HUGETLB_PMD)

        self.logStep("E1.内存借用成功")
        self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)

        self.logStep("S2.调用接口ubsmem_lease_free addr释放借用的内�?)
        rc = self.host_nodes[0].apps[0].ubsmem_lease_free(addr_desc.addr)

        self.logStep("E2.内存释放成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
