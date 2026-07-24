#!/usr/bin/python3
# -*- coding: utf-8 -*-

import random

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.common import get_random_char
from libs.modules.ubsmem.common.multi_task import MultiTask
from libs.modules.ubsmem.common.utils import pop_random_element
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    NORMAL_MALLOC_TIME,
    PROT_READ,
    PROT_WRITE,
    UBSM_FLAG_ONLY_IMPORT_NONCACHE,
    UBSM_FLAG_WR_DELAY_COMP,
    UBSM_SHMEM_OK,
    UbsMemPerfTp,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmLongTerm0005(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_LONG_TERM_0005
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        005验证创建单边NC模式不同大小共享内存16进程进行一写多�?
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
        P4.环境Biso开启Snoop
    TestStep:
        S1.查看节点是否�?6个app进程，没有就启动16�?
        S2.每个节点依次进行以下S3-S12步骤
        S3.进程0执行app ubsmem_create_region region_name 0 2 host0 0 host1 0 hostx 0指定当前节点导出共享内存
        S4.进程0�?28M�?G�?G执行app ubsm_shmem_allocate region_name shm_name 1024 0600 UBSM_FLAG_ONLY_IMPORT_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(12)创建共享内存
        S5.所有节点的所有进程并发执行app ubsm_shmem_map addr 1024 PROT_READ|PROT_WRITE(3) 0 shm_name 0 1映射进程0创建的共享内�?
        S6.所有节点依次循环执行S7-S10
        S7.执行dd if=/dev/urandom of=write_test.txt bs=1M count=size按内存大小生成随机文件并获取md5�?
        S8.当前节点进程0执行app append addr size write_test.ttxt往内存写入文件内容
        S9.其他进程同时执行app read addr size read_test.txt读取内存的内容到文件
        S10.获取文件的md5值并做对�?
        S11.所有进程都执行app ubsm_shmem_unmap addr 1024
        S12.节点0进程0执行app ubsm_shmem_deallocate shm_name
    ExpectedResult:
        E1.APP进程启动成功
        E2.开始循环执�?
        E3.共享域创建成�?
        E4.共享内存创建成功
        E5.共享内存映射成功
        E6.开始循环执�?
        E7.文件生成成功，md5获取成功
        E8.内存写入成功
        E9.内存读取成功
        E10.两次md5值一�?
        E11.内存解除成功
        E12.共享内存删除成功
    Author:
        wanghaojie 60117672
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")

        self.logStep("P2.MMI组件加载正常")

        self.logStep("P3.UBS-Memory服务加载正常")

        self.logStep("P4.环境Biso开启Snoop")
        super().setup_method()

    def test_tc_ubs_shm_long_term_0005(self):
        region_name = "TC_UBS_SHM_LONG_TERM_0005"
        shm_name = "TC_UBS_SHM_LONG_TERM_0005"

        app_count = 16
        self.logStep("S1.查看节点是否�?6个app进程，没有就启动16�?)
        for node in self.host_nodes:
            app_num = node.get_active_app_num()
            if app_num < app_count:
                node.start_apps(app_count)
        self.logStep("E1.APP进程启动成功")
        for node in self.host_nodes:
            app_num_new = node.get_active_app_num()
            self.assertGreaterEqual(app_num_new, app_count)

        self.logStep("S2.每个节点依次进行以下S3-S12步骤")
        for node in self.host_nodes:

            self.logStep("E2.开始循环执�?)
            self.logInfo(f"start test on{node.host_name}")
            self.logStep("S3.进程0执行app ubsmem_create_region region_name 0 2 host0 0 host1 0 hostx 0指定当前节点导出共享内存")
            sizes = [128 * 1024 * 1024, 1024 * 1024 * 1024]
            while sizes:
                size = pop_random_element(sizes)
                region_size = len(self.host_nodes)
                reg_attr = UbsmemRegionAttributes(region_size,[UbsmemRegionNodeDesc(n.host_name,True if n.host_name==node.host_name else False) for n in self.host_nodes])
                rc = node.apps[0].ubsmem_create_region(region_name, 0, reg_attr)
                self.logStep("E3.共享域创建成�?)
                self.assertEqual(rc, UBSM_SHMEM_OK)

                self.logStep("S4.进程0�?28M�?G�?G执行app ubsm_shmem_allocate region_name shm_name 1024 0600 UBSM_FLAG_ONLY_IMPORT_NONCACHE|UBSM_FLAG_WR_DELAY_COMP(12)创建共享内存")
                rc = node.apps[0].ubsmem_shmem_allocate(
                    region_name, shm_name, size, 0o600,
                    UBSM_FLAG_ONLY_IMPORT_NONCACHE | UBSM_FLAG_WR_DELAY_COMP,
                )
                self.logStep("E4.共享内存创建成功")
                self.assertEqual(rc, UBSM_SHMEM_OK)

                self.logStep("S5.所有节点的所有进程并发执行app ubsm_shmem_map addr 1024 PROT_READ|PROT_WRITE(3) 0 shm_name 0 1映射进程0创建的共享内�?)
                task = MultiTask([n.apps[i] for n in self.host_nodes for i in range(app_count)])
                map_list = task.ubsmem_shmem_map(0,size,PROT_READ | PROT_WRITE,1,shm_name,0,1)
                self.logStep("E5.共享内存映射成功")
                for i ,addr in enumerate(map_list):
                    self.assertEqual(addr.rc, UBSM_SHMEM_OK)

                src_chr = get_random_char()
                self.logStep("S6.所有节点依次循环执行S7-S10")
                self.logStep("E6.开始循环执�?)
                self.logStep("S7.执行dd if=/dev/urandom of=write_test.txt bs=1M count=size按内存大小生成随机文件并获取md5�?)
                self.logStep("E7.文件生成成功，md5获取成功")
                count = [n.host_name for n in self.host_nodes].index(node.host_name)
                src_addr = map_list[count * app_count].addr
                self.logStep("S8.当前节点进程0执行app append addr size write_test.ttxt往内存写入文件内容")
                result = node.apps[0].mem_write(src_addr,size,src_chr)
                self.logStep("E8.内存写入成功")
                self.assertEqual(result, UBSM_SHMEM_OK)
                self.logStep("S9.其他进程同时执行app read addr size read_test.txt读取内存的内容到文件")
                read_res_list = task.mem_check([(desc.addr,size,src_chr) for desc in map_list])
                self.logStep("E9.内存读取成功")
                self.assertEqual(read_res_list.count(UBSM_SHMEM_OK), app_count * len(self.host_nodes))
                self.logStep("S10.获取文件的md5值并做对�?)
                self.logStep("E10.两次md5值一�?)

                self.logStep("S11.所有进程都执行app ubsm_shmem_unmap addr 1024")
                unmap_res_list = task.ubsmem_shmem_unmap([(desc.addr,size)for desc in map_list])
                self.logStep("E11.内存解除成功")
                self.assertEqual(unmap_res_list.count(UBSM_SHMEM_OK), app_count * len(self.host_nodes))
                self.logStep("S12.节点0进程0执行app ubsm_shmem_deallocate shm_name")
                rc = node.apps[0].ubsmem_shmem_deallocate(shm_name)
                self.logStep("E12.共享内存删除成功")
                self.assertEqual(rc, UBSM_SHMEM_OK)

                res = node.apps[0].ubsmem_destroy_region(region_name)
                self.assertEqual(res, UBSM_SHMEM_OK)
    def teardown_method(self):
        super().teardown_method()
