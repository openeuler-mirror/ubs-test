#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestSsuK8sDfx02(KubernetesBaseCase):
    """验证containerd进程的重启不影响ssu卷的创建和容器使用卷.

    CaseNumber:
        test_ssu_k8s_dfx_02
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        验证containerd进程的重启不影响ssu卷的创建和容器使用卷
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.重启所有k8s部署节点的containerd进程
        S2.创建1个逻辑卷PVC A和组逻辑卷PVC B，A声明所需卷的size大小为1G，nsnum为1；另一个B声明所需卷的size大小为3G，nsnum为3
        S3.创建4个容器，pod1和pod2 2个容器yaml声明引用创建的PVC A，namespace一致，pod3和pod4的yaml声明引用创建的PVC B，namespace一致
        S4.尝试删除容器和PVC
    ExpectedResult:
        E1.进程重启成功
        E2.ssu-controller调用ubse创建卷成功
        E3.创建容器操作成功，设备挂载在pod内，为共享的设备
        E4.容器删除成功后，pvc与pv也一并删除成功
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_ssu_k8s_dfx_02"
        self.pvc_yaml_name = "scenario-dfx2-pvcs.yaml"
        self.pod_yaml_name = "scenario-dfx2-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_ssu_k8s_dfx_02"
        )
        self.linear_pvc = "ssu-dfx2-linear-pvc"
        self.striped_pvc = "ssu-dfx2-striped-pvc"
        self.linear_pods = ("ssu-dfx2-linear-1", "ssu-dfx2-linear-2")
        self.striped_pods = ("ssu-dfx2-striped-3", "ssu-dfx2-striped-4")

    def _assert_shared_file(self, writer: str, reader: str, payload: str) -> None:
        self.run_master(
            f"kubectl exec {writer} -- sh -c 'printf %s {payload} > /data/shared-io; sync'"
        )
        self.run_master(
            f"kubectl exec {reader} -- sh -c 'test \"$(cat /data/shared-io)\" = {payload}'"
        )

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常")
        self.locate_plugins()
        self.upload_yaml_files()
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P3", type="Functional")
    def test_ssu_k8s_dfx_02(self) -> None:
        self.logStep("S1.重启所有k8s部署节点的containerd进程")
        for node in self.nodes:
            self.run_on_node(node, "systemctl restart containerd")
        time.sleep(15)

        self.logStep("E1.进程重启成功")
        for node in self.nodes:
            status = self.run_on_node(node, "systemctl is-active containerd")
            self.assertEqual(status.strip(), "active", "containerd重启失败")

        self.logStep("S2.创建1个逻辑卷PVC A和组逻辑卷PVC B，A声明所需卷的size大小为1G，nsnum为1；另一个B声明所需卷的size大小为3G，nsnum为3")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")

        self.logStep("E2.ssu-controller调用ubse创建卷成功")
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Bound "
            f"--timeout=100s pvc/{self.linear_pvc} pvc/{self.striped_pvc}",
            timeout=120,
        )
        pvc_a_info = self.run_master(
            f"kubectl get pvc {self.linear_pvc} "
            "-o jsonpath='{.spec.volumeName}|{.spec.resources.requests.storage}|"
            "{.spec.volumeMode}'"
        )
        pvc_a_fields = pvc_a_info.split("|")
        self.assertEqual(len(pvc_a_fields), 3, f"PVC信息格式异常: {pvc_a_info}")
        self.assertEqual(pvc_a_fields[1], "1Gi", f"PVC {self.linear_pvc}申请容量不正确")
        self.assertEqual(pvc_a_fields[2], "Filesystem", f"PVC {self.linear_pvc}使用模式不正确")
        pv_a_info = self.run_master(
            f"kubectl get pv {pvc_a_fields[0]} "
            "-o jsonpath='{.spec.csi.driver}|{.spec.csi.volumeHandle}|"
            "{.status.phase}'"
        )
        pv_a_fields = pv_a_info.split("|")
        self.assertEqual(len(pv_a_fields), 3, f"PV信息格式异常: {pv_a_info}")
        self.assertEqual(pv_a_fields[0], "csi.unifiedbus.com", f"PV {pvc_a_fields[0]} CSI驱动不正确")
        self.assertTrue(pv_a_fields[1], f"PV {pvc_a_fields[0]} 的volumeHandle为空")
        self.assertEqual(pv_a_fields[2], "Bound", f"PV {pvc_a_fields[0]} 未处于Bound状态")
        pv_a_name = pvc_a_fields[0]
        volume_a_id = pv_a_fields[1]

        pvc_b_info = self.run_master(
            f"kubectl get pvc {self.striped_pvc} "
            "-o jsonpath='{.spec.volumeName}|{.spec.resources.requests.storage}|"
            "{.spec.volumeMode}'"
        )
        pvc_b_fields = pvc_b_info.split("|")
        self.assertEqual(len(pvc_b_fields), 3, f"PVC信息格式异常: {pvc_b_info}")
        self.assertEqual(pvc_b_fields[1], "3Gi", f"PVC {self.striped_pvc}申请容量不正确")
        self.assertEqual(pvc_b_fields[2], "Filesystem", f"PVC {self.striped_pvc}使用模式不正确")
        pv_b_info = self.run_master(
            f"kubectl get pv {pvc_b_fields[0]} "
            "-o jsonpath='{.spec.csi.driver}|{.spec.csi.volumeHandle}|"
            "{.status.phase}'"
        )
        pv_b_fields = pv_b_info.split("|")
        self.assertEqual(len(pv_b_fields), 3, f"PV信息格式异常: {pv_b_info}")
        self.assertEqual(pv_b_fields[0], "csi.unifiedbus.com", f"PV {pvc_b_fields[0]} CSI驱动不正确")
        self.assertTrue(pv_b_fields[1], f"PV {pvc_b_fields[0]} 的volumeHandle为空")
        self.assertEqual(pv_b_fields[2], "Bound", f"PV {pvc_b_fields[0]} 未处于Bound状态")
        pv_b_name = pvc_b_fields[0]
        volume_b_id = pv_b_fields[1]

        self.logInfo(f"PVC A对应PV信息: {pv_a_info}")
        self.logInfo(f"PVC B对应PV信息: {pv_b_info}")
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_a_id)
        self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_b_id)

        self.logStep("S3.创建4个容器，pod1和pod2 2个容器yaml声明引用创建的PVC A，namespace一致，pod3和pod4的yaml声明引用创建的PVC B，namespace一致")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml}")
        ready_pods = " ".join(f"pod/{pod}" for pod in (*self.linear_pods, *self.striped_pods))
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s {ready_pods}",
            timeout=120,
        )

        self.logStep("E3.创建容器操作成功，设备挂载在pod内，为共享的设备")
        for pod in (*self.linear_pods, *self.striped_pods):
            self.run_master(f"kubectl exec {pod} -- test -d /data")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        self.assert_log_event(node_logs, "NodePublishVolume completed (mount mode)", volume_a_id)
        self.assert_log_event(node_logs, "NodePublishVolume completed (mount mode)", volume_b_id)
        self._assert_shared_file(*self.linear_pods, "dfx2-linear-shared")
        self._assert_shared_file(*self.striped_pods, "dfx2-striped-shared")

        self.logStep("S4.尝试删除容器和PVC")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} --wait=true --timeout=100s",
            timeout=120,
        )
        self.run_master(
            f"kubectl delete -f {self.remote_pvc_yaml} --wait=true --timeout=100s",
            timeout=120,
        )

        self.logStep("E4.容器删除成功后，pvc与pv也一并删除成功")
        pv_resources = f"pv/{pv_a_name} pv/{pv_b_name}"
        self.run_master(
            f"kubectl wait --for=delete --timeout=100s {pv_resources}",
            timeout=120,
        )
        pvc_resources = f"pvc/{self.linear_pvc} pvc/{self.striped_pvc}"
        remaining_pvcs = self.run_master(
            f"kubectl get {pvc_resources} --ignore-not-found=true -o name"
        )
        remaining_pvs = self.run_master(
            f"kubectl get {pv_resources} --ignore-not-found=true -o name"
        )
        self.assertEqual(remaining_pvcs, "", f"仍存在未删除PVC: {remaining_pvcs}")
        self.assertEqual(remaining_pvs, "", f"仍存在未删除PV: {remaining_pvs}")

    def teardown_method(self) -> None:
        self.delete_resources(check=False)