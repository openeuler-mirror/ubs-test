#!/usr/local/python
# -*- coding: utf-8 -*-

"""Test VAS manual reassign command functionality."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear022(VasBaseCase):
    """验证执行手动重调度命令成功.

    CaseNumber:
        test_vm_linear_022
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证执行手动重调度命令成功
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.环境中创建范围绑核虚机VM1/VM2
    TestStep:
        S1.执行vasctl opt reassign --scope VM1
        S2.执行vasctl opt reassign --scope all
        S3.删除VM1/VM2后，执行vasctl opt reassign --scope all，有预期结果1
    ExpectedResult:
        E1.执行成功，无异常报错
        E2.执行成功，无异常报错
        E3.执行成功，提示非法虚拟机名字
    Author:
        wufangzhou 00644577
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.destroy_all()

        self.logStep("P2.环境中创建范围绑核虚机VM1/VM2")
        self.create_vm("VM1")
        self.create_vm("VM2")
        time.sleep(5)

    def test_vm_linear_022(self):
        """Test VAS manual reassign command."""
        self.logStep("S1.执行vasctl opt reassign --scope VM1")
        for i in range(1, 3):
            res = self.execute_command_with_return(f"vasctl opt reassign --scope VM{i}")
            self.assertIsNotNone(res.get("stdout"), f"vasctl opt reassign --scope VM{i} produced no output")
            self.assertIn("ReAssign success", res["stdout"], f"vasctl opt reassign --scope VM{i} failed")

        self.logStep("E1.执行成功，无异常报错")

        self.logStep("S2.执行vasctl opt reassign --scope all")
        res = self.execute_command_with_return("vasctl opt reassign --scope all")

        self.logStep("E2.执行成功，无异常报错")
        self.assertIn("ReAssign success", res["stdout"], "vasctl opt reassign --scope all failed")

        self.logStep("S3.删除VM1/VM2后，执行vasctl opt reassign --scope all，有预期结果1")
        self.destroy_vm("VM1")
        self.destroy_vm("VM2")
        res = self.execute_command_with_return("vasctl opt reassign --scope all")

        self.logStep("E3.执行成功，提示非法虚拟机名字")
        time.sleep(5)
        self.assertIn(
            "Virtual machine needs to reassign cpu does not exist",
            res["stdout"],
            "vasctl opt reassign --scope all failed"
        )

    def teardown_method(self):
        """Cleanup: Destroy all VMs."""
        self.destroy_all()