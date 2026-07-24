#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    UBSM_FLAG_MALLOC_WITH_NUMA,
    UBSM_SHMEM_OK,
    UbsMemInstance,
)

import pytest


@pytest.mark.smoke
class TestTcUbsMemProcFault0008(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_PROC_FAULT_0008
    RunLevel:
        Level T
    EnvType:

    CaseName:
        008验证numa借用后使用kill -9构造ubsmd服务故障后查看借用信息
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.调用接口ubsmem_lease_malloc name 1024*1024*1024 0 64进行numa借用
        S2.执行kill -9构造usmd故障
        S3.等待usbmd服务启动
        S4.随机选择一个字符写入内存中
        S5.检查内存的内容是否与写入的一�?
        S6.调用接口ubsmem_lease_free addr释放借用内存
        S7.所有app read size addr 1024 test.txt读取内存的内容到文件，并获取文件的MD5�?
        S8.对比文件的md5�?
        S9.调用接口ubsmem_lease_free addr释放借用内存
    ExpectedResult:
        E1.内存借用成功
        E2.命令执行成功
        E3.ubsmd服务启动成功
        E4.内存写入成功
        E5.内存检查一�?
        E6.内存释放成功
        E7.内存读取成功
        E8.两次md5值一�?
        E9.内存释放成功
    Author:
        tanghongcheng 30062639
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_proc_fault_0008(self):
        mem_size_1g = 1024 * 1024 * 1024
        self.logStep("S1.调用接口ubsmem_lease_malloc name 1024*1024*1024 0 64进行numa借用")
        addr_desc = self.host_nodes[0].apps[0].ubsmem_lease_malloc(
            "default", mem_size_1g, UbsMemInstance.DISTANCE_DIRECT_NODE, UBSM_FLAG_MALLOC_WITH_NUMA, 1)
        self.logStep("E1.内存借用成功")
        self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)

        self.logStep("S2.执行kill -9构造usmd故障")
        kill_ret = self.host_nodes[0].kill_ubsmem_by_sigal(9)
        self.logStep("E2.命令执行成功")
        self.assertEqual(kill_ret, True)
        self.sleep(15)
        self.logStep("S3.等待usbmd服务启动")
        result = self.host_nodes[0].wait_ubsmem_active(120)
        self.logStep("E3.ubsmd服务启动成功")
        self.assertEqual(result, True)
        self.sleep(10)
        expect_char = get_random_char()

        self.logStep("S4.随机选择一个字符写入内存中")
        rc = self.host_nodes[0].apps[0].mem_write(addr_desc.addr, mem_size_1g, expect_char)
        self.logStep("E4.内存写入成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S5.检查内存的内容是否与写入的一�?)
        rc = self.host_nodes[0].apps[0].mem_check(addr_desc.addr, mem_size_1g, expect_char)
        self.logStep("E5.内存检查一�?)
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S6.调用接口ubsmem_lease_free addr释放借用内存")
        ret = self.host_nodes[0].apps[0].ubsmem_lease_free(addr_desc.addr)
        self.logStep("E6.内存释放成功")
        self.assertEqual(ret, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
