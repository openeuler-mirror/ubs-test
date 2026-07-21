#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    PROT_READ,
    PROT_WRITE,
    UBSM_FLAG_ONLY_IMPORT_NONCACHE,
    UBSM_FLAG_WR_DELAY_COMP,
    UBSM_SHMEM_OK,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.ubs_mem_smoke
class TestTcUbsShmMap0043(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_MAP_0043
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        043验证导出方CC导入方NC创建1024共享内存一致性
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0进程0调用接口ubsmem_create_region name0 0 2 host0 0 host1 1指定节点1导出内存
        S2.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 UBSM_FLAG_ONLY_IMPORT_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(12)
        S3.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_WRITE|PROT_READ(3) 1 shm_name 0
        S4.节点1进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_WRITE|PROT_READ(3) 1 shm_name 0
        S5.随机取一个字符并写入得到的地址中
        S5.检查内存内容是否与写入的一致
        S7.两个进程都调用接口ubsmem_shmem_unmap addr 1024*1024*1024
        S8.节点0进程0调用接口ubsmem_shmem_deallocate shm_name
        S9.节点0进程0调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享域创建成功
        E2.共享内存创建成功
        E3.共享内存映射成功
        E4.共享内存映射成功
        E5.内存写入成功
        E6.内存检查结果一致
        E7.内存解除映射成功
        E8.共享内存删除成功
        E9.共享内存删除成功
    Author:
        yangdonglin 00919887
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_shm_map_0043(self):
        region_name = "TC_UBS_SHM_MAP_0043"
        shm_name = "TC_UBS_SHM_MAP_0043"
        size = 1024 * 1024 * 1024
        self.logStep(
            "S1.节点0进程0调用接口ubsmem_create_region name0 0 2 host0 0 host1 1指定节点1导出内存")
        rc = self.host_nodes[0].apps[0].ubsmem_create_region(
            region_name, 0,
            UbsmemRegionAttributes(2, [
                UbsmemRegionNodeDesc(self.host_nodes[0].host_name, False),
                UbsmemRegionNodeDesc(self.host_nodes[1].host_name, True),
            ]))
        self.logStep("E1.共享域创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep(
            "S2.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 1024 0600 UBSM_FLAG_ONLY_IMPORT_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(12)")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            region_name, shm_name, size, 0o600,
            UBSM_FLAG_ONLY_IMPORT_NONCACHE | UBSM_FLAG_WR_DELAY_COMP,)
        self.logStep("E2.共享内存创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep(
            "S3.节点0进程0调用接口ubsmem_shmem_map addr 1024 PROT_WRITE|PROT_READ(3) 1 shm_name 0 1")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(
            0, size, PROT_READ | PROT_WRITE, 1, shm_name, 0)
        self.logStep("E3.共享内存映射成功")
        self.assertEqual(addr_desc1.rc, UBSM_SHMEM_OK)
        self.logStep("S4.节点1进程0调用接口ubsmem_shmem_map addr 10244 PROT_READ(2) 1 shm_name 0 1")
        addr_desc2 = self.host_nodes[1].apps[0].ubsmem_shmem_map(0, size, PROT_READ, 1, shm_name, 0)
        self.logStep("E4.共享内存映射成功")
        self.assertEqual(addr_desc2.rc, UBSM_SHMEM_OK)
        for i in range(2):
            self.logInfo(f"This is {i}th test")
            expect_char = get_random_char()
            self.logStep("S5.随机取一个字符并写入得到的地址中")
            rc = self.host_nodes[0].apps[0].mem_write(addr_desc1.addr, size, expect_char)
            self.logStep("E5.内存写入成功")
            self.assertEqual(rc, UBSM_SHMEM_OK)
            self.logStep("S6.检查内存内容是否与写入的一致")
            rc = self.host_nodes[1].apps[0].mem_check(addr_desc2.addr, size, expect_char)
            self.logStep("E6.内存检查结果一致")
            self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S7.两个进程都调用接口ubsmem_shmem_unmap addr 1024")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_unmap(addr_desc2.addr, size)
        self.logStep("E7.内存解除映射成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S8.节点0进程0调用接口ubsmem_shmem_deallocate shm_name")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E8.共享内存删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[0].ubsmem_destroy_region(region_name)
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
