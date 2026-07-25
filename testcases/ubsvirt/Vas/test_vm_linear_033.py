#!/usr/local/python
# -*- coding: utf-8 -*-
"""Test VM CPU defragmentation after skip-cpuset change."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear033(VasBaseCase):
    """验证创建虚拟机后设置skip-cluster为空，虚机cpu碎片整理成功.

    CaseNumber:
        test_vm_linear_033
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证创建虚拟机后设置skip-cluster为空，虚机cpu碎片整理成功
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为'0-1，跳过vcpu0 vcpu1,重新加载后重启服务
        P3.已创建16U64G的范围绑核的虚拟机VM1，虚拟机绑定VCPU16~31
    TestStep:
        S1.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为""，重新加载后重启服务
        S2.查看虚机绑核情况，有预期结果1
    ExpectedResult:
        E1.配置成功
        E2.虚拟机绑定VCPU0~15
    Author:
        yangfan
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.wait_service_status("vas-daemon", 30)
        self.wait_service_status("libvirtd", 30)
        self.destroy_all()

        self.logStep(
            "P2.修改/usr/lib/systemd/system/vas-daemon.service中--skip-cluster配置为'0-1，跳过vcpu0 vcpu1,重新加载后重启服务"
        )
        self.command_check(f'\cp {self.config_file} {self.config_file}.bak', "cp config file failed")
        half_cluster = int(self.cluster_size / 2) - 1
        command = f'sed -i \'s/--skip-cpuset ""/--skip-cpuset "0-{half_cluster}"/g\' {self.config_file}'
        self.command_check(command, "change skip-cpuset failed")
        self.reload_daemon()
        self.restart_vas()
        time.sleep(5)

        self.logStep("P3.已创建16U64G的范围绑核的虚拟机VM1，虚拟机绑定VCPU16~31")
        self.create_vm("VM1", self.cluster_size, 64, 0)
        time.sleep(5)
        res = self.check_query_affinity("VM1", self.cluster_size, self.cluster_size * 2 - 1)
        self.assertTrue(res, f"The vm1's bound vCPUs are not {self.cluster_size} - {self.cluster_size * 2 - 1}.")

    @pytest.mark.case_info(level='P1', type='Functional')
    def test_vm_linear_033(self):
        """Test VM CPU defragmentation after skip-cpuset change."""
        self.logStep("S1.修改/usr/lib/systemd/system/vas-daemon.service中--skip-cluster配置为\"\"，重新加载后重启服务")
        self.command_check(f'\cp {self.config_file}.bak {self.config_file}', "cp config file failed")
        self.reload_daemon()
        self.restart_vas()
        time.sleep(5)

        self.logStep("E1.配置成功")

        self.logStep("S2.查看虚机绑核情况，有预期结果1")
        res1 = self.check_query_affinity("VM1", 0, self.cluster_size - 1)

        self.logStep("E2.虚拟机绑定VCPU0~15")
        self.assertTrue(res1, f"The vm1's bound vCPUs are not 0 - {self.cluster_size - 1}.")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.destroy_all()
        self.command_check(f'\cp {self.config_file}.bak {self.config_file}', "cp config file failed")
        self.reload_daemon()
        self.restart_vas()