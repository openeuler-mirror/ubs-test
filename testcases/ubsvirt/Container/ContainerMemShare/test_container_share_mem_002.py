#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMem002(KubernetesBaseCase):
    """验证容器共享内存映射后可以正常读写.

    CaseNumber:
        test_container_share_mem_002
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证容器共享内存映射后可以正常读写
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
        S3.创建1024MB共享内存，共享内存名字必须为 cr文件里的共享内存名字Name + "_" + 数字，推荐从1累增
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S4.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S5.写共享内存，file.input为绝对路径，不能在仿真器/ko目录下，地址为映射共享内存获取的mxmem_shmem_map addr，为随机值
        app append 0xffff10000000 134217728 /home/matrixplugin/file.input
        S6.读共享内存，file.input为绝对路径
        app read 0xffff10000000  134217728 /home/matrixplugin/file.output
        S7.解除映射，地址为映射共享内存获取的mxmem_shmem_map addr
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S8.删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.返回ubsm_shmem_allocate ret(0)，代表映射成功
        E4.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E5.返回write  ret(0) 写成功
        E6.返回read ret(0) 读成功
        E7.返回ubsm_shmem_unmap ret(0)
        E8.返回ubsm_shmem_deallocate ret(0)
    Author:
        handongkang 30046606
    """

    def init_shm_params(self):
        self.pod_name = "pod-for-shm"
        self.shm_size = 1073741824
        self.file_size = 134217728
        self.shm_name = "testshm_1"
        self.cr_name = self.shm_name.split("_")[0]
        self.filepath = "/tmp/memborrow"
        self.input_shm_file = "/tmp/file.input"
        self.output_shm_file = "/tmp/file.output"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_002"
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

    def test_container_share_mem_002(self):
        self.logStep("S1.创建pod")
        self.delete_pod_and_wait(self.pod_name)
        create_result = self.create_pod_and_wait_running(f"{self.pod_name}.yaml", self.pod_name)

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result, "创建测试pod失败")

        self.logStep("S2.登录pod，进入/ko目录")
        cmd_result = self.check_shm_tool_file(self.pod_name)
        self.assertNotEqual(cmd_result, [], "共享内存使用cli的路径在ko下，不存在shm_tool文件")
        start_result = self.start_shm_tool_server(self.pod_name)

        self.logStep("E2.可以成功登录，共享内存使用cli的路径在ko下，存在shm_tool文件")
        self.assertTrue(start_result, "启动shm_tool server失败")

        self.logStep("S3.创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result = self.allocate_shm_with_tool(self.pod_name, self.shm_name, self.shm_size)
        cr_result = self.get_cr_status(self.cr_name)

        self.logStep("E3.返回ubsm_shmem_allocate ret(0)，代表映射成功")
        self.logInfo(f"allocate_shm cmd_result {cmd_result}")
        self.assertTrue(cmd_result, "创建失败")
        self.assertTrue(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

        self.logStep("S4.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        shm_addr = self.map_shm_with_tool(self.pod_name, self.shm_size, "0", "1", self.shm_name)
        dev_num = self.get_shm_dev_num_with_tool(self.pod_name)

        self.logStep("E4.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")
        self.assertNotEqual(shm_addr, "", "映射共享内存失败，未获取到地址")
        self.assertEqual(dev_num, self.shm_size / 1024 / 1024 / 128, "设备数不正确")

        self.logStep("S5.写共享内存"
                     "app append 0xffff10000000 134217728 /home/matrixplugin/file.input")
        gen_result = self.gen_file_for_shm(self.pod_name, self.input_shm_file, f"{self.file_size//1024//1024}M")
        self.assertNotEqual(gen_result, [], "生成测试文件失败")
        set_result = self.set_shm_ownership_with_tool(self.pod_name, self.shm_name, shm_addr, self.shm_size)
        self.assertTrue(set_result, "设置shm权限失败")
        write_result = self.write_shm_with_tool(self.pod_name, shm_addr, self.file_size, self.input_shm_file)

        self.logStep("E5.返回write  ret(0) 写成功")
        self.assertTrue(write_result, "写文件失败")

        self.logStep("S6.读共享内存"
                     "app read 0xffff10000000  134217728 /home/matrixplugin/file.output")
        read_result = self.read_shm_with_tool(self.pod_name, shm_addr, self.file_size, self.output_shm_file)
        input_file_md5 = self.get_file_md5(self.pod_name, self.input_shm_file)
        output_file_md5 = self.get_file_md5(self.pod_name, self.output_shm_file)

        self.logStep("E6.返回read ret(0) 读成功")
        self.assertTrue(read_result, "读内存失败")
        self.assertEqual(input_file_md5, output_file_md5, "从内存中读取到的值有误")

        self.logStep("S7.解除映射"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        unmap_result = self.unmap_shm_with_tool(self.pod_name, shm_addr, self.shm_size)
        dev_num = self.get_shm_dev_num_with_tool(self.pod_name)

        self.logStep("E7.返回ubsm_shmem_unmap ret(0)")
        self.assertTrue(unmap_result, "解除映射失败")
        self.assertEqual(dev_num, 0, "设备数不正确")

        self.logStep("S8.删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        result = self.deallocate_shm_with_tool(self.pod_name, self.shm_name)

        self.logStep("E8.返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(result, "删除共享内存失败")

    def teardown_method(self):
        self.deallocate_shm_with_tool(self.pod_name, self.shm_name)
        time.sleep(5)
        self.delete_pod_and_wait(self.pod_name)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")