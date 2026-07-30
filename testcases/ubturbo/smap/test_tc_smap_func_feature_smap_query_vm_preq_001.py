# -*- coding: utf-8 -*-
import time

from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload
from libs.core.basecase.ubturbo.smap_params import MigrateNumaMsg


class TestTcSmapFuncFeatureSmapQueryVmPreq001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_QUERY_VM_PREQ_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        起一个虚机，调用smap_query_vm_freq接口，查询虚拟机页频次信息
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP驱动已正确加载
        P4.SMAP正常启动
    TestStep:
        1、查看进程pid：ps -ef | grep qemu
        2、调用SetSmapRemoteNumaInfo，设置远端内存
        3、启动SMAP，添加虚机pid，输入：smap smap_mig_out 5 [pid] 0 1
        4、迁出后等待一个迁移周期，查询虚机占用页频次，输入：smap smap_query_vm_freq
    ExpectedResult:
        E1.得到虚机pid
        E2.接口设置成功
        E3.smap 管理好虚机
        E4.查询成功
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapQueryVmPreq001, self).preTestCase()
        self.logStep("P1.OS正常运行")

        self.logStep("P2.远端借用内存已上线")

        self.logStep("P3.SMAP驱动已正确加载")

        self.logStep("P4.SMAP正常启动")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_query_vm_preq_001(self):
        self.logStep("1、查看进程pid：ps -ef | grep qemu")
        result = self.hosts[0].vm_nodes[0].create()
        self.assertEqual(result, True)
        self.logStep("E1.得到虚机pid")
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        self.assertNotEqual(vm_pid, -1)

        self.logStep("2、调用SetSmapRemoteNumaInfo，设置远端内存")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)
        remote_numa = self.remote_numa_list[0]
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 10000)
        self.logStep("E2.接口设置成功")
        self.assertEqual(rc, 0)

        self.logStep("3、启动SMAP，添加虚机pid，输入：smap smap_mig_out 5 [pid] 0 1")
        msg = MigrateOutMsg([MigrateOutPayload(remote_numa, vm_pid, 0)])
        rc = self.cli[0].smap_mig_out(msg, 1)
        self.logStep("E3.smap 管理好虚机")
        self.assertEqual(rc, 0)

        self.logStep("4、迁出后等待一个迁移周期，查询虚机占用页频次，输入：smap smap_query_vm_freq")
        time.sleep(6)
        rc = self.cli[0].smap_query_vm_freq(vm_pid, 1, 4096)
        self.logStep("E4.查询成功")
        self.assertEqual(rc, 0)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapQueryVmPreq001, self).postTestCase()
        self.safe_delete_vms()