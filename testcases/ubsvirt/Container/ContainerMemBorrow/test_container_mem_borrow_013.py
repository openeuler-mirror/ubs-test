#!/usr/local/python
# -*- coding: utf-8 -*-


import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase, PodResource
from libs.modules.ubsvirt.common.node_manager import get_new_sshconnect


@pytest.mark.smoke
class TestContainerMemBorrow013(KubernetesBaseCase):
    """验证不绑numa容器多次加压超水线后内存借用成功.

    CaseNumber:
        test_container_mem_borrow_013
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证不绑numa容器多次加压超水线后内存借用成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常
        P3.Node0节点numa上配置大页内存，每个numa预留4G内存
        P4.已完成两个内存规格容器C1，C2的创建
    TestStep:
        S1.登录C1，C2加压，使得内存超过第二水位线92%，查看借用情况
        S2.创建C3，对C3加压，查看借用情况
    ExpectedResult:
        E1.存在水位线告警，借用4G
        E2.存在水位线告警，借用8G
    Author:
        luzeren 30077053
    """

    def init_mem_borrow_params(self):
        self.yaml_base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_013"
        self.run_node_name = None
        self.node_num = 2
        self.test_pod1 = None
        self.test_pod2 = None
        self.test_pod3 = None

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

        self.logStep("P3.Node0节点numa上配置大页内存，每个numa预留4G内存")
        self.set_label_node()
        self.delete_pod_by_name("test-pod-01")
        self.delete_pod_by_name("test-pod-02")
        self.delete_pod_by_name("test-pod-03")
        self.clear_huge_pages(self.node_dict['worker1'])
        self.run_node_name = "worker1"
        self.clear_drop_cache(self.run_node_name)

        self.set_node_reserved_size([self.run_node_name], 28 * 1024)

        self.logStep("P4.已完成两个内存规格容器C1，C2的创建")
        self.test_pod1 = self.create_pod(str(self.yaml_base_path / "pod_config.yaml"))
        self.test_pod2 = self.create_pod(str(self.yaml_base_path / "pod_config2.yaml"))
        time.sleep(10)

    def test_container_mem_borrow_013(self):
        self.logStep("S1.登录C1，C2加压，使得内存超过第二水位线92%")
        self.start_redis_server(self.run_node_name, "test-pod-01")
        self.start_redis_server(self.run_node_name, "test-pod-02")
        self.stress_redis("node", "test-pod-01")
        self.stress_redis("node", "test-pod-02")

        self.logStep("E1.存在水位线告警，借用4G")
        flag1 = self.check_numa_borrow_size("worker1", 4096, 600)
        self.assertTrue(flag1, "borrow mem failed")

        self.logStep("S2.创建C3，对C3加压")
        self.test_pod3 = self.create_pod(str(self.yaml_base_path / "pod_config3.yaml"))
        self.start_redis_server(self.run_node_name, "test-pod-03")
        server_cmd = [
            f"nohup kubectl exec -n kube-system test-pod-03 -- /redis/redis-benchmark -t set,get -n 20000000 -c 128 -r 1850000 -h 127.0.0.1 -p 6379 -d 2048 --threads 64 > /dev/null 2>&1 &"]
        ssh_node = get_new_sshconnect(self.master)
        ssh_node.run({'command': server_cmd, 'waitstr': 'avg_msec'})

        self.logStep("E2.存在水位线告警，借用8G")
        flag2 = self.check_numa_borrow_size("worker1", 8192, 600)
        self.assertTrue(flag2, "Mem borrow failed")

    def teardown_method(self):
        if self.node_num > 2:
            self.node_dict['worker2'].run({'command': ['systemctl start ubse']})
            self.node_dict['worker3'].run({'command': ['systemctl start ubse']})

        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.clear_redis_stress("test-pod-01")
        self.clear_redis_stress("test-pod-02")
        self.delete_pod_by_name('test-pod-01')
        self.delete_pod_by_name('test-pod-02')
        self.clear_redis_stress("test-pod-03")
        self.delete_pod_by_name('test-pod-03')