"""
Migrated from legacy: test_vm_hot_plug_create_006
"""

import os
import time
from typing import Any, Dict, List

from pathlib import Path

from libs.modules.ubsvirt.basecase.vmhotplug_basecase import VMHotPlugBaseCase
from libs.modules.ubsvirt.api import client
from libs.utils.logger_compat import Log

XML_BASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "xml"


class TestVmHotPlugCreate006(VMHotPlugBaseCase):
    """
    CaseNumber:
        test_vm_hot_plug_create_006
    RunLevel:
        Level T
    EnvType:

    CaseName:
        借用远端内存到同numa热插
    PreCondition:
        P1、Ubs Scheduler服务正常部署，正常使能
        P2、不超分场景（ram_allocation_ratio为默认配置1）
        P3、numa0配置8G+(1G/numa数)+128M(预留冷热迁移)的2M大页内存，节点2的socket0的numa配置2G的2M大页内存
        P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0
    TestStep:
        S1、使用xml创建虚拟机vm_01，vm_02
        S2、登录虚机vm_01查看内存
        S3、使用命令对虚机热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0
        S4、查看虚机xml
        S5、查看虚机内存
        S6、使用numastat查看内存借用情况
        S7、使用stress-ng命令给虚机加压超过4G
    ExpectedResult:
        E1、虚机创建成功
        E2、内存可用大小大约为4G
        E3、内存热插成功
        E4、xml中包含扩容的1G内存信息
        E5、内存大小扩容到5G
        E6、借用>=1G的远端内存
        E7、查看内存使用量超过4G
    Author:
        chenglixiao 00961814
    """

    def setup_method(self):
        
        self.source_path = str(XML_BASE_PATH)
        self.filepath = "/root/hot_plug_test/hot_plug/xml"
        self.img_path = "/opt/install/tmp/openstack/images/"

        self.logStep("P1、Ubs Scheduler服务正常部署，正常使能")

        self.logStep("P2、不超分场景（ram_allocation_ratio为默认配置1）")

        self.logStep(
            "P3、numa0配置8G+(1G/numa数)+128M(预留冷热迁移)的2M大页内存，节点2的socket0的numa配置2G的2M大页内存"
        )
        hugepage_num = (8 * 1024 + 1024 // self.numa_num + 128) // 2
        self.distribute_huge_page(self.master, int(hugepage_num), 0)
        self.distribute_huge_page(self.agent, 1280, 0)

        self.logStep("P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0")

    def teardown_method(self):
        
        self.master.run({"command": ["hot_plug delete vm_01"], "timeout": 1800})
        self.master.run({"command": ["hot_plug delete vm_02"], "timeout": 1800})
        self.master.run({"command": [f"rm -rf {self.filepath}/vm_01.xml"], "timeout": 1800})
        self.master.run({"command": [f"rm -rf {self.filepath}/vm_02.xml"], "timeout": 1800})
        self.master.run(
            {
                "command": [
                    f"rm -rf {self.img_path}/openEuler-22.03-SP2-aarch64-everything-redis-Performance1.qcow2"
                ]
            }
        )
        self.distribute_huge_page(self.master, 0, 0)
        self.distribute_huge_page(self.agent, 0, 0)

    def test_vm_hot_plug_create_006(self):
        

        self.logStep("S1、使用xml创建虚拟机vm_01，vm_02")
        vm1_created = self.create_vm_from_xml(
            self.master, self.source_path, self.filepath, "test_vm_hot_plug_create_006_vm_01.xml"
        )
        self.assertTrue(vm1_created, "vm_01 created failed.")
        self.master.run(
            {
                "command": [
                    f"\\cp -f {self.img_path}/openEuler-22.03-SP2-aarch64-everything-redis-Performance.qcow2 "
                    f"{self.img_path}/openEuler-22.03-SP2-aarch64-everything-redis-Performance1.qcow2"
                ]
            }
        )
        vm2_created = self.create_vm_from_xml(
            self.master, self.source_path, self.filepath, "test_vm_hot_plug_create_006_vm_02.xml"
        )
        self.assertTrue(vm2_created, "vm_02 created failed.")

        self.logStep("E1、虚机创建成功")

        self.logStep("S2、登录虚机vm_01查看内存")
        vm_01_ssh = self._get_vm_ssh(self.master, "vm_01")
        vm_mem = client.get_memory(vm_01_ssh)

        self.logStep("E2、内存可用大小大约为4G")
        self.assertGreaterEqual(int(vm_mem["total"]), 3840, message="vm mem not around 4096MB.")

        self.logStep("S3、使用命令对虚机热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0")
        self.hot_plug_mem(self.master, "vm_01", 1, 0, 0, 100)

        self.logStep("E3、内存热插成功")

        self.logStep("S4、查看虚机xml")
        self.get_vm_xml_hot_plug_section_new(self.master, "vm_01", 0, 1024 * 1024)

        self.logStep("E4、xml中包含扩容的1G内存信息")

        self.logStep("S5、查看虚机内存")
        time.sleep(10)
        vm_mem = client.get_memory(vm_01_ssh)

        self.logStep("E5、内存大小扩容到5G")
        self.assertGreaterEqual(int(vm_mem["total"]), 4864, message="vm mem not around 5120MB.")

        self.logStep("S6、使用numastat查看内存借用情况")
        borrow_mem = self.get_node_borrowing_numa(self.master)

        self.logStep("E6、借用>=1G的远端内存")
        self.assertGreaterEqual(
            borrow_mem, 896, "borrowing mem from remote node is less than 896MB ."
        )

        self.logStep("S7、使用stress-ng命令给虚机加压超过4G")
        client.vm_stree(vm_01_ssh, str(4 * 1024) + "M")
        time.sleep(20)

        self.logStep("E7、查看内存使用量超过4G")
        vm_mem_res = self.wait_vm_used_mem_match_expect(vm_01_ssh, "greater", 4096, 180, 10)
        self.assertTrue(vm_mem_res, "vm used mem not match expected 4096MB")