#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved

from libs.core.basecase.ubturbo import SmapCase, EnableNodeMsg, MigrateOutMsg, MigrateOutPayload, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload, MigratePidNumaMsg, MigratePidNumaPayload


class TestTcSmapFuncFeatureSmapMigratePidRemoteNuma001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_MIGRATE_PID_REMOTE_NUMA_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        正常调用SmapMigratePidRemoteNuma，将远端内存迁移到其他远端成功
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP组件初始化成功
        P4.远端numa使能成功
    TestStep:
        S1.启动 redis-server
        S2.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 4G 设置远端可用内存
        S3.调用SmapMigrateOut redis_pid， 100 设置迁出比例为 100%
        S4.通过numastat -p redis_pid 观察远端内存使用情况
        S5.调用SmapEnableProcessMigrate redis_pid, 1, 0, 0 禁用冷热迁移
        S6.调用SetSmapRemoteNumaInfo src_nid, dest_nid_new, 4G 设置远端可用内存
        S7.SmapMigratePidRemoteNuma redis_pid, 1, dest_nid, dest_nid_new 更换远端numa
        S8.调用SmapEnableProcessMigrate redis_pid, 1, 1, 0 启用冷热迁移
        S9.通过numastat -p redis_pid 观察远端内存使用情况
    ExpectedResult:
        E1.redis-server 进程启动成功
        E2.远端可用内存设置成功
        E3.迁出配置 设置成功
        E4.能观测到redis-server dest_nid 上的内存占用增加
        E5.冷热迁移禁用成功
        E6.远端可用内存设置成功
        E7.更换远端numa成功
        E8.冷热迁移启用成功
        E9.能观测到 redis-server dest_nid 上的内存占用清零，dest_nid_new 上的占用增加
    """

    def setup_method(self):
        self.logStep("P1.OS正常运行")
        self.local_numa_list = self.hosts[0].get_local_numa()
        self.assertGreaterEqual(len(self.local_numa_list), 1)

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 2)

        self.logStep("P3.SMAP组件初始化成功")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)

        self.logStep("P4.远端numa使能成功")
        rc1 = self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        rc2 = self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[1]))
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)

    def test_tc_smap_func_feature_smap_migrate_pid_remote_numa_001(self):
        self.logStep("S1.启动 redis-server")
        self.hosts[0].stop_redis_server()
        self.hosts[0].start_redis_with_numa_nodes([self.local_numa_list[0]], 6379)
        self.logStep("E1.redis-server 进程启动成功")
        redis_pids = self.hosts[0].get_process_id("redis-server")
        self.assertEqual(len(redis_pids), 1)
        mem_topo = self.hosts[0].get_proc_mem_topo_total(redis_pids[0])

        self.logStep("S2.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 4G 设置远端可用内存")
        rc = self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[0], 4096)
        self.logStep("E2.远端可用内存设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S3.调用SmapMigrateOut redis_pid， 100 设置迁出比例为 100%")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], redis_pids[0], 100)]),
                                      0)
        self.logStep("E3.迁出配置 设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S4.通过numastat -p redis_pid 观察远端内存用量")
        result = self.hosts[0].watch_proc_mem(redis_pids[0], self.remote_numa_list[0], 0, 180)
        self.assertEqual(result, True)
        self.logStep("E4.能观测到redis-server dest_nid 上的内存占用增加")
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(redis_pids[0])):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem > mem_topo[nid], True)
            mem_topo[nid] = mem

        self.logStep("S5.调用SmapEnableProcessMigrate redis_pid, 1, 0, 0 禁用冷热迁移")
        rc = self.cli[0].smap_enable_process_migrate([redis_pids[0]], 1, 0, 0)
        self.logStep("E5.冷热迁移禁用成功")
        self.assertEqual(rc, 0)

        self.logStep("S6.调用SetSmapRemoteNumaInfo src_nid, dest_nid_new, 4G 设置远端可用内存")
        rc = self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[1], 4096)
        self.logStep("E6.远端可用内存设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S7.调用SmapMigratePidRemoteNuma redis_pid, 1, dest_nid, dest_nid_new 更换远端numa")
        msg = MigratePidNumaMsg(
            count=1,
            payload=[
                MigratePidNumaPayload(int(redis_pids[0]), self.remote_numa_list[0], self.remote_numa_list[1], 100, 0)]
        )
        rc = self.cli[0].smap_migrate_pid_remote_numa(msg, 0)
        self.logStep("E7.更换远端numa成功")
        self.assertEqual(rc, 0)

        self.logStep("S8.调用SmapEnableProcessMigrate redis_pid, 1, 1, 0 启用冷热迁移")
        rc = self.cli[0].smap_enable_process_migrate([redis_pids[0]], 1, 1, 0)
        self.logStep("E8.冷热迁移启用成功")
        self.assertEqual(rc, 0)

        self.logStep("S9.通过numastat -p redis_pid 观察远端内存用量")
        result = self.hosts[0].watch_proc_mem(redis_pids[0], self.remote_numa_list[1], 0, 180)
        self.assertEqual(result, True)

        self.logStep("E9.能观测到 redis-server dest_nid 上的内存占用清零，dest_nid_new 上的占用增加")
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(redis_pids[0])):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem == 0, True)
            if nid == self.remote_numa_list[1]:
                self.assertEqual(mem > mem_topo[nid], True)
            mem_topo[nid] = mem

    def teardown_method(self):
        if len(self.local_numa_list) == 0 or len(self.remote_numa_list) < 2:
            return
        for redis_pid in self.hosts[0].get_process_id("redis-server"):
            self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[0], 0)
            self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[1], 0)
            self.hosts[0].watch_proc_mem(redis_pid, self.remote_numa_list[0], 0, 180, True)
            self.hosts[0].watch_proc_mem(redis_pid, self.remote_numa_list[1], 0, 180, True)
            self.cli[0].smap_remove(RemoveMsg([RemovePayload(redis_pid)]), 0)
            self.hosts[0].kill_process_by_id(redis_pid)