#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
from libs.core.basecase.ubturbo import SmapCase, EnableNodeMsg
from libs.core.basecase.ubturbo.smap_params import MigrateOutSizePayload, MigrateOutSizeMsg, RemoveMsg


class TestTcSmapFuncFeatureSmapMigrateOutSync001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_MIGRATE_OUT_SYNC_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        正常调用SmapMigrateOutSync接口迁移出虚机进程，内存迁出成功
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP组件初始化成功
        P4.远端numa使能成功
    TestStep:
        S1.执行virsh create xxx.xml启动4U8G虚拟机
        S2.执行SetSmapRunMode 1 将运行模式设置为内存碎片模式
        S3.调用SmapMigrateOutSync dest_nid vm_pid 0 2G 1 1 60000 触发内存迁出
        S4.numastat -p vm_pid观察 虚机内存使用情况
        S5.调用SmapMigrateOutSync dest_nid vm_pid 0 0 1 1 60000 触发内存迁回
        S6.numastat -p vm_pid观察 虚机内存使用情况
    ExpectedResult：
        E1.虚拟机启动成功
        E2.运行模式设置成功
        E3.接口调用成功
        E4.能观测到虚机内存全部迁移到远端，在远端numa上的占用增加
        E5.接口调用成功
        E6.能观测到虚机内存全部迁移到本地，在远端numa上的占用清零
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapMigrateOutSync001, self).preTestCase()
        self.logStep("P1.OS正常运行")
        self.local_numa_list = self.hosts[0].get_local_numa()
        self.assertGreaterEqual(len(self.local_numa_list), 1)

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 1)

        self.logStep("P3.SMAP组件初始化成功")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

        self.logStep("P4.远端numa使能成功")
        rc = self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        self.assertEqual(rc, 0)

    def test_tc_smap_func_feature_smap_migrate_out_sync_001(self):
        self.logStep("S1.执行virsh create xxx.xml启动4U8G虚拟机")
        result = self.hosts[0].vm_nodes[0].create()
        self.logStep("E1.虚拟机启动成功")
        self.assertEqual(result, True)
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        self.assertNotEqual(vm_pid, -1)
        vm_numa = self.hosts[0].vm_nodes[0].get_unique_numa_node()
        rc = self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 0)
        self.assertEqual(rc, 0)
        result = self.hosts[0].watch_proc_mem(vm_pid, self.remote_numa_list[0], 0, 180, True)
        self.assertEqual(result, True)
        mem_topo = self.hosts[0].get_proc_mem_topo_total(vm_pid)

        self.logStep("S2.执行SetSmapRunMode 1 将运行模式设置为内存碎片模式")
        rc = self.cli[0].smap_set_runmode(1)
        self.logStep("E2.运行模式设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S3.调用SmapMigrateOutSync dest_nid vm_pid 0 2G 1 1 60000 触发内存迁出")
        rc = self.cli[0].smap_mig_out_memsize_sync(
            MigrateOutSizeMsg([MigrateOutSizePayload(self.remote_numa_list[0], vm_pid, 0, 1024 * 1024 * 2, 1)]), 1,
            60000)
        self.logStep("E3.接口调用成功")
        self.assertEqual(rc, 0)

        self.logStep("S4.numastat -p vm_pid观察 虚机内存使用情况")
        result = self.hosts[0].watch_proc_mem(vm_pid, self.remote_numa_list[0], 2000, 180)
        self.logStep("E4.能观测到虚机内存全部迁移到远端，在远端numa上的占用增加")
        self.assertEqual(result, True)
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(vm_pid)):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem > mem_topo[nid], True)
            if nid == vm_numa:
                self.assertEqual(mem < mem_topo[nid], True)
            mem_topo[nid] = mem

        self.logStep("S5.调用SmapMigrateOutSync dest_nid vm_pid 0 0 1 1 60000 触发内存迁回")
        rc = self.cli[0].smap_mig_out_memsize_sync(
            MigrateOutSizeMsg([MigrateOutSizePayload(self.remote_numa_list[0], vm_pid, 0, 0, 1)]), 1, 60000)
        self.logStep("E5.接口调用成功")
        self.assertEqual(rc, 0)

        self.logStep("S6.numastat -p vm_pid观察 虚机内存使用情况")
        result = self.hosts[0].watch_proc_mem(vm_pid, self.remote_numa_list[0], 0, 60, True)
        self.logStep("E6.能观测到虚机内存全部迁移到本地，在远端numa上的占用清零")
        self.assertEqual(result, True)
        for nid, mem in enumerate(self.hosts[0].get_proc_mem_topo_total(vm_pid)):
            if nid == self.remote_numa_list[0]:
                self.assertEqual(mem == 0, True)
            if nid == vm_numa:
                self.assertEqual(mem > mem_topo[nid], True)
            mem_topo[nid] = mem

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapMigrateOutSync001, self).postTestCase()
        if len(self.local_numa_list) == 0 or len(self.remote_numa_list) == 0:
            return
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        if vm_pid == -1:
            return
        self.cli[0].smap_set_runmode(0)
        vm_numa = self.hosts[0].vm_nodes[0].get_unique_numa_node()
        self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 0)
        self.hosts[0].watch_proc_mem(vm_pid, self.remote_numa_list[0], 0, 180, True)
        self.cli[0].smap_remove(RemoveMsg([vm_pid]), 1)