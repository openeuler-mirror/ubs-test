"""
Migrated from legacy: test_vm_hot_plug_delete_001
"""

import os
import time
from typing import Any, Dict, List

from pathlib import Path

from libs.modules.ubsvirt.basecase.vmhotplug_basecase import VMHotPlugBaseCase
from libs.modules.ubsvirt.api import client
from libs.utils.logger_compat import Log

XML_BASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "xml"


class TestVmHotPlugDelete001(VMHotPlugBaseCase):
    """
    CaseNumber:
        test_vm_hot_plug_delete_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        使用本地内存热插后删除虚机内存正确释放
    PreCondition:
        P1、Ubs Scheduler服务正常部署，正常使能
        P2、不超分场景（ram_allocation_ratio为默认配置1）
        P3、numa0配置5G+(1G/numa数)的2M大页内存
        P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0
    TestStep:
        S1、使用xml创建虚拟机vm_01
        S2、使用命令对虚机热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0
        S3、查看虚机xml
        S4、通过numastat命令查看内存情况
        S5、使用hot_plug delete命令删除虚机
        S6、通过numastat命令查看内存情况
    ExpectedResult:
        E1、虚机创建成功
        E2、内存热插成功
        E3、xml中包含扩容的1G内存信息
        E4、numa0上无空闲内存
        E5、虚机删除成功
        E6、numa0上有5G空闲内存
    Author:
        chenglixiao 00961814
    """

    def setup_method(self):
        
        self.source_path = str(XML_BASE_PATH)
        self.filepath = "/root/hot_plug_test/hot_plug/xml"

        self.logStep("P1、Ubs Scheduler服务正常部署，正常使能")

        self.logStep("P2、不超分场景（ram_allocation_ratio为默认配置1）")

        self.logStep("P3、numa0配置5G+(1G/numa数)的2M大页内存")
        hugepage_0 = (5 * 1024 + 1024 // self.numa_num) // 2
        self.distribute_huge_page(self.master, hugepage_0, 0)

        self.logStep("P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0")

    def teardown_method(self):
        
        self.master.run({"command": ["virsh destroy vm_01"], "timeout": 1800})
        self.master.run({"command": [f"rm -rf {self.filepath}/vm_01.xml"], "timeout": 1800})
        self.distribute_huge_page(self.master, 0, 0)

    def test_vm_hot_plug_delete_001(self):
        

        self.logStep("S1、使用xml创建虚拟机vm_01")
        self.create_vm_from_xml(self.master, self.source_path, self.filepath, "test_vm_hot_plug_delete_001_vm_01.xml")

        self.logStep("E1、虚机创建成功")

        self.logStep("S2、使用命令对虚机热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0")
        self.hot_plug_mem(self.master, "vm_01", 1, 0, 0, 100)

        self.logStep("E2、内存热插成功")

        self.logStep("S3、查看虚机xml")
        self.get_vm_xml_hot_plug_section(self.master, "vm_01", 0, 1024 * 1024)

        self.logStep("E3、xml中包含扩容的1G内存信息")

        self.logStep("S4、通过numastat命令查看内存情况")
        numa_info = client.get_numaInfo(self.master)
        node_0_huge_free = int(numa_info[0].get("HugePages_Free"))

        self.logStep("E4、numa0上无空闲内存")
        self.assertEqual(node_0_huge_free, 0, "node0 hugepage free should be none")

        self.logStep("S5、使用hot_plug delete命令删除虚机")
        self.hot_plug_delete(self.master, "vm_01", 100)

        self.logStep("E5、虚机删除成功")

        self.logStep("S6、通过numastat命令查看内存情况")
        time.sleep(2)
        numa_info_after = client.get_numaInfo(self.master)

        self.logStep("E6、numa0上有5G空闲内存")
        node_0_huge_free_after = int(numa_info_after[0].get("HugePages_Free"))
        self.assertEqual(node_0_huge_free_after, 5 * 1024, "node0 hugepage free should be 5*1024")
