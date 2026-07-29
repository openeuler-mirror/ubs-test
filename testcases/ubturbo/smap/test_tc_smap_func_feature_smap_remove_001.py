# -*- coding: utf-8 -*-

from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload, RemoveMsg
from libs.core.basecase.ubturbo.smap_params import RemovePayload


class TestTcSmapFuncFeatureSmapRemove001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_REMOVE_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        调用SmapRemove接口，进程数量为1，pid正确，pidType=0，返回码为0
    PreCondition:
        1.OS正常运行
        2.远端借用内存已上线
        3.SMAP驱动已正确加载
        4.SMAP正常启动
    TestStep:
        1、查看进程pid：ps -ef | grep redis
        2、启动SMAP，输入指令smap smap_remove [pid] [pidType]
        3、打开SMAP日志，查看日志是否正确。 0表示删除成功：cat /var/log/smap_log
        4、验证删除结果，没有VM符合预期：ls/sys/kernel/debug/smap/tiering/vm
    ExpectResult:
        移除VM管理成功
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapRemove001, self).preTestCase()
        self.logStep("1、OS正常运行")

        self.logStep("2、远端借用内存已上线")

        self.logStep("3、SMAP驱动已正确加载")

        self.logStep("4、SMAP正常启动")
        rc = self.cli[0].smap_init(0)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_remove_001(self):
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)
        remote_numa = self.remote_numa_list[0]
        self.logStep("1、查看进程pid：ps -ef | grep redis")
        result = self.hosts[0].start_redis()
        self.assertEqual(result, True)
        pid_list = self.hosts[0].get_process_id("redis-server")
        self.assertNotEqual(pid_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 10000)
        self.assertEqual(rc, 0)
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, pid_list[0], 25)]), 0)
        self.assertEqual(rc, 0)
        self.logStep("2、启动SMAP，输入指令smap smap_remove [pid] [pidType]")
        msg = RemoveMsg([RemovePayload(pid_list[0])])
        rc = self.cli[0].smap_remove(msg, 0)
        self.assertEqual(rc, 0)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapRemove001, self).postTestCase()