from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt012(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_012
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用接口更新冷热页流动开关和虚机状态成功
    PreCondition:
        P1.环境中ubse、Ubs-Scheduler状态正常
    TestStep:
        S1.调用update_page_flow_and_status相关接口查看虚机信息，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中ubse、Ubs-Scheduler状态正常")
        self.vm_py_path = '/usr/lib/python3.11/site-packages/ubse/ubs_virt_012.py'

    def teardown_method(self):
        if hasattr(self, "uuid"):
            test_api.apitest_update_page_flow_and_status(self.master, self.vm_py_path, 'true', self.uuid,
                                                         self.hostname, 0)
        self.master.run({'command': [f'rm -f {self.vm_py_path}']})
        self.clear_server()
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_ubs_virt_012(self, get_topo_path):
        self.logInfo("创建虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_ubs_virt_012")))
        self.hostname = self.master.getHostname()

        self.logStep("S1.调用update_page_flow_and_status相关接口查看虚机信息，查看响应结果是否满足预期")
        services = client.list_servers(self.controller)
        if services:
            self.uuid = services[0].get('ID')
        res = test_api.apitest_update_page_flow_and_status(self.master, self.vm_py_path, 'false', self.uuid,
                                                           self.hostname, 0)

        self.logInfo("E1.接口调用成功，相应结果符合预期")
        if res:
            self.assertNotIn('fail', res, '调用接口失败')
            lines = res.split()
            self.assertEqual('0', lines[-2], '调用接口失败')
        else:
            self.assertTrue(False, '调用接口失败')

        res = test_api.apitest_update_page_flow_and_status(self.master, self.vm_py_path, 'true', self.uuid,
                                                           self.hostname, 0)
        self.logStep("E1.接口调用成功，相应结果符合预期")
        if res:
            self.assertNotIn('fail', res, '调用接口失败')
            lines = res.split()
            self.assertEqual('0', lines[-2], '调用接口失败')
        else:
            self.assertTrue(False, '调用接口失败')
