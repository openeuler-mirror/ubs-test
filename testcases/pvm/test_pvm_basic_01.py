#!/usr/local/python
# -*- coding: utf-8 -*-
'''
用例说明：
1. L1镜像部署时已经备好，/root目录下自带pvm代码，ko在/root/pvm/arch/arm64/kvm/kvm-pvm.ko
2. L2虚机生命周期由/home/handle_l2.sh管理：--start拉起（bash /home/handle_l2.sh --start 0拉起0号实例，实例ip可通过回显获取）
'''

import pytest

from libs.modules.pvm.basecase.pvm_basecase import PvmBaseCase

# ===== 本用例可按需调整的参数 =====
L2_INSTANCE = "0"               # 传给脚本的参数：实例号 N 或显式 IP（192.168.249.0/24）


class TestPvmBasic01(PvmBaseCase):
    """验证PVM基本模块安装与卸载成功

    CaseNumber:
        test_pvm_basic_01
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证PVM基本模块安装与卸载成功
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
    TestStep:
        S1.在L1虚拟机中安装PVM的ko文件，安装后启动L2虚拟机
        S2.关闭L2虚拟机后卸载L1虚拟机的PVM的ko文件
    ExpectedResult:
        E1.L1虚拟机可以成功安装PVM的ko文件，安装后启动L2虚拟机成功
        E2.L2虚拟机关机成功，卸载成功，卸载不会导致L1虚拟机崩溃
    Author:
        handongkang
    """

    # ===== 前置资源路径 =====
    PVM_KO = "/root/pvm/arch/arm64/kvm/kvm-pvm.ko"  # L1镜像自带 pvm 代码及 ko
    L2_ROOTFS = "/home/rootfs.cpio.gz"              # L2 虚拟机根文件系统镜像

    def setup_method(self):
        """测试前置设置（对应 PreCondition P1）"""
        self.vm_ssh = None      # node -> L1 虚机的交互式 console 连接
        self.l2_started = False  # L2 是否已启动（供 teardown 兜底清理判断）
        self.l2_ip = None        # start_l2_vm 解析到的 L2 IP
        self.l2_instance = L2_INSTANCE

        # P1.完成L1虚拟机的安装部署，功能正常（可进入）
        self.logStep("P1.完成L1虚拟机的安装部署，功能正常")
        self.enter_l1_vm()

    def teardown_method(self):
        """测试清理：兜底停止本实例嵌套层虚机"""
        if self.l2_started and self.vm_ssh:
            self.destroy_l2_vm(self.l2_instance)
        self.l2_started = False
        self.release_l1_console()

    @pytest.mark.case_info(level='P0', type='Functional')
    def test_pvm_basic_01(self):
        """测试PVM基本模块安装与卸载成功"""

        self.logStep("S1.在L1虚拟机中安装PVM的ko文件，安装后启动L2虚拟机")
        # 安装前清理残留（上次异常退出可能遗留已加载的 ko），保证"安装"动作真实执行
        self.console_exec(f'rmmod {self.PVM_KO} 2>/dev/null')
        rc, out = self.console_exec(f'insmod {self.PVM_KO}; lsmod | grep -w kvm_pvm')
        self.assertEqual(rc, 0,
                         f"kvm-pvm.ko 安装失败（或插入后 lsmod 不可见）: {self.PVM_KO}")
        self.logInfo(f"kvm-pvm.ko 已安装: {out.splitlines()[0].strip() if out else ''}")
        self.start_l2_vm(L2_INSTANCE)

        self.logStep("E1.L1虚拟机可以成功安装PVM的ko文件，安装后启动L2虚拟机成功")
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, f"安装 ko 后启动 L2 ({self.l2_ip}) ping 不通，网络未就绪")
        self.logInfo(f"ko 已安装且 L2 ({self.l2_ip}) 启动成功，连通性正常")

        self.logStep("S2.关闭L2虚拟机后卸载L1虚拟机的PVM的ko文件")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False
        rc, out = self.console_exec(f'rmmod {self.PVM_KO}')
        self.assertEqual(rc, 0, f"kvm-pvm.ko 卸载失败（rmmod rc={rc}）: {out[-300:]}")
        rc, out = self.console_exec('lsmod | grep -w kvm_pvm')
        self.assertNotEqual(rc, 0, f"卸载后 kvm-pvm 仍可在 lsmod 中看到: {out}")

        self.logStep("E2.L2虚拟机关机成功，卸载成功，卸载不会导致L1虚拟机崩溃")
        self.verify_l2_destroyed(L2_INSTANCE)
        # L1 存活检查：卸载后 console 仍可正常执行命令
        rc, out = self.console_exec('echo ALIVE_CHECK_OK')
        self.assertEqual(rc, 0, "卸载 ko 后 L1 console 无响应，疑似崩溃")
        self.assertIn('ALIVE_CHECK_OK', out, "卸载 ko 后 L1 命令回显异常，疑似崩溃")
        self.logInfo("L2 已关机，ko 卸载成功，L1 未崩溃")