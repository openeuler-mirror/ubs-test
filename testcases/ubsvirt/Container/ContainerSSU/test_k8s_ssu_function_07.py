#!/usr/local/python
# -*- coding: utf-8 -*-

import time
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction07(KubernetesBaseCase):
    """验证业务容器可以自动挂载、使用、卸载已创建成功的不同类型的卷后再次挂载不丢数据

    CaseNumber:
        test_k8s_ssu_function_07
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证业务容器可以自动挂载、使用、卸载已创建成功的不同类型的卷后再次挂载不丢数据
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.创建2个逻辑卷PVC，A声明所需卷的size大小为3G，nsnum为3；一个为线性编址加顺序策略，一个是条带化编址加分布式策略
        S2.创建2个PVC，声明所需卷size大小为1G，一个为文件系统使用模式，一个是块设备使用模式
        S3.创建4个业务容器，yaml声明引用创建的PVC
        S4.在业务容器中使用系统调用读写存储设备
        S5.删除业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常
        S6.再次创建4个业务容器，yaml声明引用创建的PVC，读取之前写进卷的数据
        S7.删除业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常
    ExpectedResult:
        E1.ssu-controller调用ubse创建组逻辑卷成功
        E2.ssu-controller调用ubse创建卷成功
        E3.容器操作成功，csi-ssu-driver将设备挂载到pod内
        E4.容器内存读写存储都可以成功
        E5.业务容器删除后可以自动解挂载使用的卷，卷信息正常
        E6.数据读取成功，未丢失
        E7.业务容器删除后可以自动解挂载使用的卷，卷信息正常
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_07"
        self.pvc_yaml_name = "scenario-7-pvcs.yaml"
        self.pod_yaml_name = "scenario-7-pods.yaml"
        self.remote_pvc_yaml = f"{self.remote_dir}/{self.pvc_yaml_name}"
        self.remote_pod_yaml = f"{self.remote_dir}/{self.pod_yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_07"
        )
        self.pvc_specs = (
            ("ssu-s7-linear-pvc", "3Gi", "Filesystem"),
            ("ssu-s7-striped-pvc", "3Gi", "Filesystem"),
            ("ssu-s7-normal-fs-pvc", "1Gi", "Filesystem"),
            ("ssu-s7-normal-block-pvc", "1Gi", "Block"),
        )
        self.fs_pods = ("ssu-s7-linear-workload", "ssu-s7-striped-workload", "ssu-s7-fs-workload")
        self.block_pod = "ssu-s7-block-workload"
        self.pv_names: list[str] = []
        self.volume_ids: list[str] = []
        self.controller_namespace = ""
        self.log_start_time = ""

    def _verify_bound_pvcs(self) -> list[str]:
        pvc_names = [name for name, _, _ in self.pvc_specs]
        resources = " ".join(f"pvc/{name}" for name in pvc_names)
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Bound "
            f"--timeout=100s {resources}",
            timeout=120,
        )
        pv_names = []
        volume_ids = []
        for pvc_name, expected_size, expected_mode in self.pvc_specs:
            pvc_info = self.run_master(
                f"kubectl get pvc {pvc_name} "
                "-o jsonpath='{.spec.volumeName}|{.spec.resources.requests.storage}|"
                "{.spec.volumeMode}'"
            )
            pvc_fields = pvc_info.split("|")
            self.assertEqual(len(pvc_fields), 3, f"PVC信息格式异常: {pvc_info}")
            pv_name, requested_size, volume_mode = pvc_fields
            self.assertTrue(pv_name, f"PVC {pvc_name} 未绑定PV")
            self.assertEqual(requested_size, expected_size, f"PVC {pvc_name} 申请容量不正确")
            self.assertEqual(volume_mode, expected_mode, f"PVC {pvc_name} 使用模式不正确")
            pv_info = self.run_master(
                f"kubectl get pv {pv_name} "
                "-o jsonpath='{.spec.csi.driver}|{.spec.csi.volumeHandle}|"
                "{.status.phase}'"
            )
            pv_fields = pv_info.split("|")
            self.assertEqual(len(pv_fields), 3, f"PV信息格式异常: {pv_info}")
            self.assertEqual(pv_fields[0], "csi.unifiedbus.com", f"PV {pv_name} CSI驱动不正确")
            self.assertTrue(pv_fields[1], f"PV {pv_name} 的volumeHandle为空")
            self.assertEqual(pv_fields[2], "Bound", f"PV {pv_name} 未处于Bound状态")
            self.logInfo(f"PVC {pvc_name}对应PV信息: {pv_info}")
            pv_names.append(pv_name)
            volume_ids.append(pv_fields[1])
        return pv_names, volume_ids

    def setup_method(self) -> None:
        self.init_ssu_params()
        self.logStep("P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常")
        self.locate_plugins()
        self.upload_yaml_files()
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P2", type="Functional")
    def test_k8s_ssu_function_07(self) -> None:
        self.logStep("S1.创建2个逻辑卷PVC，A声明所需卷的size大小为3G，nsnum为3；一个为线性编址加顺序策略，一个是条带化编址加分布式策略")
        self.logStep("S2.创建2个PVC，声明所需卷size大小为1G，一个为文件系统使用模式，一个是块设备使用模式")
        self.run_master(f"kubectl apply -f {self.remote_pvc_yaml}")

        self.logStep("E1.ssu-controller调用ubse创建组逻辑卷成功")
        self.logStep("E2.ssu-controller调用ubse创建卷成功")
        self.pv_names, self.volume_ids = self._verify_bound_pvcs()
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        for volume_id in self.volume_ids:
            self.assert_log_event(controller_logs, "CreateVolume succeeded", volume_id)

        self.logStep("S3.创建4个业务容器，yaml声明引用创建的PVC")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=initial")
        ready_pods = " ".join(f"pod/{pod}" for pod in (*self.fs_pods, self.block_pod))
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s {ready_pods}",
            timeout=120,
        )

        self.logStep("E3.容器操作成功，csi-ssu-driver将设备挂载到pod内")
        for pod in self.fs_pods:
            self.run_master(f"kubectl exec {pod} -- test -d /data")
        self.run_master(f"kubectl exec {self.block_pod} -- test -b /dev/ssu-volume")
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        for volume_id in self.volume_ids:
            self.assert_log_event(node_logs, "NodePublishVolume completed", volume_id)

        self.logStep("S4.在业务容器中使用系统调用读写存储设备")
        self.logStep("E4.容器内存读写存储都可以成功")
        for pod, payload in zip(self.fs_pods, ("ssu-s7-linear-data", "ssu-s7-striped-data", "ssu-s7-fs-data")):
            self.run_master(
                f"kubectl exec {pod} -- sh -c 'printf %s {payload} > /data/persist-test; sync'"
            )
            self.run_master(
                f"kubectl exec {pod} -- sh -c 'test \"$(cat /data/persist-test)\" = {payload}'"
            )
        block_payload = "ssu-s7-block-data"
        block_count = len(block_payload)
        self.run_master(
            f"kubectl exec {self.block_pod} -- sh -c '"
            f"printf %s {block_payload} | dd of=/dev/ssu-volume bs=1 seek=1048576 "
            f"conv=fsync,notrunc 2>/tmp/dd-write.log'"
        )
        self.run_master(
            f"kubectl exec {self.block_pod} -- sh -c '"
            f"readback=$(dd if=/dev/ssu-volume bs=1 skip=1048576 count={block_count} "
            f"2>/tmp/dd-read.log); test \"$readback\" = {block_payload}'"
        )

        self.logStep("S5.删除业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=initial "
            "--wait=true --timeout=100s",
            timeout=120,
        )
        self.logStep("E5.业务容器删除后可以自动解挂载使用的卷，卷信息正常")
        for pv_name in self.pv_names:
            self.assertEqual(
                self.run_master(f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"),
                "Bound",
                f"Pod删除后PV {pv_name}状态异常",
            )
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        for volume_id in self.volume_ids:
            self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_id)
            self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_id)

        self.logStep("S6.再次创建4个业务容器，yaml声明引用创建的PVC，读取之前写进卷的数据")
        self.run_master(f"kubectl apply -f {self.remote_pod_yaml} -l ssu-test-phase=same")
        self.run_master(
            f"kubectl wait --for=condition=Ready --timeout=100s {ready_pods}",
            timeout=120,
        )

        self.logStep("E6.数据读取成功，未丢失")
        for pod, payload in zip(self.fs_pods, ("ssu-s7-linear-data", "ssu-s7-striped-data", "ssu-s7-fs-data")):
            self.run_master(
                f"kubectl exec {pod} -- sh -c 'test \"$(cat /data/persist-test)\" = {payload}'"
            )
        self.run_master(
            f"kubectl exec {self.block_pod} -- sh -c '"
            f"readback=$(dd if=/dev/ssu-volume bs=1 skip=1048576 count={block_count} "
            f"2>/tmp/dd-read.log); test \"$readback\" = {block_payload}'"
        )

        self.logStep("S7.删除业务容器，使用pv工具查看卷信息，查看卷解挂载功能是否正常")
        self.run_master(
            f"kubectl delete -f {self.remote_pod_yaml} -l ssu-test-phase=same "
            "--wait=true --timeout=100s",
            timeout=120,
        )
        self.logStep("E7.业务容器删除后可以自动解挂载使用的卷，卷信息正常")
        for pv_name in self.pv_names:
            self.assertEqual(
                self.run_master(f"kubectl get pv {pv_name} -o jsonpath='{{.status.phase}}'"),
                "Bound",
                f"Pod删除后PV {pv_name}状态异常",
            )
        node_logs = self.component_logs("ssu-csi-node", "ssu-csi-node")
        for volume_id in self.volume_ids:
            self.assert_log_event(node_logs, "NodeUnpublishVolume completed", volume_id)
            self.assert_log_event(node_logs, "NodeUnstageVolume called", volume_id)

    def teardown_method(self) -> None:
        self.delete_resources(check=False)
        self.cleanup_volumes()
