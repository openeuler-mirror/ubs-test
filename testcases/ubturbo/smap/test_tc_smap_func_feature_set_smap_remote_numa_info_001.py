#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved

from time import sleep
from libs.core.basecase.ubturbo import SmapCase
from libs.core.basecase.ubturbo.smap_params import EnableNodeMsg, MigrateOutMsg, MigrateOutPayload, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload


class TestTcSmapFuncFeatureSetSmapRemoteNumaInfo001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SET_SMAP_REMOTE_NUMA_INFO_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        正常调用SetSmapRemoteNumaInfo接口，不绑numa
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP组件初始化成功
    TestStep:
        S1.启动 redis-server 进程不绑定numa
        S2.执行redis-benchmark 加压 redis
        S3.通过numastat -p redis_pid 观察 redis 内存使用情况
        S4.调用SetSmapRemoteNumaInfo -1, dest_nid, 256M 设置远端可用内存
        S5.调用SmapMigrateOut redis_pid， 100 设置迁出比例为 100%
        S6.通过numastat -p redis_pid 观察 redis 内存使用情况
    ExpectedResult:
        E1.redis-server 进程启动成功
        E2.redis-benchmark 启动成功
        E3.能观测到redis-server进程 在本地多个numa上有内存占用
        E4.远端可用内存设置成功
        E5.迁出配置 设置成功
        E6.能观测到redis-server在远端numa上的内存占用增加且占用量始终小于256M，在本地多个numa上的占用减少
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSetSmapRemoteNumaInfo001, self).preTestCase()
        self.logStep("P1.OS正常运行")
        self.local_numa_list = self.hosts[0].get_local_numa()
        self.assertGreaterEqual(len(self.local_numa_list), 2)

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 1)

        self.logStep("P3.SMAP组件初始化成功")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)
        for remote_numa in self.remote_numa_list:
            rc = self.cli[0].smap_enable_node(EnableNodeMsg(1, remote_numa))
            self.assertEqual(rc, 0)
            rc = self.cli[0].set_smap_remote_numa_info(-1, remote_numa, 0)
            self.assertEqual(rc, 0)
            for local_numa in self.local_numa_list:
                rc = self.cli[0].set_smap_remote_numa_info(local_numa, remote_numa, 0)
                self.assertEqual(rc, 0)
        self.hosts[0].stop_redis_server()
        self.hosts[0].stop_redis_benchmark()

    def test_tc_smap_func_feature_set_smap_remote_numa_info_001(self):
        self.logStep("S1.启动 redis-server 进程不绑定numa")
        result = self.hosts[0].start_redis_with_numa_nodes([], 6379)
        self.logStep("E1.redis-server 进程启动成功")
        self.assertEqual(result, True)
        redis_pids = self.hosts[0].get_process_id("redis-server")
        self.assertEqual(len(redis_pids), 1)

        self.logStep("S2.执行redis-benchmark 加压 redis")
        result = self.hosts[0].start_redis_benchmark_full_param(
            10 ** 11, 128, 64 * 1024, 8 * 1024, 8, "127.0.0.1", 6379)
        self.logStep("E2.redis-benchmark 启动成功")
        self.assertEqual(result, True)

        self.logStep("S3.通过numastat -p redis_pid 观察 redis 内存使用情况")
        result = self.hosts[0].watch_proc_mem_sum(redis_pids[0], self.local_numa_list, 512, 180)
        self.logStep("E3.能观测到redis-server进程 在本地多个numa上有内存占用")
        self.assertEqual(result, True)
        mem_topo = self.hosts[0].get_proc_mem_topo_total(redis_pids[0])

        self.logStep("S4.调用SetSmapRemoteNumaInfo -1, dest_nid, 256M 设置远端可用内存")
        rc = self.cli[0].set_smap_remote_numa_info(-1, self.remote_numa_list[0], 256)
        self.logStep("E4.远端可用内存设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S5.调用SmapMigrateOut redis_pid， 100 设置迁出比例为 100%")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], redis_pids[0], 100)]),
                                      0)
        self.logStep("E5.迁出配置 设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S6.通过numastat -p redis_pid 观察远端内存用量")
        result = self.hosts[0].watch_proc_mem(redis_pids[0], self.remote_numa_list[0], 240, 180)
        self.assertEqual(result, True)
        self.logStep("E6.能观测到redis-server在远端numa上的内存占用增加且占用量始终小于256M，在本地多个numa上的占用减少")
        sleep(10)
        local_mem_sum_pre = 0
        local_mem_sum_cur = 0
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(redis_pids[0])):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem > mem_topo[nid], True)
                self.assertLess(mem, 256)
            if nid in self.local_numa_list:
                local_mem_sum_pre += mem_topo[nid]
                local_mem_sum_cur += mem
            mem_topo[nid] = mem
        self.assertLess(local_mem_sum_cur, local_mem_sum_pre)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSetSmapRemoteNumaInfo001, self).postTestCase()
        for redis_pid in self.hosts[0].get_process_id("redis-server"):
            self.cli[0].smap_remove(RemoveMsg([RemovePayload(redis_pid)]), 0)
        for remote_numa in self.remote_numa_list:
            self.cli[0].smap_enable_node(EnableNodeMsg(1, remote_numa))
            self.cli[0].set_smap_remote_numa_info(-1, remote_numa, 0)
            for local_numa in self.local_numa_list:
                self.cli[0].set_smap_remote_numa_info(local_numa, remote_numa, 0)