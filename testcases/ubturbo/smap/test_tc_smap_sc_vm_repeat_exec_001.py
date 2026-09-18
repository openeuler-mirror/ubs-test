# -*- coding: utf-8 -*-
import time

from libs.core.basecase.ubturbo import SmapCase, MigrateOutMsg, MigrateOutPayload, EnableNodeMsg, RemoveMsg


class TestTcSmapScVmRepeatExec001(SmapCase):
    """
    CaseId:
        TC_SMAP_SC_VM_REPEAT_EXEC_001
    RunLevel:
        Level 1
    CaseTopo:
        无
    CaseName:
        4U8G虚拟机在冷页大于25%的情况重复执行25%比例的迁出并迁回
    PreCondition:
        1、OS正常运行；
        2、远端借用内存已上线，借用内存16G
        3、SMAP成功初始化为2M大页模式
    TestStep:
        1、执行virsh create xxx.xml启动4U8G虚拟机，此时虚拟机冷页大于25%，并获取虚拟机的进程号和内存分布
        2、启动redis服务
        3、使用redis-benchmark作为客户端模拟redis数据读写业务运行，构造32M业务数据访问，保证存在大量冷页，冷页数量超过2G
            执行redis-benchmark -t set,get -n 10000000 -r 16000 -c 128 -d 2048 --threads 2 -h 127.0.0.1 -p 6379
        4、配置迁出虚拟机25%内存到远端
            执行smap set_smap_remote_numa_info 0 远端numa 16G 设置可迁出内存
            执行smap smap_mig_out 5 vm_pid 25 1, 触发VM内存迁出，并检查迁出返回状态
        5、查询虚拟机在远端内存使用量
        6、查询远端numa冷热页信息
            循环5次每次间隔5s 执行smap smap_query_vm_freq vm_pid 1 4096 1 3072 4095查询冷热页数量
        7、迁回前检查redis进程状态
        8、将虚拟机远端内存迁回本端"
            8.1）获取远端内存的地址段"
            8.2）执行smap set_smap_remote_numa_info 0 远端numa 0设置可迁出内存为0
            8.3）执行smap smap_mig_back 5 起始地址 终止地址进行进行内存迁回，并查询命令返回结果
        9、查询虚拟机在远端内存使用量
        10、检查虚拟机里面redis进程是否正常
        11、执行 smap smap_enable 1 remote_numa_id 使能远端节点
        12、重复执行4-9步骤
        13、获取redis内存占用，检查redis是否占用内存
        14、对比虚拟机前后内存分布是否一致
    ExpectResult:
        1、虚拟机启动成功
        2、redis启动成功
        3、redis加压成功
        4、内存迁出成功
        5、远端可迁出内存设置成功，2G内存分布到远端numa
        6、远端内存访问频次均为0，表示均为冷页
        7、虚拟机里面redis状态正常
        8、内存迁回成功
        9、虚拟机远端numa内存使用量为0
        10、虚拟机里面redis状态正常
        11、远端节点使能成功
        12、重复执行成功
        13、redis有内存占用
        14、虚拟机内存前后内存分布一致
    """

    def setup_method(self):
        super(TestTcSmapScVmRepeatExec001, self).preTestCase()
        self.logStep("1、OS正常运行；")
        self.logStep("2、远端借用内存已上线，借用内存16G")
        self.remote_numa_list = self.hosts[0].get_remote_numa()
        self.assertNotEqual(len(self.remote_numa_list), 0)
        self.logStep("3、SMAP成功初始化为2M大页模式")
        rc = self.cli[0].smap_init(1)
        self.assertEqual(rc in (0, -1), True)
        rc = self.cli[0].smap_set_smap_run_mode(0)
        self.assertEqual(rc, True)
        self.logStep("4、准备4U8G的虚拟机")

    def test_tc_smap_sc_vm_repeat_exec_001(self):
        self.logStep("1、执行virsh create xxx.xml启动4U8G虚拟机，此时虚拟机冷页大于25%，并获取虚拟机的进程号和内存分布")
        result = self.hosts[0].vm_nodes[0].create()
        self.logStep("预期结果：1、虚拟机启动成功")
        self.assertEqual(result, True)
        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        vm_numa = self.hosts[0].vm_nodes[0].get_unique_numa_node()
        vm_size = self.hosts[0].vm_nodes[0].get_vm_mem_size()
        vm_mem_topo = self.hosts[0].vm_nodes[0].get_vm_mem_topo()
        self.logStep("2、启动redis服务")
        result = self.hosts[0].vm_nodes[0].start_redis()
        self.logStep("预期结果：2、redis启动成功")
        self.assertEqual(result, True)
        self.logStep("3、使用redis-benchmark作为客户端模拟redis数据读写业务运行，构造32M业务数据访问，保证存在大量冷页，冷页数量超过2G"
                     "       执行redis-benchmark -t set,get -n 10000000 -r 16000 -c 128 -d 2048 --threads 2 -h 127.0.0.1 -p 6379")
        result = self.hosts[0].vm_nodes[0].run_redis_benchmark(10000000, 128, 2048, 16000, 2, '127.0.0.1')
        self.logStep("预期结果：3、redis加压成功")
        self.assertEqual(result, True)
        for _ in range(2):
            self.logStep("4、配置迁出虚拟机25%内存到远端"
                         "     执行smap set_smap_remote_numa_info 0 远端numa 16G 设置可迁出内存"
                         "     执行smap smap_mig_out 5 vm_pid 25 1, 触发VM内存迁出，并检查迁出返回状态")
            rc = self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 16384)
            self.assertEqual(rc, 0)
            rc = self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], vm_pid, 25)]), 1)
            self.logStep("预期结果：4、内存迁出成功")
            self.assertEqual(rc, 0)
            self.logStep("5、查询虚拟机在远端内存使用量")
            result = self.hosts[0].watch_proc_mem_strict_mig_out_ratio(vm_pid, self.remote_numa_list[0], vm_size, 25,
                                                                       60)
            self.logStep("预期结果：5、远端可迁出内存设置成功，2G内存分布到远端numa")
            self.assertEqual(result, True)
            self.logStep("6、查询远端numa冷热页信息"
                         "     循环5次每次间隔5s 执行smap smap_query_vm_freq vm_pid 1 4096 1 3072 4095查询冷热页数量")
            self.logStep("预期结果：6、远端内存访问频次均为0，表示均为冷页")
            for i in range(5):
                time.sleep(5)  # 等待5s
                cold_pages = self.cli[0].smap_query_vm_cold_pages(vm_pid, 1, vm_size // 2, 1, vm_size * 3 // 8,
                                                                  vm_size // 2)
                # 不保证全为冷页，预留20%容错
                self.assertGreater(cold_pages, vm_size // 8 * 0.8)
            self.logStep("7、迁回前检查redis进程状态")
            redis_pid = self.hosts[0].vm_nodes[0].get_process_id("redis-server")
            self.logStep("预期结果：7、虚拟机里面redis状态正常")
            self.assertNotEqual(redis_pid, [])
            self.logStep("8、将虚拟机远端内存迁回本端"
                         "     8.1）获取远端内存的地址段"
                         "     8.2）执行smap set_smap_remote_numa_info 0 远端numa 0设置可迁出内存为0"
                         "     8.3）执行smap smap_mig_back 5 起始地址 终止地址进行进行内存迁回，并查询命令返回结果")
            addr_list = self.hosts[0].get_smap_out_addrs(self.remote_numa_list[0])
            self.assertNotEqual(addr_list, [])
            rc = self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 0)
            self.assertEqual(rc, 0)
            result = self.cli[0].batch_mig_back(self.remote_numa_list[0], -1, addr_list)
            self.logStep("预期结果：8、内存迁回成功")
            self.assertEqual(result, True)
            self.logStep("9、查询虚拟机在远端内存使用量")
            result = self.hosts[0].watch_proc_mem_strict_mig_back(vm_pid, self.remote_numa_list[0], 60)
            self.logStep("预期结果：9、虚拟机远端numa内存使用量为0")
            self.assertEqual(result, True)
            self.logStep("10、检查虚拟机里面redis进程是否正常")
            redis_pid = self.hosts[0].vm_nodes[0].get_process_id("redis-server")
            self.logStep("预期结果：10、虚拟机里面redis状态正常")
            self.assertNotEqual(redis_pid, [])
            self.logStep("11、执行 smap smap_enable 1 remote_numa_id 使能远端节点")
            rc = self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))
            self.logStep("预期结果：11、远端节点使能成功")
            self.assertEqual(rc, 0)
            self.logStep("12、重复执行4-9步骤")
            self.logStep("预期结果：12、重复执行成功")
        self.logStep("13、获取redis内存占用，检查redis是否占用内存")
        redis_pid = self.hosts[0].vm_nodes[0].get_process_id("redis-server")
        self.assertNotEqual(redis_pid, [])
        mem_size = self.hosts[0].vm_nodes[0].get_proc_mem("redis-server")
        self.logStep("预期结果：13、redis有内存占用")
        self.assertNotEqual(mem_size, 0)
        self.logStep("14、对比虚拟机前后内存分布是否一致")
        vm_new_mem_topo = self.hosts[0].vm_nodes[0].get_vm_mem_topo()
        self.logStep("预期结果：14、虚拟机内存前后内存分布一致")
        self.assertEqual(vm_mem_topo, vm_new_mem_topo)

    def teardown_method(self):
        super(TestTcSmapScVmRepeatExec001, self).postTestCase()
        if len(self.remote_numa_list) == 0:
            return
        self.cli[0].smap_enable_node(EnableNodeMsg(1, self.remote_numa_list[0]))

        vm_pid = self.hosts[0].vm_nodes[0].get_pid()
        if vm_pid == -1:
            return
        vm_numa = self.hosts[0].vm_nodes[0].get_unique_numa_node()
        self.cli[0].set_smap_remote_numa_info(vm_numa, self.remote_numa_list[0], 0)
        self.cli[0].smap_mig_out(MigrateOutMsg([MigrateOutPayload(self.remote_numa_list[0], vm_pid, 0)]), 1)
        self.hosts[0].watch_proc_mem(vm_pid, self.remote_numa_list[0], 0, 180, True)
        self.cli[0].smap_remove(RemoveMsg([vm_pid]), 1)