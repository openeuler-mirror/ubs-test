#!/usr/local/python
# -*- coding: utf-8 -*-
"""Test dynamic binding VM same-cluster defragmentation in overcommit scenario."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear036(VasBaseCase):
    """验证超分场景下动态绑定虚机同cluster向低位整理.

    CaseNumber:
        test_vm_linear_036
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证超分场景下动态绑定虚机同cluster向低位整理
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为'0-1，跳过vcpu0 vcpu1,重新加载后重启服务
        P3.已创建两个6U64G的范围绑核的虚拟机VM1/VM2，虚拟机VM1绑定VCPU2~7,虚拟机VM2绑定VCPU8~13
    TestStep:
        S1.删除VM1
        S2.等待5s后，执行vasctl query affinity --scope all查看虚机绑核情况，有预期结果1
    ExpectedResult:
        E1.配置成功
        E2.虚拟机VM2绑定VCPU2~7
    Author:
        wufangzhou 00644577
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.destroy_all()

        self.logStep("P2.修改配置文件")
        self.command_check(f'\cp {self.config_file} {self.config_file}.bak', "cp config file failed")
        command = f'sed -i \'s/--skip-cpuset ""/--skip-cpuset "0-1"/g\' {self.config_file}'
        self.command_check(command, "change skip-cpuset failed")
        command1 = f'sed -i \'s/--sched-policy affinity /--sched-policy dynamicAffinity /g\' {self.config_file}'
        self.command_check(command1, "change sched-policy failed")
        self.reload_daemon()
        self.restart_vas()

        self.logStep("P3.已创建两个6U64G的范围绑核的虚拟机VM1/VM2")
        self.create_vm("VM1", 1, 2)
        time.sleep(5)
        res = self.check_query_affinity("VM1", 2, 2)
        self.assertTrue(res, "The vm1's bound vCPUs are not equal 2.")
        self.create_vm("VM2", 1, 2)
        time.sleep(5)
        res = self.check_query_affinity("VM2", 3, 3)
        self.assertTrue(res, "The vm2's bound vCPUs are not equal 3.")

    def test_vm_linear_036(self):
        """Test dynamic binding VM same-cluster defragmentation in overcommit scenario."""
        self.logStep("S1.删除VM1")
        self.destroy_vm("VM1")

        self.logStep("E1.配置成功")
        time.sleep(5)

        self.logStep("S2.等待5s后，执行vasctl query affinity --scope all查看虚机绑核情况，有预期结果1")
        res = self.check_query_affinity("all", 3, 3)

        self.logStep("E2.虚拟机VM2绑定VCPU8-13")
        self.assertTrue(res, "The vm2's bound vCPUs are not equal 3.")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.destroy_all()
        self.command_check(f'\cp {self.config_file}.bak {self.config_file}', "cp config file failed")
        self.reload_daemon()
        self.restart_vas()