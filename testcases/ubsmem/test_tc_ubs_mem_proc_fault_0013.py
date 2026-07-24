#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import PROT_READ, UBSM_SHMEM_OK

import pytest


@pytest.mark.smoke
class TestTcUbsMemProcFault0013(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_PROC_FAULT_0013
    RunLevel:
        Level T
    EnvType:

    CaseName:
        013验证创建共享内存后使用kill -9构造ubsmd服务故障后查看内存共享信�?
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0进程0调用接口ubsmem_shmem_allocate default shm_name 1024*1024*1024 0600 0 创建共享内存
        S2.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存
        S3.节点0执行kill -9构造usmd故障
        S4.等待ubsm服务启动成功
        S5.节点0进程1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存
        S6.节点1进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存
        S7.所有进程调用接口ubsmem_shmem_unmap addr 1024*1024*1024解除映射共享内存
        S8.节点0进程0调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享内存创建成功
        E2.共享内存映射成功
        E3.命令执行成功
        E4.ubsmd服务启动成功
        E5.共享内存映射成功
        E6.共享内存映射成功
        E7.共享内存解除映射成功
        E8.共享内存删除成功
    Author:
        yangdonglin 00919887
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_proc_fault_0013(self):
        shm_name = "TC_UBS_MEM_PROC_FAULT_0013"
        size = 1024 * 1024 * 1024
        self.logStep(
            "S1.节点0进程0调用接口ubsmem_shmem_allocate default shm_name 1024*1024*1024 0600 0 创建共享内存")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            self.default_region, shm_name, size, 0o600, 0)
        self.logStep("E1.共享内存创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep(
            "S2.节点0进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(0, size, PROT_READ, 1, shm_name, 0, 1)
        self.logStep("E2.共享内存映射成功")
        self.assertEqual(addr_desc1.rc, UBSM_SHMEM_OK)
        self.logStep("S3.节点0执行kill -9构造usmd故障")
        result = self.host_nodes[0].kill_ubsmem_by_sigal(9)
        self.logStep("E3.命令执行成功")
        self.assertEqual(result, True)
        self.sleep(15)
        self.logStep("S4.等待ubsm服务启动成功")
        result = self.host_nodes[0].wait_ubsmem_active(120)
        self.logStep("E4.ubsmd服务启动成功")
        self.assertEqual(result, True)
        self.sleep(10)
        self.logStep(
            "S5.节点0进程1调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存")
        addr_desc2 = self.host_nodes[0].apps[1].ubsmem_shmem_map(0, size, PROT_READ, 1, shm_name, 0, 1)
        self.logStep("E5.共享内存映射成功")
        self.assertEqual(addr_desc2.rc, UBSM_SHMEM_OK)
        self.logStep(
            "S6.节点1进程0调用接口ubsmem_shmem_map addr 1024*1024*1024 PROT_READ(1) 1 shm_name 0映射共享内存")
        addr_desc3 = self.host_nodes[1].apps[0].ubsmem_shmem_map(0, size, PROT_READ, 1, shm_name, 0, 1)
        self.logStep("E6.共享内存映射成功")
        self.assertEqual(addr_desc3.rc, UBSM_SHMEM_OK)
        self.logStep("S7.所有进程调用接口ubsmem_shmem_unmap addr 1024*1024*1024解除映射共享内存")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[1].ubsmem_shmem_unmap(addr_desc2.addr, size)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_unmap(addr_desc3.addr, size)
        self.logStep("E7.共享内存解除映射成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)
        self.logStep("S8.节点0进程0调用接口ubsmem_shmem_deallocate shm_name")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E8.共享内存删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
