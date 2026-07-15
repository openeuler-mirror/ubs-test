from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt008(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_008
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用接口设置场景及超分比例成功
    PreCondition:
        P1.环境中ubse、Ubs-Scheduler状态正常
    TestStep:
        S1.调用ubs_case_conf_set相关接口设置场景和超分比例，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中ubse、Ubs-Scheduler状态正常")
        self.path = '/usr/lib/python3.11/site-packages/ubse/ubs_virt_008.py'
        self.overcommitment = self.get_overcommitment(self.master)[1]
        self.casetype = "memFragmentation" if self.overcommitment == 1.0 else "overCommitment"

    def teardown_method(self):
        self.logInfo("恢复超分比例为初始值")
        self.logInfo("删库重启ubse")
        self.logInfo("删库重启ubse")
        for node in self.ubse_node_list:
            node.run({'command': ['rm -rf /var/lib/ubse/data/*']})
            self.restart_service(node, "ubse")
        self.wait_ubse_status(self.master, 900, 10)

        param = {"caseType": self.casetype, "overCommitment": self.overcommitment}
        res = test_api.apitest_ubs_case_conf_set(self.master, self.path, param)
        if not res:
            self.assertTrue(False, '调用接口失败')
        res_code = res.splitlines()[-2]
        self.assertNotIn('fail', res, '调用接口失败')
        self.assertEqual(res_code, '0', '调用接口失败')
        new_overcommitment = self.get_overcommitment(self.master)[1]
        self.assertEqual(new_overcommitment, self.overcommitment, '恢复超分比例失败')

    def test_ubs_virt_008(self, get_topo_path):
        self.logStep("S1.调用ubs_case_conf_set相关接口设置场景和超分比例，查看响应结果是否满足预期")
        self.logInfo("删库重启ubse")
        for node in self.ubse_node_list:
            node.run({'command': ['rm -rf /var/lib/ubse/data/*']})
            self.restart_service(node, "ubse")
        self.wait_ubse_status(self.master, 900, 10)

        param = {"caseType": "overCommitment", "overCommitment": 1.1}
        res = test_api.apitest_ubs_case_conf_set(self.master, self.path, param)

        self.logInfo("E1.接口调用成功，相应结果符合预期")
        if not res:
            self.assertTrue(False, '调用接口失败')
        res_code = res.splitlines()[-2]
        self.assertNotIn('fail', res, '调用接口失败')
        self.assertEqual(res_code, '0', '调用接口失败')
        new_overcommitment = self.get_overcommitment(self.master)[1]
        self.assertEqual(new_overcommitment, 1.1, '设置超分比例失败')