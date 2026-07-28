#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    PROT_READ,
    PROT_WRITE,
    UBSM_FLAG_NONCACHE,
    UBSM_FLAG_WR_DELAY_COMP,
    UBSM_SHMEM_OK,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmMap0040(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_MAP_0040
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        040验证NC同节点多进程使用写模式映射1G共享内存
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0进程0调用接口ubsmem_create_region name0 0 2 host0 1 host1 0指定节点0导出内存
        S2.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 UBSM_FLAG_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(6)
        S3.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0
        S4.节点0进程1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0
        S5.两个进程都调用接口ubsmem_shmem_unmap addr 1024*1024*1024
        S6.进程0调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享域创建成功
        E2.共享内存创建成功
        E3.共享内存映射成功
        E4.共享内存映射成功
        E5.内存解除映射成功
        E6.共享内存删除成功
    Author:
        wanghaojie
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    @pytest.mark.case_info(level='P1', type='Functional')
    def test_tc_ubs_shm_map_0040(self):
        region_name = "TC_UBS_SHM_MAP_0040"
        shm_name = "TC_UBS_SHM_MAP_0040"
        size = 1024 * 1024 * 1024
        self.logStep(
            "S1.节点0进程0调用接口ubsmem_create_region name0 0 2 host0 1 host1 0指定节点0导出内存")
        rc = self.host_nodes[0].apps[0].ubsmem_create_region(
            region_name, 0,
            UbsmemRegionAttributes(2, [
                UbsmemRegionNodeDesc(self.host_nodes[0].host_name, True),
                UbsmemRegionNodeDesc(self.host_nodes[1].host_name, False),
            ]))
        self.logStep("E1.共享域创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep(
            "S2.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 UBSM_FLAG_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(6)")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            region_name, shm_name, size, 0o600, UBSM_FLAG_NONCACHE | UBSM_FLAG_WR_DELAY_COMP)
        self.logStep("E2.共享内存创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S3.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(
            0, size, PROT_READ | PROT_WRITE, 1, shm_name, 0)
        self.logStep("E3.共享内存映射成功")
        self.assertEqual(addr_desc1.rc, UBSM_SHMEM_OK)
        self.logStep("S4.节点0进程1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0")
        addr_desc2 = self.host_nodes[0].apps[1].ubsmem_shmem_map(
            0, size, PROT_READ | PROT_WRITE, 1, shm_name, 0)
        self.logStep("E4.共享内存映射成功")
        self.assertEqual(addr_desc2.rc, UBSM_SHMEM_OK)
        self.logStep("S5.两个进程都调用接口ubsmem_shmem_unmap addr 1024")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[1].ubsmem_shmem_unmap(addr_desc2.addr, size)
        self.logStep("E5.内存解除映射成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S6.进程0调用接口ubsmem_shmem_deallocate shm_name")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E6.共享内存删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[0].ubsmem_destroy_region(region_name)
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
