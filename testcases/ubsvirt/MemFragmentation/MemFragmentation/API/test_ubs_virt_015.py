from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt015(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_015
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用接口，挂起、恢复、关闭虚机成功
    PreCondition:
        P1.环境中UBS Scheduler状态正常
        P2.获取环境中keystone的token信息
        P3.碎片场景已创建一个虚机
    TestStep:
        S1.调用/notOverAllocation/suspend相关接口，查看响应结果是否满足预期
        S2.调用/notOverAllocation/resume相关接口，查看响应结果是否满足预期
        S3.调用/notOverAllocation/powerOff相关接口，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，状态码返回200，相应结果符合预期
        E2.接口调用成功，状态码返回200，相应结果符合预期
        E3.接口调用成功，状态码返回200，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中UBS Scheduler状态正常")

        self.logStep("P2.获取环境中keystone的token信息")
        self.logInfo("获取token信息")
        self.ensure_admin_openrc_on_controller()
        res = self.controller.run({"command": ["openstack token issue -f value -c id"]}).get("stdout")
        self.token = res.replace("\r", "").replace("\n", "").replace("root@#>", "")

        self.logStep("P3.碎片场景已创建一个虚机")


    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_ubs_virt_015(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_ubs_virt_015")))
        server_detail = client.get_server_detail(self.controller, "vm_01")
        host = server_detail['OS-EXT-SRV-ATTR:host']
        vm_id = server_detail["id"]

        self.logStep("S调用/notOverAllocation/suspend相关接口，查看响应结果是否满足预期")
        suspend_res = test_api.apitest_vm_suspend(self.controller, vm_id, self.token)

        self.logInfo("E1.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIn("200", suspend_res, "return code is not 200")

        self.logStep("S2.调用/notOverAllocation/resume相关接口，查看响应结果是否满足预期")
        resume_res = test_api.apitest_vm_resum(self.controller, vm_id, self.vm_list[0].ram * 1024 * 1024, host, self.token)

        self.logInfo("E2.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIn("200", resume_res, "return code is not 200")

        self.logStep("S3.调用/notOverAllocation/powerOff相关接口，查看响应结果是否满足预期")
        power_off_res = test_api.apitest_vm_power_off(self.controller, vm_id, self.token)

        self.logInfo("E3.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIn("200", power_off_res, "return code is not 200")
