#!/usr/local/python

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction03(KubernetesBaseCase):
    """验证业务容器可以自动挂载、使用、卸载已创建成功的不同nsnum的组逻辑卷.

    CaseNumber:
        test_k8s_ssu_function_03
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证线性文件系统卷和条带块设备卷的挂载、读写及解挂载
    PreCondition:
        P1.K8s、ssu-controller、csi-ssu-driver安装完成且功能正常，存储节点正常
    TestStep:
        S1.创建2个3Gi、nsnum为3的组逻辑卷PVC，分别使用线性顺序和条带分布策略
        S2.创建2个业务Pod并分别引用文件系统PVC和块设备PVC
        S3.在业务Pod中使用系统调用读写存储
        S4.删除业务Pod，检查PV信息和卷解挂载结果
    ExpectedResult:
        E1.ssu-controller调用UBSE创建组逻辑卷成功
        E2.业务Pod创建成功，csi-ssu-driver将设备发布到Pod内
        E3.文件系统卷和块设备卷读写成功
        E4.Pod删除后卷自动Unpublish、Unstage，PV仍保持正常
    Author:
        luzeren
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_03"
        self.pvc_yaml_name = "scenario-2-pvcs.yaml"
        self.pod_yaml_name = "scenario-2-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_03"
        )
        self.linear_pvc = "ssu-s2-linear-three-ns-pvc"
        self.striped_pvc = "ssu-s2-striped-three-ns-pvc"
        self.linear_pod, self.striped_pod = "ssu-s2-linear-workload", "ssu-s2-striped-workload"

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.检查K8s、ssu-controller、csi-ssu-driver及存储节点状态")
        self.locate_plugins()
        self.upload_yaml_files()
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P1", type="Functional")
    def test_k8s_ssu_function_03(self) -> None:
        self.logStep("S1.创建两个3Gi、nsnum为3的线性和条带组逻辑卷PVC")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")
        pvc_declarations = self.run_master(
            f"kubectl get pvc {self.linear_pvc} {self.striped_pvc} "
            "-o custom-columns=NAME:.metadata.name,SIZE:.spec.resources.requests.storage,"
            "MODE:.spec.volumeMode --no-headers"
        )
        self.assertIn(f"{self.linear_pvc}", pvc_declarations, "未创建线性PVC声明")
        self.assertIn(f"{self.striped_pvc}", pvc_declarations, "未创建条带PVC声明")

        self.logStep("S2.创建两个业务Pod并引用对应PVC")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml}")
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=300s "
            f"pod/{self.linear_pod} pod/{self.striped_pod}",
            timeout=360,
        )
        self.linear_pv, self.linear_volume_id = self.bound_volume(self.linear_pvc, "Filesystem")
        self.striped_pv, self.striped_volume_id = self.bound_volume(self.striped_pvc, "Block")
        linear_context = self.run_master(
            f"kubectl get pv {self.linear_pv} "
            "-o jsonpath='{.spec.csi.volumeAttributes.nsnum}|"
            "{.spec.csi.volumeAttributes.allocStrategy}'"
        )
        self.assertEqual(linear_context, "3|1", "线性卷PV未记录三Namespace顺序策略")
        striped_context = self.run_master(
            f"kubectl get pv {self.striped_pv} "
            "-o jsonpath='{.spec.csi.volumeAttributes.nsnum}|"
            "{.spec.csi.volumeAttributes.allocStrategy}|"
            "{.spec.csi.volumeAttributes.raidLevel}|"
            "{.spec.csi.volumeAttributes.chunkSize}'"
        )
        self.assertEqual(striped_context, "3|0|0|64", "条带卷PV未记录三Namespace分布式策略")
        self.linear_node = self.run_master(
            f"kubectl get pod {self.linear_pod} -o jsonpath='{{.spec.nodeName}}'"
        )
        self.striped_node = self.run_master(
            f"kubectl get pod {self.striped_pod} -o jsonpath='{{.spec.nodeName}}'"
        )

        self.logStep("E1.ssu-controller调用UBSE创建两个组逻辑卷成功")
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        for volume_id in (self.linear_volume_id, self.striped_volume_id):
            self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_id)

        self.logStep("E2.csi-ssu-driver将文件系统和块设备发布到业务Pod内")
        self.run_master(f"kubectl exec {self.linear_pod} -- test -d /data")
        self.run_master(f"kubectl exec {self.striped_pod} -- test -b /dev/ssu-volume")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        self.assert_log_event(
            node_logs, "NodePublishVolume completed (mount mode)", self.linear_volume_id
        )
        self.assert_log_event(
            node_logs, "NodePublishVolume completed (block mode)", self.striped_volume_id
        )

        self.logStep("S3.在业务Pod中使用系统调用读写存储设备")
        self.run_master(
            f"kubectl exec {self.linear_pod} -- sh -c '"
            "payload=ssu-filesystem-io-check; printf %s \"$payload\" > /data/io-test; "
            "sync; readback=$(cat /data/io-test); test \"$readback\" = \"$payload\"'"
        )
        self.run_master(
            f"kubectl exec {self.striped_pod} -- sh -c '"
            "payload=ssu-block-io-check; printf %s \"$payload\" | "
            "dd of=/dev/ssu-volume bs=1 seek=1048576 conv=fsync,notrunc 2>/tmp/dd-write.log; "
            "readback=$(dd if=/dev/ssu-volume bs=1 skip=1048576 count=18 2>/tmp/dd-read.log); "
            "test \"$readback\" = \"$payload\"'"
        )
        self.logStep("E3.文件系统卷与块设备卷写入后均可读取并校验原始内容")

        self.logStep("S4.删除业务Pod并检查PV信息和卷解挂载结果")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} --wait=true --timeout=300s",
            timeout=360,
        )
        pv_output = self.run_master(
            f"kubectl get pv {self.linear_pv} {self.striped_pv} -o wide"
        )
        self.logInfo(f"业务Pod删除后的PV信息:\n{pv_output}")
        for pv_name in (self.linear_pv, self.striped_pv):
            phase = self.run_master(
                f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"
            )
            self.assertEqual(phase, "Bound", f"Pod删除后PV {pv_name}状态异常")

        self.logStep("E4.Pod删除后卷完成Unpublish和Unstage，PV信息保持正常")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        for volume_id in (self.linear_volume_id, self.striped_volume_id):
            self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_id)
            self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_id)

    def teardown_method(self) -> None:
        self.delete_resources(check=False)