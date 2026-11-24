#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction08(KubernetesBaseCase):
    """验证不同节点和不同namespace的多个业务容器不能共享同一个的NS的组逻辑卷

    CaseNumber:
        test_k8s_ssu_function_08
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证不同节点和不同namespace的多个业务容器不能共享同一个的NS的组逻辑卷
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.创建1个线性编址组逻辑卷PVC A和条带化编址组逻辑卷B，A声明所需卷的size大小为1G，nsnum为1；另一个B声明所需卷size大小为3G，nsnum为3
        S2.创建4个业务容器，pod1和pod2 2个容器yaml声明引用创建的PVC A，部署在不同节点
        S3.另外2个容器pod3和pod4的yaml声明引用创建的PVC B，部署在不同节点，但是pod3和pod4的namespace不一致
        S4.删除业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常
        S5.另外2个容器pod3和pod4的yaml引用创建的PVC B，部署在不同节点，但是pod3和pod4的namespace一致，创建容器
        S6.删除容器和PVC
    ExpectedResult:
        E1.ssu-controller调用ubse创建组逻辑卷成功
        E2.pod1和pod2容器创建只有一个成功，不支持pod跨节点共享组逻辑卷，存在报错信息
        E3.pod3和pod4容器创建只有一个成功，不支持pod跨节点和跨namespace共享组逻辑卷，存在报错信息
        E4.业务容器删除后可以自动解挂载使用的卷，卷信息正常
        E5.业务容器删除后可以自动解挂载使用的卷，卷信息正常
        E5.pod3和pod4容器创建只有一个成功，不支持pod跨节点共享组逻辑卷
        E6.删除成功
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_08"
        self.pvc_yaml_name = "scenario-8-pvcs.yaml"
        self.pod_yaml_name = "scenario-8-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_08"
        )
        self.linear_pvc = "ssu-s8-linear-pvc"
        self.striped_pvc = "ssu-s8-striped-pvc"
        self.linear_pods = ("ssu-s8-linear-1", "ssu-s8-linear-2")
        self.striped_pods = ("ssu-s8-striped-3", "ssu-s8-striped-4")
        self.secondary_namespace = "ssu-s8-secondary"

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常")
        self.locate_plugins()
        self.upload_yaml_files()
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P2", type="Functional")
    def test_k8s_ssu_function_08(self) -> None:
        self.logStep("S1.创建1个线性编址组逻辑卷PVC A和条带化编址组逻辑卷B，A声明所需卷的size大小为1G，nsnum为1；另一个B声明所需卷size大小为3G，nsnum为3")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")

        self.logStep("S2.创建4个业务容器，pod1和pod2 2个容器yaml声明引用创建的PVC A，部署在不同节点")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=initial")
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s "
            f"pod/{self.linear_pods[0]} pod/{self.striped_pods[0]}",
            timeout=120,
        )
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Pending "
            f"--timeout=60s pod/{self.linear_pods[1]}",
            timeout=120,
        )

        self.logStep("E1.ssu-controller调用ubse创建组逻辑卷成功")
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

        self.logStep("E2.pod1和pod2容器创建只有一个成功，不支持pod跨节点共享组逻辑卷，存在报错信息")
        self.run_master(f"kubectl exec {self.linear_pods[0]} -- test -d /data")

        self.logStep("S3.另外2个容器pod3和pod4的yaml声明引用创建的PVC B，部署在不同节点，但是pod3和pod4的namespace不一致")
        self.logStep("E3.pod3和pod4容器创建只有一个成功，不支持pod跨节点和跨namespace共享组逻辑卷，存在报错信息")
        self.run_master(
            f"kubectl wait -n {self.secondary_namespace} "
            f"--for=jsonpath='{{.status.phase}}'=Pending "
            f"--timeout=60s pod/{self.striped_pods[1]}",
            timeout=120,
        )
        self.run_master(f"kubectl exec {self.striped_pods[0]} -- test -d /data")

        self.logStep("S4.删除业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=initial "
            "--wait=true --timeout=100s",
            timeout=120,
        )
        self.logStep("E4.业务容器删除后可以自动解挂载使用的卷，卷信息正常")
        for pv_name in (pv_a_name, pv_b_name):
            self.assertEqual(
                self.run_master(f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"),
                "Bound",
                f"Pod删除后PV {pv_name}状态异常",
            )
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_a_id)
        self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_a_id)
        self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_b_id)
        self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_b_id)

        self.logStep("S5.另外2个容器pod3和pod4的yaml引用创建的PVC B，部署在不同节点，但是pod3和pod4的namespace一致，创建容器")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=same")
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s pod/{self.striped_pods[0]}",
            timeout=120,
        )
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Pending "
            f"--timeout=60s pod/{self.striped_pods[1]}",
            timeout=120,
        )
        self.logStep("E5.pod3和pod4容器创建只有一个成功，不支持pod跨节点共享组逻辑卷")
        self.run_master(f"kubectl exec {self.striped_pods[0]} -- test -d /data")

        self.logStep("S6.删除容器和PVC")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=same "
            "--wait=true --timeout=100s",
            timeout=120,
        )
        self.run_master(
            f"kubectl delete -f {self.remote_pvc_yaml} --wait=false --timeout=100s",
            timeout=120,
        )
        self.logStep("E6.删除成功")
        pv_resources = f"pv/{pv_a_name} pv/{pv_b_name}"
        self.run_master(
            f"kubectl wait --for=delete --timeout=100s {pv_resources}",
            timeout=120,
            check=False,
        )

    def teardown_method(self) -> None:
        self.delete_resources(check=False)
        self.cleanup_volumes()
