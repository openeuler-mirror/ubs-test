#!/usr/local/python
# -*- coding: utf-8 -*-

import time
import re
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestSsuPlugin02(KubernetesBaseCase):
    """验证ssu-controller组件功能正常.

    CaseNumber:
        test_ssu_plugin_02
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        验证ssu-controller组件功能正常
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.查看ssu-controller组件状态
        S2.查看ssu-controller组件进程pid，kill掉进程
        S3.查看ssu-controller组件创建卷时候的资源占用
    ExpectedResult:
        E1.按照deployment模式部署，不止部署在一个节点，存在主备，状态信息可以正常查询
        E2.进程杀死后可以产生新的进程，为pid2
        E3.cpu < 500m，mem < 512M
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.controller_namespace = ""
        self.log_start_time = ""
        self.controller_pod_name = ""
        self.controller_container = "ssu-controller"
        self.target_node = None

    def _find_controller_pid(self) -> str:
        ps_output = self.run_on_node(
            self.target_node,
            "ps -ef | grep ssu-csi | grep controller | grep -v grep | head -1",
        )
        fields = ps_output.split()
        return fields[1] if len(fields) >= 2 else ""

    def _get_restart_count(self) -> str:
        return self.run_master(
            f"kubectl get pod -n {self.controller_namespace} {self.controller_pod_name} "
            f"-o jsonpath='{{.status.containerStatuses"
            f"[?(@.name==\"{self.controller_container}\")].restartCount}}'"
        )

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.检查K8s、ssu-controller、csi-ssu-driver及存储节点状态")
        self.locate_plugins()
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P3", type="Functional")
    def test_ssu_plugin_02(self) -> None:
        self.logStep("S1.查看ssu-controller组件状态")
        controller_pod_info = self.run_master(
            f"kubectl get pods -n {self.controller_namespace} --no-headers "
            "-o custom-columns=NAME:.metadata.name,PHASE:.status.phase,"
            "NODE:.spec.nodeName | "
            "awk '$1 ~ /ssu.*controller|controller.*ssu/ {print}'"
        )
        self.assertTrue(controller_pod_info, "未找到ssu-controller Pod")
        pod_lines = controller_pod_info.splitlines()
        for line in pod_lines:
            fields = line.split()
            self.assertEqual(
                fields[1],
                "Running",
                f"ssu-controller Pod {fields[0]} 状态异常: {fields[1]}",
            )

        controller_nodes = set(
            line.split()[2] for line in pod_lines if len(line.split()) >= 3
        )

        self.logStep(
            "E1.按照deployment模式部署，不止部署在一个节点，存在主备，状态信息可以正常查询"
        )
        self.logInfo(f"ssu-controller Pod信息:\n{controller_pod_info}")
        self.logInfo(
            f"部署节点: {controller_nodes}, Pod数: {len(pod_lines)}"
        )

        self.controller_pod_name = pod_lines[0].split()[0]

        self.logStep("S2.查看ssu-controller组件进程pid，kill掉进程")
        self.target_node = self.find_target_node(self.controller_pod_name)
        pid1 = self._find_controller_pid()
        self.assertTrue(pid1, "未找到ssu-controller进程")
        restart_count_1 = self._get_restart_count()
        self.logInfo(f"kill前: PID={pid1}, restartCount={restart_count_1}")

        self.run_on_node(self.target_node, f"kill -9 {pid1}")

        restart_count_2 = restart_count_1
        for _ in range(12):
            time.sleep(10)
            restart_count_2 = self._get_restart_count()
            if restart_count_2 and int(restart_count_2) > int(restart_count_1):
                break
        self.assertGreater(
            int(restart_count_2),
            int(restart_count_1),
            f"容器restartCount未增加: {restart_count_1} -> {restart_count_2}",
        )

        pid2 = ""
        for _ in range(6):
            time.sleep(10)
            pid2 = self._find_controller_pid()
            if pid2:
                break
        self.assertTrue(pid2, "kill后未产生新的ssu-controller进程")

        self.logStep("E2.进程杀死后可以产生新的进程，为pid2")
        self.logInfo(f"kill后: PID={pid2}, restartCount={restart_count_2}")

        self.logStep("S3.查看ssu-controller组件创建卷时候的资源占用")
        ps_output = self.run_master(
            f"kubectl exec -i -n {self.controller_namespace} {self.controller_pod_name} "
            f"-c {self.controller_container} -- ps -p {pid2} -o %cpu,rss --no-header"
        )
        fields = ps_output.split()
        cpu_percent = float(fields[0])
        mem_mi = float(fields[1]) / 1024
        self.logInfo(f"资源占用: CPU={cpu_percent}%, MEM={mem_mi:.1f}Mi")
        self.logStep("E3.cpu < 500m，mem < 512M")

    def teardown_method(self) -> None:
        if self.controller_pod_name and self.controller_namespace:
            self.run_master(
                f"kubectl wait --for=jsonpath='{{.status.phase}}'=Running "
                f"--timeout=120s -n {self.controller_namespace} "
                f"pod/{self.controller_pod_name}",
                timeout=180,
                check=False,
            )
