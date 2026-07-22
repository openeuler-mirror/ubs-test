#!/usr/local/python
# -*- coding: utf-8 -*-

import re
import time
from pathlib import Path
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase
from libs.modules.ubsvirt.api.client import get_date_timestamp


@pytest.mark.smoke
class TestContainerMemBorrow010(KubernetesBaseCase):
    """验证节点级内存监控服务生成水线告警.

    CaseNumber:
        test_container_mem_borrow_010
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证节点级内存监控服务生成水线告警
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s/MXE功能正常无异常
        P3.环境中已部署pod和容器，容器limit设置host可用小页内存（可通过配置大页数来构造对应小页内存大小）
    TestStep:
        S1.登录容器执行redis加压脚本，加压到92，kubectl get event -A
        S2.清除加压脚本，执行kubectl get event -A查看水线告警
    ExpectedResult:
        E1.存在host水线告警，水线压力92
        E2.存在host水线告警，水线压力<80
    Author:
        luzeren 30077053
    """

    def init_mem_borrow_params(self):
        """初始化内存借用测试参数"""
        self.pod_name = "pod-for-mem"
        self.filepath = "/tmp/memborrow"
        self.run_node_name = "worker1"
        self.key_word1 = "node/worker1"
        self.yaml_base_path = Path(__file__).parent.parent.parent.parent.parent / "resource" / "ubsvirt" / "yaml" / "test_container_mem_borrow_010"

    def setup_method(self):
        """测试前置设置"""
        self.init_mem_borrow_params()

        self.logStep("P1.环境中存在2个及以上节点")
        node_num = self.get_node_number()
        self.assertGreaterEqual(node_num, 2, "节点数不大于等于2")

        self.logStep("P2.K8s/MXE功能正常无异常")

        self.logStep("P3.环境中已部署pod和容器，容器limit设置host可用小页内存")
        self.set_node_label(bind_numa=False)
        self.create_dir("master", self.filepath)

        params = {
            "source_file": f"{self.yaml_base_path}/pod_config.yaml",
            "destination_file": f"{self.filepath}/pod_config.yaml"
        }
        self.upload_file("master", params)

        self.clear_huge_pages(self.node_dict.get('worker1'))
        self.delete_pod_by_name(self.pod_name)

        create_result = self.create_pod_by_name("pod_config.yaml")
        self.assertTrue(create_result, "创建测试pod失败")

    def test_container_mem_borrow_010(self):
        """测试节点级内存监控服务生成水线告警"""

        self.logStep("S1.登录容器执行redis加压脚本，加压到92，kubectl get event -A")
        self.clear_drop_cache(self.run_node_name)
        for numa_num in range(self.node_numa_num):
            mem_reserved = 15.1 * 1024 / self.node_numa_num
            self.config_hugepage_with_mem_hugepage(self.run_node_name, numa_num, mem_reserved)
        time.sleep(10)
        self.start_redis_server(self.run_node_name)
        self.stress_redis("node")

        start_time = get_date_timestamp(self.node_dict[self.run_node_name])
        wait_time = 0
        borrow_flag = False
        while wait_time < 3:
            borrow_flag = self.get_matrix_agent_decision(start_time, self.run_node_name, "borrow mem from mxe success")
            if borrow_flag:
                break
            wait_time += 1

        self.assertTrue(borrow_flag, "borrow mem failed")

        res = self.master.run(
            {'command': ['kubectl get event -A | grep "mem borrow success" | head -1'], 'waitstr': '#'}).get(
            "stdout").replace("root@#>", "")

        self.logStep("E1.存在host水线告警，水线压力92")
        self.assertIn(self.key_word1, res, "host is not worker1")
        match = re.search(r"memory used ratio: (\d+\.\d+)%", res)
        flag = False
        ratio_num = 0
        if match:
            ratio_num = float(match.group(1))
            flag = (ratio_num >= 92.0)
        self.assertTrue(flag, f"memory used ratio is {ratio_num} lower than 92")

        self.logStep("S2.清除加压脚本，执行kubectl get event -A查看水线告警")
        self.delete_pod_by_name(self.pod_name)
        time.sleep(60)
        res = self.master.run(
            {'command': ['kubectl get event -A | grep "mem return success" | head -1'], 'waitstr': '#'}).get(
            "stdout").replace("root@#>", "")

        self.logStep("E2.存在host水线告警，水线压力<80")
        self.assertIn(self.key_word1, res, "host is not worker1")
        match = re.search(r"memory used ratio: (\d+\.\d+)%", res)
        flag = False
        if match:
            ratio_num = float(match.group(1))
            flag = (ratio_num < 80.0)
        self.assertTrue(flag, f"memory used ratio is {ratio_num} upper than 80")

    def teardown_method(self):
        """测试清理"""
        if self.get_pod_list_by_name(self.pod_name):
            self.delete_pod_by_name(self.pod_name)
        self.set_node_label(bind_numa=True)