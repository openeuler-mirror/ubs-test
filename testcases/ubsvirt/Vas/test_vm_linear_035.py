#!/usr/local/python
# -*- coding: utf-8 -*-
"""Test dynamic binding VM cross-cluster defragmentation in overcommit scenario."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear035(VasBaseCase):
    """验证超分场景下动态绑定虚机跨cluster向低位整理.

    CaseNumber:
        test_vm_linear_035
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证超分场景下动态绑定虚机跨cluster向低位整理
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为'0-1，跳过vcpu0 vcpu1,重新加载后重启服务
        P3.已创建一个12U64G的范围绑核的虚拟机VM1，8U虚拟机VM2，16U虚拟机VM3
        P4.虚拟机VM1绑定VCPU2~13，VM2绑定VCPU16~23，VM3绑定VCPU32~47
    TestStep:
        S1.删除虚拟机VM2, VM1，执行vasctl query affinity --scope all查看虚机绑核情况
    ExpectedResult:
        E1.删除成功，VM3绑核信息没有变化，没有碎片整理，VM2绑定2-9
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

        self.logStep("P3.已创建一个12U64G的范围绑核的虚拟机VM1，8U虚拟机VM2，16U虚拟机VM3")
        self.create_vm("VM1", 1, 2)
        time.sleep(5)
        self.create_vm("VM2", self.cluster_size - 2, self.cluster_size * 2)
        time.sleep(5)
        self.create_vm("VM3", self.cluster_size, self.cluster_size * 2)
        time.sleep(5)

        self.logStep("P4.验证虚机绑核信息")
        res1 = self.check_query_affinity("VM1", 2, 2)
        res2 = self.check_query_affinity("VM2", self.cluster_size, self.cluster_size * 2 - 3)
        res3 = self.check_query_affinity("VM3", self.cluster_size * 2, self.cluster_size * 3 - 1)
        self.assertTrue(res1, "The vm1's bound vCPUs are not equal 2.")
        self.assertTrue(res2, "The vm2's bound vCPUs are not in cluster_size - (cluster_size * 2 - 3).")
        self.assertTrue(res3, "The vm3's bound vCPUs are not in cluster_size * 2 - (cluster_size * 3 - 1).")

    def test_vm_linear_035(self):
        """Test dynamic binding VM cross-cluster defragmentation in overcommit scenario."""
        self.logStep("S1.删除虚拟机VM1，执行vasctl query affinity --scope all查看虚机绑核情况")
        self.destroy_vm("VM1")
        time.sleep(5)

        self.logStep("E1.删除成功，VM3绑核信息没有变化，没有碎片整理，VM2绑定2-9")
        res1 = self.check_query_affinity("VM3", self.cluster_size * 2, self.cluster_size * 3 - 1)
        res2 = self.check_query_affinity("VM2", 2, self.cluster_size - 1)
        self.assertTrue(res1, "The vm3's bound vCPUs are not in cluster_size * 2 - (cluster_size * 3 - 1).")
        self.assertTrue(res2, "The vm2's bound vCPUs are not in 2 - (cluster_size - 1).")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.destroy_all()
        self.command_check(f'\cp {self.config_file}.bak {self.config_file}', "cp config file failed")
        self.reload_daemon()
        self.restart_vas()