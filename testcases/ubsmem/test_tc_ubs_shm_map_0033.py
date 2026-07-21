#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    PROT_NONE,
    PROT_READ,
    PROT_WRITE,
    UBSM_FLAG_CACHE,
    UBSM_SHMEM_OK,
)

import pytest


@pytest.mark.ubs_mem_smoke
class TestTcUbsShmMap0033(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_MAP_0033
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        033验证刷新4K粒度大小的内存
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 128*1024*1024 0600 UBSM_FLAG_CACHE(0)
        S2.节点0进程0调用接口ubsmem_shmem_map addr 128*1024*1024 PROT_NONE(0) 1 shm_name 0
        S3.节点1进程0调用接口ubsmem_shmem_map addr 128*1024*1024 PROT_NONE(0) 1 shm_name 0
        S4.节点0进程0调用接口ubsmem_shmem_set_ownership shm_name 0 4K PROT_WRITE|PROT_READ(3)
        S5.随机取一个字符并写入得到的地址中
        S6.节点1进程0调用接口ubsmem_shmem_set_ownership shm_name 0 4K PROT_READ(1)
        S7.检查内存内容是否与写入的一致
        S8.两个进程都调用接口ubsmem_shmem_unmap addr 128*1024*1024
        S9.节点1进程0调用接口ubsmem_shmem_deallocate shm_name
        S10.节点1进程0调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享内存创建成功
        E2.共享内存映射成功
        E3.共享内存映射成功
        E4.共享内存状态修改成功
        E5.内存写入成功
        E6.共享内存状态修改成功
        E7.内存检查结果一致
        E8.内存解除映射成功
        E9.共享内存删除成功
        E10.共享内存删除成功
    Author:
        yangdonglin 00919887
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_shm_map_0033(self):
        shm_name = "TC_UBS_SHM_MAP_0033"
        size = 128 * 1024 * 1024
        self.logStep(
            "S1.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 128 0600 UBSM_FLAG_CACHE(0)")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            self.default_region, shm_name, size, 0o600, UBSM_FLAG_CACHE)
        self.logStep("E1.共享内存创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S2.节点0进程0调用接口ubsmem_shmem_map addr 128 PROT_NONE(0) 1 shm_name 0 1")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(0, size, PROT_NONE, 1, shm_name, 0)
        self.logStep("E2.共享内存映射成功")
        self.assertEqual(addr_desc1.rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_set_ownership(
            shm_name, addr_desc1.addr, size, PROT_NONE)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S3.节点1进程0调用接口ubsmem_shmem_map addr 128 PROT_NONE(0) 1 shm_name 0 1")
        addr_desc2 = self.host_nodes[1].apps[0].ubsmem_shmem_map(0, size, PROT_NONE, 1, shm_name, 0)
        self.logStep("E3.共享内存映射成功")
        self.assertEqual(addr_desc2.rc, UBSM_SHMEM_OK)
        expect_char = get_random_char()
        self.logStep(
            "S5.节点0进程0调用接口ubsmem_shmem_set_ownership shm_name 0 4K PROT_WRITE|PROT_READ(3)")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_set_ownership(
            shm_name, addr_desc1.addr, 4 * 1024, PROT_WRITE | PROT_READ)
        self.logStep("E5.共享内存状态修改成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S6.随机取一个字符并写入得到的地址中")
        rc = self.host_nodes[0].apps[0].mem_write(addr_desc1.addr, 4 * 1024, expect_char)
        self.logStep("E6.内存写入成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_set_ownership(
            shm_name, addr_desc1.addr, 4 * 1024, PROT_READ)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S7.节点1进程0调用接口ubsmem_shmem_set_ownership shm_name 0 4K PROT_READ(1)")
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_set_ownership(
            shm_name, addr_desc2.addr, 4 * 1024, PROT_READ)
        self.logStep("E7.共享内存状态修改成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S8.检查内存内容是否与写入的一致")
        rc = self.host_nodes[1].apps[0].mem_check(addr_desc2.addr, 4 * 1024, expect_char)
        self.logStep("E8.内存检查结果一致")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S9.两个进程都调用接口ubsmem_shmem_unmap addr 128")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_unmap(addr_desc2.addr, size)
        self.logStep("E9.内存解除映射成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S10.节点1进程0调用接口ubsmem_shmem_deallocate shm_name")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E10.共享内存删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
