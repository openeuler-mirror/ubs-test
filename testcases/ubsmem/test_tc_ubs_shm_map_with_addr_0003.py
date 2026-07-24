#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    MAP_SHARED,
    PROT_READ,
    PROT_WRITE,
    UBSM_FLAG_ONLY_IMPORT_NONCACHE,
    UBSM_FLAG_WR_DELAY_COMP,
    UBSM_SHMEM_OK,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmMapWithAddr0003(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_MAP_WITH_ADDR_0003
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        003指定地址映射1024M大小共享内存
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.节点0调用接口ubsmem_shmem_allocate default shm_name 1024*1024*1024 0600  UBSM_FLAG_ONLY_IMPORT_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(12)
        S2.节点0调用接口ubsmem_shmem_map 0x800000000000 1024*1024*1024 PROT_READ|PROT_WRITE(3)  MAP_SHARED(1) shm_name 0
        S3.节点0调用接口ubsmem_shmem_map 0x800000000000 1024*1024*1024 PROT_READ|PROT_WRITE(3)  MAP_SHARED(1) shm_name 0
        S4.随机取一个字符并写入得到的地址�?
        S5.检查内存内容是否与写入的一�?
        S6.随机取一个字符并写入得到的地址�?
        S7.检查内存内容是否与写入的一�?
        S8.调用接口ubsmem_shmem_unmap addr 1024*1024*1024 解除映射的共享内�?
        S9.调用接口ubsmem_shmem_deallocate shm_name
        S10.节点0调用接口read addr 1024 test.txt 读取内存的内容到文件
        S11.节点0获取文件的md5值并做对�?
        S12.调用接口ubsmem_shmem_unmap addr 1024*1024*1024 解除映射的共享内�?
        S13.调用接口ubsmem_shmem_deallocate shm_name
    ExpectedResult:
        E1.共享内存创建成功
        E2.共享内存映射成功，返回地址等于指定地址
        E3.共享内存映射成功，返回地址等于指定地址
        E4.内存写入成功
        E5.内存检查结果一�?
        E6.内存写入成功
        E7.内存检查结果一�?
        E8.共享内存解除成功
        E9.共享内存删除成功
        E10.文件读取成功
        E11.文件对比一�?
        E12.共享内存解除成功
        E13.共享内存删除成功
    Author:
        yangdonglin 00919887
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_shm_map_with_addr_0003(self):
        size = 1024 * 1024 * 1024
        shm_name = "TC_UBS_SHM_MAP_WITH_ADDR_0003"
        self.logStep(
            "S1.节点0调用接口ubsmem_shmem_allocate default shm_name 1024*1024*1024 0600  UBSM_FLAG_ONLY_IMPORT_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(12)")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
            self.default_region, shm_name, size, 0o600,
            UBSM_FLAG_ONLY_IMPORT_NONCACHE | UBSM_FLAG_WR_DELAY_COMP,)
        self.logStep("E1.共享内存创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        addr = "800000000000"
        self.logStep(
            "S2.节点0调用接口ubsmem_shmem_map 0x800000000000 1024*1024*1024 PROT_READ|PROT_WRITE(3)  MAP_SHARED(1) shm_name 0")
        addr_desc1 = self.host_nodes[0].apps[0].ubsmem_shmem_map(
            addr, size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_name, 0)
        self.logStep("E2.共享内存映射成功，返回地址等于指定地址")
        self.assertEqual(addr_desc1.addr, addr)

        self.logStep(
            "S3.节点0调用接口ubsmem_shmem_map 0x800000000000 1024*1024*1024 PROT_READ|PROT_WRITE(3)  MAP_SHARED(1) shm_name 0")
        addr_desc2 = self.host_nodes[1].apps[0].ubsmem_shmem_map(
            addr, size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_name, 0)
        self.logStep("E3.共享内存映射成功，返回地址等于指定地址")
        self.assertEqual(addr_desc2.addr, addr)

        expect_char = get_random_char()
        self.logStep("S4.随机取一个字符并写入得到的地址�?)
        rc = self.host_nodes[0].apps[0].mem_write(addr_desc1.addr, size, expect_char)
        self.logStep("E4.内存写入成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S5.检查内存内容是否与写入的一�?)
        rc = self.host_nodes[1].apps[0].mem_check(addr_desc2.addr, size, expect_char)
        self.logStep("E5.内存检查结果一�?)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        expect_char = get_random_char()
        self.logStep("S6.随机取一个字符并写入得到的地址�?)
        rc = self.host_nodes[1].apps[0].mem_write(addr_desc2.addr, size, expect_char)
        self.logStep("E6.内存写入成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S7.检查内存内容是否与写入的一�?)
        rc = self.host_nodes[0].apps[0].mem_check(addr_desc2.addr, size, expect_char)
        self.logStep("E7.内存检查结果一�?)
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S8.调用接口ubsmem_shmem_unmap addr 1024*1024*1024 解除映射的共享内�?)
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_unmap(addr_desc1.addr, size)
        self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[1].apps[0].ubsmem_shmem_unmap(addr_desc2.addr, size)
        self.logStep("E8.共享内存解除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S9.调用接口ubsmem_shmem_deallocate shm_name")
        rc = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
        self.logStep("E9.共享内存删除成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
