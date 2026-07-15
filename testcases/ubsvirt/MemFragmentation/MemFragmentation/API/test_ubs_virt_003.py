from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api
from libs.modules.ubsvirt.model.model import VMResource
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt003(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_003
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        碎片场景，调用/notOverAllocation/creation/numaInfo获取虚机创建的numa_id结果成功
    PreCondition:
        P1.环境中UBS Scheduler状态正常
        P2.获取环境中keystone的token信息
        P3.环境为碎片场景
    TestStep:
        S1.调用/not_over_allocation/creation/numaInfo相关接口，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，状态码返回200，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中UBS Scheduler状态正常")

        self.logStep("P2.获取环境中keystone的token信息")
        self.ensure_admin_openrc_on_controller()
        res = self.controller.run({"command": ["openstack token issue -f value -c id"]}).get("stdout")
        self.token = res.replace("\r", "").replace("\n", "").replace("root@#>", "")

        self.logStep("P3.环境为碎片场景")

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_ubs_virt_003(self, get_topo_path):
        self.vms = self.prepare_topo(str(get_topo_path("test_ubs_virt_003")))
        vm_02 = VMResource('vm_02', 'openEuler-22.03-everything', 1024, 'node1', False,
                           '2', '', 'true', '25')
        self.create_server_only(vm_02)
        status_detail = self.wait_server_target_status('vm_02', {'status': 'BUILD'}, sleep_time=1)
        self.assertEqual(status_detail['status'], 'BUILD')

        self.logStep("S1.调用/not_over_allocation/creation/numaInfo相关接口，查看响应结果是否满足预期")
        server_detail = client.get_server_detail(self.controller, "vm_02")
        vm_id = server_detail['id']
        check_msg = "\"numa_id\":0"
        query_res = test_api.wait_apitest_creation_numa_info(self.controller, vm_id, self.token, check_msg, sleep_time=1)

        self.logInfo("E1.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIn("200", query_res, "return code is not 200")
        hostname = self.node_dict['node1'].host
        self.assertIn(hostname, query_res, f"调用接口返回的信息不包含主机名或主机名不正确")