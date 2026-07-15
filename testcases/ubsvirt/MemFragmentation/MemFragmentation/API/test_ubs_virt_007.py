import re

from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt007(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_007
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用接口查询场景及超分比例成功
    PreCondition:
        P1.环境中ubse、Ubs-Scheduler状态正常
    TestStep:
        S1.调用ubs_case_conf_info相关接口查询场景和超分比例，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中ubse、Ubs-Scheduler状态正常")
        self.path = '/usr/lib/python3.11/site-packages/ubse/ubs_virt_007.py'

    def teardown_method(self):
        self.master.run({'command': [f'rm -f {self.path}']})

    def test_ubs_virt_007(self, get_topo_path):
        self.logStep("S1.调用ubs_case_conf_info相关接口查询场景和超分比例，查看响应结果是否满足预期")
        overcommitment = str(self.get_overcommitment(self.master)[1])
        res = test_api.apitest_ubs_case_conf_info(self.master, self.path)
        if not res:
            self.assertTrue(False, '调用接口无回显')
        line = res.splitlines()[-2]
        api_overcommitment = re.search(r"over_commitment=([0-9.]+)", line).group(1)

        self.logInfo("E1.接口调用成功，相应结果符合预期")
        self.assertNotIn("fail", res, '调用接口失败')
        self.assertEqual(api_overcommitment, overcommitment, '查询的超分比例不符合预期')