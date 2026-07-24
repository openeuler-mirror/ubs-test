

import time

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemBorrow25(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_mem_borrow_25
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证内存借用后，远端内存访问功能正常
    PreCondition:
        P1.在Node0节点使用Openstack的主机聚合模式, 创建5G虚拟机
    TestStep:
        S1、登录虚拟机对虚拟机进行加压至95%，借用1G内存
        S2、删除虚机压力后，归还1G内存。
    ExpectedResult:
        E1、借用1G内存
        E2、归还1G内存
    Author:
        wufangzhou 00644577
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_borrow_25(self, get_topo_path):

        self.logStep("P1、在Node0节点使用Openstack的主机聚合模式, 创建5G虚拟机")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_borrow_25")))

        self.logStep("S1、登录虚拟机对虚拟机进行加压至95%，借用1G内存")
        self.add_stress_to_vm(self.vms[0], 77)
        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 1024 * 0.9), "the borrowed size is not 1024M")

        self.logStep("S2、删除虚机压力后，归还1G内存。")
        time.sleep(30)
        self.clean_vm_stress(self.vms[0])
        self.assertTrue(self.check_return_mem("node1", 900), "the returning size is not 1024M")
