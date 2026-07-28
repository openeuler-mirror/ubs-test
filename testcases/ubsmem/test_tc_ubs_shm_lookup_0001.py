#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    PROT_READ,
    PROT_WRITE,
    UBSM_SHMEM_OK,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc, UBSMemShmInfo,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmLookup0001(UbsMemCase):
    """
    CaseNumber:
         TC_UBS_SHM_LOOKUP_0001
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        001验证创建共享内存后查询指定的共享内存信息
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0调用接口ubsmem_create_region region_name 0 2 host0 host1创建共享域
        S2.节点0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 0
        S3.节点0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0
        S4.调用接口ubsmem_shmem_lookup  shm_name查询共享内存信息是否合理
        S5.节点1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0
        S6.调用接口ubsmem_shmem_lookup  shm_name查询共享内存信息是否合理
        S7.节点0调用接口ubsmem_shmem_unmap addr 1024*1024*1024
        S8.节点1调用接口ubsmem_shmem_unmap addr 1024*1024*1024
        S9.节点1调用接口ubsmem_shmem_deallocate shm_name
        S10.app ubsmem_destroy_region region_name
    ExpectedResult:
        E1.共享域创建成功
        E2.共享内存创建成功
        E3.共享内存映射成功
        E4.共享内存信息合理
        E5.共享内存映射成功
        E6.共享内存信息合理
        E7.内存解除映射成功
        E8.内存解除映射成功
        E9.共享内存删除成功
        E10.共享域删除成功
    Author:
        wanghaojie
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    @pytest.mark.case_info(level='P1', type='Functional')
    def test_tc_ubs_shm_lookup_0001(self):
        region_name = "TC_UBS_SHM_LOOKUP_0001"
        shm_name = "TC_UBS_SHM_LOOKUP_0001"
        size = 1024 * 1024 * 1024
        self.logStep("S1.节点0调用接口ubsmem_create_region region_name 0 2 host0 host1创建共享域")
        rc = self.host_nodes[0].apps[0].ubsmem_create_region(
            region_name, 0,
            UbsmemRegionAttributes(2, [
                UbsmemRegionNodeDesc(self.host_nodes[0].host_name, False),
                UbsmemRegionNodeDesc(self.host_nodes[1].host_name, True)]))
        self.logStep("E1.共享域创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S2.节点0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 0")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            region_name, shm_name, size, 0o600, 0)
        self.logStep("E2.共享内存创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep(
            "S3.节点0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(
            0, size, PROT_READ | PROT_WRITE, 1, shm_name, 0, 1)
        self.logStep("E3.共享内存映射成功")
        self.assertEqual(addr_desc1.rc, UBSM_SHMEM_OK)

        self.logStep("S4.调用接口ubsmem_shmem_lookup  shm_name查询共享内存信息是否合理")
        shm_info = UBSMemShmInfo()
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_lookup(shm_name, shm_info)
        self.logStep("E4.共享内存信息合理")
        self.logInfo(f"共享内存信息：{shm_info}")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.assertEqual(shm_info.name, shm_name)
        self.assertEqual(shm_info.size, size)

        self.logStep(
            "S5.节点1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ|PROT_WRITE(3) 1 shm_name 0")
        addr_desc2 = self.host_nodes[1].apps[0].ubsmem_shmem_map(
            0, size, PROT_READ | PROT_WRITE, 1, shm_name, 0, 1)
        self.logStep("E5.共享内存映射成功")
        self.assertEqual(addr_desc2.rc, UBSM_SHMEM_OK)

        self.logStep("S6.调用接口ubsmem_shmem_lookup  shm_name查询共享内存信息是否合理")
        shm_info = UBSMemShmInfo()
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_lookup(shm_name, shm_info)
        self.logStep("E6.共享内存信息合理")
        self.logInfo(f"共享内存信息：{shm_info}")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.assertEqual(shm_info.name, shm_name)
        self.assertEqual(shm_info.size, size)

        self.logStep("S7.节点0调用接口ubsmem_shmem_unmap addr 1024*1024*1024")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        self.logStep("E7.内存解除映射成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S8.节点1调用接口ubsmem_shmem_unmap addr 1024*1024*1024")
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_unmap(addr_desc2.addr, size)
        self.logStep("E8.内存解除映射成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S9.节点1调用接口ubsmem_shmem_deallocate shm_name")
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E9.共享内存删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S10.app ubsmem_destroy_region region_name")
        rc = self.host_nodes[0].apps[0].ubsmem_destroy_region(region_name)
        self.logStep("E10.共享域删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
