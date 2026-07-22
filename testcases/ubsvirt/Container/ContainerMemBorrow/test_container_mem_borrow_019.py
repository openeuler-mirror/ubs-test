#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase, PodResource


@pytest.mark.smoke
class TestContainerMemBorrow019(KubernetesBaseCase):
    """验证不配置超分的容器加压超水线后不支持内存借用.

    CaseNumber:
        test_container_mem_borrow_019
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不配置超分的容器加压超水线后不支持内存借用
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常
        P3.Node0节点numa0上配置大页内存，预留4G可用小页
        P4.已完成内存规格容器C1的创建，且不配置remote-mem-allocation-ratio
    TestStep:
        S1.登录容器C1，执行加压命令加压
    ExpectedResult:
        E1.event有水位线告警，Matrix agent日志本周期无内存借用决策打印
    Author:
        dongrenchen 00889960
    """

    def init_mem_borrow_params(self):
        self.yaml_base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_019"
        self.test_pod = None
        self.run_node_name = None
        self.node_num = 2

    def setup_method(self):
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")
        self.node_num = self.get_node_number()
        self.assertGreaterEqual(self.node_num, 2, "节点数不大于等于2")
        pod_list = self.get_pod_list_by_name("kube-matrix-agent")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")

        self.logStep("P2.K8s/RackManager功能正常无异常")

        self.logStep("P3.Node0节点numa0上配置大页内存，预留4G可用小页")
        self.set_label_node()
        self.delete_pod_by_name("test-pod-01")
        self.clear_huge_pages(self.node_dict['worker1'])
        self.run_node_name = "worker1"
        self.clear_drop_cache(self.run_node_name)

        self.logStep("P4.已完成内存规格容器C1的创建，且不配置remote-mem-allocation-ratio")
        self.test_pod = self.create_pod(str(self.yaml_base_path / "pod_config1.yaml"))

    def test_container_mem_borrow_019(self):
        self.logStep("S1.登录容器C1，执行加压命令加压")
        self.clear_huge_pages(self.node_dict['worker1'])

        mem_reserved = 15.5 * 1024
        self.set_node_reserved_size(['worker1'], mem_reserved)

        self.node_dict['worker1'].run({'command': ['numastat -cvm']})
        self.start_redis_server(self.run_node_name, self.test_pod.pod_name)
        self.stress_redis("node", self.test_pod.pod_name)

        self.logStep("E1.event有水位线告警，Matrix agent日志本周期无内存借用决策打印")
        time.sleep(150)

        flag2 = self.check_numa_borrow_size("worker1", 4096, 60)
        self.assertFalse(flag2, "has borrow mem, not expect")

    def teardown_method(self):
        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.delete_pod_by_name(self.test_pod.pod_name if self.test_pod else "test-pod-01")