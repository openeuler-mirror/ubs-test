from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api
from libs.modules.ubsvirt.model.model import VMResource
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt006(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_006
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用/vm/{uuid}删除虚机感知成功
    PreCondition:
        P1.环境中UBS Scheduler状态正常
        P2.获取环境中keystone的token信息
    TestStep:
        S1.调用/vm/{uuid}相关接口，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，状态码返回200，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中UBS Scheduler状态正常")

        self.logStep("P2.获取环境中keystone的token信息")
        self.ensure_admin_openrc_on_controller()
        res = self.controller.run({"command": ["openstack token issue -f value -c id"]}).get("stdout")
        self.token = res.replace("\r", "").replace("\n", "").replace("root@#>", "")

    def teardown_method(self):
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_ubs_virt_006(self, get_topo_path):
        self.vm_list = self.prepare_topo(str(get_topo_path("test_ubs_virt_006")))
        vm_02 = VMResource('vm_02', 'openEuler-22.03-everything', 1024, 'node1', False,
                           '2', '', 'true', '25')
        self.create_server(vm_02)
        server_detail = client.get_server_detail(self.controller, "vm_01")
        vm_id = server_detail['id']

        self.logStep("S1.调用/vm/{uuid}相关接口，查看响应结果是否满足预期")
        del_res = test_api.apitest_ubs_virt_delete_vm(self.controller, vm_id, self.token)

        self.logInfo("E1.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIn("200", del_res, "return code is not 200")
        msg = f'Execute deletion task of vm: {vm_id}, create monitor and update task'
        self.assertIn(msg, del_res, "接口返回无msg信息")