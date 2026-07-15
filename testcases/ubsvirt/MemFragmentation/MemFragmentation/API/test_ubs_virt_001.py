from libs.modules.ubsvirt.api import test_api
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt001(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_001
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用status接口成功
    PreCondition:
        P1.环境中UBS Scheduler状态正常
        P2.获取环境中keystone的token信息
    TestStep:
        S1.调用status相关接口，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，状态码返回200，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中UBS Scheduler状态正常")

        self.logStep("P2.获取环境中keystone的token信息")
        self.ensure_admin_openrc_on_controller()
        res = self.controller.run({"command": ["openstack token issue -f value -c id"]}).get("stdout")
        self.token = res.replace("\r", "").replace("\n", "").replace("root@#>", "")

    def test_ubs_virt_001(self):
        self.logStep("S1.调用status相关接口，查看响应结果是否满足预期")
        query_res = test_api.apitest_ubs_scheduler_status(self.controller, self.token)

        self.logInfo("E1.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIn("200", query_res, "return code is not 200")
        self.assertIn("is_over_allocation", query_res, "没有场景信息")