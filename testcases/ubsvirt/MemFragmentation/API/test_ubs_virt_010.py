from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt010(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_010
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用接口查询本节点节点信息成功
    PreCondition:
        P1.环境中ubse、Ubs-Scheduler状态正常
    TestStep:
        S1.调用ubs_node_info_list相关接口查看节点信息，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中ubse、Ubs-Scheduler状态正常")
        self.vm_py_path = '/usr/lib/python3.11/site-packages/ubse/ubs_virt_010.py'

    def teardown_method(self):
        client.refresh_hugePage(self.master, {0: 0})
        self.master.run({'command': [f'rm -f {self.vm_py_path}']})

    def test_ubs_virt_010(self):
        self.logStep("S1.调用ubs_node_info_list相关接口查看节点信息，查看响应结果是否满足预期")
        node_dict = {0: 2048}
        client.refresh_hugePage(self.master, node_dict)
        node_info = test_api.apitest_ubs_virt_node_info_list(self.master, self.vm_py_path)
        self.logInfo("node_info=" + node_info)

        self.logInfo("E1.接口调用成功，相应结果符合预期")
        hostname = self.master.getHostname()
        self.assertIsNotNone(node_info, "接口调用失败，返回信息为None")
        self.assertIn(hostname, node_info, "调用接口返回的信息不包含主机名或主机名不正确")
        self.assertIn('huge_page_total=' + str(node_dict[0]), node_info, "调用接口返回的信息不包含大页值或大页值不正确")