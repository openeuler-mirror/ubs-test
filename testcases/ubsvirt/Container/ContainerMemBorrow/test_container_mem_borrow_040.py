#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase
from libs.modules.ubsvirt.api.client import get_date_timestamp


@pytest.mark.smoke
class TestContainerMemBorrow040(KubernetesBaseCase):
    """验证绑numa容器加压超水线后邻居节点无空闲大页内存借用失败.

    CaseNumber:
        test_container_mem_borrow_040
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证绑numa容器加压超水线后邻居节点无空闲大页内存借用失败
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常
        P3.使用命令将环境设置为绑定numa
        P4.创建pod的yaml文件，request为8G，limits为8G
    TestStep:
        S1.创建pod
        S2.登录pod，清理缓存，配置大页
        S3.在pod使用redis模型进行加压触发内存借用
        S4.在日志中查看借用失败标志
        S5.在master节点查询借用事件
        S6.删除pod，清理环境
    ExpectedResult:
        E1.pod创建成功
        E2.清理缓存、预留内存成功
        E3.没有借用2G内存
        E4.可以查到相关日志
        E5.查询到一次借用失败事件
        E6.删除成功，清理环境成功
    Author:
        luoyikang 00668584
    """

    def init_mem_borrow_params(self):
        self.yaml_base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_040"
        self.filepath = "/tmp/memborrow"
        self.run_node_name = "worker1"

    def setup_method(self):
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")
        node_num = self.get_node_number()
        self.assertGreaterEqual(node_num, 2, "节点数不大于等于2")

        self.logStep("P2.K8s/RackManager功能正常无异常")

        pod_list = self.get_pod_list_by_name("kube-matrix-agent")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")

        self.logStep("P3.使用命令将环境设置为绑定numa")
        self.set_label_numa()

        self.logStep("P4.创建pod的yaml文件，request为8G，limits为8G")
        self.create_dir("master", self.filepath)

        params = {
            "source_file": str(self.yaml_base_path / "pod-numa-worker1.yaml"),
            "destination_file": f"{self.filepath}/pod-numa-worker1.yaml"
        }
        self.upload_file("master", params)

    def test_container_mem_borrow_040(self):
        self.logStep("S1.创建pod")
        self.delete_pod_by_name("pod-for-mem")

        create_result = self.create_pod_by_name("pod-numa-worker1.yaml")
        self.assertTrue(create_result, "创建测试pod失败")

        self.logStep("E1.pod创建成功，没有报错")

        self.logStep("S2.登录pod，清理缓存，配置大页")
        self.clear_drop_cache(self.run_node_name)
        self.set_watermark(75, 80, 85)
        numa_num = self.get_node_container_numa_affinity_by_name(self.run_node_name)
        self.assertIn(int(numa_num), [0, 1, 2, 3], f"numa affinity is invalid, num is {numa_num}")
        self.config_hugepage_with_mem_hugepage(self.run_node_name, numa_num, 7.1 * 1024)
        time.sleep(10)
        if self.get_node_number() == 4:
            self.set_node_reserved_size(['master', 'worker2', 'worker3'], 300)
        elif self.get_node_number() == 2:
            self.set_node_reserved_size(['master'], 300)

        self.logStep("E2.清理缓存、预留内存成功")

        self.start_redis_server(self.run_node_name)

        self.logStep("S3.在pod使用redis模型进行加压触发内存借用")
        self.stress_redis()

        self.logStep("E3.没有借用2G内存")

        self.logStep("S4.在日志中查看借用失败标志")
        start_time = get_date_timestamp(self.node_dict[self.run_node_name])
        wait_time = 0
        no_borrow_flag = False
        while wait_time < 2:
            no_borrow_flag = self.get_matrix_agent_decision(start_time, self.run_node_name, "err:borrow mem from mxe failed")
            if no_borrow_flag:
                break
            wait_time += 1
        self.assertTrue(no_borrow_flag, "no borrow failed flag")

        self.logStep("E4.可以查到相关日志")
        wait_event_time = 0
        time_str = ""
        while wait_event_time < 10:
            time_str = self.get_latest_borrow_failed_event(self.run_node_name)
            if time_str and time_str.count("invalid") == 0:
                break
            wait_event_time += 1
            time.sleep(3)
        time_int = self.to_seconds(time_str)
        self.assertTrue(time_str, "未获取到借用事件")

        self.logStep("S5.在master节点查询借用事件")
        self.assertTrue(time_int < 300, "no borrow failed event")

        self.logStep("E5.查询到一次借用失败事件")

        self.logStep("S6.删除pod，清理环境")
        self.delete_pod_by_name("pod-for-mem")
        numa_num_val = numa_num if isinstance(numa_num, int) else 4
        if numa_num_val == 4:
            self.clear_all_huge_size(['master', 'worker2', 'worker3'])
        else:
            self.clear_all_huge_size(['master'])

        self.logStep("E6.删除成功，清理环境成功")

    def teardown_method(self):
        self.set_watermark(80, 85, 92)
        node_num = self.get_node_number()
        self.delete_pod_by_name("pod-for-mem")
        if node_num == 4:
            self.clear_all_huge_size(['master', 'worker1', 'worker2', 'worker3'])
        elif node_num == 2:
            self.clear_all_huge_size(['master', 'worker1'])