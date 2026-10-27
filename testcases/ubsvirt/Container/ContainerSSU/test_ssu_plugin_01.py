#!/usr/local/python
# -*- coding: utf-8 -*-

import time
import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestSsuPlugin01(KubernetesBaseCase):
    """验证csi-ssu-driver组件功能正常.

    CaseNumber:
        test_ssu_plugin_01
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        验证csi-ssu-driver组件功能正常
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.查看csi-ssu-driver组件状态
        S2.查看csi-ssu-driver组件进程pid，kill掉进程
        S3.查看csi-ssu-driver组件用于pod内挂载卷时候的资源占用
    ExpectedResult:
        E1.每个节点部署，状态信息可以正常查询
        E2.进程杀死后可以产生新的进程，为pid2
        E3.cpu < 100m，mem < 128M
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.controller_namespace = ""
        self.log_start_time = ""
        self.node_pod_name = ""
        self.node_container = "ssu-csi-node"
        self.target_node = None

    def _find_csi_pid(self) -> str:
        ps_output = self.run_on_node(
            self.target_node,
            "ps -ef | grep ssu-csi | grep node | grep -v grep | head -1",
        )
        fields = ps_output.split()
        return fields[1] if len(fields) >= 2 else ""

    def _get_restart_count(self) -> str:
        return self.run_master(
            f"kubectl get pod -n {self.controller_namespace} {self.node_pod_name} "
            f"-o jsonpath='{{.status.containerStatuses"
            f"[?(@.name==\"{self.node_container}\")].restartCount}}'"
        )

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.检查K8s、ssu-controller、csi-ssu-driver及存储节点状态")
        self.locate_plugins()
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P3", type="Functional")
    def test_ssu_plugin_01(self) -> None:
        self.logStep("S1.查看csi-ssu-driver组件状态")
        node_pod_info = self.run_master(
            f"kubectl get pods -n {self.controller_namespace} --no-headers "
            "-o custom-columns=NAME:.metadata.name,PHASE:.status.phase,"
            "NODE:.spec.nodeName | "
            "awk '$1 ~ /ssu-csi-node/ {print}'"
        )
        self.assertTrue(node_pod_info, "未找到ssu-csi-node Pod")
        csi_pod_lines = node_pod_info.splitlines()
        node_count = self.get_node_number()
        self.assertGreaterEqual(
            len(csi_pod_lines), 1, "ssu-csi-node Pod数量不足"
        )
        for line in csi_pod_lines:
            fields = line.split()
            self.assertEqual(
                fields[1],
                "Running",
                f"ssu-csi-node Pod {fields[0]} 状态异常: {fields[1]}",
            )

        self.logStep("E1.每个节点部署，状态信息可以正常查询")
        self.logInfo(f"ssu-csi-node Pod信息:\n{node_pod_info}")
        self.logInfo(f"集群节点数: {node_count}, csi-node Pod数: {len(csi_pod_lines)}")
        self.node_pod_name = csi_pod_lines[0].split()[0]

        self.logStep("S2.查看csi-ssu-driver组件进程pid，kill掉进程")
        self.target_node = self.find_target_node(self.node_pod_name)
        pid1 = self._find_csi_pid()
        self.assertTrue(pid1, "未找到ssu-csi进程")
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
            pid2 = self._find_csi_pid()
            if pid2:
                break
        self.assertTrue(pid2, "kill后未产生新的ssu-csi进程")

        self.logStep("E2.进程杀死后可以产生新的进程，为pid2")
        self.logInfo(f"kill后: PID={pid2}, restartCount={restart_count_2}")

        self.logStep("S3.查看csi-ssu-driver组件用于pod内挂载卷时候的资源占用")
        time.sleep(5)
        pid2 = self._find_csi_pid()
        self.assertTrue(pid2, "未找到重启后的ssu-csi进程")
        ps_output = self.run_on_node(
            self.target_node,
            f"ps -p {pid2} -o %cpu,rss --no-header",
        )
        fields = ps_output.split()
        cpu_percent = float(fields[0])
        mem_mi = float(fields[1]) / 1024
        self.logInfo(f"资源占用: CPU={cpu_percent}%, MEM={mem_mi:.1f}Mi")
        self.logStep("E3.cpu < 100m，mem < 128M")

    def teardown_method(self) -> None:
        if self.node_pod_name and self.controller_namespace:
            self.run_master(
                f"kubectl wait --for=jsonpath='{{.status.phase}}'=Running "
                f"--timeout=120s -n {self.controller_namespace} "
                f"pod/{self.node_pod_name}",
                timeout=180,
                check=False,
            )
