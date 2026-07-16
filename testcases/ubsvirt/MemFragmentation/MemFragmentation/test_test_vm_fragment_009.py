import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmFragment009(OpenStackBaseCase):
    """
    预置条件：
    P1、4P环境，openstack部署成功
    P2、Ubs Scheduler服务正常部署，正常使能
    P3、软总线已经正常运行，内存子系统模块成功加载
    P4、不超分场景（ram_allocation_ratio为默认配置1）
    P5、控制节点分配大页内存 15G

    测试步骤：
    S1、Openstack可视化界面创建卷
    S2、Openstack可视化界面创建实例类型
    S3、创建2G虚机
    S4、查看ubs-scheduler-controller.log日志，观察决策信息

    预期结果：
    E1、卷创建成功
    E2、实例类型创建成功
    E3、在控制节点创建虚机成功，状态正常
    E4、ubs-scheduler-controller.log日志中存在INFO决策信息打印，本地创建为True（"should_borrow_mem": False），需要本地已有虚机进行内存迁移的量为0（"migrate_mem": 0）， 远端创建内存量为0（"remote_mem": 0）
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_fragment_009(self, get_topo_path):
        """
        Test for test_vm_fragment_009
        """

        self.logStep("S3、创建2G虚机")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_test_vm_fragment_009")))

        self.logInfo("E3、在控制节点创建虚机成功，状态正常")
        server_detail = self.wait_server_target_status(
            "vm_01", {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host}
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node1"].host)
