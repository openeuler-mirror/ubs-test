#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from libs.core.basecase.ubturbo import SmapCase, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload


class TestTcSmapFuncFeatureSmapAddProcessTracking001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_ADD_PROCESS_TRACKING_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        添加扫描模式后，查询虚拟机的访问频次
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP组件初始化成功
    TestStep:
        S1.执行virsh create xxx.xml, 启动4U8G虚拟机
        S2.通知SMAP添加进程扫描，并设置扫描周期参数
        S2.1）执行 smap smap_remove vm_pid 1 确保虚机进程未被SMAP纳管
        S2.2）执行 smap smap_add_process_tracking pid_str pid_time 1 0 将进程设置为只扫描状态
        S3.检查 /proc/{PID}_t/tracking_info 是否存在
        S4.调用 smap smap_query_freq_info vm_pid 读取 /proc/{PID}_t/tracking_info 文件
    ExpectedResult:
        E1.虚拟机启动成功
        E2.添加扫描模式成功
        E3. /proc/{PID}_t/tracking_info 文件存在
        E4. /proc/{PID}_t/tracking_info 内容不为空
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapAddProcessTracking001, self).preTestCase()
        self.logStep("P1.OS正常运行")

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)

        self.logStep("P3.SMAP组件初始化成功")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_add_process_tracking_001(self):
        self.logStep("S1.执行virsh create xxx.xml, 启动4U8G虚拟机")
        self.logStep("E1.虚拟机启动成功")
        result = self.hosts[0].vm_nodes[0].create()
        self.assertEqual(result, True)
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()

        self.logStep("S2.通知SMAP添加进程扫描，并设置扫描周期参数")
        self.logStep("S2.1）执行 smap smap_remove vm_pid 1 确保虚机进程未被SMAP纳管")
        self.logStep("S2.2）执行 smap smap_add_process_tracking pid_str pid_time 1 0 将进程设置为只扫描状态")
        self.logStep("E2.添加扫描模式成功")
        rc = self.cli[0].smap_remove(RemoveMsg([RemovePayload(vm_pid)]), 1)
        self.assertEqual(rc in (0, -1), True)

        rc = self.cli[0].smap_remove_process_tracking([vm_pid], 1, 0)
        self.assertEqual(rc, 0)

        rc = self.cli[0].smap_add_process_tracking([vm_pid], [50], 1, 0)
        self.assertEqual(rc, 0)

        self.logStep("S3.检查 /proc/{PID}_t/tracking_info 是否存在")
        self.logStep("E3. /proc/{PID}_t/tracking_info 文件存在")
        result = self.hosts[0].check_file_exists(f"/proc/{vm_pid}_t/tracking_info")
        self.assertEqual(result, True)

        self.logStep("S4.调用 smap smap_query_freq_info vm_pid 读取 /proc/{PID}_t/tracking_info 文件")
        self.logStep("E4. /proc/{PID}_t/tracking_info 内容不为空")
        result = self.cli[0].read_proc_tracking_info(vm_pid)
        self.assertNotEqual(result, [])

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapAddProcessTracking001, self).postTestCase()
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        if vm_pid == -1:
            return
        self.cli[0].smap_remove_process_tracking([vm_pid], 1, 0)