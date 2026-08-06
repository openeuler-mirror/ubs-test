# -*- coding: utf-8 -*-
from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload, EnableNodeMsg


class TestTcSmapScMemlinkDynamic001(SmapCase):
    """
    CaseId:
        TC_SMAP_SC_MEMLINK_DYNAMIC_001
    RunLevel:
        Level 1
    CaseTopo:
        无
    CaseName:
        VM处于正常状态，虚拟机加压百分之75,向远端NUMA进行内存迁移并迁回，使能远端NUMA，迁出比例变更为50%，再次迁移并迁回成功
    PreCondition:
        1、OS正常运行；
        2、远端借用内存已上线；
        3、SMAP驱动已正确加载；
        4、SMAP正常启动
    TestStep:
        1、启动虚拟机
        virsh create xxx.xml
        2、启动SMAP
        smap smap_init 1
        3、虚拟机加压百分之75
        stress-ng --vm 1 --vm-bytes {size}M --vm-keep
        4、进行内存迁出
        smap smap_mig_out remote_numa pid 25 1
        5、进行内存迁回
        smap smap_mig_back remote_numa 起始地址 终止地址
        6、使能远端节点
        smap smap_enable 1 5
        7、修改迁出比例
        smap smap_mig_out 5 pid 50 1
        8、查看日志
        查看冷热迁移信息：
        tail -f /home/log/smap_itering.log
        查看smap执行信息
        tail -f /var/log/smap_log
    ExpectResult:
        SMAP可以正常运行流程
    """

    def setup_method(self):
        super(TestTcSmapScMemlinkDynamic001, self).preTestCase()
        self.logStep("1、OS正常运行；")

        self.logStep("2、远端借用内存已上线；")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)

        self.logStep("3、SMAP驱动已正确加载；")

        self.logStep("4、SMAP正常启动")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)

        self.recover_smap_env_pre()

    def test_tc_smap_sc_memlink_dynamic_001(self):
        remote_numa = self.remote_numa_list[0]

        self.logStep("1、启动虚拟机 virsh create xxx.xml")
        self.hosts[0].vm_nodes[0].create()
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()

        self.logStep("2、虚拟机加压百分之75 stress-ng --vm 1 --vm-bytes {size}M --vm-keep")
        vm_mem_total = self.hosts[0].vm_nodes[0].get_mem_total_size()
        self.hosts[0].vm_nodes[0].stress_ng_mem(1, vm_mem_total * 0.75)

        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 0, 60, True)
        self.assertEqual(result, True, f"remote_numa{remote_numa} 被占用")
        vm1_mem_topo = self.hosts[0].vm_nodes[0].get_vm_mem_topo()

        self.logStep("3、进行内存迁出 smap smap_mig_out remote_numa pid 25 1")
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 17000)
        self.assertEqual(rc, 0)
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, vm_pid, 25)]), 1)
        self.assertEqual(rc, 0)
        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 1, 180)
        self.assertEqual(result, True)

        self.logStep("4、进行内存迁回 smap smap_mig_back remote_numa 起始地址 终止地址")
        addr_list = self.hosts[0].get_smap_out_addrs(remote_numa)
        self.assertNotEqual(addr_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 0)
        self.assertEqual(rc, 0)

        result = self.cli[0].batch_mig_back(remote_numa, -1, addr_list)
        self.assertEqual(result, True)
        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 0, 180, True)
        self.assertEqual(result, True)

        self.logStep("5、使能远端节点 smap smap_enable 1 5")
        rc = self.cli[0].smap_enable_node(EnableNodeMsg(1, remote_numa))
        self.assertEqual(rc, 0)

        self.logStep("6、再次迁出 smap smap_mig_out remote_numa pid 25 1")
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 17000)
        self.assertEqual(rc, 0)
        rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(remote_numa, vm_pid, 50)]), 1)
        self.assertEqual(rc, 0)
        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 1, 180)
        self.assertEqual(result, True)

        addr_list = self.hosts[0].get_smap_out_addrs(remote_numa)
        self.assertNotEqual(addr_list, [])
        rc = self.cli[0].set_smap_remote_numa_info(0, remote_numa, 0)
        self.assertEqual(rc, 0)

        result = self.cli[0].batch_mig_back(remote_numa, -1, addr_list)
        self.assertEqual(result, True)
        result = self.hosts[0].watch_proc_mem(vm_pid, remote_numa, 0, 180, True)
        self.assertEqual(result, True)

        self.logStep("7、查看日志"
                     "查看冷热迁移信息："
                     "tail -f /home/log/smap_itering.log"
                     "查看smap执行信息"
                     "tail -f /var/log/smap_log")
        result = self.hosts[0].vm_nodes[0].check_vm_real_status()
        self.assertEqual(result, True)

        vm1_new_mem_topo = self.hosts[0].vm_nodes[0].get_vm_mem_topo()
        self.assertEqual(vm1_mem_topo, vm1_new_mem_topo)

    def teardown_method(self):
        super(TestTcSmapScMemlinkDynamic001, self).postTestCase()
        if len(self.remote_numa_list) == 0:
            return
        self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
        if self.hosts[0].vm_nodes[0].in_use():
            self.hosts[0].vm_nodes[0].stop_stress_ng()
        self.safe_delete_vms()