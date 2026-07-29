#!/usr/local/python
# -*- coding: utf-8 -*-
from libs.core.basecase.ubturbo import SmapCase, EnableNodeMsg
from libs.core.basecase.ubturbo.smap_params import MigrateOutSizeMsg, MigrateOutSizePayload


class TestTcSmapScMemFragmentation001(SmapCase):
    """
    CaseId:
        TC_SMAP_SC_MEM_FRAGMENTATION_001
    RunLevel:
        Level 1
    CaseTopo:
        无
    CaseName:
        内存碎片场景虚机，迁出2G内存到远端numa 并迁回
    PreCondition:
        1、系统正常；
        2、SMAP组件初始化成功,内存碎片场景
    TestStep:
        1、借用2G远端内存
        2、创建一个4U8G的虚拟机
        3、执行smap set_smap_remote_numa_info src_nid dst_nid available_mem设置可以迁移的远端内存
        4、对虚拟机分别执行smap_mig_out_memsize dest_nid pid 25 2097152 migMode 1 迁出2G内存
        5、迁回远端内存
        6、观察虚拟机状态
    ExpectResult:
        1、内存借用成功
        2、虚拟机启动成功
        3、设置远端内存成功
        4、迁出成功
        5、远端内存设置成功
        6、虚拟机状态正常

    """

    def setup_method(self):
        super(TestTcSmapScMemFragmentation001, self).preTestCase()
        self.logStep("1、系统正常；")

        self.logStep("2、SMAP组件初始化成功,内存碎片场景")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)
        rc = self.cli[0].smap_set_smap_run_mode(1)
        self.assertEqual(rc, True)

    def test_tc_smap_sc_mem_fragmentation_001(self):
        self.logStep("1、借用2G远端内存")

        self.logStep("2、创建一个4U8G的虚拟机")
        self.hosts[0].vm_nodes[0].create()
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()

        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)
        remote_numa = self.remote_numa_list[0]

        self.logStep("3、执行smap set_smap_remote_numa_info src_nid dst_nid available_mem设置可以迁移的远端内存")
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 17000)
        self.assertEqual(rc, 0)

        self.logStep("4、对虚拟机分别执行smap_mig_out_memsize dest_nid pid 25 2097152 migMode 1 迁出1M内存")
        result = self.cli[0].smap_mig_out_memsize(
            MigrateOutSizeMsg([MigrateOutSizePayload(remote_numa, vm_pid, 0, 2097152, 1)]), 1)
        self.assertEqual(result, 0)

        self.logStep("5、迁回远端内存")
        addr_list = self.hosts[0].get_smap_out_addrs(remote_numa)
        self.assertNotEqual(addr_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 0)
        self.assertEqual(rc, 0)
        result = self.cli[0].batch_mig_back(remote_numa, -1, addr_list)
        self.assertEqual(result, True)

        self.logStep("6、观察虚拟机状态")
        result = self.hosts[0].vm_nodes[0].check_vm_real_status()
        self.assertEqual(result, True)

    def teardown_method(self):
        super(TestTcSmapScMemFragmentation001, self).postTestCase()
        self.cli[0].smap_set_smap_run_mode(0)
        if len(self.remote_numa_list) == 0:
            return
        self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        self.safe_delete_vms()