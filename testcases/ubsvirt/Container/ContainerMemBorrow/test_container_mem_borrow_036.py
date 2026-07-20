#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase
from libs.modules.ubsvirt.api.client import get_date_timestamp


@pytest.mark.smoke
class TestContainerMemBorrow036(KubernetesBaseCase):
    """验证绑numa容器加压超水线后内存借用成功.

    CaseNumber:
        test_container_mem_borrow_036
    RunLevel:
        Level 0
    EnvType:

    CaseName:
        验证绑numa容器加压超水线后内存借用成功
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/RackManager功能正常无异常，完成容器内存借用需要的环境部署工作
        P3.使用命令将环境设置为绑定numa策略
            kubectl label nodes pod所在节点名 watermark-escape-strategy=numa --overwrite
        P4.创建pod的yaml文件，request为8G，limits为8G
    TestStep:
        S1.创建pod
        S2.登录pod，清理缓存，使用大页占用小页内存，对根据pod的yaml的cpu设置的numa预留7.2G
            命令：echo 3 > /proc/sys/vm/drop_caches
        S3.在pod使用redis模型进行加压触发内存借用
            加压命令：./redis-server redis.conf &
            ./redis-benchmark -t set,get -n 20000000 -c 128 -r 2850000 -h 127.0.0.1 -p 6379 -d 2048 --threads 64
        S4.在日志中查看借用成功标志
            日志目录：/var/log/pods/kube-system_kube-matrix-agent-xxxxx（随机码）/kube-matrix-agent/
            借用成功标志：borrow mem from mxe success
        S5.在master节点使用kubectl get event查询借用事件，使用numastat -vm查询借用内存，借用值为2G
        S6.删除pod，清理环境
    ExpectedResult:
        E1.pod创建成功，没有报错
        E2.可以成功登录，清理缓存、预留内存成功
        E3.借用2G内存
        E4.可以查到相关日志
        E5.查询到一次借用事件成功
        E6.删除成功，清理环境成功
    Author:
        luoyikang 00668584
    """


    def init_mem_borrow_params(self):
        """初始化内存借用测试参数"""
        self.pod_name = "pod-for-mem"
        self.filepath = "/tmp/memborrow"
        self.run_node_name = "worker1"
        self.borrow_size = 2048
        base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_036"
        self.yaml_base_path = base_path

    def setup_method(self):
        """测试前置设置"""
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")
        node_num = self.get_node_number()
        self.assertGreaterEqual(node_num, 2, "节点数不大于等于2")

        self.logStep("P2.K8s/RackManager功能正常无异常，完成容器内存借用需要的环境部署工作")
        pod_list = self.get_pod_list_by_name("kube-matrix-agent")
        self.assertGreaterEqual(len(pod_list), 2, "pod数不大于等于2")

        self.logStep("P3.使用命令将环境设置为绑定numa策略")
        self.set_label_numa()

        self.logStep("P4.创建pod的yaml文件，request为8G，limits为8G")
        self.create_dir("master", self.filepath)
        params = {
            "source_file": f"{self.yaml_base_path}/pod-numa-worker1.yaml",
            "destination_file": f"{self.filepath}/pod-numa-worker1.yaml"
        }
        self.upload_file("master", params)

    def test_container_mem_borrow_036(self):
        """测试绑numa容器加压超水线后内存借用成功"""

        self.logStep("S1.创建pod")
        self.delete_pod_by_name(self.pod_name)
        create_result = self.create_pod_by_name("pod-numa-worker1.yaml")

        self.logStep("E1.pod创建成功，没有报错")
        self.assertTrue(create_result, "创建测试pod失败")

        self.logStep("S2.登录pod，清理缓存，使用大页占用小页内存，对根据pod的yaml的cpu设置的numa预留7.2G")
        self.clear_drop_cache(self.run_node_name)
        self.set_watermark(75, 80, 85)

        numa_num = self.get_node_container_numa_affinity_by_name(self.run_node_name)
        self.assertIn(numa_num, [0, 1, 2, 3], f"numa affinity is invalid, num is {numa_num}")

        numa_name = f"Node {numa_num}"
        numa_node_for_huagepage = f"node{numa_num}"
        self.change_hugepage(self.run_node_name, numa_node_for_huagepage, 0)

        mem_free = self.get_node_numa_free(self.run_node_name, numa_name)
        mem_reserved = 7.2 * 1024
        mem_hugepage = mem_free - mem_reserved
        hugepage_count = int(mem_hugepage / 2)
        self.change_hugepage(self.run_node_name, numa_node_for_huagepage, hugepage_count)
        time.sleep(10)

        self.logStep("E2.可以成功登录，清理缓存、预留内存成功")
        self.start_redis_server(self.run_node_name)

        self.logStep("S3.在pod使用redis模型进行加压触发内存借用")
        self.stress_redis()

        self.logStep("E3.借用2G内存")

        self.logStep("S4.在日志中查看借用成功标志")
        start_time = get_date_timestamp(self.node_dict[self.run_node_name])

        wait_time = 0
        borrow_flag = False
        while wait_time < 3:
            borrow_flag = self.get_matrix_agent_decision(start_time, self.run_node_name, "borrow mem from mxe success")
            if borrow_flag:
                break
            wait_time += 1

        self.assertTrue(borrow_flag, "borrow mem failed")

        self.logStep("E4.可以查到相关日志")

        self.logStep("S5.在master节点使用kubectl get event查询借用事件，使用numastat -vm查询借用内存")
        wait_event_time = 0
        time_str = ""
        while wait_event_time < 10:
            time_str = self.get_latest_borrow_event(self.run_node_name)
            if time_str and time_str.count("invalid") == 0:
                break
            wait_event_time += 1
            time.sleep(3)

        self.assertTrue(time_str, "未获取到借用事件")
        time_int = self.to_seconds(time_str)
        self.assertLess(time_int, 300, "no borrow event")

        self.logStep("E5.查询到一次借用事件成功")

        borrow_numa_name_list = [f"Node {i}" for i in range(self.node_numa_num, self.node_numa_num + 18)]
        borrow_numa = ""
        for borrow_numa_name in borrow_numa_name_list:
            borrow_numa_total = self.get_node_numa_total(self.run_node_name, borrow_numa_name)
            if borrow_numa_total != 0:
                borrow_numa = borrow_numa_name
                self.assertEqual(borrow_numa_total, self.borrow_size, f"借用内存大小不匹配，期望{self.borrow_size}，实际{borrow_numa_total}")
                break

        self.assertNotEqual(borrow_numa, "", "numa node is empty")

        wait_swap_time = 0
        swap_flag = False
        while wait_swap_time < 10:
            swap_flag = self.get_node_numa_free(self.run_node_name, borrow_numa) != self.borrow_size
            if swap_flag:
                break
            wait_swap_time += 1
            time.sleep(10)

        self.assertTrue(swap_flag, "mem swap failed")

        self.logStep("S6.删除pod，清理环境")
        self.delete_pod_by_name(self.pod_name)

        self.logStep("E6.删除成功，清理环境成功")

    def teardown_method(self):
        """测试清理"""
        self.set_watermark(80, 85, 92)
        self.delete_pod_by_name("pod-for-mem")
        self.clear_huge_pages(self.node_dict.get('worker1'))