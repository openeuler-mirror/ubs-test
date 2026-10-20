#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction05(KubernetesBaseCase):
    """验证不同节点多个容器可以共享自己NS下的普通SSU卷.

    CaseNumber:
        test_k8s_ssu_function_05
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证不同节点多个容器可以共享自己NS下的普通SSU卷
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.创建1个PVC，声明所需卷的size大小为1G，是Block模式
        S2.在相同节点创建2个相同的namespace业务容器，yaml声明引用创建的一个pvc
        S3.再在其他节点创建1个相同的namespace容器，yaml声明引用之前容器创建使用的一个pvc
        S4.在所有容器的挂载目录创建文件进行读写
        S5.再在其他节点创建1个不相同的namespace容器，yaml声明引用之前容器创建使用的一个pvc
        S6.删除所有容器和pvc
    ExpectedResult:
        E1.ssu-controller调用ubse创建卷成功
        E2.容器操作成功，csi-ssu-driver将设备挂载到pod内
        E3.容器操作成功，csi-ssu-driver将设备挂载到pod内
        E4.容器内存读写存储都读写可以成功，读写可体现出是共享卷
        E5.容器创建失败，有相应的报错信息
        E6.删除容器和pvc成功
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_05"
        self.pvc_yaml_name = "scenario-6-pvcs.yaml"
        self.pod_yaml_name = "scenario-6-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_05"
        )
        self.pvc_name = "ssu-s5-shared-block-pvc"
        self.secondary_namespace = "ssu-s5-secondary"
        self.same_node_pods = ("ssu-s5-block-1", "ssu-s5-block-2")
        self.cross_node_pod = "ssu-s5-block-3"
        self.cross_ns_pod = "ssu-s5-block-4"

    def _assert_same_node(self, first_pod: str, second_pod: str) -> str:
        nodes = tuple(
            self.run_master(
                f"kubectl get pod {first_pod} {second_pod} "
                "-o jsonpath='{range .items[*]}{.spec.nodeName}{\"\\n\"}{end}'"
            ).splitlines()
        )
        self.assertEqual(len(nodes), 2, "未获取到两个业务Pod的节点信息")
        self.assertTrue(nodes[0], f"Pod {first_pod}尚未调度")
        self.assertEqual(nodes[0], nodes[1], "两个业务Pod未部署在同一节点")
        return nodes[0]

    def _assert_different_node(self, first_pod: str, second_pod: str) -> None:
        nodes = tuple(
            self.run_master(
                f"kubectl get pod {first_pod} {second_pod} "
                "-o jsonpath='{range .items[*]}{.spec.nodeName}{\"\\n\"}{end}'"
            ).splitlines()
        )
        self.assertEqual(len(nodes), 2, "未获取到两个业务Pod的节点信息")
        self.assertTrue(nodes[0], f"Pod {first_pod}尚未调度")
        self.assertTrue(nodes[1], f"Pod {second_pod}尚未调度")
        self.assertNotEqual(nodes[0], nodes[1], "两个业务Pod应部署在不同节点")

    def _assert_shared_block(self, writer: str, reader: str, payload: str) -> None:
        count = len(payload)
        self.run_master(
            f"kubectl exec {writer} -- sh -c '"
            f"printf %s {payload} | dd of=/dev/ssu-volume bs=1 seek=1048576 "
            f"conv=fsync,notrunc 2>/tmp/dd-write.log'"
        )
        self.run_master(
            f"kubectl exec {reader} -- sh -c '"
            f"readback=$(dd if=/dev/ssu-volume bs=1 skip=1048576 count={count} "
            f"2>/tmp/dd-read.log); test \"$readback\" = {payload}'"
        )

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.检查K8s、ssu-controller、csi-ssu-driver及存储节点状态")
        self.locate_plugins()
        self.upload_yaml_files()
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P2", type="Functional")
    def test_k8s_ssu_function_05(self) -> None:
        self.logStep("S1.创建1个PVC，声明所需卷的size大小为1G，是Block模式")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")

        self.logStep("S2.在相同节点创建2个相同的namespace业务容器，yaml声明引用创建的一个pvc")
        self.run_master(
            f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=same-node"
        )
        ready_pods = " ".join(f"pod/{pod}" for pod in self.same_node_pods)
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s {ready_pods}",
            timeout=120,
        )

        self.logStep("E1.ssu-controller调用ubse创建卷成功")
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Bound "
            f"--timeout=100s pvc/{self.pvc_name}",
            timeout=120,
        )
        pvc_info = self.run_master(
            f"kubectl get pvc {self.pvc_name} "
            "-o jsonpath='{.spec.volumeName}|{.spec.resources.requests.storage}|"
            "{.spec.volumeMode}'"
        )
        pvc_fields = pvc_info.split("|")
        self.assertEqual(len(pvc_fields), 3, f"PVC信息格式异常: {pvc_info}")
        self.assertEqual(pvc_fields[1], "1Gi", f"PVC {self.pvc_name}申请容量不正确")
        self.assertEqual(pvc_fields[2], "Block", f"PVC {self.pvc_name}使用模式不正确")
        pv_info = self.run_master(
            f"kubectl get pv {pvc_fields[0]} "
            "-o jsonpath='{.spec.csi.driver}|{.spec.csi.volumeHandle}|"
            "{.status.phase}'"
        )
        pv_fields = pv_info.split("|")
        self.assertEqual(len(pv_fields), 3, f"PV信息格式异常: {pv_info}")
        self.assertEqual(pv_fields[0], "csi.unifiedbus.com", f"PV {pvc_fields[0]} CSI驱动不正确")
        self.assertTrue(pv_fields[1], f"PV {pvc_fields[0]} 的volumeHandle为空")
        self.assertEqual(pv_fields[2], "Bound", f"PV {pvc_fields[0]} 未处于Bound状态")
        pv_name = pvc_fields[0]
        volume_id = pv_fields[1]
        self.logInfo(f"PVC {self.pvc_name}对应PV信息: {pv_info}")
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_id)

        self.logStep("E2.容器操作成功，csi-ssu-driver将设备挂载到pod内")
        self._assert_same_node(*self.same_node_pods)
        for pod in (*self.same_node_pods, self.cross_node_pod):
            self.run_master(f"kubectl exec {pod} -- test -b /dev/ssu-volume")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        self.assert_log_event(
            node_logs, "NodePublishVolume completed (block mode)", volume_id
        )

        self.logStep(
            "S3.再在其他节点创建1个相同的namespace容器，yaml声明引用之前容器创建使用的一个pvc"
        )
        self.run_master(
            f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=cross-node"
        )
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s pod/{self.cross_node_pod}",
            timeout=120,
        )
        self._assert_different_node(self.same_node_pods[0], self.cross_node_pod)

        self.logStep("E3.容器操作成功，csi-ssu-driver将设备挂载到pod内")

        self.logStep("S4.在所有容器的挂载目录创建文件进行读写")
        self.logStep("E4.容器内存读写存储都读写可以成功，读写可体现出是共享卷")
        self._assert_shared_block(
            self.same_node_pods[0], self.same_node_pods[1], "ssu-shared-from-pod1"
        )
        self._assert_shared_block(
            self.same_node_pods[0], self.cross_node_pod, "ssu-shared-from-pod1"
        )
        self._assert_shared_block(
            self.cross_node_pod, self.same_node_pods[0], "ssu-shared-from-pod3"
        )

        self.logStep(
            "S5.再在其他节点创建1个不相同的namespace容器，yaml声明引用之前容器创建使用的一个pvc"
        )
        self.run_master(
            f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=cross-ns"
        )

        self.logStep("E5.容器创建失败，有相应的报错信息")
        self.run_master(
            f"kubectl wait -n {self.secondary_namespace} "
            f"--for=jsonpath='{{.status.phase}}'=Pending "
            f"--timeout=60s pod/{self.cross_ns_pod}",
            timeout=120,
        )

        self.logStep("S6.删除所有容器和pvc")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=cross-ns "
            "--wait=true --timeout=300s",
            timeout=360,
        )
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=cross-node "
            "--wait=true --timeout=300s",
            timeout=360,
        )
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=same-node "
            "--wait=true --timeout=300s",
            timeout=360,
        )
        self.run_master(
            f"kubectl delete -f {self.remote_pvc_yaml} --wait=true --timeout=300s",
            timeout=360,
        )

        self.logStep("E6.删除容器和pvc成功")
        self.run_master(
            f"kubectl wait --for=delete --timeout=300s pv/{pv_name}",
            timeout=360,
        )

    def teardown_method(self) -> None:
        self.delete_resources(check=False)
