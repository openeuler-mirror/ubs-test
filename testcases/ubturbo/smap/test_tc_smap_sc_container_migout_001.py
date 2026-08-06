#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubturbo import SmapCase, EnableNodeMsg, MigrateOutMsg, MigrateOutPayload, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload


class TestTcSmapScContainerMigout001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_SC_CONTAINER_MIGOUT_001
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        001容器内进程绑定单numa，迁出后迁回
    PreCondition:
        P1.OS正常运行
        P2.容器正常运行
        P3.远端借用内存已上线
        P4.SMAP组件初始化成功
        P5.远端numa使能成功
    TestStep:
        S1.容器内启动 redis-server 进程绑定单numa
        S2.执行 redis-benchmark 加压 redis
        S3.通过numastat -p redis_pid 观察 redis 内存使用情况
        S4.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 4G 设置远端可用内存
        S5.调用SmapMigrateOut redis_pid, 25 设置迁出比例为 25%
        S6.通过numastat -p redis_pid 观察远端内存用量
        S7.调用SmapMigrateOut redis_pid, 0 触发内存迁回
        S8.通过numastat -p redis_pid 观察远端内存用量
    ExpectedResult:
        E1.redis-server 进程启动成功
        E2.redis-benchmark 启动成功
        E3.能观测到 redis-server 进程 src_nid上有内存占用
        E4.远端可用内存设置成功
        E5.迁出配置 设置成功
        E6.能观测到 redis-server dest_nid 上的内存占用增加，src_nid 上的占用减少
        E7.接口调用成功
        E8.能观测到 redis-server dest_nid 上的内存占用清零，src_nid 上的占用增加

    """

    def setup_method(self):
        super(TestTcSmapScContainerMigout001, self).preTestCase()
        self.logStep("P1.OS正常运行")
        self.local_numa_list = self.hosts[0].get_local_numa()
        self.assertGreaterEqual(len(self.local_numa_list), 1)

        self.logStep("P2.容器正常运行")
        result = self.hosts[0].containers[0].check_container_running_status()
        self.assertEqual(result, True)

        self.logStep("P3.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 1)

        self.logStep("P4.SMAP组件初始化成功")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)

        self.logStep("P5.远端numa使能成功")
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

    def test_tc_smap_sc_container_migout_001(self):
        self.logStep("S1.容器内启动 redis-server 进程绑定单numa")
        result = self.hosts[0].containers[0].start_redis_with_numa_nodes([self.local_numa_list[0]], 6379)
        self.logStep("E1.redis-server 进程启动成功")
        self.assertEqual(result, True)
        redis_pids = self.hosts[0].get_process_id("redis-server")
        self.assertEqual(len(redis_pids), 1)

        self.logStep("S2.执行 redis-benchmark 加压 redis")
        result = self.hosts[0].start_redis_benchmark_full_param(
            10 ** 11, 128, 64 * 1024, 8 * 1024, 4, self.hosts[0].containers[0].get_container_ip(), 6379)
        self.logStep("E2.redis-benchmark 启动成功")
        self.assertEqual(result, True)

        self.logStep("S3.通过numastat -p redis_pid 观察 redis 内存使用情况")
        result = self.hosts[0].watch_proc_mem(redis_pids[0], self.local_numa_list[0], 512, 300)
        self.logStep("E3.能观测到 redis-server 进程 src_nid上有内存占用")
        self.assertEqual(result, True)
        mem_topo = self.hosts[0].get_proc_mem_topo_total(redis_pids[0])

        self.logStep("S4.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 4G 设置远端可用内存")
        rc = self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[0], 4096)
        self.logStep("E4.远端可用内存设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S5.调用SmapMigrateOut redis_pid, 25 设置迁出比例为 25%")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], redis_pids[0], 25)]),
                                      0)
        self.logStep("E5.迁出配置 设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S6.通过numastat -p redis_pid 观察远端内存用量")
        result = self.hosts[0].watch_proc_mem(redis_pids[0], self.remote_numa_list[0], 128, 180)
        self.assertEqual(result, True)
        self.logStep("E6.能观测到 redis-server dest_nid 上的内存占用增加，src_nid 上的占用减少")
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(redis_pids[0])):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem > mem_topo[nid], True)
            if nid == self.local_numa_list[0]:
                self.assertEqual(mem < mem_topo[nid], True)
            mem_topo[nid] = mem

        self.logStep("S7.调用SmapMigrateOut redis_pid, 0 触发内存迁回")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], redis_pids[0], 0)]), 0)
        self.logStep("E7.接口调用成功")
        self.assertEqual(rc, 0)

        self.logStep("S8.通过numastat -p redis_pid 观察远端内存用量")
        result = self.hosts[0].watch_proc_mem(redis_pids[0], self.remote_numa_list[0], 0, 180, True)
        self.assertEqual(result, True)
        self.logStep("E8.能观测到 redis-server dest_nid 上的内存占用清零，src_nid 上的占用增加")
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(redis_pids[0])):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem == 0, True)
            if nid == self.local_numa_list[0]:
                self.assertEqual(mem > mem_topo[nid], True)
            mem_topo[nid] = mem

    def teardown_method(self):
        super(TestTcSmapScContainerMigout001, self).postTestCase()
        for redis_pid in self.hosts[0].get_process_id("redis-server"):
            self.cli[0].smap_remove(RemoveMsg([RemovePayload(redis_pid)]), 0)
        for remote_numa in self.remote_numa_list:
            self.cli[0].smap_enable_node(EnableNodeMsg(1, remote_numa))
            self.cli[0].set_smap_remote_numa_info(-1, remote_numa, 0)
            for local_numa in self.local_numa_list:
                self.cli[0].set_smap_remote_numa_info(local_numa, remote_numa, 0)
        self.hosts[0].stop_redis_server()
        self.hosts[0].stop_redis_benchmark()