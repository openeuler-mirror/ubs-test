#!/usr/local/python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerShareMemRecycle001(KubernetesBaseCase):
    """验证pod删除时候容器共享内存归还成功.

    CaseNumber:
        test_container_share_mem_recycle_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证pod删除时候容器共享内存归还成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager、ubmsd功能正常无异常，完成容器内存共享需要的环境部署工作
        P3.在master节点配置crd.yaml文件，kubelet apply -f crd.yaml
        P4.在master节点配置cr.yaml文件，cr文件确定好共享内存名称和共享内存限额大小，限额配置为5G，kubelet apply -f cr.yaml
        p5.配置完成应用pod的yaml文件，配置项中共享内存名与cr文件里共享内存名一致
    TestStep:
        S1.创建pod
        S2.创建1024MB共享内存
        例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0
        S3.映射共享内存
        例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1
        S4.查看映射目录
        S5.退出pod，删除pod
        例如 app ubsm_shmem_unmap 0xffff10000000 1073741824
        S6.查看主机/dev与/root/kubernetes/var/lib/kubelet/plugins/tmpdev/sharememory映射目录
        例如 app ubsm_shmem_deallocate sharememory_1
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.返回ubsm_shmem_allocate ret(0)，代表映射成功
        E3.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值
        E4.可以在容器/dev/目录下观测到映射的文件
        E5.退出删除pod成功
        E6.主机/dev/(主机侧5min内消失)与/root/kubernetes/var/lib/kubelet/plugins/tmpdev/sharememory目录下映射的文件消失。
    Author:
        handongkang 30046606
    """

    def init_shm_params(self):
        self.pod_name = "pod-for-shm"
        self.shm_size = 1073741824
        self.shm_name = "sharememory_1"
        self.cr_name = self.shm_name.split("_")[0]
        self.filepath = "/tmp/memborrow"
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_share_mem_recycle_001"
        self.shm_base_path = base_path

    def setup_method(self):
        self.init_shm_params()

        self.logStep("P1.环境中存在2个及以上节点")
        node_num = self.get_node_number()
        self.assertGreaterEqual(node_num, 2, "节点数不大于等于2")

        self.logStep("P2.K8s/RackManager、ubmsd功能正常无异常，完成容器内存共享需要的环境部署工作")
        pod_list = self.get_pod_list_by_name("shm-csi-driver")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")
        self.change_shm_driver_timer("shm-csi-driver", "1")

        self.logStep("P3.在master节点配置crd.yaml文件，kubelet apply -f crd.yaml")
        self.create_dir("master", self.filepath)
        params = {
            "source_file": f"{self.shm_base_path}/shm-cr.yaml",
            "destination_file": f"{self.filepath}/shm-cr.yaml"
        }
        self.upload_file("master", params)
        create_result = self.create_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")
        self.assertTrue(create_result, "创建CR失败")

        self.logStep("P4.在master节点配置cr.yaml文件"
                     "p5.配置完成应用pod的yaml文件，配置项中共享内存名与cr文件里共享内存名一致")
        params = {
            "source_file": f"{self.shm_base_path}/pod-for-shm.yaml",
            "destination_file": f"{self.filepath}/pod-for-shm.yaml"
        }
        self.upload_file("master", params)

    def test_container_share_mem_recycle_001(self):
        self.logStep("S1.创建pod")
        self.delete_pod_and_wait(self.pod_name)
        create_result = self.create_pod_and_wait_running(f"{self.pod_name}.yaml", self.pod_name)
        cmd_result = self.check_shm_demo_file(self.pod_name)

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result, "创建测试pod失败")
        self.assertNotEqual(cmd_result, [], "共享内存使用cli的路径在ko下，不存在shm_demo文件")

        self.logStep("S2.创建1024MB共享内存"
                     "例如 app ubsm_shmem_allocate default sharememory_1 1073741824 777 0")
        cmd_result = self.allocate_shm(self.pod_name, self.shm_name, self.shm_size)
        cr_result = self.get_cr_status("sharememory")

        self.logStep("E2.返回ubsm_shmem_allocate ret(0)，代表映射成功")
        self.logInfo(f"allocate_shm cmd_result {cmd_result}")
        self.assertTrue(cmd_result, "映射失败")
        self.assertTrue(self.get_key_from_result(cr_result, self.shm_name), "CR文件未更新")

        self.logStep("S3.映射共享内存"
                     "例如 app ubsm_shmem_map 0 1073741824 3 1 sharememory_1 0 1")
        cmd_result = self.unmap_shm(self.pod_name, self.shm_size, "0", "1", self.shm_name)

        self.logStep("E3.返回ubsm_shmem_allocate addr 0xffff10000000 ,ret(0)。地址为随机值")
        self.assertTrue(cmd_result, "映射共享内存失败，未获取到映射地址")

        self.logStep("S4.查看映射目录")
        num = self.get_shm_dev_nums(cmd_result)

        self.logStep("E4.可以在容器/dev/目录下观测到映射的文件")
        self.logInfo(f"obmm dev num is {num}")
        self.assertEqual(num, self.shm_size / 1024 / 1024 / 128, "映射的文件数量不正确")

        self.logStep("S5.退出pod，删除pod"
                     "例如 app ubsm_shmem_unmap 0xffff10000000 1073741824")
        cmd_result = self.delete_pod_by_name(self.pod_name)
        self.logInfo("删除pod后，需要等一个定时器周期才能看到资源被清理")
        cr_result = self.check_shm_driver_timer_clean(self.cr_name, self.shm_name)

        self.logStep("E5.退出删除pod成功")
        self.assertTrue(cmd_result, "退出删除pod失败")
        self.assertTrue(cr_result, "CR文件未更新")

        self.logStep("S6.查看主机/dev与/root/kubernetes/var/lib/kubelet/plugins/tmpdev/sharememory映射目录"
                     "例如 app ubsm_shmem_deallocate sharememory_1")
        dev_num = self.get_tmp_dev_num(self.pod_name)

        self.logStep("E6.主机/dev/(主机侧5min内消失)与/root/kubernetes/var/lib/kubelet/plugins/tmpdev/sharememory目录下映射的文件消失。")
        self.assertEqual(self.get_shm_dev_nums(dev_num), 0, "映射的文件数量不正确")

    def teardown_method(self):
        self.delete_resource_by_yaml(f"{self.filepath}/shm-cr.yaml")
        self.change_shm_driver_timer("shm-csi-driver", "5")