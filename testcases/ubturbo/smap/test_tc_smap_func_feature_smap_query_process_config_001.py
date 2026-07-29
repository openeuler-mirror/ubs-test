# -*- coding: utf-8 -*-
from libs.core.basecase.ubturbo import SmapCase, MigrateOutPayload, MigrateOutMsg


class TestTcSmapFuncFeatureSmapQueryProcessConfig001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_QUERY_PROCESS_CONFIG_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        正常调用SmapMigrateOut接口进行虚机配置，再调用QueryProcessConfig接口
    PreCondition:
        1. smap初始化成功
    TestStep:
        1. 创建虚机
        2. 设置远端numa信息
        3. 虚机迁出25%
        4. 调用smap smap_query_process_config接口
    ExpectedResult:
        1. 虚机创建成功
        2. 设置numa信息成功
        3. 迁出成功
        4. 查询结果符合预期
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapQueryProcessConfig001, self).preTestCase()
        self.logStep("1. smap初始化成功")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

    def test_tc_smap_func_feature_smap_query_process_config_001(self):
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)
        remote_numa = self.remote_numa_list[0]
        self.logStep("1. 创建虚机")
        self.logStep("预期结果：1. 虚机创建成功")
        self.hosts[0].vm_nodes[0].create()
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        self.logStep("2. 设置远端numa信息")
        self.logStep("预期结果：2. 设置远端numa信息成功")
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 10000)
        self.assertEqual(rc, 0)

        self.logStep("3. 虚机迁出25%")
        self.logStep("预期结果：3. 迁出成功")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, vm_pid, 25)]), 1)
        self.assertEqual(rc, 0)
        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 1, 60)
        self.assertEqual(result, True)

        self.logStep("4. 调用smap smap_query_process_config接口")
        self.logStep("预期结果：4. 查询结果符合预期")
        process_config = self.cli[0].smap_query_process_config(remote_numa, 1, 4, 1)
        self.assertEqual(process_config.ret, 0)
        self.assertGreaterEqual(process_config.outLen, 1)
        self.assertEqual(vm_pid in list(map(lambda payload: payload.pid, process_config.payload)), True)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapQueryProcessConfig001, self).postTestCase()
        self.safe_delete_vms()