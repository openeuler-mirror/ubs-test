#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMemRecycle003(KubernetesBaseCase):
    """验证pod内进程退出后共享内存不会回收.

    CaseNumber:
        test_container_share_mem_recycle_003
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证pod内进程退出后共享内存不会回收
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
        S1.创建pod
        S2.登录pod，进入/ko目录
        S3.执行使用udms的cli工具准备命令
        S4.创建1024MB共享内存
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S5.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S6.写共享内存
        app append 0xffff10000000 134217728 /home/matrixplugin/file.input
        S7.读共享内存
        app read 0xffff10000000  134217728 /home/matrixplugin/file.output
        S8.退出cli工具，不退出pod，再次映射共享目录
        S9.解除映射
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S10.删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.成功进入接口输入页面
        E4.返回ubsm_shmem_allocate ret(0)，代表映射成功
        E5.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E6.返回write  ret(0) 写成功
        E7.返回read ret(0) 读成功
        E8.退出工具成功，成功再次映射内存成功
        E9.返回ubsm_shmem_unmap ret(0)
        E10.返回ubsm_shmem_deallocate ret(0)
    Author:
        handongkang 30046606
    """

    def init_shm_params(self):
        self.pod_name = "pod-for-shm"
        self.shm_size = 1073741824
        self.shm_name = "testshm_1"
        self.cr_name = self.shm_name.split("_")[0]
        self.filepath = "/tmp/memborrow"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_recycle_003"
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

    def test_container_share_mem_recycle_003(self):
        self.logStep("S1.创建pod")
        self.delete_pod_by_name(self.pod_name)
        create_result = self.create_pod_by_name(f"{self.pod_name}.yaml")

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result, "创建测试pod失败")

        self.logStep("S2.登录pod，进入/ko目录")
        cmd_result = self.check_shm_demo_file(self.pod_name)

        self.logStep("E2.可以成功登录，共享内存使用cli的路径在ko下，存在shm_demo文件")
        self.assertNotEqual(cmd_result, [], "共享内存使用cli的路径在ko下，不存在shm_demo文件")

        self.logStep("S3.执行使用udms的cli工具准备命令")
        self.logInfo("测试用例自带测试二进制")

        self.logStep("E3.成功进入接口输入页面")

        self.logStep("S4.创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result = self.allocate_shm(self.pod_name, self.shm_name, self.shm_size)
        cr_result = self.get_cr_status(self.cr_name)

        self.logStep("E4.返回ubsm_shmem_allocate ret(0)，代表映射成功")
        self.logInfo(f"allocate_shm cmd_result {cmd_result}")
        self.assertTrue(cmd_result, "映射失败")
        self.assertTrue(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

        self.logStep("S5.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        self.logInfo("测试工具读写时自动实现映射")

        self.logStep("E5.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")

        self.logStep("S6.写共享内存"
                     "app append 0xffff10000000 134217728 /home/matrixplugin/file.input")
        write_result = self.write_shm(self.pod_name, self.shm_size, 0, 1, self.shm_name, 128 * 1024, "/tmp/in.txt")

        self.logStep("E6.返回write  ret(0) 写成功")
        self.assertTrue(self.get_key_from_result(write_result, "append Success"), "写文件失败")

        self.logStep("S7.读共享内存"
                     "app read 0xffff10000000  134217728 /home/matrixplugin/file.output")
        read_result = self.read_shm(self.pod_name, self.shm_size, 0, 1, self.shm_name, 128 * 1024, "/tmp/out.txt")
        input_file_md5 = self.get_file_md5(self.pod_name, "/tmp/in.txt")
        output_file_md5 = self.get_file_md5(self.pod_name, "/tmp/out.txt")

        self.logStep("E7.返回read ret(0) 读成功")
        self.assertEqual(input_file_md5, output_file_md5, "读文件失败")

        self.logStep("S8.退出cli工具，不退出pod，再次映射共享目录")
        self.logInfo("测试工具读写时自动实现退出断链")

        self.logStep("E8.退出工具成功，成功再次映射内存成功")

        self.logStep("S9.解除映射"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        self.logInfo("测试工具读写时自动实现解除映射")

        self.logStep("E9.返回ubsm_shmem_unmap ret(0)")
        self.assertTrue(self.get_key_from_result(read_result, "unmap done"), "解除映射失败")

        self.logStep("S10.删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        result = self.deallocate_shm(self.pod_name, self.shm_name)

        self.logStep("E10.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(result, "解除映射失败")

    def teardown_method(self):
        self.deallocate_shm(self.pod_name, self.shm_name)
        time.sleep(5)
        self.delete_pod_by_name(self.pod_name)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")