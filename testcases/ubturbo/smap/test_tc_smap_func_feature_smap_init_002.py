# -*- coding: utf-8 -*-
from libs.core.basecase.ubturbo import SmapCase


class TestTcSmapFuncFeatureSmapInit002(SmapCase):
    """
    CaseNumber:
        TC_SMAP_FUNC_FEATURE_SMAP_INIT_002
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        内存超分场景 无配置文件时调用SmapInit后生成配置文件
    PreCondition:
        1、节点正常
        2、节点上无smap_config文件存在
    TestStep:
        1、启动SMAP
        smap smap_init 1
        2、查看文件/dev/shm/smap_config是否生成
    ExpectedResult:
        SMAP初始化成功
        1、/dev/shm/smap_config文件被生成
        2、smap_config文件内容符合预期
    """

    def setup_method(self):
        super(TestTcSmapFuncFeatureSmapInit002, self).preTestCase()
        self.logStep("1、节点正常")

        self.logStep("2、节点上无smap_config文件存在")
        self.hosts[0].run(f"rm -f /dev/shm/smap_config")
        result = self.hosts[0].check_file_exists("/dev/shm/smap_config")
        self.assertEqual(result, False)

    def test_tc_smap_func_feature_smap_init_002(self):
        self.logStep("1、启动SMAP"
                     "smap smap_init 1")
        result = self.hosts[0].start_smap_client()
        self.assertEqual(result, True)
        result = self.cli[0].smap_init(1)
        self.assertEqual(result, 0)
        self.logStep("预期结果：1、/dev/shm/smap_config文件被生成")
        self.logStep("2、查看文件/dev/shm/smap_config是否生成")
        result = self.hosts[0].check_file_exists("/dev/shm/smap_config")
        self.assertEqual(result, True)
        self.logStep("预期结果：2、smap_config文件内容符合预期")
        result = self.hosts[0].check_smap_config_file()
        self.assertEqual(result, True)

    def teardown_method(self):
        super(TestTcSmapFuncFeatureSmapInit002, self).postTestCase()