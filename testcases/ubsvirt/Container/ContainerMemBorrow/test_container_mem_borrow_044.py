#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase, PodResource
from libs.modules.ubsvirt.api.client import get_date_timestamp


@pytest.mark.smoke
class TestContainerMemBorrow044(KubernetesBaseCase):
    """验证绑numa容器删除后内存归还成功.

    CaseNumber:
        test_container_mem_borrow_044
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证绑numa容器删除后内存归还成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常，完成容器内存借用需要的环境部署工作
        P3.使用命令将环境设置为绑定numa
        P4.创建两个相同的规格的pod的yaml文件，request为8G，limits为8G
    TestStep:
        S1.创建pod
        S2.登录pod，清理缓存，使用大页占用小页内存，预留8G
        S3.在pod使用redis模型进行加压触发内存借用
        S4.在master节点查询借用事件
        S5.删除pod
        S6.在日志中查看归还借用内存成功标志
    ExpectedResult:
        E1.pod创建成功
        E2.清理缓存、预留内存成功
        E3.借用2G内存
        E4.查询到借用事件成功
        E5.删除成功
        E6.日志可以查到对应记录，且numa上借用内存归还成功
    Author:
        dongrenchen 00889960
    """

    def init_mem_borrow_params(self):
        self.yaml_base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_044"
        self.test_pod = None
        self.numa_affinity = 0

    def setup_method(self):
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")

        self.logStep("P2.K8s/RackManager功能正常无异常，完成容器内存借用需要的环境部署工作")

        self.logStep("P3.使用命令将环境设置为绑定numa")
        self.set_node_label(bind_numa=True)

        self.logStep("P4.创建两个相同的规格的pod的yaml文件，request为8G，limits为8G")

    def test_container_mem_borrow_044(self):
        self.logStep("S1.创建pod")
        self.test_pod = self.create_pod(str(self.yaml_base_path / "pod_config.yaml"))
        self.numa_affinity = self.test_pod.numa_affinity

        self.logStep("E1.pod创建成功，没有报错")
        search_cmd = f"kubectl get pod -n {self.test_pod.name_space} {self.test_pod.pod_name} -owide"
        res = self.master.run({'command': [search_cmd], 'waitstr': '#'}).get('stdout')
        self.assertIn("Running", res, "can not find pod in kube")

        self.logStep("S2.登录pod，清理缓存，使用大页占用小页内存，预留8G")
        self.clear_huge_pages(self.node_dict['worker1'])
        self.set_watermark(75, 80, 85)

        self.logStep("E2.清理缓存、预留内存成功")

        self.logStep("S3.在pod使用redis模型进行加压触发内存借用")
        self.add_stress(self.test_pod, 94, "worker1", bind_numa=True)

        self.logStep("E3.借用2G内存")
        flag1 = self.check_numa_borrow_size("worker1", 2048, 600)
        self.assertTrue(flag1, "borrow mem failed")

        self.logStep("S4.在master节点查询借用事件")
        res = self.master.run({'command': ['kubectl get event -A | grep "mem borrow success"'], 'waitstr': '#'}).get("stdout").replace("root@#>", "")

        self.logStep("E4.查询到一次借用事件成功")
        self.assertIsNotNone(res, "kubectl get borrow event failed")

        self.logStep("S5.删除pod")
        self.delete_pod(self.test_pod)
        self.pod_list.remove(self.test_pod)
        self.clear_huge_pages(self.node_dict['worker1'])

        self.logStep("E5.删除成功，清理环境成功")
        res = self.master.run({'command': [search_cmd], 'waitstr': '#'}).get('stderr')
        self.assertIn("not found", res)

        self.logStep("S6.在日志中查看归还借用内存成功标志")
        flag2 = self.check_numa_mem_return("worker1")

        self.logStep("E6.日志可以查到对应记录，且numa上借用内存归还成功")
        self.assertTrue(flag2, "mem return failed")

    def teardown_method(self):
        self.set_watermark(80, 85, 92)
        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.clear_test_pod()