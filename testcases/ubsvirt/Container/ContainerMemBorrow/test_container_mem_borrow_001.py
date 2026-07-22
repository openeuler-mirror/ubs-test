#!/usr/local/python
# -*- coding: utf-8 -*-


import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestContainerMemBorrow001(KubernetesBaseCase):
    """验证支持命令行配置节点标签支持绑定NUMA.

    CaseNumber:
        test_container_mem_borrow_001
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证支持命令行配置节点标签支持绑定NUMA
    PreCondition:
        P1.环境中存在2个及以上节点
        P2.K8s功能正常无异常
        P3.按照资料配置cpuManagerPolicy字段为static
    TestStep:
        S1.执行kubectl label nodes <nodeA> watermark-escape-strategy=node --overwrite
        S2.执行kubectl label nodes <nodeB> watermark-escape-strategy=numa --overwrite
        S3.执行kubectl get nodes --show-labels查询所有节点的标签
    ExpectedResult:
        E1.配置成功
        E2.配置成功
        E3.nodeA节点watermark-escape-strategy标签为node，nodeB节点watermark-escape-strategy标签为numa
    Author:
        luzeren 30077053
    """

    def setup_method(self):
        """测试前置设置"""
        self.key_word1 = "node/master labeled"
        self.key_word2 = "node/worker1 labeled"
        self.key_word3 = "watermark-escape-strategy=node"
        self.key_word4 = "watermark-escape-strategy=numa"

        self.logStep("P1.环境中存在2个及以上节点")

        self.logStep("P2.K8s功能正常无异常")

        self.logStep("P3.按照资料配置cpuManagerPolicy字段为static")
        self.master.run({'command': ["kubectl label nodes master watermark-escape-strategy=numa --overwrite"]})
        self.master.run({'command': ["kubectl label nodes worker1 watermark-escape-strategy=node --overwrite"]})

    def test_container_mem_borrow_001(self):
        """测试命令行配置节点标签支持绑定NUMA"""

        self.logStep("S1.执行kubectl label nodes <nodeA> watermark-escape-strategy=node --overwrite")
        res = self.master.run({'command': ["kubectl label nodes master watermark-escape-strategy=node --overwrite"]}).get("stdout")

        self.logStep("E1.配置成功")
        self.assertIn(self.key_word1, res, "Failed to add configuration")

        self.logStep("S2.执行kubectl label nodes <nodeB> watermark-escape-strategy=numa --overwrite")
        res = self.master.run({'command': ["kubectl label nodes worker1 watermark-escape-strategy=numa --overwrite"]}).get("stdout")

        self.logStep("E2.配置成功")
        self.assertIn(self.key_word2, res, "Failed to add configuration")

        self.logStep("S3.执行kubectl get nodes --show-labels查询所有节点的标签")
        res = self.master.run({'command': ["kubectl get nodes --show-labels"]}).get("stdout")

        self.logStep("E3.nodeA节点watermark-escape-strategy标签为node，nodeB节点watermark-escape-strategy标签为numa")
        master_line = [line for line in res.splitlines() if line.startswith('master')][0]
        worker1_line = [line for line in res.splitlines() if line.startswith('worker1')][0]
        self.assertIn(self.key_word3, master_line, "watermark-escape-strategy of nodeA is not node")
        self.assertIn(self.key_word4, worker1_line, "watermark-escape-strategy of nodeB is not numa")

    def teardown_method(self):
        """测试清理"""
        self.master.run({'command': ["kubectl label nodes master watermark-escape-strategy=numa --overwrite"]})
        self.master.run({'command': ["kubectl label nodes worker1 watermark-escape-strategy=numa --overwrite"]})