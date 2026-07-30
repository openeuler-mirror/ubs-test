#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
import time

from libs.core.basecase.ubturbo import SmapCase
from libs.core.basecase.ubturbo.smap_params import EnableNodeMsg, MigrateOutMsg, MigrateOutPayload, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload


class TestTcSmapFuncFeatureEnableNode002(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_ENABLE_NODE_002
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        正常调用SmapEnableNode禁止远端numa，内存迁出失败
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP组件初始化成功
    TestStep:
        S1.启动 redis-server
        S2.调用SmapEnableNode 0 dest_nid 禁用远端节点
        S3.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 256M 设置远端可用内存
        S4.调用SmapMigrateOut redis_pid， 100 设置迁出比例为 100%
        S5.通过numastat -p redis_pid 观察 redis 内存使用情况
    ExpectedResult:
        E1.redis-server 进程启动成功
        E2.远端节点禁用成功
        E3.远端可用内存设置成功
        E4.迁出配置 设置失败
        E5.能观测到redis-server进程 在远端numa上的内存占用始终为0
    """

    def setup_method(self):
        self.logStep("P1.OS正常运行")
        self.local_numa_list = self.hosts[0].get_local_numa()
        self.assertGreaterEqual(len(self.local_numa_list), 1)

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 1)

        self.logStep("P3.SMAP组件初始化成功")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_enable_node_002(self):
        self.logStep("S1.启动 redis-server")
        self.hosts[0].stop_redis_server()
        self.hosts[0].start_redis_with_numa_nodes([self.local_numa_list[0]], 6379)
        self.logStep("E1.redis-server 进程启动成功")
        redis_pids = self.hosts[0].get_process_id("redis-server")
        self.assertEqual(len(redis_pids), 1)
        mem_topo = self.hosts[0].get_proc_mem_topo_total(redis_pids[0])

        self.logStep("S2.调用SmapEnableNode 0 dest_nid 禁用远端节点")
        rc = self.cli[0].smap_enable_node(EnableNodeMsg(0, self.remote_numa_list[0]))
        self.logStep("E2.远端节点禁用成功")
        self.assertEqual(rc, 0)

        self.logStep("S3.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 256M 设置远端可用内存")
        rc = self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[0], 256)
        self.logStep("E3.远端可用内存设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S4.调用SmapMigrateOut redis_pid， 100 设置迁出比例为 100%")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], redis_pids[0], 100)]),
                                      0)
        self.logStep("E4.迁出配置 设置失败")
        self.assertEqual(rc, -22)

        self.logStep("S5.通过numastat -p redis_pid 观察 redis 内存使用情况")
        time.sleep(10)
        mem_topo_total = self.hosts[0].get_proc_mem_topo_total(redis_pids[0])
        self.logStep("E5.能观测到redis-server进程 在远端numa上的内存占用始终为0")
        for nid, mem in enumerate(mem_topo_total):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem == 0, True)
            mem_topo[nid] = mem

    def teardown_method(self):
        if len(self.local_numa_list) == 0 or len(self.remote_numa_list) == 0:
            return
        self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        self.cli[0].set_smap_remote_numa_info(self.local_numa_list[0], self.remote_numa_list[0], 0)
        for redis_pid in self.hosts[0].get_process_id("redis-server"):
            self.hosts[0].watch_proc_mem(redis_pid, self.remote_numa_list[0], 0, 180, True)
            self.cli[0].smap_remove(RemoveMsg([RemovePayload(redis_pid)]), 0)
            self.hosts[0].kill_process_by_id(redis_pid)