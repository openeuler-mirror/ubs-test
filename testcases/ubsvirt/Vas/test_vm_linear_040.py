#!/usr/local/python
# -*- coding: utf-8 -*-
"""Test dynamic binding VM defragmentation with range-affinity=false."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear040(VasBaseCase):
    """验证range-affinity为false动态绑定虚机碎片整理与重调度正常.

    CaseNumber:
        test_vm_linear_040
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证range-affinity为false动态绑定虚机碎片整理与重调度正常
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为'0-1'，range-affinity设置为false，重新加载后重启服务
        P3.已创建8U16G的范围绑核（绑定单numa 0~95）的虚拟机VM1和虚机VM2，VM1虚拟机绑定VCPU2~9，VM2虚拟机绑定VCPU16~23
        P4..已创建10U16G的范围绑核（绑定单numa 0~95）的虚拟机VM3，VM3虚拟机绑定VCPU31-40
    TestStep:
        S1.删除VM1
        S2.等待5s后，执行vasctl query affinity --scope all查看虚机绑核情况
        S3.执行重调度vasctl opt reassign --scope all
    ExpectedResult:
        E1.配置成功
        E2.虚拟机VM2绑定VCPU2~9，VM3绑核信息不变化
        E3.虚拟机VM3绑定VCPU16-25
    Author:
        yangfan
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.destroy_all()

        self.logStep("P2.修改配置文件")
        self.command_check(f'\cp {self.config_file} {self.config_file}.bak', "cp config file failed")
        command = f'sed -i \'s/--skip-cpuset ""/--skip-cpuset "0-1"/g\' {self.config_file}'
        self.command_check(command, "change skip-cpuset failed")
        command1 = f'sed -i \'s/--range-affinity true/--range-affinity false/g\' {self.config_file}'
        self.command_check(command1, "change range-affinity failed")
        command2 = f'sed -i \'s/--sched-policy affinity /--sched-policy dynamicAffinity /g\' {self.config_file}'
        self.command_check(command2, "change sched-policy failed")
        self.reload_daemon()
        self.restart_vas()

        self.logStep("P3.已创建8U16G的虚拟机VM1和VM2")
        self.create_vm("VM1", self.cluster_size / 2, self.cluster_size)
        time.sleep(5)
        res = self.check_query_affinity("VM1", 2, 2 + self.cluster_size / 2 - 1)
        self.assertTrue(res, "The vm1's bound vCPUs are not in expected range.")
        self.create_vm("VM2", self.cluster_size / 2, self.cluster_size)
        time.sleep(5)
        res = self.check_query_affinity("VM2", self.cluster_size, 3 * self.cluster_size / 2 - 1)
        self.assertTrue(res, "The vm2's bound vCPUs are not in expected range.")

        self.logStep("P4.已创建10U16G的虚拟机VM3")
        self.create_vm("VM3", self.cluster_size / 2 + 2, self.cluster_size)
        time.sleep(5)
        res = self.check_query_affinity("VM3", 2 * self.cluster_size, 5 * self.cluster_size / 2 + 1)
        self.assertTrue(res, "The vm3's bound vCPUs are not in expected range.")

    @pytest.mark.case_info(level='P1', type='Functional')
    def test_vm_linear_040(self):
        """Test dynamic binding VM defragmentation with range-affinity=false."""
        self.logStep("S1.删除VM1")
        self.destroy_vm("VM1")

        self.logStep("E1.配置成功")
        time.sleep(5)

        self.logStep("S2.等待5s后，执行vasctl query affinity --scope all查看虚机绑核情况")
        res2 = self.check_query_affinity("VM2", 2, 2 + self.cluster_size / 2 - 1)
        res3 = self.check_query_affinity("VM3", 2 * self.cluster_size, 5 * self.cluster_size / 2 + 1)

        self.logStep("E2.虚拟机VM2绑定VCPU2~9，VM3绑核信息不变化")
        self.assertTrue(res2, "The vm2's bound vCPUs are not in expected range.")
        self.assertTrue(res3, "The vm3's bound vCPUs are not in expected range.")

        self.logStep("S3.执行重调度vasctl opt reassign --scope all")
        res = self.execute_command_with_return("vasctl opt reassign --scope all")
        self.assertIn("ReAssign success", res["stdout"], "vasctl opt reassign --scope all failed")
        time.sleep(5)

        self.logStep("E3.虚拟机VM3绑定VCPU16-25")
        res3 = self.check_query_affinity("VM3", self.cluster_size, 3 * self.cluster_size / 2 + 1)
        self.assertTrue(res3, "The vm3's bound vCPUs are not in expected range.")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.destroy_all()
        self.command_check(f'\cp {self.config_file}.bak {self.config_file}', "cp config file failed")
        self.reload_daemon()
        self.restart_vas()