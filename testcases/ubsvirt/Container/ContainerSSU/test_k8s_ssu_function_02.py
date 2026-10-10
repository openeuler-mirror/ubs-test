#!/usr/local/python

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction02(KubernetesBaseCase):
    """验证业务容器可以自动挂载、使用、卸载已创建成功的块设备与文件系统卷.

    CaseNumber:
        test_k8s_ssu_function_02
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证普通文件系统卷和块设备卷的挂载、读写及解挂载
    PreCondition:
        P1.K8s、ssu-controller、csi-ssu-driver安装完成且功能正常，存储节点正常
    TestStep:
        S1.创建两个1Gi普通卷PVC，分别使用Filesystem和Block模式
        S2.创建两个业务Pod并分别引用对应PVC
        S3.在两个业务Pod中使用系统调用读写存储
        S4.删除两个业务Pod，检查PV信息和卷解挂载结果
    ExpectedResult:
        E1.ssu-controller调用UBSE创建卷成功
        E2.业务Pod创建成功，csi-ssu-driver将设备发布到Pod内并打印成功日志
        E3.文件系统卷和块设备卷读写成功
        E4.Pod删除后卷自动Unpublish、Unstage，PV正常并打印成功日志
    Author:
        luzeren
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_02"
        self.pvc_yaml_name = "scenario-3-pvcs.yaml"
        self.pod_yaml_name = "scenario-3-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_02"
        )
        self.filesystem_pvc = "ssu-s3-normal-filesystem-pvc"
        self.block_pvc = "ssu-s3-normal-block-pvc"
        self.filesystem_pod = "ssu-s3-filesystem-workload"
        self.block_pod = "ssu-s3-block-workload"

    def _bound_volume(self, pvc_name: str, expected_mode: str) -> tuple[str, str, str]:
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Bound "
            f"--timeout=300s pvc/{pvc_name}",
            timeout=360,
        )
        pvc_info = self.run_master(
            f"kubectl get pvc {pvc_name} "
            "-o jsonpath='{.spec.volumeName}|{.spec.resources.requests.storage}|"
            "{.spec.volumeMode}'"
        )
        pvc_fields = pvc_info.split("|")
        self.assertEqual(len(pvc_fields), 3, f"PVC信息格式异常: {pvc_info}")
        self.assertEqual(pvc_fields[1], "1Gi", f"PVC {pvc_name}申请容量不正确")
        self.assertEqual(pvc_fields[2], expected_mode, f"PVC {pvc_name}使用模式不正确")
        pv_info = self.run_master(
            f"kubectl get pv {pvc_fields[0]} "
            "-o jsonpath='{.spec.csi.driver}|{.spec.csi.volumeHandle}|"
            "{.spec.csi.volumeAttributes.deviceID}|{.status.phase}'"
        )
        pv_fields = pv_info.split("|")
        self.assertEqual(len(pv_fields), 4, f"PV信息格式异常: {pv_info}")
        self.assertEqual(pv_fields[0], "csi.unifiedbus.com", "PV的CSI驱动不正确")
        self.assertTrue(pv_fields[1], f"PV {pvc_fields[0]}的volumeHandle为空")
        self.assertTrue(pv_fields[2], f"PV {pvc_fields[0]}的deviceID为空")
        self.assertEqual(pv_fields[3], "Bound", f"PV {pvc_fields[0]}未处于Bound状态")
        return pvc_fields[0], pv_fields[1], pv_fields[2]

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.检查K8s、ssu-controller、csi-ssu-driver及存储节点状态")
        storage_class = self.run_master(
            "kubectl get storageclass ub-ssu-csi "
            "-o jsonpath='{.provisioner}|{.volumeBindingMode}'"
        )
        self.assertTrue(storage_class.startswith("csi.unifiedbus.com|"), "ub-ssu-csi配置异常")
        self.locate_plugins()
        self.upload_yaml_files()
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P1", type="Functional")
    def test_k8s_ssu_function_02(self) -> None:
        self.logStep("S1.创建两个1Gi普通卷PVC，分别使用Filesystem和Block模式")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")
        pvc_declarations = self.run_master(
            f"kubectl get pvc {self.filesystem_pvc} {self.block_pvc} "
            "-o custom-columns=NAME:.metadata.name,SIZE:.spec.resources.requests.storage,"
            "MODE:.spec.volumeMode --no-headers"
        )
        self.assertIn(self.filesystem_pvc, pvc_declarations, "未创建Filesystem PVC声明")
        self.assertIn(self.block_pvc, pvc_declarations, "未创建Block PVC声明")

        self.logStep("S2.创建两个业务Pod并引用对应PVC")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml}")
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=300s "
            f"pod/{self.filesystem_pod} pod/{self.block_pod}",
            timeout=360,
        )
        filesystem_pv, filesystem_volume_id, filesystem_device_id = self._bound_volume(
            self.filesystem_pvc, "Filesystem"
        )
        block_pv, block_volume_id, block_device_id = self._bound_volume(self.block_pvc, "Block")
        filesystem_node = self.run_master(
            f"kubectl get pod {self.filesystem_pod} -o jsonpath='{{.spec.nodeName}}'"
        )
        block_node = self.run_master(
            f"kubectl get pod {self.block_pod} -o jsonpath='{{.spec.nodeName}}'"
        )

        self.logStep("E1.ssu-controller调用UBSE创建两个普通卷成功")
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        for volume_id in (filesystem_volume_id, block_volume_id):
            self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_id)

        self.logStep("E2.csi-ssu-driver将文件系统和块设备发布到Pod内并打印成功日志")
        self.run_master(f"kubectl exec {self.filesystem_pod} -- test -d /data")
        self.run_master(f"kubectl exec {self.block_pod} -- test -b /dev/ssu-volume")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        self.assert_log_event(
            node_logs, "NodePublishVolume completed (mount mode)", filesystem_volume_id
        )
        self.assert_log_event(
            node_logs, "NodePublishVolume completed (block mode)", block_volume_id
        )

        self.logStep("S3.在两个业务Pod中使用系统调用读写存储设备")
        self.run_master(
            f"kubectl exec {self.filesystem_pod} -- sh -c '"
            "payload=ssu-filesystem-io-check; printf %s \"$payload\" > /data/io-test; "
            "sync; readback=$(cat /data/io-test); test \"$readback\" = \"$payload\"'"
        )
        self.run_master(
            f"kubectl exec {self.block_pod} -- sh -c '"
            "payload=ssu-block-io-check; printf %s \"$payload\" | "
            "dd of=/dev/ssu-volume bs=1 seek=1048576 conv=fsync,notrunc 2>/tmp/dd-write.log; "
            "readback=$(dd if=/dev/ssu-volume bs=1 skip=1048576 count=18 2>/tmp/dd-read.log); "
            "test \"$readback\" = \"$payload\"'"
        )
        self.logStep("E3.两个业务Pod写入后均可读取并校验原始内容")

        self.logStep("S4.删除两个业务Pod并检查PV信息和卷解挂载结果")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} --wait=true --timeout=300s",
            timeout=360,
        )
        pv_output = self.run_master(f"kubectl get pv {filesystem_pv} {block_pv} -o wide")
        self.logInfo(f"业务Pod删除后的PV信息:\n{pv_output}")
        for pv_name in (filesystem_pv, block_pv):
            phase = self.run_master(
                f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"
            )
            self.assertEqual(phase, "Bound", f"Pod删除后PV {pv_name}状态异常")

        self.logStep("E4.Pod删除后卷完成Unpublish和Unstage，PV正常且日志存在成功打印")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        for volume_id in (filesystem_volume_id, block_volume_id):
            self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_id)
            self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_id)

    def teardown_method(self) -> None:
        self.delete_resources(check=False)
