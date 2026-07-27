#!/usr/bin/python3
# -*- coding: utf-8 -*-


import pytest

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.common.multi_task import MultiTask
from libs.modules.ubsmem.common.utils import pop_random_element
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    UBSM_FLAG_MALLOC_WITH_NUMA,
    UBSM_SHMEM_OK,
    UbsMemInstance,
)


@pytest.mark.smoke
class TestTcUbsShmLongTerm0003(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_LONG_TERM_0003
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        003验证不同节点16进程进行不同大小内存借用
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.UBS-Memory打开缓存服务
        P3.UBS-Memory服务加载正常
        P4.释放借用内存缓存
    TestStep:
        S1.查看节点是否有16个app进程，没有就启动16个
        S2.每个节点依次进行以下步骤
        S3.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行fd借用
        S4.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行numa借用
        S5.每个进程去并发释放借用的内存
        S6.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行fd借用
        S7.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行numa借用
        S8.执行dd if=/dev/urandom of=write_test.txt bs=1M count=size按内存大小生成随机文件并获取md5值
        S9.每个进程写入文件到借入的内存
        S10.每个进程去读取接入的内存，并对比读写内存一致性
        S11.每个进程去并发归还借用的内存
    ExpectedResult:
        E1.APP进程启动成功
        E2.开始执行
        E3.fd内存借用成功
        E4.numa内存借用成功
        E5.内存归还成功
        E6.fd内存借用成功
        E7.numa内存借用成功
        E8.md5值获取成功
        E9.内存写入成功
        E10.内存读取成功
        E11.内存归还成功
    Author:
        wanghaojie
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.UBS-Memory打开缓存服务")

        self.logStep("P3.UBS-Memory服务加载正常")
        #需要开启ubse配置的obmm.memory.offline.timeout=100
        self.logInfo("需要开启ubse配置的obmm.memory.offline.timeout=100")
        self.logStep("P4.释放借用内存缓存")
        super().setup_method()

    @pytest.mark.case_info(level='P3', type='Functional')
    def test_tc_ubs_shm_long_term_0003(self):

        app_count = 10
        self.logStep("S1.查看节点是否有16个app进程，没有就启动16个")
        for node in self.host_nodes:
            app_num = node.get_active_app_num()
            if app_num < app_count:
                node.start_apps(app_count)
        self.sleep(5)
        self.logStep("E1.APP进程启动成功")
        for node in self.host_nodes:
            app_num_new = node.get_active_app_num()
            self.assertGreaterEqual(app_num_new, app_count)

        self.logStep("S2.每个节点依次进行以下步骤")
        sizes = [128 * 1024 * 1024, 1024 * 1024 * 1024]
        for node in self.host_nodes:
            self.logStep("E2.开始执行")
            task = MultiTask(node.apps[:app_count])
            sizes1 = sizes.copy()
            while sizes1:
                self.logStep("S3.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行fd借用")

                size = pop_random_element(sizes1)
                fd_addr_desc_list1 = task.ubsmem_lease_malloc([(self.default_region, size,UbsMemInstance.DISTANCE_DIRECT_NODE,0) for _ in range(app_count)])
                self.logStep("E3.fd内存借用成功")
                succ_count = sum(1 for addr_desc in fd_addr_desc_list1 if addr_desc.rc == UBSM_SHMEM_OK)
                self.assertEqual(succ_count, app_count)

                self.logStep("S4.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行numa借用")
                numa_addr_desc_list1 = task.ubsmem_lease_malloc([(self.default_region,size,UbsMemInstance.DISTANCE_DIRECT_NODE,UBSM_FLAG_MALLOC_WITH_NUMA)for _ in range(app_count)])
                self.logStep("E4.numa内存借用成功")
                succ_count = sum(1 for addr_desc in numa_addr_desc_list1 if addr_desc.rc == UBSM_SHMEM_OK)
                self.assertEqual(succ_count, app_count)

                self.logStep("S5.每个进程去并发释放借用的内存")
                fd_results1 = task.ubsmem_lease_free([(addr_desc.addr,)for addr_desc in fd_addr_desc_list1])
                self.assertEqual(fd_results1.count(UBSM_SHMEM_OK),app_count)
                self.logStep("E5.内存归还成功")
                numa_results1 = task.ubsmem_lease_free([(addr_desc.addr,)for addr_desc in numa_addr_desc_list1])
                self.assertEqual(numa_results1.count(UBSM_SHMEM_OK),app_count)

            sizes2 = sizes.copy()
            while sizes2:
                self.logStep("S6.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行fd借用")
                size2 = pop_random_element(sizes2)
                fd_addr_desc_list2 = task.ubsmem_lease_malloc([(self.default_region,size2,UbsMemInstance.DISTANCE_DIRECT_NODE,0)for i in range(app_count)])
                self.logStep("E6.fd内存借用成功")
                succ_count = sum(1 for addr_desc in fd_addr_desc_list2 if addr_desc.rc == UBSM_SHMEM_OK)
                self.assertEqual(succ_count, app_count)

                self.logStep("S7.每个进程按照128M、1G、4G的粒度中的随机大小去并发进行numa借用")
                numa_addr_desc_list2 = task.ubsmem_lease_malloc([(self.default_region,size2,UbsMemInstance.DISTANCE_DIRECT_NODE,UBSM_FLAG_MALLOC_WITH_NUMA)for i in range(app_count)])
                self.logStep("E7.numa内存借用成功")
                succ_count = sum(1 for addr_desc in numa_addr_desc_list2 if addr_desc.rc == UBSM_SHMEM_OK)
                self.assertEqual(succ_count, app_count)
                self.logStep("S8.执行dd if=/dev/urandom of=write_test.txt bs=1M count=size按内存大小生成随机文件并获取md5值")

                self.logStep("E8.md5值获取成功")
                src_chr = get_random_char()
                self.logStep("S9.每个进程写入文件到借入的内存")
                append_res_list = task.mem_write([(desc.addr,size2,src_chr)for desc in fd_addr_desc_list2])
                self.assertEqual(append_res_list.count(UBSM_SHMEM_OK),app_count)
                self.logStep("E9.内存写入成功")
                append_res_list = task.mem_write([(desc.addr,size2,src_chr)for desc in numa_addr_desc_list2])
                self.assertEqual(append_res_list.count(UBSM_SHMEM_OK), app_count)

                self.logStep("S10.每个进程去读取接入的内存，并对比读写内存一致性")
                read_res_list = task.mem_check([(desc.addr,size2,src_chr)for desc in fd_addr_desc_list2])
                self.assertEqual(read_res_list.count(UBSM_SHMEM_OK), app_count)
                self.logStep("E10.内存读取成功")
                read_res_list = task.mem_check([(desc.addr, size2, src_chr) for desc in numa_addr_desc_list2])
                self.assertEqual(read_res_list.count(UBSM_SHMEM_OK), app_count)
                self.logStep("S11.每个进程去并发归还借用的内存")
                fd_results2 = task.ubsmem_lease_free([(addr_desc.addr,)for addr_desc in fd_addr_desc_list2])
                self.assertEqual(fd_results2.count(UBSM_SHMEM_OK),app_count)
                self.logStep("E11.内存归还成功")
                numa_results2 = task.ubsmem_lease_free([(addr_desc.addr,)for addr_desc in numa_addr_desc_list2])
                self.assertEqual(numa_results2.count(UBSM_SHMEM_OK), app_count)
            for n in self.host_nodes:
                obmm_device_count = n.get_obmm_device_count()
                self.assertEqual(obmm_device_count, 0)
    def teardown_method(self):
        super().teardown_method()
