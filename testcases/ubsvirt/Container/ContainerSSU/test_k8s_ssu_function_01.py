#!/usr/local/python
# -*- coding: utf-8 -*-

import time
import re
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction01(KubernetesBaseCase):
    """验证k8s用户可通过声明式方式创建和删除SSU存储卷.

    CaseNumber:
        test_k8s_ssu_function_01
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证k8s用户可通过声明式方式创建和删除SSU存储卷
    PreCondition:
        P1.K8s、ssu-controller、csi-ssu-driver安装完成且功能正常，存储节点正常
    TestStep:
        S1.创建2个1Gi PVC，一个为Filesystem模式，一个为Block模式
        S2.创建2个3Gi组逻辑卷PVC，一个为线性编址加顺序策略，一个为条带化编址加分布式策略
        S3.删除SSU卷和声明的PVC
    ExpectedResult:
        E1.ssu-controller调用UBSE创建普通卷成功，PV可查询且日志存在创建成功打印
        E2.ssu-controller调用UBSE创建组逻辑卷成功，PV可查询且日志存在创建成功打印
        E3.PVC及其动态PV删除成功，日志存在删除卷成功打印
    Author:
        luzeren
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_01"
        self.yaml_name = "scenario-1-pvcs.yaml"
        self.remote_yaml = f"{self.remote_dir}/{self.yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_01"
        )
        self.normal_pvcs = (
            ("ssu-s1-normal-filesystem-pvc", "1Gi", "Filesystem"),
            ("ssu-s1-normal-block-pvc", "1Gi", "Block"),
        )
        self.group_pvcs = (
            ("ssu-s1-linear-sequential-pvc", "3Gi", "Filesystem"),
            ("ssu-s1-striped-distributed-pvc", "3Gi", "Filesystem"),
        )
        self.pv_names: list[str] = []
        self.controller_namespace = ""
        self.log_start_time = ""

    def _controller_logs(self) -> str:
        return self.run_master(
            "for pod in $(kubectl get pods "
            f"-n {self.controller_namespace} --no-headers "
            "-o custom-columns=NAME:.metadata.name,PHASE:.status.phase | "
            "awk '$1 ~ /ssu-controller/ && $2 == \"Running\" {print $1}'); do "
            f"kubectl logs -n {self.controller_namespace} \"$pod\" -c ssu-controller "
            f"--since-time={self.log_start_time}; done",
            timeout=300,
        )

    def _verify_bound_pvcs(self, pvc_specs) -> list[str]:
        pvc_names = [name for name, _, _ in pvc_specs]
        resources = " ".join(f"pvc/{name}" for name in pvc_names)
        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Bound "
            f"--timeout=300s {resources}",
            timeout=360,
        )

        pv_names = []
        for pvc_name, expected_size, expected_mode in pvc_specs:
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
                "-o jsonpath='{.metadata.name}|{.spec.csi.driver}|"
                "{.spec.csi.volumeHandle}|{.status.phase}'"
            )
            pv_fields = pv_info.split("|")
            self.assertEqual(len(pv_fields), 4, f"PV信息格式异常: {pv_info}")
            self.assertEqual(pv_fields[0], pv_name, f"未查询到PVC {pvc_name}对应的PV")
            self.assertEqual(pv_fields[1], "csi.unifiedbus.com", f"PV {pv_name} CSI驱动不正确")
            self.assertTrue(pv_fields[2], f"PV {pv_name} 的volumeHandle为空")
            self.assertEqual(pv_fields[3], "Bound", f"PV {pv_name} 未处于Bound状态")
            self.logInfo(f"PVC {pvc_name}对应PV信息: {pv_info}")
            pv_names.append(pv_name)
        return pv_names

    @staticmethod
    def _count_success_logs(logs: str, rpc_name: str) -> int:
        pattern = re.compile(rf"{rpc_name}\s+succeeded", re.IGNORECASE)
        return sum(bool(pattern.search(line)) for line in logs.splitlines())

    def setup_method(self) -> None:
        self.init_ssu_params()

        self.logStep("P1.检查K8s、ssu-controller、csi-ssu-driver及存储节点状态")
        self.locate_plugins()

        self.create_dir("master", self.remote_dir)
        self.upload_file(
            "master",
            {
                "source_file": f"{self.yaml_base_path}/{self.yaml_name}",
                "destination_file": self.remote_yaml,
            },
        )
        self.delete_resources(check=False)
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P0", type="Functional")
    def test_k8s_ssu_function_01(self) -> None:
        self.logStep("S1.创建2个1Gi PVC，分别使用Filesystem和Block模式")
        apply_output = self.run_master(f"kubectl apply -f {self.remote_yaml}")
        self.assertTrue(
            "created" in apply_output or "configured" in apply_output,
            f"应用PVC场景YAML失败: {apply_output}",
        )
        normal_pv_names = self._verify_bound_pvcs(self.normal_pvcs)

        self.logStep("E1.普通SSU卷创建成功，PV可查询且Controller日志存在创建成功打印")
        normal_pv_output = self.run_master(
            f"kubectl get pv {' '.join(normal_pv_names)} -o wide"
        )
        self.logInfo(f"普通卷PV信息:\n{normal_pv_output}")
        time.sleep(5)
        normal_create_success_count = self._count_success_logs(
            self._controller_logs(), "CreateVolume"
        )
        self.assertGreaterEqual(normal_create_success_count, 2, "Controller创建普通卷成功日志少于2条")

        self.logStep("S2.核验2个3Gi组逻辑卷PVC：线性顺序策略和条带化分布式策略")
        self.assertEqual(
            self.run_master(
                "kubectl get storageclass ub-ssu-csi-s1-linear "
                "-o jsonpath='{.parameters.allocStrategy}'"
            ),
            "1",
            "线性卷StorageClass未使用顺序分配策略",
        )
        self.assertEqual(
            self.run_master(
                "kubectl get storageclass ub-ssu-csi-s1-striped "
                "-o jsonpath='{.parameters.allocStrategy}'"
            ),
            "0",
            "条带卷StorageClass未使用分布式分配策略",
        )
        group_pv_names = self._verify_bound_pvcs(self.group_pvcs)
        self.pv_names = normal_pv_names + group_pv_names

        linear_context = self.run_master(
            f"kubectl get pv {group_pv_names[0]} "
            "-o jsonpath='{.spec.csi.volumeAttributes.nsnum}|"
            "{.spec.csi.volumeAttributes.allocStrategy}'"
        )
        self.assertEqual(linear_context, "2|1", "线性卷PV未记录双Namespace顺序策略")
        striped_context = self.run_master(
            f"kubectl get pv {group_pv_names[1]} "
            "-o jsonpath='{.spec.csi.volumeAttributes.nsnum}|"
            "{.spec.csi.volumeAttributes.allocStrategy}|"
            "{.spec.csi.volumeAttributes.raidLevel}|"
            "{.spec.csi.volumeAttributes.chunkSize}'"
        )
        self.assertEqual(striped_context, "2|0|0|64", "条带卷PV未记录双Namespace分布式策略")

        controller_logs = self._controller_logs()
        create_success_count = self._count_success_logs(controller_logs, "CreateVolume")
        self.assertGreaterEqual(create_success_count, 4, "Controller创建卷成功日志少于4条")

        self.logStep("E2.组逻辑SSU卷创建成功，PV可查询且Controller日志存在创建成功打印")
        group_pv_output = self.run_master(
            f"kubectl get pv {' '.join(group_pv_names)} -o wide"
        )
        self.logInfo(f"组逻辑卷PV信息:\n{group_pv_output}")

        self.logStep("S3.删除声明的PVC，并由Delete回收策略删除PV和后端SSU卷")
        pvc_resources = " ".join(
            f"pvc/{name}" for name, _, _ in self.normal_pvcs + self.group_pvcs
        )
        self.run_master(
            f"kubectl delete {pvc_resources} --wait=true --timeout=300s",
            timeout=360,
        )
        pv_resources = " ".join(f"pv/{name}" for name in self.pv_names)
        self.run_master(
            f"kubectl wait --for=delete --timeout=300s {pv_resources}",
            timeout=360,
        )

        delete_logs = self._controller_logs()
        delete_success_count = self._count_success_logs(delete_logs, "DeleteVolume")
        self.assertGreaterEqual(delete_success_count, 4, "Controller删除卷成功日志少于4条")

        self.logStep("E3.PVC和动态PV删除成功，Controller日志存在删除卷成功打印")
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
