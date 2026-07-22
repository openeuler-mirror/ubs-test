#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMemRecycle002(KubernetesBaseCase):
    """验证不同pod使用一块容器共享内存时归还成功.

    CaseNumber:
        test_container_share_mem_recycle_002
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不同pod使用一块容器共享内存时归还成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager、ubmsd功能正常无异常，完成容器内存共享需要的环境部署工作
        P3.在master节点配置CDR.yaml文件，拉起CDR服务
        P4.在master节点配置cr.yaml文件，cr文件确定好共享内存名称和共享内存限额大小，限额配置为3G，拉起服务
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
        S6.在pod0、pod1分别查共享目录映射结果
        S7.在pod0解除映射
        S8.在pod0删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
        S9.在pod1解除映射
        S10.在pod1删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
        S11.在pod0、pod1分别查共享目录映射结果
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.pod0、pod1分别可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.成功进入接口输入页面
        E4.分别返回ubsm_shmem_allocate ret(0)，代表映射成功
        E5.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E6.都可以在容器/dev/目录下观测到映射的文件，一块文件
        E7.返回ubsm_shmem_deallocate ret(0)
        E8.返回ubsm_shmem_deallocate ret(0)
        E9.返回ubsm_shmem_deallocate ret(0)
        E10.返回ubsm_shmem_deallocate ret(0)
        E11.在容器/dev/目录下没有映射的文件
    Author:
        handongkang 30046606
    """

    def init_shm_params(self):
        self.pod0_name = "pod-for-shm"
        self.pod1_name = "pod-for-shm1"
        self.shm_size = 1073741824
        self.shm_name = "testshm_1"
        self.cr_name = self.shm_name.split("_")[0]
        self.filepath = "/tmp/memborrow"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_recycle_002"
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
        params0 = {
            "source_file": f"{self.shm_base_path}/{self.pod0_name}.yaml",
            "destination_file": f"{self.filepath}/{self.pod0_name}.yaml"
        }
        params1 = {
            "source_file": f"{self.shm_base_path}/{self.pod1_name}.yaml",
            "destination_file": f"{self.filepath}/{self.pod1_name}.yaml"
        }
        self.upload_file("master", params0)
        self.upload_file("master", params1)

        self.logStep("P7.使用udms的cli工具准备命令"
                     "./matrix_diagnose 123 &"
                     "./cli_server &"
                     "./cli_client"
                     "attach 123")
        self.logInfo("测试用例自带测试二进制")

    def test_container_share_mem_recycle_002(self):
        self.logStep("S1.创建2个pod，pod0和pod1")
        self.delete_pod_by_name(self.pod0_name)
        self.delete_pod_by_name(self.pod1_name)
        create_result0 = self.create_pod_by_name(f"{self.pod0_name}.yaml")
        create_result1 = self.create_pod_by_name(f"{self.pod1_name}.yaml")

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result0, "创建测试pod0失败")
        self.assertTrue(create_result1, "创建测试pod1失败")

        self.logStep("S2.分别登录两个pod，进入/ko目录")
        cmd_result0 = self.check_shm_demo_file(self.pod0_name)
        cmd_result1 = self.check_shm_demo_file(self.pod1_name)

        self.logStep("E2.pod0、pod1分别可以成功登录，共享内存使用cli的路径在ko下，存在shm_demo文件")
        self.assertNotEqual(cmd_result0, [], "共享内存使用cli的路径在ko下，pod0不存在shm_demo文件")
        self.assertNotEqual(cmd_result1, [], "共享内存使用cli的路径在ko下，pod1不存在shm_demo文件")

        self.logStep("S3.执行使用udms的cli工具准备命令")
        self.logInfo("自动化工具直接进入cli")

        self.logStep("E3.成功进入接口输入页面")

        self.logStep("S4.在pod0、pod1分别创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result = self.allocate_shm(self.pod0_name, self.shm_name, self.shm_size)
        cr_result = self.get_cr_status(self.cr_name)

        self.logStep("E4.分别返回ubsm_shmem_allocate ret(0)，代表映射成功")
        self.logInfo(f"allocate_shm cmd_result {cmd_result}")
        self.assertTrue(cmd_result, "映射失败")
        self.assertTrue(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

        self.logStep("S5.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        cmd_result0 = self.unmap_shm(self.pod0_name, self.shm_size, "0", "1", self.shm_name)
        cmd_result1 = self.unmap_shm(self.pod1_name, self.shm_size, "0", "1", self.shm_name)

        self.logStep("E5.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")
        self.assertTrue(self.get_key_from_result(cmd_result0, "ptr"), "pod0映射共享内存失败，未获取到映射地址")

        self.logStep("S6.在pod0、pod1分别查共享目录映射结果")
        num0 = self.get_shm_dev_nums(cmd_result0)
        num1 = self.get_shm_dev_nums(cmd_result1)

        self.logStep("E6.都可以在容器/dev/目录下观测到映射的文件，一块文件")
        self.logInfo(f"obmm dev num0 is {num0}")
        self.assertEqual(num0, self.shm_size / 1024 / 1024 / 128, "pod0映射的文件数量不正确")
        self.logInfo(f"obmm dev num1 is {num1}")
        self.assertEqual(num1, self.shm_size / 1024 / 1024 / 128, "pod1映射的文件数量不正确")

        self.logStep("S7.在pod0解除映射")
        self.logInfo("二进制退出时，自动解除映射")

        self.logStep("E7.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(self.get_key_from_result(cmd_result0, "unmap done"), "pod0解除映射失败")

        self.logStep("S8.在pod0删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        cmd_result0 = self.deallocate_shm(self.pod0_name, self.shm_name)

        self.logStep("E8.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(cmd_result0, "删除pod0共享内存失败")

        self.logStep("S9.在pod1解除映射")
        self.logInfo("二进制退出时，自动解除映射")

        self.logStep("E9.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(self.get_key_from_result(cmd_result1, "unmap done"), "pod1解除映射失败")

        self.logStep("S10.在pod1删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        cmd_result1 = self.deallocate_shm(self.pod1_name, self.shm_name)

        self.logStep("E10.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(cmd_result1, "删除pod1共享内存失败")

        self.logStep("S11.在pod0、pod1分别查共享目录映射结果")
        dev_num0 = self.get_tmp_dev_num(self.pod0_name, self.cr_name)
        dev_num1 = self.get_tmp_dev_num(self.pod1_name, self.cr_name)

        self.logStep("E11.在容器/dev/目录下没有映射的文件")
        self.assertEqual(self.get_shm_dev_nums(dev_num0), 0, "pod0映射的文件数量不正确")
        self.assertEqual(self.get_shm_dev_nums(dev_num1), 0, "pod1映射的文件数量不正确")

    def teardown_method(self):
        self.deallocate_shm(self.pod1_name, self.shm_name)
        time.sleep(5)
        self.delete_pod_by_name(self.pod0_name)
        self.delete_pod_by_name(self.pod1_name)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")