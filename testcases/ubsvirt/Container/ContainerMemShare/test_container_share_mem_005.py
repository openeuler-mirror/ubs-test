#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMem005(KubernetesBaseCase):
    """验证不同pod创建多个共享内存后资源超出限制创建失败.

    CaseNumber:
        test_container_share_mem_005
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不同pod创建多个共享内存后资源超出限制创建失败
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager、ubmsd功能正常无异常，完成容器内存共享需要的环境部署工作
        P3.在master节点配置CDR.yaml文件，拉起CDR服务
        P4.在master节点配置cr.yaml文件，cr文件确定好共享内存名称和共享内存限额大小，限额配置为2G，拉起服务
        P5.创建完成编写shm-csi-driver的yaml文件，拉起服务
        p6.配置完成应用pod的yaml文件，配置项中共享内存名与cr文件里共享内存名一致
        P7.使用udms的cli工具准备命令
        ./matrix_diagnose 123 &
        ./cli_server &
        ./cli_client
        attach 123
    TestStep:
        S1.创建2个pod，pod0和pod1
        S2.分别登录两个pod，进入/ko目录
        S3.执行使用udms的cli工具准备命令
        S4.在pod0、pod1分别创建1024MB共享内存
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S5.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S6.再次创建一个pod2，登录后创建1024MB共享内存
        S7.两个pod内解除映射
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S8.两个pod内删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
        S9.在pod0、pod1分别查共享目录映射结果
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.pod0、pod1分别可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.成功进入接口输入页面
        E4.分别返回ubsm_shmem_allocate ret(0)，代表映射成功
        E5.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E6.创建失败，报错资源不足，超过CR文件配置限制额度
        E7.均返回ubsm_shmem_deallocate ret(0)
        E8.均返回ubsm_shmem_deallocate ret(0)
        E9.在容器/dev/目录下没有映射的文件
    Author:
        luoyikang 00668584
    """

    def init_shm_params(self):
        self.pod_name1 = "pod-for-shm1"
        self.pod_name2 = "pod-for-shm2"
        self.pod_name3 = "pod-for-shm3"
        self.shm_size = 1073741824
        self.shm_name1 = "testshm_1"
        self.shm_name2 = "testshm_2"
        self.shm_name3 = "testshm_3"
        self.cr_name = self.shm_name1.split("_")[0]
        self.filepath = "/tmp/memborrow"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_005"
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
            "source_file": f"{self.shm_base_path}/pod-for-shm1.yaml",
            "destination_file": f"{self.filepath}/pod-for-shm1.yaml"
        }
        self.upload_file("master", params)
        params = {
            "source_file": f"{self.shm_base_path}/pod-for-shm2.yaml",
            "destination_file": f"{self.filepath}/pod-for-shm2.yaml"
        }
        self.upload_file("master", params)
        params = {
            "source_file": f"{self.shm_base_path}/pod-for-shm3.yaml",
            "destination_file": f"{self.filepath}/pod-for-shm3.yaml"
        }
        self.upload_file("master", params)

        self.logStep("P7.使用udms的cli工具准备命令"
                     "./matrix_diagnose 123 &"
                     "./cli_server &"
                     "./cli_client"
                     "attach 123")
        self.logInfo("测试用例自带测试二进制")

    def test_container_share_mem_005(self):
        self.logStep("S1.创建2个pod，pod0和pod1")
        self.delete_pod_by_name(self.pod_name1)
        create_result1 = self.create_pod_by_name(f"{self.pod_name1}.yaml")
        self.delete_pod_by_name(self.pod_name2)
        create_result2 = self.create_pod_by_name(f"{self.pod_name2}.yaml")

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result1, "创建测试pod失败")
        self.assertTrue(create_result2, "创建测试pod失败")

        self.logStep("S2.分别登录两个pod，进入/ko目录")
        cmd_result = self.check_shm_demo_file(self.pod_name1)

        self.logStep("E2.pod0、pod1分别可以成功登录，共享内存使用cli的路径在ko下，存在shm_demo文件")
        self.assertNotEqual(cmd_result, [], "共享内存使用cli的路径在ko下，不存在shm_demo文件")

        self.logStep("S3.执行使用udms的cli工具准备命令")
        self.logInfo("测试用例自带测试二进制")

        self.logStep("E3.成功进入接口输入页面")

        self.logStep("S4.在pod0、pod1分别创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result1 = self.allocate_shm(self.pod_name1, self.shm_name1, self.shm_size)
        self.logInfo(f"allocate_shm cmd_result {cmd_result1}")
        self.assertTrue(cmd_result1, "映射失败")
        cmd_result2 = self.allocate_shm(self.pod_name2, self.shm_name2, self.shm_size)
        self.logInfo(f"allocate_shm cmd_result {cmd_result2}")
        self.assertTrue(cmd_result2, "映射失败")

        self.logStep("E4.分别返回ubsm_shmem_allocate ret(0)，代表映射成功")

        self.logStep("S5.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        cmd_result3 = self.unmap_shm(self.pod_name1, self.shm_size, "0", "1", self.shm_name1)
        cmd_result4 = self.unmap_shm(self.pod_name2, self.shm_size, "0", "1", self.shm_name2)

        self.logStep("E5.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")
        self.assertTrue(self.get_key_from_result(cmd_result3, "ptr"), "映射共享内存失败，未获取到映射地址")
        self.assertTrue(self.get_key_from_result(cmd_result4, "ptr"), "映射共享内存失败，未获取到映射地址")

        self.logStep("S6.再次创建一个pod2，登录后创建1024MB共享内存")
        cmd_result5 = self.allocate_shm(self.pod_name3, self.shm_name3, self.shm_size)
        self.logInfo(f"allocate_shm cmd_result {cmd_result5}")
        self.assertFalse(cmd_result5, "预期报错资源不足")

        self.logStep("E6.创建失败，报错资源不足，超过CR文件配置限制额度")

        self.logStep("S7.两个pod内解除映射"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        self.logInfo("二进制退出时，自动解除映射")

        self.logStep("E7.均返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(self.get_key_from_result(cmd_result3, "unmap done"), "解除映射失败")
        self.assertTrue(self.get_key_from_result(cmd_result4, "unmap done"), "解除映射失败")

        self.logStep("S8.两个pod内删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        cmd_result6 = self.deallocate_shm(self.pod_name1, self.shm_name1)
        cmd_result7 = self.deallocate_shm(self.pod_name2, self.shm_name2)

        self.logStep("E8.均返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(cmd_result6, "删除共享内存失败")
        self.assertTrue(cmd_result7, "删除共享内存失败")

        self.logStep("S9.在pod0、pod1分别查共享目录映射结果")
        cr_result = self.get_cr_status(self.cr_name)
        self.assertFalse(self.get_key_from_result(cr_result, self.shm_name1), "CR文件未更新")
        self.assertFalse(self.get_key_from_result(cr_result, self.shm_name2), "CR文件未更新")

        self.logStep("E9.在容器/dev/目录下没有映射的文件")

    def teardown_method(self):
        self.deallocate_shm(self.pod_name1, self.shm_name1)
        self.deallocate_shm(self.pod_name2, self.shm_name2)
        time.sleep(5)
        self.delete_pod_by_name(self.pod_name1)
        self.delete_pod_by_name(self.pod_name2)
        self.delete_pod_by_name(self.pod_name3)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")