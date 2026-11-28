#!/usr/local/python
# -*- coding: utf-8 -*-

import time
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestSsuPlugin03(KubernetesBaseCase):
    """验证csi-ssu-driver和ssu-controller组件在环境重启后可以自启动

    CaseNumber:
        test_ssu_plugin_03
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        验证csi-ssu-driver和ssu-controller组件在环境重启后可以自启动
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.查看csi-ssu-driver和ssu-controller组件组件状态
        S2.重启os，环境重启后等待30s查看组建状态
        S3.查看csi-ssu-driver和ssu-controller组件组件状态
    ExpectedResult:
        E1.csi-ssu-driver每个节点部署，ssu-controller组件存在主备，状态信息可以正常查询
        E2.环境重启成功
        E3.csi-ssu-driver和ssu-controller组件被重新拉起，状态正常
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.controller_namespace = ""
        self.log_start_time = ""

    def _check_plugins_status(self) -> None:
        controller_info = self.run_master(
            f"kubectl get pods -n {self.controller_namespace} --no-headers "
            "-o custom-columns=NAME:.metadata.name,PHASE:.status.phase | "
            "awk '$1 ~ /ssu.*controller|controller.*ssu/ {print}'"
        )
        self.assertTrue(controller_info, "未找到ssu-controller Pod")
        for line in controller_info.splitlines():
            fields = line.split()
            self.assertEqual(fields[1], "Running", f"ssu-controller Pod {fields[0]} 状态异常: {fields[1]}")

        node_info = self.run_master(
            f"kubectl get pods -n {self.controller_namespace} --no-headers "
            "-o custom-columns=NAME:.metadata.name,PHASE:.status.phase | "
            "awk '$1 ~ /ssu-csi-node/ {print}'"
        )
        self.assertTrue(node_info, "未找到ssu-csi-node Pod")
        for line in node_info.splitlines():
            fields = line.split()
            self.assertEqual(fields[1], "Running", f"ssu-csi-node Pod {fields[0]} 状态异常: {fields[1]}")

        helper_info = self.run_master(
            "kubectl get pods -A --no-headers "
            "-o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,PHASE:.status.phase | "
            "awk '$2 ~ /ubse-helper/ && $3 == \"Running\" {print}'"
        )
        self.assertTrue(helper_info, "未找到ubse-helper Pod")

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常")
        self.locate_plugins()

    @pytest.mark.case_info(level="P3", type="Functional")
    def test_ssu_plugin_03(self) -> None:
        self.logStep("S1.查看csi-ssu-driver和ssu-controller组件组件状态")
        self._check_plugins_status()

        self.logStep("E1.csi-ssu-driver每个节点部署，ssu-controller组件存在主备，状态信息可以正常查询")
        node_count = self.get_node_number()
        node_pod_count = len(
            self.run_master(
                f"kubectl get pods -n {self.controller_namespace} --no-headers "
                "-o custom-columns=NAME:.metadata.name | "
                "awk '$1 ~ /ssu-csi-node/'"
            ).splitlines()
        )
        controller_pod_count = len(
            self.run_master(
                f"kubectl get pods -n {self.controller_namespace} --no-headers "
                "-o custom-columns=NAME:.metadata.name | "
                "awk '$1 ~ /ssu.*controller|controller.*ssu/'"
            ).splitlines()
        )
        self.assertGreaterEqual(node_pod_count, node_count, "ssu-csi-node Pod数少于节点数")
        self.assertGreaterEqual(controller_pod_count, 2, "ssu-controller Pod数不足2个，不存在主备")
        self.logInfo(f"集群节点数: {node_count}, csi-node Pod数: {node_pod_count}, controller Pod数: {controller_pod_count}")

        self.logStep("S2.重启os，环境重启后等待30s查看组建状态")
        for node in self.nodes:
            self.run_on_node(node, "reboot")
        for node in self.nodes:
            for _ in range(60):
                try:
                    result = node.run({"command": ["echo ok"], "timeout": 10})
                    if result.get("rc") == 0:
                        break
                except Exception:
                    pass
                time.sleep(10)
            else:
                self.assertTrue(False, f"节点 {node} 重启后SSH无法连接")
        time.sleep(30)

        self.logStep("E2.环境重启成功")

        self.logStep("S3.查看csi-ssu-driver和ssu-controller组件组件状态")
        self.logStep("E3.csi-ssu-driver和ssu-controller组件被重新拉起，状态正常")
        self._check_plugins_status()

    def teardown_method(self) -> None:
        pass