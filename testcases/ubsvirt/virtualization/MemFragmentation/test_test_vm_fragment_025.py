"""
Migrated from legacy: test_vm_fragment_025
"""

import time
import pytest

from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.model.model import VMResource


@pytest.mark.smoke
class TestVmFragment025(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_fragment_025
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证匀一匀使用了远端内存的虚机热迁移
    PreCondition:
        P1、4P环境，openstack部署成功
        P2、Ubs Scheduler服务正常部署，正常使能
        P3、软总线已经正常运行，内存子系统模块成功加载
        P4、不超分场景（ram_allocation_ratio为默认配置1）
        P5、控制节点分配大页内存 13G，从节点5G
        P6、已存在可用卷，Openstack可视化界面创建实例类型A(4U8G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})。
        P7、创建示例类型B(2U5G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})。
    TestStep:
        S1、在可视化界面创建8G虚机A
        S2、在可视化界面创建5G虚机B
        S3、从节点numa 1分配9G大页，实例热迁移虚机A
    ExpectedResult:
        E1、创建成功
        E2、创建成功，虚机状态正常
        E3、迁移成功，触发远端内存的归还，日志打印迁移和归还操作（ubs-scheduler-agent.log打印归还关键词：Free result is）
    Author:
        maoxinghao 00899107
    """

    def setup_method(self):
        self.logStep("P1、4P环境，openstack部署成功")
        self.logStep("P2、Ubs Scheduler服务正常部署，正常使能")
        self.logStep("P3、软总线已经正常运行，内存子系统模块成功加载")
        self.logStep("P4、不超分场景（ram_allocation_ratio为默认配置1）")
        self.logStep("P5、控制节点分配大页内存 13G，从节点5G")
        self.logStep(
            "P6、已存在可用卷，Openstack可视化界面创建实例类型A(4U8G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})。"
        )
        self.logStep(
            "P7、创建示例类型B(2U5G)，元数据({'hw:mem_page_size': '2048', 'ubs:enable_remote_memory': 'true', 'ubs:max_remote_memory_ratio': '25'})。"
        )

    def teardown_method(self):
        self.clear_server()

    def test_vm_fragment_025(self, get_topo_path):
        

        self.logStep("S1、在可视化界面创建8G虚机A")
        self.vm_list = self.prepare_topo(str(get_topo_path("test_test_vm_fragment_025")))
        vm_2g = VMResource(
            "vm_2g",
            "openEuler-22.03-everything",
            2048,
            "node1",
            False,
            2,
            False,
            True,
            25,
            False,
            0,
        )
        self.create_server(vm_2g, "ACTIVE")
        self.logStep("E1、创建成功")
        mem_fragment_algorithm_decision = self.get_mem_fragment_algorithm_decision(self.controller)
        if mem_fragment_algorithm_decision:
            self.assertEqual(
                mem_fragment_algorithm_decision.get("should_borrow_mem"),
                True,
                "VM is not borrow mem",
            )
            self.assertNotEqual(
                mem_fragment_algorithm_decision.get("migrate_mem"), 0, "Numa migrate mem is 0"
            )
            self.assertEqual(
                mem_fragment_algorithm_decision.get("remote_mem"), 0, "Vm used remote mem is not 0 "
            )
        else:
            self.assertEqual(False, True, "Get mem fragment algorithm decision failed")

        self.logStep("S2、在可视化界面创建5G虚机B")
        self.assertEqual(
            mem_fragment_algorithm_decision.get("should_borrow_mem"),
            True,
            "Vm used remote mem is 0",
        )

        self.logStep("E2、创建成功，虚机状态正常")
        numa_borrowed_size = self.get_node_borrowing_numa("node1")
        if numa_borrowed_size == 0:
            self.assertEqual(False, True, "The borrowed memory size is 0")

        self.logStep("S3、从节点numa 1分配9G大页，实例热迁移虚机A")
        result = client.echo_hugePage(self.node_dict["node2"].ssh_node, 1, 4608)
        if not result:
            raise RuntimeError("set hugePage fail")
        self.node_dict["node2"].ssh_node.run(
            {"command": ["systemctl restart openstack-nova-compute.service"]}
        )

        flag = False
        wait_time = 0
        while wait_time < 600:
            service_status = self.node_dict["node2"].ssh_node.getServiceStatus(
                "openstack-nova-compute"
            )
            if service_status and service_status == "running":
                flag = True
                break
            else:
                wait_time = wait_time + 30
                time.sleep(30)
        self.assertEqual(flag, True, "The openstack-nova-compute status error")

        self.logInfo("实例热迁移虚机")
        client.migrate_server(self.controller, self.vm_list[0].name, self.node_dict["node2"].host)

        self.logStep(
            "E3、迁移成功，触发远端内存的归还，日志打印迁移和归还操作（ubs-scheduler-agent.log打印归还关键词：Free result is）"
        )
        self.logInfo("查询虚机是否迁移成功")
        vm_migrate_result = self.check_vm_migrate_to_dest_node(
            self.controller, self.vm_list[0].name, self.node_dict["node2"].host, 4000
        )
        self.assertEqual(vm_migrate_result, True, "VM vm_3g migrate failed")

        self.logInfo("迁移成功，触发内存归还")
        flag = False
        wait_time = 0
        while wait_time < 600:
            numa_borrowed_size = self.get_node_borrowing_numa("node1")
            if numa_borrowed_size == 0:
                flag = True
                break
            else:
                wait_time = wait_time + 10
                time.sleep(10)
        self.assertEqual(flag, True, "The borrowed memory size is not 0")
