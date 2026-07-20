#!/usr/local/python
# -*- coding: utf-8 -*-


import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerMemBorrow002(KubernetesBaseCase):
    """验证支持命令行批量配置节点标签支持绑定NUMA.

    CaseNumber:
        test_container_mem_borrow_002
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证支持命令行批量配置节点标签支持绑定NUMA
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s功能正常无异常
        P3.按照资料配置cpuManagerPolicy字段为static
    TestStep:
        S1.执行批量脚本，设置所有节点为绑定numa
        S2.执行kubectl get nodes --show-labels查询所有节点的标签
    ExpectedResult:
        E1.执行成功
        E2.所有节点watermark-escape-strategy标签为numa
    Author:
        luzeren 30077053
    """

    def setup_method(self):
        """测试前置设置"""
        self.key_word1 = "error"
        self.key_word2 = "watermark-escape-strategy=numa"
        self.valid_nodes = {'master', 'worker1', 'worker2', 'worker3'}

        self.logStep("P1.环境中存在2个及以上节点")

        self.logStep("P2.K8s功能正常无异常")

        self.logStep("P3.按照资料配置cpuManagerPolicy字段为static")
        self.set_node_label()

    def test_container_mem_borrow_002(self):
        """测试命令行批量配置节点标签支持绑定NUMA"""

        self.logStep("S1.执行批量脚本，设置所有节点为绑定numa")
        res_dict = {}
        for node in self.node_dict:
            if node in self.valid_nodes:
                res_dict[node] = self.master.run({'command': [f"kubectl label nodes {node} watermark-escape-strategy=numa --overwrite"]})

        self.logStep("E1.执行成功")
        for node in self.node_dict:
            if node in self.valid_nodes:
                flag = self.key_word1 not in str(res_dict[node])
                self.assertTrue(flag, "Execution failed")

        self.logStep("S2.执行kubectl get nodes --show-labels查询所有节点的标签")
        res_dict = {}
        for node in self.node_dict:
            if node in self.valid_nodes:
                res_dict[node] = self.master.run({'command': [f"kubectl get nodes --show-labels | grep \"{node}\""]}).get("stdout").replace("root@#>", "")

        self.logStep("E2.所有节点watermark-escape-strategy标签为numa")
        for node in self.node_dict:
            if node in self.valid_nodes:
                self.assertIn(self.key_word2, res_dict[node], "watermark-escape-strategy is not numa")

    def teardown_method(self):
        """测试清理"""
        for node in self.node_dict:
            if node in self.valid_nodes:
                self.master.run({'command': [f"kubectl label nodes {node} watermark-escape-strategy=numa --overwrite"]})