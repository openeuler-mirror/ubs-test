# -*- coding: utf-8 -*-

from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload, EnableNodeMsg, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload


class TestTcSmapFuncFeatureSmapMigrateBack001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_MIGRATE_BACK_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用SmapMigrateBack接口，count = 1，src_nid = 5，返回0
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP驱动已正确加载
        P4.SMAP正常启动
        P5.SmapMigrateOut内存迁出成功
    TestStep:
        S1.查看虚机pid: pgrep -lf qemu, 其中pidType等于1表示虚机
        S2.启动SMAP，输入指令：smap smap_mig_out [dest_nid] [pid] 25 1
        S3.迁出成功后，首先查询要迁回的内存地址，执行demsg | grep smap_iomem
        S4.执行指令：smap smap_mig_back [src_nid] [paStart] [paEnd]
        S5.查看返回码
    ExpectedResult:
        内存迁回成功
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapMigrateBack001, self).preTestCase()
        self.logStep("P1.OS正常运行")

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertGreaterEqual(len(self.remote_numa_list), 1)

        self.logStep("P3.SMAP驱动已正确加载")

        self.logStep("P4.SMAP正常启动")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_migrate_back_001(self):
        remote_numa = self.remote_numa_list[0]
        self.logStep("1、查看进程id")
        result = self.hosts[0].start_redis()
        self.assertEqual(result, True)
        pid_list = self.hosts[0].get_process_id("redis-server")
        self.assertNotEqual(pid_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(-1, remote_numa, 10000)
        self.assertEqual(rc, 0)
        self.logStep("2、启动SMAP，输入指令：smap smap_mig_out [dest_nid] [pid] 25 0")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, pid_list[0], 25)]), 0)
        self.assertEqual(rc, 0)
        self.logStep("3、迁出成功后，首先查询要迁回的内存地址，执行demsg | grep smap_iomem")
        addr_list = self.hosts[0].get_smap_out_addrs(remote_numa)
        self.assertNotEqual(addr_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(-1, remote_numa, 0)
        self.assertEqual(rc, 0)
        self.logStep("4、执行指令：smap smap_mig_back [src_nid] [paStart] [paEnd]")
        result = self.cli[0].batch_mig_back(remote_numa, -1, addr_list)
        self.logStep("5、查看返回码")
        self.assertEqual(result, True)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapMigrateBack001, self).postTestCase()
        if len(self.remote_numa_list) == 0:
            return
        self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        self.cli[0].set_smap_remote_numa_info(-1, self.remote_numa_list[0], 0)
        for redis_pid in self.hosts[0].get_process_id("redis-server"):
            self.hosts[0].watch_proc_mem(redis_pid, self.remote_numa_list[0], 0, 180, True)
            self.cli[0].smap_remove(RemoveMsg([RemovePayload(redis_pid)]), 0)
            self.hosts[0].kill_process_by_id(redis_pid)