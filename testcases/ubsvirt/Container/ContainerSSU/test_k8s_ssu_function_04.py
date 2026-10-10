#!/usr/local/python

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction04(KubernetesBaseCase):
    """验证同节点的多个业务容器可以共享同一个NS的组逻辑卷

    CaseNumber:
        test_k8s_ssu_function_04
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证普通文件系统卷和块设备卷的挂载、读写及解挂载
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.创建1个线性编址组逻辑卷PVC A和条带编址组逻辑卷B，A声明所需卷的size大小为1G，nsnum为1；另一个B声明所需卷的size大小为3G，nsnum为3
        S2.创建4个业务容器，pod1和pod2个容器yaml声明引用创建的PVC A，部署在同一个节点
        S3.另外2个容器pod3和pod4的yaml声明引用创建的PVC B，部署在同一个节点，但是pod3和pod4的namespace不一致。
        S4.在业务容器pod1和pod2中使用系统调用读写存储设备
        S5.删除所有的业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常
        S6.在同一Namespace创建共享条带卷B的Pod3和Pod4
        S7.在业务容器pod3和pod4中使用系统调用读写存储设备
        S8.删除所有的业务容器、PVC及其动态PV
    ExpectedResult:
        E1.ssu-controller调用ubse创建组逻辑卷成功
        E2.pod1和pod2容器操作成功， csi-ssu-driver将设备挂载到pod内，为共享的设备
        E3.pod3和pod4只有一个容器操作成功， csi-ssu-driver将设备挂载到pod内，不支持pod跨k8s的Namespace共享一个卷，存在报错信息
        E4.pod1和pod2容器内存读写存储都读写可以成功，读写可体现出是共享卷
        E5.业务容器删除后可以自动解挂载使用的块设备卷与文件系统卷，卷信息正常
        E6.pod3和pod4都拉起成功， csi-ssu-driver将设备挂载到pod内，同k8s的Namespace的pod共享一个卷
        E7.pod3和pod4容器内存读写存储都读写可以成功，读写可体现出是共享卷
        E8.删除成功
    Author:
        luzeren
    """
    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_04"
        self.pvc_yaml_name, self.pod_yaml_name = "scenario-4-pvcs.yaml", "scenario-4-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parents[4] / "resource/ubsvirt/yaml/test_k8s_ssu_function_04"
        )
        self.linear_pvc = "ssu-s4-linear-shared-pvc"
        self.striped_pvc = "ssu-s4-striped-shared-pvc"
        self.linear_pods = "ssu-s4-linear-1", "ssu-s4-linear-2"
        self.striped_pods = "ssu-s4-striped-3", "ssu-s4-striped-4"
        self.secondary_namespace = "ssu-s4-secondary"

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

    @pytest.mark.case_info(level="P1", type="Functional")
    def test_k8s_ssu_function_04(self) -> None:
        self.logStep("S1.创建1个线性编址组逻辑卷PVC A和条带编址组逻辑卷B，A声明所需卷的size大小为1G，nsnum为1；另一个B声明所需卷的size大小为3G，nsnum为3")
        self.logStep("E1.ssu-controller调用ubse创建组逻辑卷成功")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")

        self.logStep("S2.创建4个业务容器，pod1和pod2个容器yaml声明引用创建的PVC A，部署在同一个节点")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=initial")
        self.logStep("E2.pod1和pod2容器操作成功， csi-ssu-driver将设备挂载到pod内，为共享的设备")
        ready_pods = " ".join(f"pod/{pod}" for pod in (*self.linear_pods, *self.striped_pods[:1]))
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=300s {ready_pods}", timeout=360
        )
        self.logStep("S3.另外2个容器pod3和pod4的yaml声明引用创建的PVC B，部署在同一个节点，但是pod3和pod4的namespace不一致。")
        self.logStep("E3.pod3和pod4只有一个容器操作成功， csi-ssu-driver将设备挂载到pod内，不支持pod跨k8s的Namespace共享一个卷，存在报错信息")
        self.run_master(
            f"kubectl wait -n {self.secondary_namespace} --for=jsonpath='{{.status.phase}}'=Pending "
            f"--timeout=60s pod/{self.striped_pods[1]}"
        )
        linear_pv, linear_volume = self.bound_volume(self.linear_pvc, "1Gi")
        striped_pv, striped_volume = self.bound_volume(self.striped_pvc, "3Gi")
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        for volume_id in (linear_volume, striped_volume):
            self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_id)
        for pod in (*self.linear_pods, *self.striped_pods[:1]):
            self.run_master(f"kubectl exec {pod} -- test -d /data")

        self.logStep("S4.在业务容器pod1和pod2中使用系统调用读写存储设备")
        self.logStep("E4.pod1和pod2容器内存读写存储都读写可以成功，读写可体现出是共享卷")
        self._assert_shared_file(*self.linear_pods, "linear-from-pod1")
        self._assert_shared_file(self.linear_pods[1], self.linear_pods[0], "linear-from-pod2")

        self.logStep("S5.删除所有的业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=initial "
            "--wait=true --timeout=300s",
            timeout=360,
        )
        self.logStep("E5.业务容器删除后可以自动解挂载使用的块设备卷与文件系统卷，卷信息正常")
        for pv_name in (linear_pv, striped_pv):
            self.assertEqual(
                self.run_master(f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"),
                "Bound",
                f"Pod删除后PV {pv_name}状态异常",
            )
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        for volume_id in (linear_volume, striped_volume):
            self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_id)
            self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_id)

        self.logStep("S6.再把2个容器pod3和pod4的yaml声明引用创建的PVC B，部署在同一个节点，pod3和pod4的namespace一致，创建容器")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=same")
        self.logStep("E6.pod3和pod4都拉起成功， csi-ssu-driver将设备挂载到pod内，同k8s的Namespace的pod共享一个卷")
        same_pods = " ".join(f"pod/{pod}" for pod in self.striped_pods)
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=300s {same_pods}", timeout=360
        )
        self._assert_same_node(*self.striped_pods)
        for pod in self.striped_pods:
            self.run_master(f"kubectl exec {pod} -- test -d /data")

        self.logStep("S7.在Pod3和Pod4中交叉读写条带共享卷")
        self.logStep("E7.pod3和pod4容器内存读写存储都读写可以成功，读写可体现出是共享卷")
        self._assert_shared_file(*self.striped_pods, "striped-from-pod3")
        self._assert_shared_file(self.striped_pods[1], self.striped_pods[0], "striped-from-pod4")

        self.logStep("S8.删除容器和pvc")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=same "
            "--wait=true --timeout=300s",
            timeout=360,
        )
        self.run_master(
            f"kubectl delete -f {self.remote_pvc_yaml} --wait=true --timeout=300s",
            timeout=360,
        )
        self.logStep("E8.删除成功")
        pv_resources = " ".join(f"pv/{pv}" for pv in (linear_pv, striped_pv))
        self.run_master(f"kubectl wait --for=delete --timeout=300s {pv_resources}", timeout=360)

    def teardown_method(self) -> None:
        self.delete_resources(check=False)
