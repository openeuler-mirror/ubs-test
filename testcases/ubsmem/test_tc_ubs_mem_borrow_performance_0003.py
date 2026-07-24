#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    NORMAL_MALLOC_TIME,
    UBSM_SHMEM_OK,
    UbsMemInstance,
    UbsMemPerfTp,
)

import pytest


@pytest.mark.smoke
class TestTcUbsMemBorrowPerformance0003(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_MEM_BORROW_PERFORMANCE_0003
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        003验证多次进行正常fd借用借用连续借用1024M性能
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
        P4.环境无借用内存缓存
        P5.CPU负载加压�?0%
    TestStep:
        S1.重启测试程序,获取进程pid
        S2.循环10次调用接口ubsmem_lease_malloc name 1024*1024*1024 0 0进行fd借用
        S3.查询借用性能文件，查询内存借用时延
        S4.调用接口ubsmem_lease_free addr释放所有借用内存
    ExpectedResult:
        E1.重启成功，获取pid成功
        E2.内存借用成功
        E3.查询内存借用时延符合要求
        E4.内存释放成功
    Author:
        zhulinhao 30063494
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_mem_borrow_performance_0003(self):
        self.logStep("S1.重启测试程序,获取进程pid")
        self.host_nodes[0].start_app_by_index(0)
        pid = self.host_nodes[0].get_app_pid(0)

        self.logStep("E1.重启成功，获取pid成功")
        self.assertNotEqual(pid, -1)

        self.logStep("S2.循环10次调用接口ubsmem_lease_malloc name 1024*1024*1024 0 0进行fd借用")
        mem_size = 1024 * 1024 * 1024
        addr_vec = []
        for _ in range(10):
            addr_desc = self.host_nodes[0].apps[0].ubsmem_lease_malloc(
                self.default_region, mem_size, UbsMemInstance.DISTANCE_DIRECT_NODE, 0)

            self.logStep("E2.内存借用成功")
            self.assertEqual(addr_desc.rc, UBSM_SHMEM_OK)
            addr_vec.append(addr_desc.addr)

        self.sleep(35)

        self.logStep("S3.查询借用性能文件，查询内存借用时延")
        latency_time = self.host_nodes[0].get_perf_data(pid, UbsMemPerfTp.TP_UBSM_MALLOC)

        self.logStep("E3.查询内存借用时延符合要求")
        self.assertLess(latency_time.max, NORMAL_MALLOC_TIME)

        self.logStep("S4.调用接口ubsmem_lease_free addr释放所有借用内存")
        for addr in addr_vec:
            ret = self.host_nodes[0].apps[0].ubsmem_lease_free(addr)

            self.logStep("E4.内存释放成功")
            self.assertEqual(ret, UBSM_SHMEM_OK)

    def teardown_method(self):
        super().teardown_method()
        for node in self.host_nodes:
            node.clear_stress()
