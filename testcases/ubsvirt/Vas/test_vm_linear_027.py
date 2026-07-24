#!/usr/local/python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2025. All rights reserved.
"""Test dynamic binding VM creation with same cluster priority."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear027(VasBaseCase):
    """验证动态绑定虚机创建申请cpu优先申请同一Cluster.

    CaseNumber:
        test_vm_linear_027
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证动态绑定虚机创建申请cpu优先申请同一Cluster
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为'0-1'，跳过vcpu0 vcpu1,重新加载后重启服务
    TestStep:
        S1.创建16U32G的范围绑核的虚拟机VM1（绑定范围为当前numa所有vcpu）
        S2.执行vasctl query affinity --scope ，查看虚机绑核情况，有预期结果1
    ExpectedResult:
        E1.创建成功
        E2.虚拟机绑定VCPU16~31，为同一个cluster
    Author:
        wufangzhou 00644577
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.destroy_all()

        self.logStep("P2.修改/usr/lib/systemd/system/vas-daemon.service中--skip-cluster配置为'0-1'，跳过vcpu0 vcpu1,重新加载后重启服务")
        self.command_check(f'\cp {self.config_file} {self.config_file}.bak', "cp config file failed")
        command = f'sed -i \'s/--skip-cpuset ""/--skip-cpuset "0-1"/g\' {self.config_file}'
        self.command_check(command, "change skip-cpuset failed")
        command1 = f'sed -i \'s/--sched-policy affinity /--sched-policy dynamicAffinity /g\' {self.config_file}'
        self.command_check(command1, "change sched-policy failed")
        self.reload_daemon()
        self.restart_vas()

    def test_vm_linear_027(self):
        """Test dynamic binding VM creation with same cluster priority."""
        self.logStep("S1.创建16U32G的范围绑核的虚拟机VM1（绑定范围为当前numa所有vcpu）")
        self.create_vm("VM1", self.cluster_size, self.cluster_size * 2)
        time.sleep(5)

        self.logStep("E1.创建成功")
        res = self.check_vm("VM1")
        self.assertTrue(res, "VM1 create failed")

        self.logStep("S2.执行vasctl query affinity --scope ，查看虚机绑核情况，有预期结果1")
        res = self.check_query_affinity("VM1", self.cluster_size, self.cluster_size * 2 - 1)

        self.logStep("E2.虚拟机绑定VCPU16~31，为同一个cluster")
        self.assertTrue(res, "The vm's bound vCPU are not in self.cluster_size - (self.cluster_size * 2 - 1).")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.destroy_all()
        self.node.run({'command': [f'\cp {self.config_file}.bak {self.config_file}']})
        self.reload_daemon()
        self.restart_vas()