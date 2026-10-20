#!/usr/local/python
# -*- coding: utf-8 -*-

import time
import re
from pathlib import Path

import pytest

from libs.modules.ubsvirt.basecase.kubernetes_basecase import KubernetesBaseCase


@pytest.mark.smoke
class TestK8sSsuFunction06(KubernetesBaseCase):
    """验证k8s用户创建存储卷下限为1G.

    CaseNumber:
        test_k8s_ssu_function_06
    RunLevel:
        Level 3
    EnvType:

    CaseName:
        验证k8s用户创建存储卷下限为1G
    PreCondition:
        P1.环境完成K8s、ssu-controller、csi-ssu-driver安装，且功能正常，存储节点正常
    TestStep:
        S1.创建1个PVC，声明所需卷的size大小为0.9G，为文件系统使用模式
        S2.创建1个PVC，声明所需卷的size大小为1G，为文件系统使用模式
        S3.删除SSU卷和声明的PVC
    ExpectedResult:
        E1.ssu-controller调用ubse创建卷失败
        E2.ssu-controller调用ubse创建卷成功，可以使用pv命令查看到创建成功的ssu卷的信息
        E3.操作成功
    Author:
        yangfan
    """

    def init_ssu_params(self) -> None:
        self.remote_dir = "/tmp/container_ssu/test_k8s_ssu_function_06"
        self.yaml_name = "scenario-5-pvcs.yaml"
        self.remote_yaml = f"{self.remote_dir}/{self.yaml_name}"
        self.yaml_base_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "resource"
            / "ubsvirt"
            / "yaml"
            / "test_k8s_ssu_function_06"
        )
        self.small_pvc = "ssu-s5-undersize-filesystem-pvc"
        self.normal_pvc = "ssu-s5-minimum-filesystem-pvc"
        self.pv_name: str = ""
        self.volume_id: str = ""
        self.controller_namespace = ""
        self.log_start_time = ""

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
        self.run_master(
            f"kubectl delete -f {self.remote_yaml} "
            "--ignore-not-found=true --wait=true --timeout=300s",
            timeout=360,
            check=False,
        )
        self.log_start_time = self.run_master("date -u +%Y-%m-%dT%H:%M:%SZ")
        time.sleep(5)

    @pytest.mark.case_info(level="P3", type="Functional")
    def test_k8s_ssu_function_06(self) -> None:
        self.logStep("S1.创建1个PVC，声明所需卷的size大小为0.9G，为文件系统使用模式")
        apply_output = self.run_master(f"kubectl apply -f {self.remote_yaml}")
        self.assertTrue(
            "created" in apply_output or "configured" in apply_output,
            f"应用PVC场景YAML失败: {apply_output}",
        )

        self.run_master(
            f"kubectl wait --for=jsonpath='{{.status.phase}}'=Bound "
            f"--timeout=300s pvc/{self.normal_pvc}",
            timeout=360,
        )

        self.logStep("E1.ssu-controller调用ubse创建卷失败")
        small_phase = self.run_master(
            f"kubectl get pvc {self.small_pvc} -o jsonpath='{{.status.phase}}'"
        )
        self.assertEqual(
            small_phase,
            "Pending",
            f"PVC {self.small_pvc} 应保持Pending状态，实际为{small_phase}",
        )
        controller_logs = self.component_logs("ssu-controller", "ssu-controller")
        size_error_pattern = re.compile(
            r"requested size \S+ smaller than minimun 1073741824 bytes",
            re.IGNORECASE,
        )
        self.assertTrue(
            any(
                size_error_pattern.search(line)
                for line in controller_logs.splitlines()
            ),
            "未找到卷容量下限报错日志: requested size smaller than minimun 1073741824 bytes",
        )

        self.logStep("S2.创建1个PVC，声明所需卷的size大小为1G，为文件系统使用模式")
        pvc_info = self.run_master(
            f"kubectl get pvc {self.normal_pvc} "
            "-o jsonpath='{.spec.volumeName}|{.spec.resources.requests.storage}|"
            "{.spec.volumeMode}'"
        )
        pvc_fields = pvc_info.split("|")
        self.assertEqual(len(pvc_fields), 3, f"PVC信息格式异常: {pvc_info}")
        self.assertEqual(
            pvc_fields[1], "1Gi", f"PVC {self.normal_pvc}申请容量不正确"
        )
        self.assertEqual(
            pvc_fields[2], "Filesystem", f"PVC {self.normal_pvc}使用模式不正确"
        )
        self.assertTrue(pvc_fields[0], f"PVC {self.normal_pvc} 未绑定PV")
        self.pv_name = pvc_fields[0]

        pv_info = self.run_master(
            f"kubectl get pv {self.pv_name} "
            "-o jsonpath='{.spec.csi.driver}|{.spec.csi.volumeHandle}|"
            "{.status.phase}'"
        )
        pv_fields = pv_info.split("|")
        self.assertEqual(len(pv_fields), 3, f"PV信息格式异常: {pv_info}")
        self.assertEqual(
            pv_fields[0],
            "csi.unifiedbus.com",
            f"PV {self.pv_name} CSI驱动不正确",
        )
        self.assertTrue(pv_fields[1], f"PV {self.pv_name} 的volumeHandle为空")
        self.assertEqual(
            pv_fields[2], "Bound", f"PV {self.pv_name} 未处于Bound状态"
        )
        self.volume_id = pv_fields[1]
        self.logInfo(f"PVC {self.normal_pvc}对应PV信息: {pv_info}")
        normal_pv_output = self.run_master(
            f"kubectl get pv {self.pv_name} -o wide"
        )
        self.logInfo(f"1Gi卷PV信息:\n{normal_pv_output}")

        self.logStep(
            "E2.ssu-controller调用ubse创建卷成功，可以使用pv命令查看到创建成功的ssu卷的信息"
        )
        self.assert_log_event(
            controller_logs, "CreateVolume succeeded", self.volume_id
        )

        self.logStep("S3.删除SSU卷和声明的PVC")
        self.run_master(
            f"kubectl delete -f {self.remote_yaml} --wait=true --timeout=300s",
            timeout=360,
        )
        self.run_master(
            f"kubectl wait --for=delete --timeout=300s pv/{self.pv_name}",
            timeout=360,
            check=False,
        )

        self.logStep("E3.操作成功")
        delete_logs = self.component_logs("ssu-controller", "ssu-controller")
        self.assert_log_event(
            delete_logs, "DeleteVolume succeeded", self.volume_id
        )
        remaining_pvcs = self.run_master(
            f"kubectl get pvc {self.small_pvc} {self.normal_pvc} "
            "--ignore-not-found=true -o name"
        )
        remaining_pvs = self.run_master(
            f"kubectl get pv {self.pv_name} --ignore-not-found=true -o name"
        )
        self.assertEqual(remaining_pvcs, "", f"仍存在未删除PVC: {remaining_pvcs}")
        self.assertEqual(remaining_pvs, "", f"仍存在未删除PV: {remaining_pvs}")

    def teardown_method(self) -> None:
        self.run_master(
            f"kubectl delete -f {self.remote_yaml} "
            "--ignore-not-found=true --wait=true --timeout=300s",
            timeout=360,
            check=False,
        )