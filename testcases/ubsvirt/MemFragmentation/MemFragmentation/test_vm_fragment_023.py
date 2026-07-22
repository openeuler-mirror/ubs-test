import time
import pytest

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.model.model import VMResource


@pytest.mark.smoke
class TestVmFragment023(OpenStackBaseCase):
    """
    CaseId:
        test_vm_fragment_023
    RunLevel:
        Level 1
    CaseTopo:

    CaseName:
        验证匀一匀创建的虚机销毁
    PreCondition:
        P1、4P环境，openstack部署成功
        P2、Ubs Scheduler服务正常部署，正常使能
        P3、软总线已经正常运行，内存子系统模块成功加载
        P4、不超分场景（ram_allocation_ratio为默认配置1）
        P5、控制节点分配大页内存 13G，从节点4G
        P6、已存在可用卷
        P7、创建实例类型A(4U8G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_create': 'true',
         'ubs:remote_create_memory_ratio': '25', 'ubs:enable_remote_memory': 'true',
          'ubs:max_remote_memory_ratio': '25'})。
        P8、创建示例类型B(2U5G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_create': 'false',
         'ubs:remote_create_memory_ratio': ‘0', 'ubs:enable_remote_memory': 'true',
          'ubs:max_remote_memory_ratio': '25'})。
    TestStep:
        S1、在可视化界面创建8G虚机A
        S2、在可视化界面创建5G虚机B
        S3、观察ubs-scheduler-controller.log日志的调度决策信息
        S4、销毁虚机B
        S5、销毁虚机A
    ExpectResult:
        E1、创建成功，ubs-scheduler-controller.log日志中存在INFO决策信息打印，决策为本地创建（"should_borrow_mem": False），需要本地已有虚机进行内存迁移的量为0（"migrate_mem": 0）， 远端创建内存量为0（"remote_mem": 0）
        E2、触发匀一匀创建，创建成功，虚机状态正常
        E3、ubs-scheduler-controller.log日志中存在INFO决策信息打印，决策为匀一匀创建（"should_borrow_mem": True），需要本地已有虚机进行内存迁移的量为256M（"migrate_mem"）， 远端创建内存量为0（"remote_mem": 0）
        E4、销毁成功，触发远端内存的归还，归还的内存大小根据实际空闲内存决定
        E5、销毁成功，触发远端内存的归还，归还所有远端内存
    """

    def setup_method(self):
        pass

    def teardown_method(self):
        self.clear_server()

    def test_vm_fragment_023(self, get_topo_path):
        

        self.logStep("S1. 使用flavor_remote_memory_25创建8G虚机A")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_vm_fragment_023")))
        self.logStep("E1、8G虚机创建成功")
        server_detail = self.wait_server_target_status(
            "Delete_VM_002_01",
            {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host},
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node1"].host)

        self.logStep("S2. 使用flavor_remote_memory_25创建5G虚机B")
        delete_VM_002_02 = VMResource(
            "Delete_VM_002_02",
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
        self.create_server(delete_VM_002_02)

        self.logStep("E2、触发匀一匀创建，创建成功，虚机状态正常")
        server_detail = self.wait_server_target_status(
            "Delete_VM_002_02",
            {"status": "ACTIVE", "OS-EXT-SRV-ATTR:host": self.node_dict["node1"].host},
        )
        self.assertEqual(server_detail["OS-EXT-SRV-ATTR:host"], self.node_dict["node1"].host)

        self.logStep("S3、观察ubs-scheduler-controller.log日志的调度决策信息")
        mem_fragment_algorithm_decision = self.get_mem_fragment_algorithm_decision(self.controller)
        self.logStep("E3、观察ubs-scheduler-controller.log日志的调度决策信息")
        if mem_fragment_algorithm_decision:
            self.assertTrue(
                mem_fragment_algorithm_decision.get("should_borrow_mem"), "VM is not create local"
            )
            self.assertNotEqual(
                mem_fragment_algorithm_decision.get("migrate_mem"), 0, "Numa migrate mem is not 0"
            )
            self.assertEqual(
                mem_fragment_algorithm_decision.get("remote_mem"), 0, "vm create remote mem is 0"
            )
        borrowing_numa = self.get_node_borrowing_numa("node1")
        self.logStep("S4. 销毁虚机B")
        client.delete_server(self.controller, "Delete_VM_002_02")
        flag = False
        wait_time = 0
        while wait_time < 600:
            servers = client.list_servers(self.controller)
            if servers[0]["Name"] != "Delete_VM_002_02":
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)
        self.assertEqual(flag, True, "销毁虚机Delete_VM_002_02失败")

        self.logStep("S5. 销毁虚机A")
        client.delete_server(self.controller, "Delete_VM_002_01")
        flag = False
        wait_time = 0
        while wait_time < 600:
            current_servers = client.list_servers(self.controller)
            if not bool(current_servers):
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)
        self.assertEqual(flag, True, "销毁虚机Delete_VM_002_01失败")

        self.logStep("E5、销毁成功，触发内存归还")
        flag = False
        wait_time = 0
        while wait_time < 900:
            numa_borrowed_size = self.get_node_borrowing_numa("node1")
            if numa_borrowed_size < borrowing_numa:
                flag = True
                break
            else:
                wait_time = wait_time + 15
                time.sleep(15)
        self.assertEqual(flag, True, "Numa borrowed size is not 0")
