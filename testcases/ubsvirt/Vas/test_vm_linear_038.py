#!/usr/local/python
# -*- coding: utf-8 -*-
"""Test vas-daemon configuration parameters."""

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear038(VasBaseCase):
    """验证vas-daemon配置项生效成功.

    CaseNumber:
        test_vm_linear_038
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证vas-daemon配置项生效成功
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务且服务正常
    TestStep:
        S1.修改vas-daemon.service中-smt false --sched-policy affinity --dynamic-util-thresh 80 --skip-cluster-cpumask 0-1 --range-affinity false,重新加载后重启服务，执行ps -ef | grep daemon查看配置项，有预期结果1
    ExpectedResult:
        E1.配置成功，进程配置项-smt false --sched-policy affinity --dynamic-util-thresh 80 --skip-cluster-cpumask 0-1 --range-affinity false
    Author:
        wufangzhou 00644577
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务且服务正常")
        self.destroy_all()

    def test_vm_linear_038(self):
        """Test vas-daemon configuration parameters."""
        self.logStep(
            "S1.修改vas-daemon.service配置项后重启服务"
        )
        self.stop_vas()
        self.command_check(f'\cp {self.config_file} {self.config_file}.bak', "cp config file failed")
        command = (
            f'sed -i '
            f'\'s/-smt true --sched-policy affinity --dynamic-util-thresh 85 --skip-cpuset "" '
            f'--range-affinity true/-smt false --sched-policy affinity --dynamic-util-thresh 80 '
            f'--skip-cpuset 0-1 --range-affinity false/g\' '
            f'{self.config_file}'
        )
        self.command_check(command, "change vas-daemon.service failed")
        self.reload_daemon()
        self.start_vas()

        self.logStep(
            "E1.配置成功，验证进程配置项"
        )
        command = (
            "ps -ef | grep vas_daemon | grep -v grep | "
            "grep -e '-smt false' -e '--sched-policy affinity' "
            "-e '--dynamic-util-thresh 80' -e '--skip-cpuset 0-1' -e '--range-affinity false'"
        )
        self.command_check(command, "config vas-daemon.service failed")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.stop_vas()
        self.command_check(f'\cp {self.config_file}.bak {self.config_file}', "cp config file failed")
        self.reload_daemon()
        self.start_vas()