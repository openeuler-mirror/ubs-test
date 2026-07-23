#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2025. All rights reserved.
"""Test VAS query affinity command functionality."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear024(VasBaseCase):
    """验证查询虚拟机绑核信息命令成功.

    CaseNumber:
        test_vm_linear_024
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证查询虚拟机绑核信息命令成功
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.环境中创建范围绑核虚机VM1/VM2
    TestStep:
        S1.执行vasctl query affinity --scope 
        S2.执行vasctl query affinity --scope all
        S3.删除VM1/VM2后，执行vasctl query affinity --scope all，有预期结果1
    ExpectedResult:
        E1.执行成功，返回虚机相关信息
        E2.执行成功，返回主机上所有虚机相关信息
        E3.执行成功，返回为空
    Author:
        wufangzhou 00644577
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.destroy_all()

        self.logStep("P2.环境中创建范围绑核虚机VM1/VM2")
        self.create_vm("VM1")
        time.sleep(5)
        self.create_vm("VM2")
        time.sleep(5)

    def test_vm_linear_024(self):
        """Test VAS query affinity command."""
        self.logStep("S1.执行vasctl query affinity --scope")
        vm1_id = self.get_vm_id("VM1")
        vm2_id = self.get_vm_id("VM2")

        command = f"vasctl query affinity --scope {vm1_id}"
        vm1_result = self.execute_command_with_return(command)
        self.assertTrue(
            vm1_result["return_code"],
            f"执行vasctl query affinity --scope vm1_id failed, result: {vm1_result}"
        )

        command2 = f"vasctl query affinity --scope {vm2_id}"
        vm2_result = self.execute_command_with_return(command2)
        self.assertTrue(
            vm2_result["return_code"],
            f"执行vasctl query affinity --scope vm2_id failed, result: {vm2_id}"
        )
        self.logStep("E1.执行成功，返回虚机相关信息")

        self.logStep("S2.执行vasctl query affinity --scope all")
        command = "vasctl query affinity --scope all"
        vm_all_result = self.execute_command_with_return(command)
        self.assertTrue(
            vm_all_result["return_code"],
            f"执行vasctl query affinity --scope all failed, result: {vm_all_result}"
        )
        self.logStep("E2.执行成功，返回主机上所有虚机相关信息")

        self.logStep("S3.删除VM1/VM2后，执行vasctl query affinity --scope all，有预期结果1")
        self.destroy_vm("VM1")
        self.destroy_vm("VM2")
        time.sleep(5)
        command = "vasctl query affinity --scope all"
        query_result = self.execute_command_with_return(command)

        self.logStep("E3.执行成功，返回为空")
        self.assertIn(
            "No affinity information available",
            query_result["stdout"],
            "vasctl query affinity --scope all 返回不为空"
        )

    def teardown_method(self):
        """Cleanup: Destroy all VMs."""
        self.destroy_all()