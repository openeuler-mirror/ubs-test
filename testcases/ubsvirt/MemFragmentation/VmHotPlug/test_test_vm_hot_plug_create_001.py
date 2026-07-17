import time

from pathlib import Path

from libs.modules.ubsvirt.basecase.vmhotplug_basecase import VMHotPlugBaseCase
from libs.modules.ubsvirt.api import client

XML_BASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "xml"


class TestVmHotPlugCreate001(VMHotPlugBaseCase):
    """
    CaseNumber:
        test_vm_hot_plug_create_001
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        使用同numa的本地内存热插
    PreCondition:
        P1、Ubs Scheduler服务正常部署，正常使能
        P2、不超分场景（ram_allocation_ratio为默认配置1）
        P3、numa0配置5G+(1G/numa数)的2M大页内存
        P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0
    TestStep:
        S1、使用xml创建虚拟机vm_01
        S2、登录虚机查看内存
        S3、使用命令对虚机热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0
        S4、查看虚机xml
        S5、查看虚机内存
        S6、使用stress-ng命令给虚机加压超过4G
    ExpectedResult:
        E1、虚机创建成功
        E2、内存可用大小大约为4G
        E3、内存热插成功
        E4、xml中包含扩容的1G内存信息
        E5、内存大小扩容到5G
        E6、查看内存使用量超过4G
    """

    def setup_method(self):
        
        self.source_path = str(XML_BASE_PATH)
        self.filepath = "/root/hot_plug_test/hot_plug/xml"

        self.logStep("P1、Ubs Scheduler服务正常部署，正常使能")

        self.logStep("P2、不超分场景（ram_allocation_ratio为默认配置1）")

        self.logStep("P3、numa0配置5G+(1G/numa数)的2M大页内存")
        hugepage_num = (5 * 1024 + 1024 // self.numa_num + 128) // 2
        self.distribute_huge_page(self.master, hugepage_num, 0)

        self.logStep("P4、环境上存在4G虚机的xml，xml需要有guest numa 0和内存插槽slot 0")

    def teardown_method(self):
        
        self.master.run({"command": ["hot_plug delete vm_01"], "timeout": 1800})
        self.master.run({"command": [f"rm -rf {self.filepath}/vm_01.xml"], "timeout": 1800})
        self.distribute_huge_page(self.master, 0, 0)

    def test_vm_hot_plug_create_001(self):
        

        self.logStep("S1、使用xml创建虚拟机vm_01")
        vm_created = self.create_vm_from_xml(
            self.master, self.source_path, self.filepath, "test_vm_hot_plug_create_001_vm_01.xml"
        )
        self.assertTrue(vm_created, "vm created failed.")

        self.logStep("E1、虚机创建成功")

        self.logStep("S2、登录虚机查看内存")
        vm_01_ssh = self._get_vm_ssh(self.master, "vm_01")
        vm_mem = client.get_memory(vm_01_ssh)

        self.logStep("E2、内存可用大小大约为4G")
        self.assertTrue(
            3584 <= int(vm_mem["total"]) <= 4096,
            f"vm_01 mem {vm_mem['total']} not in expected range",
        )

        self.logStep("S3、使用命令对虚机热插1G内存，hot_plug add vm_01 -size 1 -gnode 0 -slot 0")
        self.hot_plug_mem(self.master, "vm_01", 1, 0, 0, 100)

        self.logStep("E3、内存热插成功")

        self.logStep("S4、查看虚机xml")
        self.get_vm_xml_hot_plug_section(self.master, "vm_01", 0, 1048576)

        self.logStep("E4、xml中包含扩容的1G内存信息")

        self.logStep("S5、查看虚机内存")
        vm_mem = client.get_memory(vm_01_ssh)

        self.logStep("E5、内存大小扩容到5G")
        self.assertTrue(
            4096 <= int(vm_mem["total"]) <= 5120,
            f"vm_01 mem {vm_mem['total']} not in expected range",
        )

        self.logStep("S6、使用stress-ng命令给虚机加压超过4G")
        client.vm_stree(vm_01_ssh, str(4096) + "M")
        time.sleep(120)
        self.logStep("E6、查看内存使用量超过4G")
        vm_mem = client.get_memory(vm_01_ssh)
        self.assertGreaterEqual(int(vm_mem["used"]), 4096, "vm used mem less than 4096MB.")