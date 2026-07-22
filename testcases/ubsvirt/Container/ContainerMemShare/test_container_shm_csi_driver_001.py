#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShmCsiDriver001(KubernetesBaseCase):
    """验证shm-csi-driver异常退出自动恢复建链后可以创建共享内存.

    CaseNumber:
        test_container_shm_csi_driver_001
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证shm-csi-driver异常退出自动恢复建链后可以创建共享内存
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
        S3.执行使用udms的cli工具准备命令
        S4.构造matrix-csi-driver进程退出故障，然后创建1024MB共享内存
        S5.等待一分钟查看matrix-csi-driver进程状态
        S6.再次创建1024MB共享内存
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S7.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S8.解除映射
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S9.删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.成功进入接口输入页面
        E4.构造成功，matrix-csi-driver进程挂掉，创建共享内存失败
        E5.matrix-csi-driver进程状态可以恢复正常
        E6.返回ubsm_shmem_allocate ret(0)，代表映射成功
        E7.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E8.返回ubsm_shmem_unmap  ret(0)
        E9.返回ubsm_shmem_deallocate ret(0)
    Author:
        luoyikang 00668584
    """

    def init_shm_params(self):
        self.pod_name1 = "pod-for-shm1"
        self.shm_size = 1073741824
        self.shm_name1 = "testshm_1"
        self.cr_name = self.shm_name1.split("_")[0]
        self.filepath = "/tmp/memborrow"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_shm_csi_driver_001"
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
        self.logInfo("自动化部署CRD已经在了")

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

        self.logStep("P7.使用udms的cli工具准备命令"
                     "./matrix_diagnose 123 &"
                     "./cli_server &"
                     "./cli_client"
                     "attach 123")
        self.logInfo("测试用例自带测试二进制")

    def test_container_shm_csi_driver_001(self):
        self.logStep("S1.创建pod")
        self.delete_pod_and_wait(self.pod_name1)
        create_result1 = self.create_pod_and_wait_running(f"{self.pod_name1}.yaml", self.pod_name1)
        self.assertTrue(create_result1, "创建测试pod失败")

        self.logStep("E1.pod创建成功，没有报错")

        self.logStep("S2.登录pod，进入/ko目录")
        cmd_result = self.check_shm_demo_file(self.pod_name1)
        self.assertNotEqual(cmd_result, [], "共享内存使用cli的路径在ko下，不存在shm_demo文件")

        self.logStep("E2.可以成功登录，共享内存使用cli的路径在ko下，存在shm_demo文件")

        self.logStep("S3.执行使用udms的cli工具准备命令")
        self.logInfo("测试用例自带测试二进制")

        self.logStep("E3.成功进入接口输入页面")

        self.logStep("S4.构造matrix-csi-driver进程退出故障，然后创建1024MB共享内存")
        self.stop_shm_pod()
        cmd_result1 = self.allocate_shm(self.pod_name1, self.shm_name1, self.shm_size)
        self.logInfo(f"allocate_shm cmd_result {cmd_result1}")
        self.assertFalse(cmd_result1, "预期映射失败")
        self.restart_shm_pod()

        self.logStep("E4.构造成功，matrix-csi-driver进程挂掉，创建共享内存失败")

        self.logStep("S5.等待一分钟查看matrix-csi-driver进程状态")
        pod_list = self.get_pod_list_by_name("shm-csi-driver")
        self.assertGreaterEqual(len(pod_list), 2, "进程恢复正常")

        self.logStep("E5.matrix-csi-driver进程状态可以恢复正常")

        self.logStep("S6.再次创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result2 = self.allocate_shm(self.pod_name1, self.shm_name1, self.shm_size)
        self.logInfo(f"allocate_shm cmd_result {cmd_result2}")
        self.assertTrue(cmd_result2, "预期映射成功")

        self.logStep("E6.返回ubsm_shmem_allocate ret(0)，代表映射成功")

        self.logStep("S7.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        cmd_result3 = self.unmap_shm(self.pod_name1, self.shm_size, "0", "1", self.shm_name1)

        self.logStep("E7.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")

        self.logStep("S8.解除映射"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        self.assertTrue(self.get_key_from_result(cmd_result3, "unmap done"), "解除映射失败")

        self.logStep("E8.返回ubsm_shmem_unmap  ret(0)")

        self.logStep("S9.删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        cmd_result6 = self.deallocate_shm(self.pod_name1, self.shm_name1)
        self.assertTrue(cmd_result6, "删除共享内存失败")

        self.logStep("E9.返回ubsm_shmem_deallocate ret(0)")

    def teardown_method(self):
        self.restart_shm_pod()
        self.deallocate_shm(self.pod_name1, self.shm_name1)
        time.sleep(5)
        self.delete_pod_and_wait(self.pod_name1)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")