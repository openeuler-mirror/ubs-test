"""
Migrated from legacy: test_vm_mem_borrow_001
"""

import time

import pytest
from libs.modules.ubsvirt.basecase.openstack_basecase import OpenStackBaseCase


@pytest.mark.smoke
class TestVmMemBorrow001(OpenStackBaseCase):
    """
    P1.环境中存在2个及以上节点
    P2.OpenStack/RackManager功能正常无异常
    P3.Node0上配置4G可用大页内存
    P4.已完成内存规格4G虚拟机VM1的创建

    S1.登录VM1，执行加压命令对VM1加压，使得内存超过第二水位线92%（3.68G），查看水位线告警、借用策略、借入借出点水位线告警变化情况（obmm占用256M内存，虚拟机自身进程占用8-10%大页内存）
    加压命令：stress-ng --vm 1 --vm-bytes {streeNum} --vm-keep &

    E1.存在水位线告警，预期借用收益1G，借用账本借用量1G，触发内存借用操作，内存接入点水位线会降低，内存借出点水线会上涨
    水线告警：tail -f /var/log/scbus/vm_plugin.log|grep -C2 "percent"
    借用决策/预期收益：tail -f /var/log/scbus/vm_plugin.log|grep -C2 "actionType"
    账本借用：curl --unix-socket /var/run/scbus/rackAgentUds.socket  -X GET "http://127sds/rest/rackmaster/v1/memory-info" -w "%{http_code}"
    """

    def teardown_method(self):
        self.clear_server()

    def test_vm_mem_borrow_001(self, get_topo_path):
        """
        Test for test_vm_mem_borrow_001
        """

        self.logStep("P1、在Node0节点使用Openstack的主机聚合模式, 创建8G虚拟机。")
        self.vms = self.prepare_topo(str(get_topo_path("test_test_vm_mem_borrow_001")))

        self.logStep("S1、登录虚拟机对虚拟机进行加压至95%，借用1G内存。")
        self.add_stress_to_vm(self.vms[0], 92)
        self.assertTrue(self.check_borrowed_numa_size("node1", 600, 1024 * 0.9), "the borrowed size is not 1024M")

        self.logStep("S2、删除虚机压力后，归还1G内存。")
        time.sleep(30)
        self.clean_vm_stress(self.vms[0])
        self.assertTrue(self.check_return_mem("node1", 600), "the returning size is not 1024M")
