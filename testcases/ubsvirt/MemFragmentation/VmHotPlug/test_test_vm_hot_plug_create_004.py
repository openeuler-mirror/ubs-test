"""
Migrated from legacy: test_vm_hot_plug_create_004
"""

import os
import time
from typing import Any, Dict, List

from pathlib import Path

from libs.modules.ubsvirt.basecase.vmhotplug_basecase import VMHotPlugBaseCase
from libs.modules.ubsvirt.api import client
from libs.utils.logger_compat import Log

XML_BASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "xml"


class TestVmHotPlugCreate004(VMHotPlugBaseCase):
    """
    CaseNumber:
        test_vm_hot_plug_create_004
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证两个虚机分别热插成功
    PreCondition:
        P1、Ubs Scheduler服务正常部署，正常使能
        P2、不超分场景（ram_allocation_ratio为默认配置1）
        P3、numa0配置10G+(1G/numa数)的2M大页内存
        P4、环境上存在2个4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0
    TestStep:
        S1、使用xml创建虚拟机vm_01，vm_02
        S2、登录虚机查看内存
        S3、使用命令对虚机vm_01热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0
        S4、查看虚机xml
        S5、查看虚机内存
        S6、使用命令对虚机vm_02热插1G内存，hot_plug add vm_02 -size 1 -gnode 0 -slot 0
        S7、查看虚机xml
        S8、查看虚机内存
    ExpectedResult:
        E1、虚机创建成功
        E2、内存可用大小大约为4G
        E3、内存热插成功
        E4、xml中包含扩容的1G内存信息
        E5、内存大小扩容到5G
        E6、内存热插成功
        E7、xml中包含扩容的1G内存信息
        E8、内存大小扩容到5G
    """

    def setup_method(self):
        
        self.source_path = str(XML_BASE_PATH)
        self.file_path = "/root/hot_plug_test/hot_plug/xml"
        self.img_path = "/opt/install/tmp/openstack/images/"

        self.logStep("P1、Ubs Scheduler服务正常部署，正常使能")

        self.logStep("P2、不超分场景（ram_allocation_ratio为默认配置1）")

        self.logStep("P3、numa0配置10G+(1G/numa数)的2M大页内存")
        hugepage_0 = (10 * 1024 + 1024 // self.numa_num) // 2
        self.distribute_huge_page(self.master, hugepage_0, 0)

        self.logStep("P4、环境上存在2个4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0")

    def teardown_method(self):
        
        self.master.run({"command": ["hot_plug delete vm_01"], "timeout": 1800})
        self.master.run({"command": ["hot_plug delete vm_02"], "timeout": 1800})
        self.master.run({"command": [f"rm -rf {self.file_path}/vm_01.xml"]})
        self.master.run({"command": [f"rm -rf {self.file_path}/vm_02.xml"]})
        self.master.run(
            {
                "command": [
                    f"rm -rf {self.img_path}/openEuler-22.03-SP2-aarch64-everything-redis-Performance1.qcow2"
                ]
            }
        )
        self.distribute_huge_page(self.master, 0, 0)

    def test_vm_hot_plug_create_004(self):
        

        self.logStep("S1、使用xml创建虚拟机vm_01，vm_02")
        vm1_created = self.create_vm_from_xml(
            self.master, self.source_path, self.file_path, "test_vm_hot_plug_create_004_vm_01.xml"
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
            self.master, self.source_path, self.file_path, "test_vm_hot_plug_create_004_vm_02.xml"
        )
        self.assertTrue(vm2_created, "vm_02 created failed.")

        self.logStep("E1、虚机创建成功")

        self.logStep("S2、登录虚机查看内存")
        vm_01_ssh = self._get_vm_ssh(self.master, "vm_01")
        vm_02_ssh = self._get_vm_ssh(self.master, "vm_02")

        vm1_mem = client.get_memory(vm_01_ssh)
        vm2_mem = client.get_memory(vm_02_ssh)

        self.logStep("E2、内存可用大小大约为4G")
        self.assertTrue(
            3584 <= int(vm1_mem["total"]) <= 4096,
            f"vm_01 mem {vm1_mem['total']} not in expected range",
        )
        self.assertTrue(
            3584 <= int(vm2_mem["total"]) <= 4096,
            f"vm_02 mem {vm2_mem['total']} not in expected range",
        )

        self.logStep(
            "S3、使用命令对虚机vm_01热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0"
        )

        self.hot_plug_mem(self.master, "vm_01", 1, 0, 0, 100)

        self.logStep("E3、内存热插成功")

        self.logStep("S4、查看虚机xml")
        self.get_vm_xml_hot_plug_section(self.master, "vm_01", 0, 1048576)

        self.logStep("E4、xml中包含扩容的1G内存信息")

        self.logStep("S5、查看虚机内存")
        vm1_mem = client.get_memory(vm_01_ssh)

        self.logStep("E5、内存大小扩容到5G")
        self.assertTrue(
            4608 <= int(vm1_mem["total"]) <= 5120,
            f"vm_01 mem {vm1_mem['total']} not in expected range",
        )

        self.logStep(
            "S6、使用命令对虚机vm_02热插1G内存，hot_plug add vm_02 -size 1 -gnode 0 -slot 0"
        )
        self.hot_plug_mem(self.master, "vm_02", 1, 0, 0, 100)

        self.logStep("E6、内存热插成功")

        self.logStep("S7、查看虚机xml")
        self.get_vm_xml_hot_plug_section(self.master, "vm_02", 0, 1048576)

        self.logStep("E7、xml中包含扩容的1G内存信息")

        self.logStep("S8、查看虚机内存")
        vm2_mem = client.get_memory(vm_02_ssh)

        self.logStep("E8、内存大小扩容到5G")
        self.assertTrue(
            4608 <= int(vm2_mem["total"]) <= 5120,
            f"vm_02 mem {vm2_mem['total']} not in expected range",
        )