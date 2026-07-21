#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    UBSM_SHMEM_OK,
    UbsMemInstance,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.ubs_mem_smoke
class TestTcUbsMemBorrow0046(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_BORROW_0046
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        046验证四节点指定2个节点进行fd借用借用
    PreCondition:
        P1.四节点环境
        P2.UBS-Engine进程正常拉起
        P3.MMI组件加载正常
        P4.UBS-Memory服务加载正常
    TestStep:
        S1.节点0调用接口ubsmem_create_region region_name 0 2 hostx 0 hostx 1 hostx 1创建可以从2节点借出内存共享域
        S2.调用接口ubsmem_lease_malloc region_name 1024*1024*1024 0 0进行fd借用
        S3.查询借用账本
        S4.调用接口ubsmem_lease_free addr释放借用内存
        S5.节点0调用接口ubsmem_destroy_region region_name
    ExpectedResult:
        E1.共享域创建成功
        E2.内存借用成功
        E3.账本查询成功，内存由指定节点借出
        E4.内存释放成功
        E5.共享域删除成功
    Author:
        wanghaojie 60104182
    """

    def setup_method(self):
        self.logStep("P1.四节点环境")
        self.logStep("P2.UBS-Engine进程正常拉起")

        self.logStep("P3.MMI组件加载正常")

        self.logStep("P4.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_borrow_0046(self):
        region_name = "TC_UBS_MEM_BORROW_0046"
        size = 1024 * 1024 * 1024
        self.logStep(
            "S1.节点0调用接口ubsmem_create_region region_name 0 2 hostx 0 hostx 1 hostx 1创建可以从2节点借出内存共享域")
        rc = self.host_nodes[0].apps[0].ubsmem_create_region(
            region_name, 0,
            UbsmemRegionAttributes(2, [
                UbsmemRegionNodeDesc(self.host_nodes[0].host_name, False),
                UbsmemRegionNodeDesc(self.host_nodes[1].host_name, True),
            ]))
        self.logStep("E1.共享域创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logInfo(f"共享域：{region_name}创建成功,导出节点{self.host_nodes[1].host_name}")
        self.logStep("S2.调用接口ubsmem_lease_malloc region_name 1024*1024*1024 0 0进行fd借用")
        addr_desc = self.host_nodes[0].apps[0].ubsmem_lease_malloc(
            region_name, size, UbsMemInstance.DISTANCE_DIRECT_NODE, 0)
        self.logStep("E2.内存借用成功")
        self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)
        self.logStep("S3.查询借用账本")
        borrow_account_list = self.host_nodes[0].get_borrow_account(self.host_nodes[0].get_host_name())
        self.logStep("E3.账本查询成功，内存由指定节点借出")
        self.logInfo(f"账本信息：{borrow_account_list}")
        self.assertEqual(borrow_account_list[0].lend_node, 2)
        self.logStep("S4.调用接口ubsmem_lease_free addr释放借用内存")
        rc = self.host_nodes[0].apps[0].ubsmem_lease_free(addr_desc.addr)
        self.logStep("E4.内存释放成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S5.节点0调用接口ubsmem_destroy_region region_name")
        rc = self.host_nodes[0].apps[0].ubsmem_destroy_region(region_name)
        self.logStep("E5.共享域删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
