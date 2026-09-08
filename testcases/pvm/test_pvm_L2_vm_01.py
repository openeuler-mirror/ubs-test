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


class TestPVML2Vm01(PvmBaseCase):
    """验证L2层虚拟机启动加载成功且功能正常

    CaseNumber:
        test_pvm_L2_vm_01
    RunLevel:
        Level T
    EnvType:

    CaseName:
        验证L2层虚拟机启动加载成功且功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.在L1虚拟机中启动L2虚拟机
        S2.在L2虚拟机执行命令类ls -al
        S3.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动L2虚拟机，内核加载成功
        E2.ls -al执行结果正常，可以正常回显
        E3.删除虚拟机成功
    Author:
        handongkang
    """

    # ===== 前置资源路径 =====
    PVM_KO = "/root/pvm/arch/arm64/kvm/kvm-pvm.ko"  # L1镜像自带 pvm 代码及 ko
    L2_ROOTFS = "/home/rootfs.cpio.gz"              # L2 虚拟机根文件系统镜像

    def setup_method(self):
        """测试前置设置（对应 PreCondition P1~P3）"""
        self.vm_ssh = None      # node -> L1 虚机的交互式 console 连接
        self.l2_started = False  # L2 是否已启动（供 teardown 兜底清理判断）
        self.l2_ip = None        # start_l2_vm 解析到的 L2 IP
        self.l2_instance = L2_INSTANCE

        # P1.完成L1虚拟机的安装部署，功能正常（可进入）
        self.logStep("P1.完成L1虚拟机的安装部署，功能正常")
        self.enter_l1_vm()

        # P2.在L1虚拟机中安装PVM的ko文件（插入后 lsmod 可见）
        self.logStep("P2.在L1虚拟机中安装PVM的ko文件")
        rc, out = self.console_exec(f'insmod {self.PVM_KO} 2>/dev/null; '
                                    f'lsmod | grep -w kvm_pvm')
        self.assertEqual(rc, 0,
                         f"kvm-pvm.ko 加载失败（或插入后 lsmod 不可见）: {self.PVM_KO}")
        self.logInfo(f"kvm-pvm.ko 已加载: {out.splitlines()[0].strip() if out else ''}")

        # P3.成功编译L2层虚拟机镜像（/home/rootfs.cpio.gz 存在）
        self.logStep("P3.成功编译L2层虚拟机镜像")
        rc, out = self.console_exec(f'ls -l {self.L2_ROOTFS}')
        self.assertEqual(rc, 0, f"L2 根文件系统镜像不存在: {self.L2_ROOTFS}")

    def teardown_method(self):
        """测试清理：兜底停止本实例嵌套层虚机"""
        if self.l2_started and self.vm_ssh:
            self.destroy_l2_vm(self.l2_instance)
        self.l2_started = False
        self.release_l1_console()

    @pytest.mark.case_info(level='P0', type='Functional')
    def test_pvm_L2_vm_01(self):
        """测试L2层虚拟机启动加载成功且功能正常"""

        self.logStep("S1.在L1虚拟机中启动L2虚拟机")
        self.start_l2_vm(L2_INSTANCE)

        self.logStep("E1.可以成功启动L2虚拟机，内核加载成功")
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, f"启动后 L2 ({self.l2_ip}) ping 不通，网络未就绪")
        self.logInfo(f"L2 ({self.l2_ip}) ping 连通性正常")

        self.logStep("S2.在L2虚拟机执行命令类ls -al")
        rc, out = self.l2_ssh_exec('ls -al')

        self.logStep("E2.ls -al执行结果正常，可以正常回显")
        self.assertEqual(rc, 0, "L2 内执行 ls -al 失败")
        self.assertIn('total', out, "ls -al 输出异常")

        self.logStep("S3.删除L2虚拟机")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False

        self.logStep("E3.删除虚拟机成功")
        self.verify_l2_destroyed(L2_INSTANCE)
