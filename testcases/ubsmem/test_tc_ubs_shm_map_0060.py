#!/usr/bin/python3
# -*- coding: utf-8 -*-

from libs.core.basecase.ubsmem import UbsMemCase
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import (
    MAP_SHARED,
    PROT_READ,
    PROT_WRITE,
    UBSM_FLAG_MMAP_HUGETLB_PMD,
    UBSM_FLAG_ONLY_IMPORT_NONCACHE,
    UBSM_FLAG_WR_DELAY_COMP,
    UBSM_SHMEM_OK,
    UbsmemRegionAttributes,
    UbsmemRegionNodeDesc,
)

import pytest


@pytest.mark.smoke
class TestTcUbsShmMap0060(UbsMemCase):
    """
    CaseNumber:
        TC_UBS_SHM_MAP_0060
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        060每节点按1G粒度创建512G共享内存后互相映射
    PreCondition:
        P1.UBS-Engine进程正常拉起
        P2.MMI组件加载正常
        P3.UBS-Memory服务加载正常
    TestStep:
        S1.每个节点调用接口ubsmem_create_region name0 0 2 host0 1 host1 0，以当前节点为导出节点
        S2.每个节点调用接口ubsmem_shmem_allocate_batch  region_name shm_name 1024*1024*1024 0600 shm_count=512 ...
        S3.每个节点调用接口ubsmem_shmem_map_batch 0 1024*1024*1024 PROT_READ|PROT_WRITE(3) MAP_SHARED(1) shm_name 0 512 ...
        S4.每个节点都调用接口ubsmem_shmem_unmap_batch shm_name 1024*1024*1024 512将映射的共享内存解除映射
        S5.每个节点都调用接口ubsmem_shmem_deallocate_batch shm_name 512删除共享内存映射
    ExpectedResult:
        E1.共享域创建成功
        E2.共享内存创建成功
        E3.共享内存映射成功
        E4.共享内存解除映射成功
        E5.共享内存删除成功
    Author:
        wanghaojie
    """

    def setup_method(self):
        self.logStep("P1.UBS-Engine进程正常拉起")
        self.logStep("P2.MMI组件加载正常")
        self.logStep("P3.UBS-Memory服务加载正常")
        super().setup_method()

    @pytest.mark.case_info(level='P3', type='Functional')
    def test_tc_ubs_shm_map_0060(self):
        region_name = "TC_UBS_SHM_MAP_0060"
        shm_name_prefix = "TC_UBS_SHM_MAP_0060"
        shm_count = 512
        size = 1024 * 1024 * 1024
        flag = UBSM_FLAG_ONLY_IMPORT_NONCACHE | UBSM_FLAG_WR_DELAY_COMP | UBSM_FLAG_MMAP_HUGETLB_PMD
        host_nodes_shm_list = []

        self.logStep(
            "S1.每个节点调用接口ubsmem_create_region name0 0 2 host0 1 host1 0，以当前节点为导出节点")
        for node in self.host_nodes:
            reg_attr = UbsmemRegionAttributes(
                self.node_count,
                [
                    UbsmemRegionNodeDesc(n_node.host_name, True if node == n_node else False)
                    for n_node in self.host_nodes
                ],)
            res = node.apps[0].ubsmem_create_region(region_name, 0, reg_attr)
            self.logStep("E1.共享域创建成功")
            self.assertEqual(res, UBSM_SHMEM_OK, "共享域创建失败")
            host_nodes_shm_list.append((node, f"{shm_name_prefix}_{node.node_id}"))

        self.logStep(
            "S2.每个节点调用接口ubsmem_shmem_allocate_batch  region_name shm_name 1024 0600 ...")
        for node, shm_name in host_nodes_shm_list:
            res = node.apps[0].ubsmem_shmem_allocate_batch(
                region_name, shm_name, size, 0o600, flag, shm_count)
            self.logStep("E2.共享内存创建成功")
            self.assertEqual(res, UBSM_SHMEM_OK, "共享内存批量创建失败")

        self.logStep(
            "S3.每个节点调用接口ubsmem_shmem_map_batch 0 1024 PROT_READ|PROT_WRITE(3) 0 shm_name 0 512 ...")
        for _, shm_name in host_nodes_shm_list:
            for node in self.host_nodes:
                rc = node.apps[0].ubsmem_shmem_map_batch(
                    0, size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_name, 0, shm_count)
                self.logStep("E3.共享内存映射成功")
                self.assertEqual(rc, UBSM_SHMEM_OK, "共享内存批量映射失败")

        self.logStep(
            "S4.每个节点都调用接口ubsmem_shmem_unmap_batch addr 1024 512将映射的共享内存解除映射")
        for _, shm_name in host_nodes_shm_list:
            for node in self.host_nodes:
                rc = node.apps[0].ubsmem_shmem_unmap_batch(shm_name, size, shm_count)
                self.logStep("E4.共享内存解除映射成功")
                self.assertEqual(rc, UBSM_SHMEM_OK, "共享内存批量解除映射失败")

        self.logStep(
            "S5.每个节点都调用接口ubsmem_shmem_deallocate_batch shm_name 512删除共享内存映射")
        for node, shm_name in host_nodes_shm_list:
            res = node.apps[0].ubsmem_shmem_deallocate_batch(shm_name, shm_count)
            self.logStep("E5.共享内存删除成功")
            self.assertEqual(res, UBSM_SHMEM_OK, "共享内存批量删除失败")

        for node in self.host_nodes:
            res = node.apps[0].ubsmem_destroy_region(region_name)
            self.assertEqual(res, UBSM_SHMEM_OK, "共享域删除失败")

    def teardown_method(self):
        super().teardown_method()
