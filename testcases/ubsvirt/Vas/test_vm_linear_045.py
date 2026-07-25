#!/usr/local/python
# -*- coding: utf-8 -*-
"""Test dynamic binding VM creation in overcommit scenario with layer."""

import time

import pytest

from libs.modules.ubsvirt.basecase.VasBaseCase import VasBaseCase


class TestVmLinear045(VasBaseCase):
    """验证超分场景超分比例大于1时动态绑定虚机创建申请cpu在第二层.

    CaseNumber:
        test_vm_linear_045
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证超分场景超分比例大于1时动态绑定虚机创建申请cpu在第二层
    PreCondition:
        P1.环境中已部署libvirt和vas awared scheduler服务
        P2.修改"/usr/lib/systemd/system/vas-daemon.service"中--skip-cluster配置为'0-7，且设置绑核方式为动态绑核，重新加载后重启服务
    TestStep:
        S1.创建8U16G的范围绑核的虚拟机VM1，cpuset限制设置为0-32，创建虚拟机
        S2.查看虚拟机绑核信息
        S3.创建16U16G的范围绑核的虚拟机VM2，cpuset限制设置为0-32，创建虚拟机，查看虚拟机绑核信息
        S4.创建4U16G的范围绑核的虚拟机VM3，cpuset限制设置为0-32，创建虚拟机，查看虚拟机绑核信息
    ExpectedResult:
        E1.创建虚拟机成功
        E2.查看虚拟机绑核信息，绑核信息为8-15
        E3.查看虚拟机绑核信息，绑核信息为16-31
        E4.查看虚拟机绑核信息，绑核信息为8-11，为第二层
    Author:
        yangfan
    """

    def setup_method(self):
        """PreCondition: 环境准备."""
        self.logStep("P1.环境中已部署libvirt和vas awared scheduler服务")
        self.wait_service_status("vas-daemon", 30)
        self.wait_service_status("libvirtd", 30)
        self.destroy_all()

        self.logStep("P2.修改配置文件，设置动态绑核")
        self.command_check(f'\cp {self.config_file} {self.config_file}.bak', "cp config file failed")
        half_cluster_size = int(self.cluster_size / 2 - 1)
        command = f'sed -i \'s/--skip-cpuset ""/--skip-cpuset "0-{half_cluster_size}"/g\' {self.config_file}'
        self.command_check(command, "change skip-cpuset failed")
        command1 = f'sed -i \'s/--sched-policy affinity /--sched-policy dynamicAffinity /g\' {self.config_file}'
        self.command_check(command1, "change sched-policy failed")
        self.reload_daemon()
        self.restart_vas()

    def test_vm_linear_045(self):
        """Test dynamic binding VM creation in overcommit scenario with layer."""
        self.logStep("S1.创建8U16G的范围绑核的虚拟机VM1，cpuset限制设置为0-32")
        self.create_vm("VM1", self.cluster_size / 2, self.cluster_size, 0, 0, self.cluster_size * 2 - 1)
        time.sleep(5)

        self.logStep("E1.创建虚拟机成功")
        res = self.check_vm("VM1")
        self.assertTrue(res, "VM1 create failed")

        self.logStep("S2.查看虚拟机绑核信息")
        res = self.check_query_affinity("VM1", self.cluster_size / 2, self.cluster_size - 1)

        self.logStep("E2.查看虚拟机绑核信息，绑核信息为8-15")
        self.assertTrue(res, "The vm's bound vCPU are not in expected range.")

        self.logStep("S3.创建16U16G的范围绑核的虚拟机VM2")
        self.create_vm("VM2", self.cluster_size, self.cluster_size, 0, 0, self.cluster_size * 2 - 1)
        time.sleep(5)

        self.logStep("E3.查看虚拟机绑核信息，绑核信息为16-31")
        res = self.check_query_affinity("VM2", self.cluster_size, self.cluster_size * 2 - 1)
        self.assertTrue(res, "The vm's bound vCPU are not in expected range.")

        self.logStep("S4.创建4U16G的范围绑核的虚拟机VM3")
        self.create_vm("VM3", self.cluster_size / 4, self.cluster_size, 0, 0, self.cluster_size * 2 - 1)
        time.sleep(5)
        res = self.check_query_affinity("VM3", self.cluster_size / 2, self.cluster_size / 4 * 3 - 1)

        self.logStep("E4.查看虚拟机绑核信息，绑核信息为8-11，为第二层")
        self.assertTrue(res, "The vm's bound vCPU are not in expected range.")
        res = self.get_layerId("VM3", 1)
        self.assertTrue(res, "The vm is not at the second layer(layerId=1).")

    def teardown_method(self):
        """Cleanup: Restore configuration."""
        self.destroy_all()
        self.node.run({'command': [f'\cp {self.config_file}.bak {self.config_file}']})
        self.reload_daemon()
        self.restart_vas()