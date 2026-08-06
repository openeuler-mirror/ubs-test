# -*- coding: utf-8 -*-
from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload, EnableNodeMsg


class TestTcSmapScVm1650HeatScan001(SmapCase):
    """
    CaseId:
        TC_SMAP_SC_VM_1650_HEAT_SCAN_001
    RunLevel:
        Level 1
    CaseTopo:
        无
    CaseName:
        1650判热场景,虚拟机迁移1G远端内存
    PreCondition:
        1、系统正常
        2、环境支持1650判热
        3、准备8U32G虚拟机
        3、SMAP组件初始化成功
    TestStep:
        1、启动8U32G虚拟机
        2、执行smap set_smap_remote_numa_info src_nid dst_nid available_mem设置可以迁移的远端内存
        3、对虚拟机分别执行smap smap_mig_out pid ratio迁出1G内存
        4、虚拟机里面启动redis-server
        5、虚拟机里面启动redis-benchmark访问远端内存
        6、执行smap set_smap_remote_numa_info src_nid dst_nid 0设置远端内存为0
        7、迁回虚拟机内存
        8、检查虚拟机状态是否正常
    ExpectResult:
        1、虚拟机启动成功
        2、远端内存设置成功
        3、虚拟机迁出成功
        4、redis启动成功
        5、benchmark启动成功
        6、内存大小设置成功
        7、内存迁回成功，进程正常
        8、虚拟机状态正常
    """

    def setup_method(self):
        super(TestTcSmapScVm1650HeatScan001, self).preTestCase()
        self.logStep("1、系统正常")

        self.logStep("2、环境支持1650判热")
        self.hosts[0].install_hist_tracking_ko()

        self.logStep("3、准备8U32G虚拟机")

        self.logStep("3、SMAP组件初始化成功")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

        self.recover_smap_env_pre()

    def test_tc_smap_sc_vm_1650_heat_scan_001(self):
        remote_numa = self.remote_numa_list[0]

        self.logStep("1、启动8U32G虚拟机")
        self.logStep("预期结果：1、虚拟机启动成功")
        result = self.hosts[0].vm_nodes[0].create()
        self.assertEqual(result, True)
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        self.assertNotEqual(vm_pid, -1)

        self.logStep("2、执行smap set_smap_remote_numa_info src_nid dst_nid available_mem设置可以迁移的远端内存")
        self.logStep("预期结果：2、远端内存设置成功")
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 17408)
        self.assertEqual(rc, 0)

        self.logStep("3、对虚拟机分别执行smap smap_mig_out pid ratio迁出1G内存")
        self.logStep("预期结果：3、虚拟机迁出成功")
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, vm_pid, 100)]), 1)
        self.assertEqual(rc, 0)
        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 1, 180)
        self.assertEqual(result, True)

        self.logStep("4、虚拟机里面启动redis-server")
        self.logStep("预期结果：4、redis启动成功")
        vm_ip = self.hosts[0].vm_nodes[0].get_data_ip()
        self.hosts[0].vm_nodes[0].update_redis_ip(vm_ip)
        result = self.hosts[0].vm_nodes[0].start_redis()
        self.assertEqual(result, True)

        self.logStep("5、虚拟机里面启动redis-benchmark访问远端内存")
        self.logStep("预期结果：5、benchmark启动成功")
        result = self.hosts[0].vm_nodes[0].run_redis_benchmark(100000, 128, 2048, 16000, 2, vm_ip)
        self.assertEqual(result, True)

        self.logStep("6、执行smap set_smap_remote_numa_info src_nid dst_nid 0设置远端内存为0")
        self.logStep("预期结果：6、内存大小设置成功")
        rc = self.cli[0].set_smap_remote_numa_info(0, self.remote_numa_list[0], 0)
        self.assertEqual(rc, 0)

        self.logStep("7、迁回虚拟机内存")
        self.logStep("预期结果：7、内存迁回成功，进程正常")
        addr_list = self.hosts[0].get_smap_out_addrs(self.remote_numa_list[0])
        self.assertNotEqual(addr_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(0, self.remote_numa_list[0], 0)
        self.assertEqual(rc, 0)
        result = self.cli[0].batch_mig_back(self.remote_numa_list[0], -1, addr_list)
        self.assertEqual(result, True)

        self.logStep("8、检查虚拟机状态是否正常")
        self.logStep("预期结果：8、虚拟机状态正常")
        result = self.hosts[0].vm_nodes[0].check_vm_real_status()
        self.assertEqual(result, True)

    def teardown_method(self):
        super(TestTcSmapScVm1650HeatScan001, self).postTestCase()
        self.hosts[0].remove_hist_tracking_ko()
        if len(self.remote_numa_list) == 0:
            return
        self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        self.safe_delete_vms()