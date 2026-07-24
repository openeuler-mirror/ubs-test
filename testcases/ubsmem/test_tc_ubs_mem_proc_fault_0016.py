#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    PROT_READ,
    UBSM_SHMEM_ERR_ALREADY_EXIST,
    UBSM_SHMEM_OK,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.smoke
class TestTcUbsMemProcFault0016(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_PROC_FAULT_0016
    RunLevel:
        Level T
    EnvType:

    CaseName:
        016验证创建共享域使用kill -9构造ubsmd服务故障后查看共享域信息
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.进程0调用接口ubsmem_create_region region_name 0 2 host0 host1
        S2.执行kill -9构造usmd故障
        S3.等待ubsm服务启动成功
        S4.进程1调用接口ubsmem_create_region region_name 0 2 host0 host1创建共享�?
        S5.进程1调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 0 创建共享内存
        S6.进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存
        S7.进程0调用接口ubsmem_shmem_unmap addr 1024*1024*1024解除映射共享内存
        S8.节点0进程0调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享域创建成�?
        E2.命令执行成功
        E3.ubsmd服务启动成功
        E4.共享域创建失�?
        E5.共享内存创建成功
        E6.共享内存映射成功
        E7.共享内存借出映射成功
        E8.共享内存删除成功
    Author:
        liyupeng 30050169
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_proc_fault_0016(self):
        alloc_size = 1024 * 1024 * 1024
        shm_name = "TC_UBS_MEM_PROC_FAULT_0016"
        region_name = "TC_UBS_MEM_PROC_FAULT_0016"
        reg_attr = UbsmemRegionAttributes(2, [
            UbsmemRegionNodeDesc(self.host_nodes[0].host_name, True),
            UbsmemRegionNodeDesc(self.host_nodes[1].host_name, False),
        ])

        self.logStep("S1.进程0调用接口ubsmem_create_region region_name 0 2 host0 host1")
        res = self.host_nodes[0].apps[0].ubsmem_create_region(region_name, 0, reg_attr)
        self.logStep("E1.共享域创建成�?)
        self.assertEqual(res, UBSM_SHMEM_OK)

        self.logStep("S2.执行kill -9构造usmd故障")
        res = self.host_nodes[0].kill_ubsmem_by_sigal(9)
        self.logStep("E2.命令执行成功")
        self.assertTrue(res)
        self.sleep(5)
        self.logStep("S3.等待ubsm服务启动成功")
        result = self.host_nodes[0].wait_ubsmem_active(120)
        self.logStep("E3.ubsmd服务启动成功")
        self.assertEqual(result, True)
        self.sleep(15)
        self.logStep("S4.进程1调用接口ubsmem_create_region region_name 0 2 host0 host1创建共享�?)
        res = self.host_nodes[0].apps[1].ubsmem_create_region(region_name, 0, reg_attr)
        self.logStep("E4.共享域创建失�?)
        self.assertEqual(res, UBSM_SHMEM_ERR_ALREADY_EXIST)

        self.logStep(
            "S5.进程1调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 0 创建共享内存")
        res = self.host_nodes[0].apps[1].ubsmem_shmem_allocate(
            region_name, shm_name, alloc_size, 0o600, 0)
        self.logStep("E5.共享内存创建成功")
        self.assertEqual(res, UBSM_SHMEM_OK)

        self.logStep(
            "S6.进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存")
        addr_desc = self.host_nodes[0].apps[0].ubsmem_shmem_map(
            0, alloc_size, PROT_READ, 1, shm_name, 0, 1)
        self.logStep("E6.共享内存映射成功")
        self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)

        self.logStep("S7.进程0调用接口ubsmem_shmem_unmap addr 1024*1024*1024解除映射共享内存")
        res = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc.addr, alloc_size)
        self.logStep("E7.共享内存借出映射成功")
        self.assertEqual(res, UBSM_SHMEM_OK)

        self.logStep("S8.节点0进程0调用接口ubsmem_shmem_deallocate shm_name")
        res = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E8.共享内存删除成功")
        self.assertEqual(res, UBSM_SHMEM_OK)

        res = self.host_nodes[0].apps[0].ubsmem_destroy_region(region_name)
        self.assertEqual(res, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
