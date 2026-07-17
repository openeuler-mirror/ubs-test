#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMem003(KubernetesBaseCase):
    """验证多个pod使用一块容器共享内存.

    CaseNumber:
        test_container_share_mem_003
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证多个pod使用一块容器共享内存
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
        S2.分别登录两个pod，进入/ko目录，两个pod生成一个读写文件
        S3.执行使用udms的cli工具准备命令
        S4.在pod0、pod1分别创建1024MB共享内存，共享内存名字必须为 cr文件里的共享内存名字Name + "_" + 数字，推荐从1累增
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S5.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S6.在pod0、pod1分别写共享内存
        app append 0xffff10000000 134217728 /home/matrixplugin/file.input
        S7.在pod0、pod1分别读共享内存
        app read 0xffff10000000  134217728 /home/matrixplugin/file.output
        S8.在pod0、pod1分别解除映射
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S9.在pod0、pod1分别删除共享内存
        例如 app ubsm_shmem_deallocate sharememory_1
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.pod0、pod1分别可以成功登录，共享内存使用cli的路径在ko下，存在cli_server、cli_client、matrix_diagnose三个文件
        E3.成功进入接口输入页面
        E4.pod0、pod1分别返回ubsm_shmem_allocate ret(0)，代表申请内存成功
        E5.pod0、pod1分别返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E6.pod0、pod1分别返回write  ret(0) 写成功
        E7.pod0、pod1分别返回read ret(0) 读成功
        E8.pod0、pod1分别返回ubsm_shmem_unmap ret(0) 读成功
        E9.pod0、pod1分别返回ubsm_shmem_deallocate ret(0)
    Author:
        handongkang 30046606
    """

    def init_shm_params(self):
        self.pod0_name = "pod-for-shm"
        self.pod1_name = "pod-for-shm1"
        self.pod2_name = "pod-for-shm2"
        self.shm_size = 1073741824
        self.file_size = 134217728
        self.shm_name = "testshm_1"
        self.cr_name = self.shm_name.split("_")[0]
        self.filepath = "/tmp/memborrow"
        self.input_shm_file = "/tmp/file.input"
        self.output_shm_file1 = "/tmp/file.output1"
        self.output_shm_file2 = "/tmp/file.output2"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_003"
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
        params0 = {
            "source_file": f"{self.shm_base_path}/{self.pod0_name}.yaml",
            "destination_file": f"{self.filepath}/{self.pod0_name}.yaml"
        }
        self.upload_file("master", params0)
        params1 = {
            "source_file": f"{self.shm_base_path}/{self.pod1_name}.yaml",
            "destination_file": f"{self.filepath}/{self.pod1_name}.yaml"
        }
        self.upload_file("master", params1)
        params2 = {
            "source_file": f"{self.shm_base_path}/{self.pod2_name}.yaml",
            "destination_file": f"{self.filepath}/{self.pod2_name}.yaml"
        }
        self.upload_file("master", params2)

        self.logStep("P7.使用udms的cli工具准备命令"
                     "./matrix_diagnose 123 &"
                     "./cli_server &"
                     "./cli_client"
                     "attach 123")
        self.logInfo("测试用例自带测试二进制")

    def test_container_share_mem_003(self):
        self.logStep("S1.创建2个pod，pod0和pod1")
        self.delete_pod_and_wait(self.pod0_name)
        create_result0 = self.create_pod_and_wait_running(f"{self.pod0_name}.yaml", self.pod0_name)
        self.delete_pod_and_wait(self.pod1_name)
        create_result1 = self.create_pod_and_wait_running(f"{self.pod1_name}.yaml", self.pod1_name)
        self.delete_pod_and_wait(self.pod2_name)
        create_result2 = self.create_pod_and_wait_running(f"{self.pod2_name}.yaml", self.pod2_name)

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result0, "创建测试pod0失败")
        self.assertTrue(create_result1, "创建测试pod1失败")
        self.assertTrue(create_result2, "创建测试pod2失败")

        self.logStep("S2.分别登录两个pod，进入/ko目录，两个pod生成一个读写文件")
        cmd_result0 = self.check_shm_tool_file(self.pod0_name)
        cmd_result1 = self.check_shm_tool_file(self.pod1_name)
        cmd_result2 = self.check_shm_tool_file(self.pod2_name)

        self.logStep("E2.pod0、pod1分别可以成功登录，共享内存使用cli的路径在ko下，存在shm_tool文件")
        self.assertNotEqual(cmd_result0, [], "pod0 下没有测试工具shm_tool")
        self.assertNotEqual(cmd_result1, [], "pod1 下没有测试工具shm_tool")
        self.assertNotEqual(cmd_result2, [], "pod2 下没有测试工具shm_tool")

        self.logStep("S3.执行使用udms的cli工具准备命令")
        start_result = self.start_shm_tool_server(self.pod0_name)
        start_result1 = self.start_shm_tool_server(self.pod1_name)
        start_result2 = self.start_shm_tool_server(self.pod2_name)

        self.logStep("E3.成功进入接口输入页面")
        self.assertTrue(start_result, "pod0启动shm_tool server失败")
        self.assertTrue(start_result1, "pod1启动shm_tool server失败")
        self.assertTrue(start_result2, "pod2启动shm_tool server失败")

        self.logStep("S4.在pod0、pod1分别创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result = self.allocate_shm_with_tool(self.pod0_name, self.shm_name, self.shm_size)
        cr_result = self.get_cr_status(self.cr_name)

        self.logStep("E4.pod0、pod1分别返回ubsm_shmem_allocate ret(0)，代表申请内存成功")
        self.assertTrue(cmd_result, "映射失败")
        self.assertTrue(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

        self.logStep("S5.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        shm_addr = self.map_shm_with_tool(self.pod0_name, self.shm_size, "0", "1", self.shm_name)
        dev_num = self.get_shm_dev_num_with_tool(self.pod0_name)
        shm_addr1 = self.map_shm_with_tool(self.pod1_name, self.shm_size, "0", "1", self.shm_name)
        dev_num1 = self.get_shm_dev_num_with_tool(self.pod1_name)
        shm_addr2 = self.map_shm_with_tool(self.pod2_name, self.shm_size, "0", "1", self.shm_name)
        dev_num2 = self.get_shm_dev_num_with_tool(self.pod2_name)

        self.logStep("E5.pod0、pod1分别返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")
        self.assertNotEqual(shm_addr, "", "pod0映射共享内存失败，未获取到地址")
        self.assertEqual(dev_num, self.shm_size / 1024 / 1024 / 128, "pod0设备数不正确")
        self.assertNotEqual(shm_addr1, "", "pod1映射共享内存失败，未获取到地址")
        self.assertEqual(dev_num1, self.shm_size / 1024 / 1024 / 128, "pod1设备数不正确")
        self.assertNotEqual(shm_addr2, "", "pod2映射共享内存失败，未获取到地址")
        self.assertEqual(dev_num2, self.shm_size / 1024 / 1024 / 128, "pod2设备数不正确")

        self.logStep("S6.在pod0、pod1分别写共享内存"
                     "app append 0xffff10000000 134217728 /home/matrixplugin/file.input")
        gen_result = self.gen_file_for_shm(self.pod0_name, self.input_shm_file, f"{self.file_size // 1024 // 1024}M")
        self.assertNotEqual(gen_result, [], "生成测试文件失败")
        set_result = self.set_shm_ownership_with_tool(self.pod0_name, self.shm_name, shm_addr, self.shm_size, 3)
        self.assertTrue(set_result, "pod0设置shm权限为3失败")
        write_result = self.write_shm_with_tool(self.pod0_name, shm_addr, self.file_size, self.input_shm_file)
        set_result = self.set_shm_ownership_with_tool(self.pod0_name, self.shm_name, shm_addr, self.shm_size, 0)
        self.assertTrue(set_result, "pod0设置shm权限为0失败")

        self.logStep("E6.pod0、pod1分别返回write  ret(0) 写成功")
        self.assertTrue(write_result, "写文件失败")

        self.logStep("S7.在pod0、pod1分别读共享内存"
                     "app read 0xffff10000000  134217728 /home/matrixplugin/file.output")
        set_result1 = self.set_shm_ownership_with_tool(self.pod1_name, self.shm_name, shm_addr1, self.shm_size, 3)
        self.assertTrue(set_result1, "pod1设置shm权限3失败")
        read_result1 = self.read_shm_with_tool(self.pod1_name, shm_addr1, self.file_size, self.output_shm_file1)
        set_result1 = self.set_shm_ownership_with_tool(self.pod1_name, self.shm_name, shm_addr1, self.shm_size, 0)
        self.assertTrue(set_result1, "pod1设置shm权限0失败")

        set_result2 = self.set_shm_ownership_with_tool(self.pod2_name, self.shm_name, shm_addr2, self.shm_size, 3)
        self.assertTrue(set_result2, "pod2设置shm权限3失败")
        read_result2 = self.read_shm_with_tool(self.pod2_name, shm_addr2, self.file_size, self.output_shm_file2)
        set_result2 = self.set_shm_ownership_with_tool(self.pod2_name, self.shm_name, shm_addr2, self.shm_size, 0)
        self.assertTrue(set_result2, "pod2设置shm权限0失败")

        input_file_md5 = self.get_file_md5(self.pod0_name, self.input_shm_file)
        output_file1_md5 = self.get_file_md5(self.pod1_name, self.output_shm_file1)
        output_file2_md5 = self.get_file_md5(self.pod2_name, self.output_shm_file2)

        self.logStep("E7.pod0、pod1分别返回read ret(0) 读成功")
        self.assertTrue(read_result1, "pod1读内存失败")
        self.assertEqual(input_file_md5, output_file1_md5, "pod1从内存中读取到的值有误")
        self.assertTrue(read_result2, "pod2读内存失败")

        self.logStep("S8.在pod0、pod1分别解除映射"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        unmap_result = self.unmap_shm_with_tool(self.pod0_name, shm_addr, self.shm_size)
        unmap_result1 = self.unmap_shm_with_tool(self.pod1_name, shm_addr1, self.shm_size)
        unmap_result2 = self.unmap_shm_with_tool(self.pod2_name, shm_addr2, self.shm_size)
        dev_num = self.get_shm_dev_num_with_tool(self.pod0_name)
        dev_num1 = self.get_shm_dev_num_with_tool(self.pod1_name)
        dev_num2 = self.get_shm_dev_num_with_tool(self.pod2_name)

        self.logStep("E8.pod0、pod1分别返回ubsm_shmem_unmap ret(0) 读成功")
        self.assertTrue(unmap_result, "pod0解除映射失败")
        self.assertEqual(dev_num, 0, "pod0设备数不正确")
        self.assertTrue(unmap_result1, "pod1解除映射失败")
        self.assertEqual(dev_num1, 0, "pod1设备数不正确")
        self.assertTrue(unmap_result2, "pod2解除映射失败")
        self.assertEqual(dev_num2, 0, "pod2设备数不正确")

        self.logStep("S9.在pod0、pod1分别删除共享内存"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        result = self.deallocate_shm_with_tool(self.pod0_name, self.shm_name)

        self.logStep("E9.pod0、pod1分别返回ubsm_shmem_deallocate ret(0)")
        self.assertTrue(result, "解除映射失败")

    def teardown_method(self):
        self.deallocate_shm_with_tool(self.pod0_name, self.shm_name)
        time.sleep(5)
        self.delete_pod_and_wait(self.pod0_name)
        self.delete_pod_and_wait(self.pod1_name)
        self.delete_pod_and_wait(self.pod2_name)
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")