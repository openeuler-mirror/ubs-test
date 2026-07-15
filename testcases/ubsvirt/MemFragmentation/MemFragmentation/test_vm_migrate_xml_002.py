"""Migrated from legacy: test_vm_migrate_xml_002

使用xml创建8G虚拟机multicopy热迁移
"""

import time
import pytest

from libs.modules.ubsvirt.basecase.vmxml_basecase import VMxmlBaseCase
from libs.modules.ubsvirt.api import client

@pytest.mark.smoke
class TestVmMigrateXml002(VMxmlBaseCase):
    """使用xml创建8G虚拟机multicopy热迁移.
    
    CaseNumber:
        test_vm_migrate_xml_002
    RunLevel:
        Level 0
    PreCondition:
        P1、环境中存在2个及以上节点
        P2、libvirt和qemu组件正常部署
        P3、环境上存在4U8G虚机xml和相应虚机镜像
        P4、节点1和节点2的numa0分别配置10G大页内存
    TestStep:
        S1、使用xml在节点1创建虚机
        S2、登录虚机，使用stress-ng加压80%
        S3、执行虚机迁移virsh migrate --p2p --live --unsafe --migrateuri hcom://dst_ip vm_name --listen-address dst_ip qemu+tcp://dst_ip/system --verbose --rdma-pin-all
    ExpectedResult:
        E1、虚机创建成功
        E2、加压成功，虚机正常运行
        E3、虚机成功迁移到对端
    Author:
        w00832982
    """
    
    def setup_method(self):
        self.vm_name = "test_vm_migrate_xml_002_vm"
        self.VM_XML_PATH = "/home/migrate_test/xml"
    
    def teardown_method(self):
        self.agent.run({'command': [f"virsh destroy {self.vm_name}"], "timeout": 600})
        self.master.run({'command': [f"virsh destroy {self.vm_name}"], "timeout": 600})
        self.master.run({'command': [f"rm -rf {self.VM_XML_PATH}/test_vm_migrate_xml_002_vm.xml"]})
        self.distribute_huge_page(self.master, 0, 0)
        self.distribute_huge_page(self.agent, 0, 0)
    
    def test_vm_migrate_xml_002(self, xml_base_path):
        self.logStep("P1、环境中存在2个及以上节点")
        self.logStep("P2、libvirt和qemu组件正常部署")
        self.logStep("P3、环境上存在4U8G虚机xml和相应虚机镜像")
        self.logStep("P4、节点1和节点2的numa0分别配置10G大页内存")
        self.distribute_huge_page(self.master, 5120, 0)
        self.distribute_huge_page(self.agent, 5120, 0)
        self.dst_ip = getattr(self.agent, 'ip', '')
        
        self.logStep("S1、使用xml在节点1创建虚机")
        vm_created = self.create_vm_from_xml(
            self.master, str(xml_base_path), self.VM_XML_PATH, "test_vm_migrate_xml_002_vm.xml"
        )
        
        self.logStep("E1、虚机创建成功")
        self.assertTrue(vm_created, "vm created failed.")
        
        self.logStep("S2、登录虚机，使用stress-ng加压80%")
        vm_ssh_node = self.add_stress_to_vm(self.master, self.vm_name, 80)
        
        self.logStep("E2、加压成功，虚机正常运行")
        time.sleep(20)
        vm_mem = client.get_memory(vm_ssh_node)
        self.logInfo(f"虚机实际使用内存: {vm_mem} MB")
        self.assertTrue(6144 <= int(vm_mem["used"]),
                        f"test_vm_migrate_xml_002_vm mem {vm_mem['used']} not in expected range")
        
        self.logStep("S3、执行虚机迁移virsh migrate --p2p --live --unsafe --migrateuri hcom://dst_ip vm_name --listen-address dst_ip qemu+tcp://dst_ip/system --verbose --rdma-pin-all")
        migrate_cmd = (
            f"virsh migrate --p2p --live --unsafe --migrateuri hcom://{self.dst_ip} {self.vm_name} "
            f"--listen-address {self.dst_ip} qemu+tcp://{self.dst_ip}/system "
            f"--verbose --rdma-pin-all"
        )
        self.master.run({"command": [migrate_cmd], 'timeout': 120})
        
        self.logStep("E3、虚机成功迁移到对端")
        time.sleep(10)
        vm_migrated = self.wait_vm_state(self.agent, self.vm_name, "running", timeout=300)
        self.assertTrue(vm_migrated, "vm migrate failed.")
        
        vm_ssh_node = self._get_vm_ssh(self.agent, self.vm_name)
        vm_mem = client.get_memory(vm_ssh_node)
        self.logInfo(f"虚机实际使用内存: {vm_mem} MB")
        self.assertTrue(6144 <= int(vm_mem["used"]),
                        f"test_vm_migrate_xml_002_vm mem {vm_mem['used']} not in expected range")
