#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
from libs.core.basecase.ubturbo import SmapCase


class TestTcSmapFuncFeatureSmapInit001(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_INIT_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        正常调用SmapInit将smap初始化为4k页模式，接口返回成功
    PreCondition:
        P1.OS正常运行
    TestStep:
        S1.通过 smap_client 启动SMAP
        S2.删除/dev/shm/smap_config
        S3.调用SmapInit 0 将smap初始化为4k模式
        S4.查看文件/dev/shm/smap_config是否正确生成
    ExpectedResult:
        E1.smap启动成功
        E2.文件不存在或者删除成功
        E3.smap成功初始化为4k模式
        E4.smap_config文件内容符合预期
    """

    def setup_method(self):
        self.logStep("P1.OS正常运行")
        super(TestTcSmapFuncFeatureSmapInit001, self).preTestCase()

    def test_tc_smap_func_feature_smap_init_001(self):
        self.logStep("S1.通过 smap_client 启动SMAP")
        result = self.hosts[0].start_smap_client()

        self.logStep("E1.smap启动成功")
        self.assertEqual(result, True)

        self.logStep("S2.删除/dev/shm/smap_config")
        self.hosts[0].run(f"rm -f /dev/shm/smap_config")

        self.logStep("E2.文件不存在或者删除成功")
        result = self.hosts[0].check_file_exists("/dev/shm/smap_config")
        self.assertEqual(result, False)

        self.logStep("S3.调用SmapInit 0 将smap初始化为4k模式")
        result = self.hosts[0].start_smap_client()
        self.assertEqual(result, True)
        result = self.cli[0].smap_init(0)

        self.logStep("E3.smap成功初始化为4k模式")
        self.assertEqual(result, 0)

        self.logStep("S4.查看文件/dev/shm/smap_config是否正确生成")
        result = self.hosts[0].check_file_exists("/dev/shm/smap_config")
        self.assertEqual(result, True)

        self.logStep("E4.smap_config文件内容符合预期")
        result = self.hosts[0].check_smap_config_file()
        self.assertEqual(result, True)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapInit001, self).postTestCase()