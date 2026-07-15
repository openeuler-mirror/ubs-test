from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt011(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_011
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用接口查询本节点虚机信息成功
    PreCondition:
        P1.环境中ubse、Ubs-Scheduler状态正常
    TestStep:
        S1.调用ubs_vm_info_list相关接口查看虚机信息，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中ubse、Ubs-Scheduler状态正常")
        self.vm_py_path = '/usr/lib/python3.11/site-packages/ubse/ubs_virt_011.py'

    def teardown_method(self):
        self.master.run({'command': [f'rm -f {self.vm_py_path}']})
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_ubs_virt_011(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_ubs_virt_011")))
        server_detail = client.get_server_detail(self.controller, 'vm_01')

        self.logStep("S1.调用ubs_vm_info_list相关接口查看虚机信息，查看响应结果是否满足预期")
        vm_info = test_api.apitest_ubs_virt_vm_info_list(self.master, self.vm_py_path)
        self.logInfo("node_info=" + vm_info)

        self.logInfo("E1.接口调用成功，相应结果符合预期")
        self.assertIn(server_detail["OS-EXT-SRV-ATTR:instance_name"], vm_info, "虚拟机查询失败")
        hostname = self.node_dict["node1"].host
        self.assertIn(hostname, vm_info, "调用接口返回的信息不包含主机名或主机名不正确")
        self.assertIn("max_mem='1048576'" , vm_info, "vm max mem 不是1048576")