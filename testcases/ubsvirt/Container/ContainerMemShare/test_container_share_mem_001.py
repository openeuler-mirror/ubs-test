#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMem001(KubernetesBaseCase):
    """验证容器共享内存映射成功.

    CaseNumber:
        test_container_share_mem_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证容器共享内存映射成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager、ubmsd功能正常无异常，完成容器内存共享需要的环境部署工作
        P3.在master节点配置CDR.yaml文件，拉起CDR服务
        P4.在master节点配置cr.yaml文件，cr文件确定好共享内存名称和共享内存限额大小，限额配置为5G，拉起服务
        P5.创建完成编写shm-csi-driver的yaml文件，拉起服务
        p6.配置完成应用pod的yaml文件，配置项中共享内存名与cr文件里共享内存名一致
        P7.使用udms的cli工具准备命令
        ./matrix_diagnose 123 &
        ./cli_server &
        ./cli_client
        attach 123
    TestStep:
        S1.创建pod
        S2.登录pod，进入/ko目录
        S3.创建1024MB共享内存，共享内存名字必须为 cr文件里的共享内存名字Name + "_" + 数字，推荐从1累增，查看CR文件的Status，是否记录当前已使用的共享内存的数据
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S4.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S5.查看映射目录
        S6.解除映射，地址为映射共享内存获取的mxmem_shmem_map addr
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S7.删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
        S8.查看映射目录，查看CR文件的Status，是否删除CR的status相应的name
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.返回ubsm_shmem_allocate ret(0)，代表映射成功，CR文件更新，已经记录当前已使用的共享内存的数据
        E4.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E5.可以在容器/dev/目录下观测到映射的文件
        E6.返回ubsm_shmem_unmap  ret(0)
        E7.返回ubsm_shmem_deallocate ret(0)
        E8.在容器/dev/目录下映射的文件消失。查看CR文件的Status，已经删除CR的status相应的name
    Author:
        handongkang 30046606
    """

    def init_shm_params(self):
        self.pod_name = "pod-for-shm"
        self.shm_size = 1073741824
        self.shm_name = "testshm_1"
        self.cr_name = self.shm_name.split("_")[0]
        self.filepath = "/tmp/memborrow"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_001"
        self.shm_base_path = base_path

    def setup_method(self):
        self.init_shm_params()

        self.logStep("P1.环境中存在2个及以上节点")
        node_num = self.get_node_number()
        self.assertGreaterEqual(node_num, 2, "节点数不大于等于2")

        self.logStep("P2.K8s/RackManager、ubmsd功能正常无异常，完成容器内存共享需要的环境部署工作")
        pod_list = self.get_pod_list_by_name("shm-csi-driver")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")

        self.logStep("P3.在master节点配置CDR.yaml文件，拉起CDR服务")
        self.logInfo("自动化部署直接拉起crd")

        self.logStep("P4.在master节点配置cr.yaml文件")
        self.create_dir("master", self.filepath)
        params = {
            "source_file": f"{self.shm_base_path}/shm-cr.yaml",
            "destination_file": f"{self.filepath}/shm-cr.yaml"
        }
        self.upload_file("master", params)
        create_result = self.create_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")
        self.assertTrue(create_result, "创建CR失败")

        self.logStep("P5.创建完成编写shm-csi-driver的yaml文件，拉起服务"
                     "p6.配置完成应用pod的yaml文件，配置项中共享内存名与cr文件里共享内存名一致")
        params = {
            "source_file": f"{self.shm_base_path}/pod-for-shm.yaml",
            "destination_file": f"{self.filepath}/pod-for-shm.yaml"
        }
        self.upload_file("master", params)

        self.logStep("P7.使用udms的cli工具准备命令"
                     "./matrix_diagnose 123 &"
                     "./cli_server &"
                     "./cli_client"
                     "attach 123")
        self.logInfo("测试用例自带测试二进制")

    def test_container_share_mem_001(self):
        self.logStep("S1.创建pod")
        self.delete_pod_and_wait(self.pod_name)
        create_result = self.create_pod_and_wait_running(f"{self.pod_name}.yaml", self.pod_name)

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result, "创建测试pod失败")

        self.logStep("S2.登录pod，进入/ko目录")
        cmd_result = self.check_shm_demo_file(self.pod_name)

        self.logStep("E2.可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件")
        self.assertNotEqual(cmd_result, [], "共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件")

        self.logStep("S3.创建1024MB共享内存，共享内存名字必须为 cr文件里的共享内存名字Name + \"_\" + 数字，推荐从1累增，查看CR文件的Status，是否记录当前已使用的共享内存的数据"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result = self.allocate_shm(self.pod_name, self.shm_name, self.shm_size)
        cr_result = self.get_cr_status(self.cr_name)

        self.logStep("E3.返回ubsm_shmem_allocate ret(0)，代表映射成功，CR文件更新，已经记录当前已使用的共享内存的数据")
        self.logInfo(f"allocate_shm cmd_result {cmd_result}")
        self.assertTrue(cmd_result, "映射失败")
        self.assertTrue(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

        self.logStep("S4.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        cmd_result = self.unmap_shm(self.pod_name, self.shm_size, "0", "1", self.shm_name)

        self.logStep("E4.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")
        self.assertTrue(self.get_key_from_result(cmd_result, "ptr"), "映射共享内存失败，未获取到映射地址")

        self.logStep("S5.查看映射目录")
        num = self.get_shm_dev_nums(cmd_result)

        self.logStep("E5.可以在容器/dev/目录下观测到映射的文件")
        self.logInfo(f"obmm dev num is {num}")
        self.assertEqual(num, self.shm_size / 1024 / 1024 / 128, "映射的文件数量不正确")

        self.logStep("S6.解除映射，地址为映射共享内存获取的mxmem_shmem_map addr"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        self.logInfo("二进制退出时，自动解除映射")

        self.logStep("E6.返回ubsm_shmem_unmap  ret(0)")
        self.assertTrue(self.get_key_from_result(cmd_result, "unmap done"), "解除映射失败")

        self.logStep("S7.删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        cmd_result = self.deallocate_shm(self.pod_name, self.shm_name)

        self.logStep("E7.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(cmd_result, "删除共享内存失败")

        self.logStep("S8.查看映射目录，查看CR文件的Status，是否删除CR的status相应的name")
        cr_result = self.get_cr_status(self.cr_name)

        self.logStep("E8.在容器/dev/目录下映射的文件消失。查看CR文件的Status，已经删除CR的status相应的name")
        self.assertFalse(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

    def teardown_method(self):
        self.deallocate_shm(self.pod_name, self.shm_name)
        time.sleep(5)
        self.delete_pod_and_wait(self.pod_name)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")
