# -*- coding: utf-8 -*-
from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload


class TestTcSmapFuncFeatureSmapMigrateOut001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_MIGRATE_OUT_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用SmapMigrateOut接口，pid对应一个存在的普通进程，ratio = 50，node_id = 5, pidType与SmapInit接口的pageType对应为0，返回码为0
    PreCondition:
        P1.OS正常运行
        P2.远端借用内存已上线
        P3.SMAP驱动已正确加载
        P4.SMAP正常启动
    TestStep:
        S1.查看进程pid：ps -ef | grep redis
        S2.启动SMAP，输入指令：smap smap_mig_out 0 [pid] 50 0
        S3.打开SMAP日志，查看日志是否正确 0表示迁出成功：cat /var/log/smap_log
        S4.验证是否迁出成功，查看虚机状态：numastat -p qemu-system-aar
    ExpectedResult:
        迁出成功
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapMigrateOut001, self).preTestCase()
        self.logStep("P1.OS正常运行")

        self.logStep("P2.远端借用内存已上线")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)

        self.logStep("P3.SMAP驱动已正确加载")

        self.logStep("P4.SMAP正常启动")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_migrate_out_001(self):
        remote_numa = self.remote_numa_list[0]
        self.logStep("1、查看进程pid：ps -ef | grep redis")
        result = self.hosts[0].start_redis()
        self.assertEqual(result, True)
        pid_list = self.hosts[0].get_process_id("redis-server")
        self.assertNotEqual(pid_list, [])
        self.hosts[0].start_redis_benchmark()
        rc = self.cli[0].set_smap_remote_numa_info(-1, remote_numa, 10000)
        self.assertEqual(rc, 0)
        self.logStep("2、启动SMAP，输入指令：smap smap_mig_out 5 [pid] 50 0")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, pid_list[0], 50)]), 0)
        self.assertEqual(rc, 0)
        self.logStep("4、验证是否迁出成功，查看虚机状态：numastat -p qemu-system-aar")
        result = self.hosts[0].watch_proc_mem(pid_list[0], remote_numa, 1, 60)
        self.assertEqual(result, True)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapMigrateOut001, self).postTestCase()
        self.hosts[0].stop_redis_server()
        self.hosts[0].stop_redis_benchmark()