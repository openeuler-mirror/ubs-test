"""
Migrated from legacy: test_vm_mem_return_008
"""

import pytest
from libs.modules.ubsvirt.api import client
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemReturn008(OpenStackBaseCase):
    """
    CaseNumber:
        test_vm_mem_return_008
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证单虚拟机从node1借用归还后，node2借用归还成功
    PreCondition:
        P1.环境中存在4个及以上节点
        P2.OpenStack/RackManager功能正常无异常
        P3.Node1上配置4G可用大页内存，Node2上配置4G可用大页
        P4.已完成内存规格4G虚拟机VM1的创建
        P5.对VM1加压触发了内存借用操作
    TestStep:
        S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况
        S2.配置Node2上配置4G可用大页为1G可用大页，Node3上配置4G可用大页，并重启libvirt和nova-compute生效。
        S3.对VM1加压触发了内存借用操作后，停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况
    ExpectedResult:
        E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。
        E2.修改成功
        E3.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。
    Author:
        fanmingzhan 30077318
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_return_008(self, get_topo_path):

        self.logStep("P4.已完成内存规格4G虚拟机VM1的创建")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_return_008")))

        self.logStep("P5.对VM1加压触发了内存借用操作")
        self.add_stress_to_vm(self.vms[0], 97)
        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 1024), "the borrowed size is not 1024M")

        self.logStep("S1.登录VM1,停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况")
        self.clean_vm_stress(self.vms[0])
        flag = self.check_return_mem("node1", 1800)
        self.logStep(
            "E1.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。"
        )
        self.assertTrue(flag, "the borrowed size is not returned")

        self.logStep(
            "S2.配置Node2上配置4G可用大页为1G可用大页，Node3上配置4G可用大页，并重启libvirt和nova-compute生效。"
        )
        node = self.node_dict["node2"].ssh_node
        res = client.echo_hugePage(node, 0, 512)
        self.restart_service(node, "nova-compute")
        self.waitServiceStatus(node, "openstack-nova-compute", 1200)
        self.assertTrue(res, "大页配置失败")
        node = self.node_dict["node3"].ssh_node
        res = client.echo_hugePage(node, 0, 2048)
        self.restart_service(node, "nova-compute")
        self.waitServiceStatus(node, "openstack-nova-compute", 1200)

        self.logStep("E2.修改成功")
        self.assertTrue(res, "大页配置失败")

        self.logStep(
            "S3.对VM1加压触发了内存借用操作后，停止VM1的加压进程，查看借用策略、借入借出点水位线告警变化情况"
        )
        self.add_stress_to_vm(self.vms[0], 97)
        self.assertTrue(self.check_borrowed_numa_size("node1", 1800, 1024), "the borrowed size is not 1024M")

        self.clean_vm_stress(self.vms[0])
        flag = self.check_return_mem("node1", 1800)

        self.logStep(
            "E3.预期归还收益1G，归还账本借用量1G，存在内存归还操作，内存归还成功后，内存借出点水线下降。"
        )
        self.assertTrue(flag, "the borrowed size is not returned")
