#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase, PodResource


@pytest.mark.smoke
class TestContainerMemBorrow012(KubernetesBaseCase):
    """验证绑numa容器多次加压超水线后内存借用成功.

    CaseNumber:
        test_container_mem_borrow_012
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证绑numa容器多次加压超水线后内存借用成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常
        P3.Node0节点numa1上配置大页内存，预留16G可用小页
        P4.已完成两个内存规格容器C1，C2的创建
    TestStep:
        S1.登录C1，C2加压，使得内存超过第二水位线92%，查看借用情况
        S2.创建C3，对C3加压，查看借用情况
    ExpectedResult:
        E1.存在水位线告警，借用2G
        E2.存在水位线告警，借用4G
    Author:
        dongrenchen 00889960
    """

    def init_mem_borrow_params(self):
        self.yaml_base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_012"
        self.test_pod1 = None
        self.test_pod2 = None
        self.test_pod3 = None
        self.node_num = 2
        self.run_node_name = "worker1"

    def setup_method(self):
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")
        self.node_num = self.get_node_number()
        self.assertGreaterEqual(self.node_num, 2, "节点数不大于等于2")
        pod_list = self.get_pod_list_by_name("kube-matrix-agent")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")

        self.logStep("P2.K8s/RackManager功能正常无异常")
        if self.node_num > 2:
            self.node_dict['worker2'].run({'command': ['systemctl stop ubse']})
            self.node_dict['worker3'].run({'command': ['systemctl stop ubse']})

        self.logStep("P3.Node0节点numa1上配置大页内存，预留16G可用小页")
        self.set_label_numa()
        self.delete_pod_by_name("test-pod-01")
        self.delete_pod_by_name("test-pod-02")
        self.delete_pod_by_name("test-pod-03")
        self.clear_huge_pages(self.node_dict['worker1'])
        self.clear_drop_cache(self.run_node_name)

        self.logStep("P4.已完成两个内存规格容器C1，C2的创建")
        self.test_pod1 = self.create_pod(str(self.yaml_base_path / "pod_config1.yaml"))
        self.test_pod2 = self.create_pod(str(self.yaml_base_path / "pod_config2.yaml"))
        time.sleep(10)

    def test_container_mem_borrow_012(self):
        self.logStep("S1.登录C1，C2加压，使得内存超过第二水位线92%")
        self.assertIn(int(self.test_pod1.numa_affinity), [0, 1, 2, 3],
                      f"pod1 numa affinity is empty, num is {self.test_pod1.numa_affinity}")
        self.assertIn(int(self.test_pod2.numa_affinity), [0, 1, 2, 3],
                      f"pod2 numa affinity is empty, num is {self.test_pod2.numa_affinity}")
        self.assertEqual(self.test_pod1.numa_affinity, self.test_pod2.numa_affinity,
                         f"pod1 and pod2 numa affinity not same")

        numa_name = f"Node {self.test_pod1.numa_affinity}"
        numa_node_for_huagepage = f"node{self.test_pod1.numa_affinity}"
        self.change_hugepage(self.run_node_name, numa_node_for_huagepage, 0)
        mem_free = self.get_node_numa_free(self.run_node_name, numa_name)
        mem_reserved = 14.5 * 1024
        mem_hugepage = mem_free - mem_reserved
        hugepage_count = int(mem_hugepage / 2)
        self.change_hugepage(self.run_node_name, numa_node_for_huagepage, hugepage_count)

        self.start_redis_server(self.run_node_name, "test-pod-01")
        self.start_redis_server(self.run_node_name, "test-pod-02")
        self.stress_redis("numa", "test-pod-01")
        self.stress_redis("numa", "test-pod-02")

        self.logStep("E1.存在水位线告警，借用2G")
        flag1 = self.check_numa_borrow_size(self.run_node_name, 2048, 600)
        self.assertTrue(flag1, "borrow mem failed")

        self.logStep("S2.创建C3，对C3加压")
        self.test_pod3 = self.create_pod(str(self.yaml_base_path / "pod_config3.yaml"))
        self.start_redis_server(self.run_node_name, "test-pod-03")
        self.stress_redis("numa", "test-pod-03")

        self.logStep("E2.存在水位线告警，借用4G")
        flag2 = self.check_numa_borrow_size(self.run_node_name, 4096, 600)
        self.assertTrue(flag2, "borrow mem failed")

    def teardown_method(self):
        if self.node_num > 2:
            self.node_dict['worker2'].run({'command': ['systemctl start ubse']})
            self.node_dict['worker3'].run({'command': ['systemctl start ubse']})

        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.delete_pod_by_name('test-pod-01')
        self.delete_pod_by_name('test-pod-02')
        self.delete_pod_by_name('test-pod-03')