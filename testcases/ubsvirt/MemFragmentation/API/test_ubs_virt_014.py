from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.api import test_api

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt014(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_014
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        调用碎片场景接口成功
    PreCondition:
        P1.环境中ubse、Ubs-Scheduler状态正常
    TestStep:
        S1.调用相关接口，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中ubse、Ubs-Scheduler状态正常")
        self.path = '/usr/lib/python3.11/site-packages/ubse/ubs_virt_014.py'
        if self.is_Simulation:
            self.srcSocketId = 36
            self.destSocketId = 36
        else:
            self.srcSocketId = 0
            self.destSocketId = 0

    def teardown_method(self):
        self.master.run({'command': [f'rm -f {self.path}']})
        client.echo_hugePage(self.master, 0, 0)
        client.echo_hugePage(self.agent, 0, 0)
        self.restart_service(self.master, "nova-compute")
        self.restart_service(self.agent, "nova-compute")
        self.waitServiceStatus(self.master, "openstack-nova-compute", 600)
        self.waitServiceStatus(self.agent, "openstack-nova-compute", 600)

    def test_ubs_virt_014(self):
        self.logStep("S1.调用相关接口，查看响应结果是否满足预期")
        client.echo_hugePage(self.master, 0, 2048)
        client.echo_hugePage(self.agent, 0, 2048)
        self.restart_service(self.master, "nova-compute")
        self.restart_service(self.agent, "nova-compute")
        self.waitServiceStatus(self.master, "openstack-nova-compute", 600)
        self.waitServiceStatus(self.agent, "openstack-nova-compute", 600)

        self.logInfo("内存借用策略")
        node_id = self.get_ubse_node_id(self.master)
        self.assertTrue(node_id != "", "get ubse node id is null")
        param = {'srcParam': {'srcNid': node_id, 'srcSocketId': self.srcSocketId, 'srcNumaId': 0}, 'borrowSize': 1048576}
        res = test_api.apitest_ubs_mem_borrow_strategy(self.master, self.path, param)

        self.logInfo("内存借用执行")
        node_id2 = self.get_ubse_node_id(self.agent)
        self.assertTrue(node_id2 != "", "get ubse node id is null")
        param2 = {"srcParam": {"srcNid": node_id, "srcSocketId": self.srcSocketId, "srcNumaId": 0}, "borrowSize": 1048576,
                  "destParam": [{"destNid": node_id2, "destSocketId": self.destSocketId, "destNumaNum": 1, "destNumaId": [0],
                                 "memSize": [1048576]}]}
        res2 = test_api.apitest_ubs_mem_borrow_execute(self.master, self.path, param2)

        self.logInfo("内存归还执行")
        res3 = test_api.apitest_ubs_mem_return(self.master, self.path)

        self.logInfo("E1.接口调用成功，相应结果符合预期")
        self.assertNotIn('fail', res, "mem strategy is error")
        self.assertIn(f"host_id='{node_id2}'", res, "mem strategy is error")
        self.assertNotIn('fail', res2, "mem execute is error")
        self.assertIn("borrow_ids", res2, "mem execute is error")
        self.assertNotIn('fail', res3, "mem return is error")
        flag = res3.splitlines()[-2]
        self.assertIn("(0,", flag, "mem return is error")
