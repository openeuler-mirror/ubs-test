#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
from libs.core.basecase.ubturbo import SmapCase, EnableNodeMsg, MigrateOutMsg, MigrateOutPayload, RemoveMsg


class TestTcSmapFuncFeatureSmapRemove002(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_REMOVE_002
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        正常调用SmapRemove移除虚机进程，移除smap纳管成功
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP组件初始化成功
        P4.远端numa使能成功
    TestStep:
        S1.执行virsh create xxx.xml启动4U8G虚拟机
        S2.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 4G 设置远端可用内存
        S3.调用SmapMigrateOut vm_pid, 25 设置迁出比例为 25%
        S4.调用SmapQueryProcessConfig 查询SMAP进程配置
        S5.调用SmapRemove vm_pid 1 将虚机进程移除纳管
        S6.调用SmapQueryProcessConfig 查询SMAP进程配置
    ExpectedResult:
        E1.虚拟机启动成功
        E2.远端可用内存设置成功
        E3.迁出配置 设置成功
        E4.能查询到虚机相关配置
        E5.移除虚机纳管成功
        E6.查询不到虚机相关配置
    """

    def setup_method(self):
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

    def test_tc_smap_func_feature_smap_remove_002(self):
        self.logStep("S1.执行virsh create xxx.xml启动4U8G虚拟机")
        result = self.hosts[0].vm_nodes[0].create()
        self.logStep("E1.虚拟机启动成功")
        self.assertEqual(result, True)
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        self.assertNotEqual(vm_pid, -1)
        vm_numa = self.hosts[0].vm_nodes[0].get_unique_numa_node()

        self.logStep("S2.调用SetSmapRemoteNumaInfo src_nid, dest_nid, 4G 设置远端可用内存")
        rc = self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 4096)
        self.logStep("E2.远端可用内存设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S3.调用SmapMigrateOut vm_pid, 25 设置迁出比例为 25%")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], vm_pid, 25)]), 1)
        self.logStep("E3.迁出配置 设置成功")
        self.assertEqual(rc, 0)

        self.logStep("S4.调用SmapQueryProcessConfig 查询SMAP进程配置")
        process_config = self.cli[0].smap_query_process_config(self.remote_numa_list[0], 1, 4, 1)
        self.logStep("E4.能查询到虚机相关配置")
        self.assertEqual(process_config.ret, 0)
        self.assertGreaterEqual(process_config.outLen, 1)
        self.assertEqual(vm_pid in list(map(lambda payload: payload.pid, process_config.payload)), True)

        self.logStep("S5.调用SmapRemove vm_pid 1 将虚机进程移除纳管")
        rc = self.cli[0].smap_remove(vm_pid, 1)
        self.logStep("E5.移除虚机纳管成功")
        self.assertEqual(rc, 0)

        self.logStep("S6.调用SmapQueryProcessConfig 查询SMAP进程配置")
        process_config = self.cli[0].smap_query_process_config(self.remote_numa_list[0], 1, 4, 1)
        self.logStep("E6.查询不到虚机相关配置")
        self.assertEqual(process_config.ret, 0)
        self.assertGreaterEqual(process_config.outLen, 0)
        self.assertEqual(vm_pid not in list(map(lambda payload: payload.pid, process_config.payload)), True)

    def teardown_method(self):
        if len(self.local_numa_list) == 0 or len(self.remote_numa_list) == 0:
            return
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        if vm_pid == -1:
            return
        vm_numa = self.hosts[0].vm_nodes[0].get_unique_numa_node()
        self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 0)
        self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], vm_pid, 0)]), 1)
        self.hosts[0].watch_proc_mem(vm_pid, self.remote_numa_list[0], 0, 180, True)
        self.cli[0].smap_remove(RemoveMsg([vm_pid]), 1)