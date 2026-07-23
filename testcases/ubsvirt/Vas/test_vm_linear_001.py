#!/usr/local/python
# -*- coding: utf-8 -*-

"""Test VAS daemon start/stop functionality."""

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear001(VasBaseCase):
    """验证vas进程启停成功.

    CaseNumber:
        test_vm_linear_001
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证vas进程启停成功
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务且服务正常
    TestStep:
        S1.执行systemctl stop vas-daemon，后执行systemctl status vas-daemon查看服务
        S2.修改vas-daemon.service中-smt为false后，执行systemctl daemon-reload 和  systemctl start vas-daemon
        S3.执行systemctl start vas-daemon，后执行systemctl status vas-daemon查看服务
    ExpectedResult:
        E1.停止成功，进程停止状态
        E2.执行成功
        E3.启动成功，进程running状态，-smt参数为false
    Author:
        wufangzhou 00644577
    """

    def setup_method(self):
        """PreCondition: 环境中已部署libvirt和vas awared scheduler服务且服务正常."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务且服务正常")

    def test_vm_linear_001(self):
        """Test VAS daemon start/stop with SMT parameter modification."""
        self.logStep("S1.执行systemctl stop vas-daemon，后执行systemctl status vas-daemon查看服务")
        self.stop_vas()

        self.logStep("E1.停止成功，进程停止状态")

        self.logStep("S2.修改vas-daemon.service中-smt为false后，执行systemctl daemon-reload 和  systemctl start vas-daemon")
        command = f"sed -i 's/-smt true/-smt false/g' /usr/lib/systemd/system/vas-daemon.service"
        self.command_check(command, "change smt failed")
        command = "systemctl daemon-reload"
        self.command_check(command, "reload vas-daemon failed")

        self.logStep("E2.执行成功")

        self.logStep("S3.执行systemctl start vas-daemon，后执行systemctl status vas-daemon查看服务")
        self.start_vas()

        self.logStep("E3.启动成功，进程running状态，-smt参数为false")
        command = "ps -ef | grep vas_daemon | grep -v grep | grep -e -smt -e false"
        self.command_check(command, "-smt param is not changed")

    def teardown_method(self):
        """Cleanup: Restore original configuration."""
        self.stop_vas()
        command = "sed -i 's/-smt false/-smt true/g' /usr/lib/systemd/system/vas-daemon.service"
        self.command_check(command, "change smt failed")
        self.reload_daemon()
        self.start_vas()