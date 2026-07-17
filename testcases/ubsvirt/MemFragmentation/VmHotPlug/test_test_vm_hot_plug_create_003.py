"""
Migrated from legacy: test_vm_hot_plug_create_003
"""

import os
import time
from typing import Any, Dict, List

from pathlib import Path

from libs.modules.ubsvirt.basecase.vmhotplug_basecase import VMHotPlugBaseCase
from libs.modules.ubsvirt.api import client
from libs.utils.logger_compat import Log

XML_BASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "xml"


class TestVmHotPlugCreate003(VMHotPlugBaseCase):
    """
    CaseNumber:
        test_vm_hot_plug_create_003
    RunLevel:
        Level T
    EnvType:

    CaseName:
        使用跨socket的本地内存热插
    PreCondition:
        P1、Ubs Scheduler服务正常部署，正常使能
        P2、不超分场景（ram_allocation_ratio为默认配置1）
        P3、numa0配置8G+(1G/numa数)的2M大页内存，socket1上numa配置2G+(1G/numa数)的2M大页内存
        P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0，xml不严格指定numa
    TestStep:
        S1、使用xml创建虚拟机vm_01
        S2、登录虚机查看内存
        S3、使用命令对虚机热插2G内存，hot_plug add vm_01 -size 2 -gnode 0 -slot 0
        S4、查看虚机xml
        S5、查看虚机内存
        S6、使用stress-ng命令给虚机加压超过8G
    ExpectedResult:
        E1、虚机创建成功
        E2、内存可用大小大约为8G
        E3、内存热插成功
        E4、xml中包含扩容的1G内存信息
        E5、内存大小扩容到10G
        E6、查看内存使用量超过8G
    """

    def setup_method(self):
        
        self.source_path = str(XML_BASE_PATH)
        self.filepath = "/root/hot_plug_test/hot_plug/xml"

        self.logStep("P1、Ubs Scheduler服务正常部署，正常使能")

        self.logStep("P2、不超分场景（ram_allocation_ratio为默认配置1）")

        self.logStep(
            "P3、numa0配置8G+(1G/numa数)的2M大页内存，socket1上numa配置2G+(1G/numa数)的2M大页内存"
        )
        hugepage_0 = (8 * 1024 + 1024 // self.numa_num) // 2
        hugepage_1 = (2 * 1024 + 1024 // self.numa_num) // 2

        self.distribute_huge_page(self.master, hugepage_0, 0)
        self.distribute_huge_page(self.master, hugepage_1, (self.numa_num - 1))

        self.logStep(
            "P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0，xml不严格指定numa"
        )

    def teardown_method(self):
        
        self.master.run({"command": ["hot_plug delete vm_01"], "timeout": 1800})
        self.master.run({"command": [f"rm -rf {self.filepath}/vm_01.xml"], "timeout": 1800})
        self.distribute_huge_page(self.master, 0, 0)
        self.distribute_huge_page(self.master, 0, (self.numa_num - 1))

    def test_vm_hot_plug_create_003(self):
        

        self.logStep("S1、使用xml创建虚拟机vm_01")
        vm_created = self.create_vm_from_xml(
            self.master, self.source_path, self.filepath, "test_vm_hot_plug_create_003_vm_01.xml"
        )
        self.assertTrue(vm_created, "vm created failed.")

        self.logStep("E1、虚机创建成功")
        vm_01_ssh = self._get_vm_ssh(self.master, "vm_01")

        self.logStep("S2、登录虚机查看内存")
        vm_mem = client.get_memory(vm_01_ssh)

        self.logStep("E2、内存可用大小大约为8G")
        self.assertTrue(
            7168 <= int(vm_mem["total"]) <= 8192,
            f"vm_01 mem {vm_mem['total']} not in expected range",
        )

        self.logStep("S3、使用命令对虚机热插2G内存，hot_plug add vm_01 -size 2 -gnode 0 -slot 0")
        self.hot_plug_mem(self.master, "vm_01", 2, 0, 0, 100)

        self.logStep("E3、内存热插成功")

        self.logStep("S4、查看虚机xml")
        self.get_vm_xml_hot_plug_section(self.master, "vm_01", 0, 2097152)

        self.logStep("E4、xml中包含扩容的1G内存信息")

        self.logStep("S5、查看虚机内存")
        vm_mem = client.get_memory(vm_01_ssh)

        self.logStep("E5、内存大小扩容到10G")
        self.assertTrue(
            9120 <= int(vm_mem["total"]) <= 10240,
            f"vm_01 mem {vm_mem['total']} not in expected range",
        )

        self.logStep("S6、使用stress-ng命令给虚机加压超过8G")
        client.vm_stree(vm_01_ssh, str(8192) + "M")
        time.sleep(20)

        self.logStep("E6、查看内存使用量超过8G")
        vm_mem_res = self.wait_vm_used_mem_match_expect(vm_01_ssh, "greater", 8192, 180, 10)
        self.assertTrue(vm_mem_res, "vm used mem not match expected 8192MB")
