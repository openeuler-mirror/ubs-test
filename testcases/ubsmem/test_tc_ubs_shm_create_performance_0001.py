#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    NORMAL_MALLOC_TIME,
    UBSM_SHMEM_OK,
    UbsMemPerfTp,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmCreatePerformance0001(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_CREATE_PERFORMANCE_0001
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        001验证多次在请求节点创建共享内存1024M性能
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
        P4.CPU负载加压到50%
    TestStep:
        S1.重启测试程序,获取进程pid
        S2.调用接口ubsmem_create_region name 0 0 2 host0 1 host1 0指定请求节点导出内存
        S3.节点0循环10次调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 0
        S4.查询借用性能文件，查询创建共享内存时延
        S5.节点1调用接口ubsmem_shmem_deallocate shm_name删除所有共享内存
    ExpectedResult:
        E1.重启成功，获取pid成功
        E2.共享域创建成功
        E3.共享内存创建成功
        E4.查询共享内存创建时延符合要求
        E5.共享内存删除成功
    Author:
        zhulinhao 30063494
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    def test_tc_ubs_shm_create_performance_0001(self):
        self.logStep("S1.重启测试程序,获取进程pid")
        self.host_nodes[0].start_app_by_index(0)
        pid = self.host_nodes[0].get_app_pid(0)

        self.logStep("E1.重启成功，获取pid成功")
        self.assertNotEqual(pid, -1)

        region_name = "TC_UBS_SHM_CREATE_PERFORMANCE_0001"
        shm_name_prefix = "TC_UBS_SHM_CREATE_PERFORMANCE_0001"
        size = 1024 * 1024 * 1024
        shm_name_list = []

        self.logStep(
            "S2.调用接口ubsmem_create_region name 0 0 2 host0 1 host1 0指定请求节点导出内存")
        rc = self.host_nodes[0].apps[0].ubsmem_create_region(
            region_name, 0,
            UbsmemRegionAttributes(2, [
                UbsmemRegionNodeDesc(self.host_nodes[0].host_name, True),
                UbsmemRegionNodeDesc(self.host_nodes[1].host_name, False),
            ]))

        self.logStep("E2.共享域创建成功")
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.logStep("S3.节点0循环10次调用接口ubsmem_shmem_allocate region_name shm_name 1024*1024*1024 0600 0")
        for i in range(10):
            shm_name = f"{shm_name_prefix}{i}"
            rc = self.host_nodes[0].apps[0].ubsmem_shmem_allocate(
                region_name, shm_name, size, 0o600, 0)

            self.logStep("E3.共享内存创建成功")
            self.assertEqual(rc, UBSM_SHMEM_OK)
            shm_name_list.append(shm_name)

        self.sleep(35)

        self.logStep("S4.查询借用性能文件，查询创建共享内存时延")
        latency_time = self.host_nodes[0].get_perf_data(pid, UbsMemPerfTp.TP_UBSM_SHM_CREATE)

        self.logStep("E4.查询共享内存创建时延符合要求")
        self.logger.info(f"malloc time {latency_time}")

        self.logStep("S5.节点1调用接口ubsmem_shmem_deallocate shm_name删除所有共享内存")
        for shm_name in shm_name_list:
            rc = self.host_nodes[0].apps[0].ubsmem_shmem_deallocate(shm_name)
            self.logStep("E5.共享内存删除成功")
            self.assertEqual(rc, UBSM_SHMEM_OK)
        rc = self.host_nodes[0].apps[0].ubsmem_destroy_region(region_name)
        self.assertEqual(rc, UBSM_SHMEM_OK)

        self.assertLess(latency_time.max, NORMAL_MALLOC_TIME)

    def teardown_method(self):
        super().teardown_method()
        for node in self.host_nodes:
            node.clear_stress()
