#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
from libs.core.basecase.ubturbo import SmapCase
from libs.core.basecase.ubturbo.smap_params import MigrateNumaMsg, MigrateNumaPayload


class TestTcSmapFuncFeatureSmapMigrateRemoteNuma001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_MIGRATE_REMOTE_NUMA_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用迁移远端NUMA禁用PID迁移后迁出进程到远端numa
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3、SMAP驱动已正确加载
        P4、SMAP正常启动
    TestStep:
        S1.启动cli_client执行输入：smap smap_enable_process_migrate011[pid] 禁用pid迁移
        S2.启动cli_client执行输入：smap_migrate_remote_numa561pa1pa2

        E1.禁用成功
        E2.迁出成功

    """

    def setup_method(self):
        self.logStep("P1、OS正常运行")
        self.local_numa_list = self.hosts[0].get_local_numa()
        self.assertGreaterEqual(len(self.local_numa_list), 1)

        self.logStep("P2、远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 1)

        self.logStep("P3、SMAP驱动已正确加载")

        self.logStep("P4、SMAP正常启动")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_migrate_remote_numa_001(self):
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)
        remote_numa = self.remote_numa_list[0]
        remote_numa_1 = self.remote_numa_list[1]

        result = self.hosts[0].create_vms(0, 0)
        self.assertEqual(result, True)
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        self.assertNotEqual(vm_pid, -1)

        self.logStep("S1.启动cli_client执行输入：smap smap_enable_process_migrate011[pid] 禁用pid迁移")
        result = self.cli[0].smap_enable_process_migrate([vm_pid], 1, 0, 0)
        self.logStep("E1.禁用成功")
        self.assertEqual(result, 0)

        self.logStep("S2.启动cli_client执行：smap_migrate_remote_numa561pa1pa2")
        addr_list = self.hosts[0].get_smap_out_addrs(remote_numa)
        self.assertNotEqual(addr_list, [])
        msg = MigrateNumaMsg(remote_numa, remote_numa_1, 1,
                             [MigrateNumaPayload(addr_list[0].pa_start, addr_list[0].pa_end)])
        result = self.cli[0].smap_migrate_remote_numa(msg)
        self.logStep("E2.迁出成功")
        self.assertEqual(result, 0)

    def teardown_method(self):
        self.safe_delete_vms()