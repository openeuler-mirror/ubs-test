import uuid

from libs.modules.ubsvirt.api import test_api
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


class TestUbsVirt002(OpenStackBaseCase):
    """
    CaseNumber:
        test_ubs_virt_002
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        碎片场景，调用/notOverAllocation/creation/hostname获取虚机创建的目标节点成功
    PreCondition:
        P1.环境中UBS Scheduler状态正常
        P2.获取环境中keystone的token信息
        P3.环境为碎片场景
    TestStep:
        S1.调用/notOverAllocation/creation/hostname相关接口，查看响应结果是否满足预期
    ExpectedResult:
        E1.接口调用成功，状态码返回200，相应结果符合预期
    """

    def setup_method(self):
        self.logStep("P1.环境中UBS Scheduler状态正常")

        self.logStep("P2.获取环境中keystone的token信息")
        self.token = self.get_keystone_token()

        self.logStep("P3.环境为碎片场景")

    def teardown_method(self):
        for node_name in self.node_dict:
            node = self.node_dict[node_name]
            self.clear_huge_pages(node.ssh_node)

    def test_ubs_virt_002(self, get_topo_path):
        self.prepare_topo(str(get_topo_path("test_ubs_virt_002")))

        vm_id = uuid.uuid1()

        self.logStep("S1.调用/notOverAllocation/creation/hostname相关接口，查看响应结果是否满足预期")
        query_res = test_api.apitest_creation_hostname(self.controller, vm_id, 4096 * 1024 * 1024, self.token)

        self.logInfo("E1.接口调用成功，状态码返回200，相应结果符合预期")
        self.assertIsNotNone(query_res, "接口调用失败，返回信息为None")
        self.assertIn("200", query_res, "return code is not 200")
        hostname = self.node_dict['node1'].host
        self.assertIn(hostname, query_res, f"接口查询的hostname与预期：{hostname}不一致")