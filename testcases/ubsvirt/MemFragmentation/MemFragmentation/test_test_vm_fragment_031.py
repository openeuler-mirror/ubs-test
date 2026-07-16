import pytest

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.model.model import VMResource


class TestVmFragment031(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_fragment_031
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不同numa上本地资源不足匀一匀创建虚机
    PreCondition:
        P1、4P环境，openstack部署成功
        P2、Ubs Scheduler服务正常部署，正常使能
        P3、软总线已经正常运行，内存子系统模块成功加载
        P4、不超分场景（ram_allocation_ratio为默认配置1）
        P5、控制节点numa1分配大页内存13G，从节点numa1上分配4G+512M
        P6、已存在可用卷
        P7、创建实例类型A(4U8G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})
        P8、创建示例类型B(2U5G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})
    TestStep:
        S1、在可视化界面创建8G虚机A
        S2、在可视化界面创建5G虚机B
        S3、观察ubs-scheduler-controller.log日志的调度决策信息
        S4、观察ubs-scheduler-agent.log日志是否存在内存借用日志，查看内存借用情况与numastat
    ExpectedResult:
        E1、创建成功，ubs-scheduler-controller.log日志中存在INFO决策信息打印，决策为本地创建（"should_borrow_mem": False）
        E2、触发匀一匀创建，创建成功，虚机状态正常
        E3、ubs-scheduler-controller.log日志中存在INFO决策信息打印，决策为匀一匀创建（"should_borrow_mem": True）
        E4、日志存在内存借用结果（关键词：Borrow execute result）
    """

    def setup_method(self):
        self.logStep("P1、4P环境，openstack部署成功")
        self.logStep("P2、Ubs Scheduler服务正常部署，正常使能")
        self.logStep("P3、软总线已经正常运行，内存子系统模块成功加载")
        self.logStep("P4、不超分场景（ram_allocation_ratio为默认配置1）")
        self.logStep("P5、控制节点numa1分配大页内存13G，从节点numa1上分配4G+512M")
        self.logStep("P6、已存在可用卷")
        self.logStep(
            "P7、创建实例类型A(4U8G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})。"
        )
        self.logStep(
            "P8、创建示例类型B(2U5G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})。"
        )

    def teardown_method(self):
        self.clear_server()

    def test_vm_fragment_031(self, get_topo_path):
        self.logStep("S1、在可视化界面创建8G虚机A")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_test_vm_fragment_031")))
        server_detail = self.wait_server_target_status(
            "test_vm_fragment_031",
            {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host},
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node1"].host)

        self.logStep(
            "E1、创建成功，ubs-scheduler-controller.log日志中存在INFO决策信息打印，"
            '决策为本地创建（"should_borrow_mem": False），'
            '需要本地已有虚机进行内存迁移的量为0（"migrate_mem": 0），'
            '远端创建内存量为0（"remote_mem": 0）'
        )
        mem_fragment_algorithm_decision = self.get_mem_fragment_algorithm_decision(self.controller)
        self.assertIsNotNone(mem_fragment_algorithm_decision, "Algorithm decision log is None")
        self.assertEqual(
            mem_fragment_algorithm_decision.get("should_borrow_mem"), False, "VM is borrow mem"
        )
        self.assertEqual(
            mem_fragment_algorithm_decision.get("migrate_mem"), 0, "Migrate mem is not 0"
        )
        self.assertEqual(
            mem_fragment_algorithm_decision.get("remote_mem"), 0, "Vm used remote mem is not 0"
        )

        self.logStep("S2、在可视化界面创建5G虚机B")
        vm_5g = VMResource(
            "vm_5g",
            "openEuler-22.03-everything",
            5120,
            "node1",
            False,
            3,
            False,
            True,
            25,
            False,
            0,
        )
        self.create_server(vm_5g)

        self.logStep("E2、触发匀一匀创建，创建成功，虚机状态正常")
        server_detail = self.wait_server_target_status(
            "vm_5g",
            {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host},
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node1"].host)

        self.logStep("S3、观察ubs-scheduler-controller.log日志的调度决策信息")
        mem_fragment_algorithm_decision = self.get_mem_fragment_algorithm_decision(self.controller)

        self.logStep(
            'E3、ubs-scheduler-controller.log日志中存在INFO决策信息打印，决策为匀一匀创建（"should_borrow_mem": True）'
        )
        self.assertIsNotNone(mem_fragment_algorithm_decision, "Algorithm decision log is None")
        self.assertEqual(
            mem_fragment_algorithm_decision.get("should_borrow_mem"), True, "VM is not borrow mem"
        )
        self.assertNotEqual(
            mem_fragment_algorithm_decision.get("migrate_mem"), 0, "Migrate mem is 0"
        )
        self.assertEqual(
            mem_fragment_algorithm_decision.get("remote_mem"), 0, "Vm used remote mem is not 0"
        )

        self.logStep(
            "S4、观察ubs-scheduler-agent.log日志是否存在内存借用日志，查看内存借用情况与numastat"
        )
        flag = self.check_borrowed_numa_size("node1", 300, 100)

        self.logStep("E4、日志存在内存借用结果（关键词：Borrow execute result）")
        self.assertEqual(flag, True, "Borrow Memory failed")