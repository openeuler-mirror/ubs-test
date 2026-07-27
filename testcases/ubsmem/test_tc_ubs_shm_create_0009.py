#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    PROT_NONE,
    UBSM_FLAG_CACHE,
    UBSM_SHMEM_OK,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmCreate0010(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_CREATE_0009
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        009验证单次创建UBSM_FLAG_CACHE(0)类型的1024M共享内存
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 UBSM_FLAG_CACHE(0)
        S2.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_NONE(0) 1 shm_name 0
        S3.节点0进程1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_NONE(0) 1 shm_name 0
        S4.两个进程都调用接口ubsmem_shmem_unmap addr 1024*1024*1024
        S5.进程0调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享内存创建成功
        E2.共享内存映射成功
        E3.共享内存映射成功
        E4.内存解除映射成功
        E5.共享内存删除成功
    Author:
        wanghaojie
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_tc_ubs_shm_create_0009(self):
        shm_name = "TC_UBS_SHM_CREATE_0009"
        size = 1024 * 1024 * 1024
        self.logStep(
            "S1.节点0进程0调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 UBSM_FLAG_CACHE(0)")
        res = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            self.default_region, shm_name, size, 0o600, UBSM_FLAG_CACHE)

        self.logStep("E1.共享内存创建成功")
        self.assertEqual(res, UBSM_SHMEM_OK)

        self.logStep("S2.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_NONE(0) 1 shm_name 0")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(0, size, PROT_NONE, 1, shm_name, 0, 1)

        self.logStep("E2.共享内存映射成功")
        self.assertEqual(addr_desc1.rc, UBSM_SHMEM_OK)

        self.logStep("S3.节点0进程1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_NONE(0) 1 shm_name 0")
        addr_desc2 = self.host_nodes[0].apps[1].ubsmem_shmem_map(0, size, PROT_NONE, 1, shm_name, 0, 1)

        self.logStep("E3.共享内存映射成功")
        self.assertEqual(addr_desc2.rc, UBSM_SHMEM_OK)

        self.logStep("S4.两个进程都调用接口ubsmem_shmem_unmap addr 1024*1024*1024")
        ret_code1 = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        ret_code2 = self.host_nodes[0].apps[1].ubsmem_shmem_unmap(addr_desc2.addr, size)

        self.logStep("E4.内存解除映射成功")
        self.assertEqual(ret_code1, UBSM_SHMEM_OK)
        self.assertEqual(ret_code2, UBSM_SHMEM_OK)

        self.logStep("S5.进程0调用接口ubsmem_shmem_deallocate shm_name")
        ret_code = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)

        self.logStep("E5.共享内存删除成功")
        self.assertEqual(ret_code, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
