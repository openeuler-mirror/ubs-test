#!/usr/local/python
# -*- coding: utf-8 -*-
'''
用例说明：
1. L1镜像部署时已经备好，/root目录下自带pvm代码，ko在/root/pvm/arch/arm64/kvm/kvm-pvm.ko
2. L2虚机生命周期由/home/handle_l2.sh管理：--start拉起（bash /home/handle_l2.sh --start 0拉起0号实例，实例ip可通过回显获取）
'''

import re

import pytest

from libs.modules.pvm.basecase.pvm_basecase import PvmBaseCase

# ===== 本用例可按需调整的参数 =====
L2_INSTANCE = "0"               # 传给脚本的参数：实例号 N 或显式 IP（192.168.249.0/24）


class TestPVML2Vm05(PvmBaseCase):
    """验证L2层虚拟机内存读写工具测试读写功能正常

    CaseNumber:
        test_pvm_L2_vm_05
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证L2层虚拟机内存读写工具测试读写功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像，镜像中集成内存读写测试工具（stress、lmbench）
    TestStep:
        S1.在L1虚拟机中启动L2虚拟机
        S2.在L2虚拟机中使用内存读写测试工具进行读写测试、构造一定读写压力混合读写几分钟
		S3.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动L2虚拟机，内核加载成功，日志记录相关信息
        E2.读写功能正常，L1和L2虚拟机功能不受影响，两层虚拟机内核日志不出现报错
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

    @pytest.mark.case_info(level='P1', type='Functional')
    def test_pvm_L2_vm_05(self):
        """测试L2层虚拟机内存读写工具测试读写功能正常"""

        # 内核日志报错关键字（两层共用）。方括号技巧：pattern 自身不含
        # 连续的 "BUG:" 等字样，避免 grep 命令回显被本地扫描误判为报错行；
        # Oops 带冒号，避免误匹配内核 cmdline 里的 "oops=panic" 等字样
        err_pat = '[O]ops:|[B]UG:|[K]ernel panic|[C]all trace|[I]/O error'

        def dmesg_errors(exec_fn, baseline: int) -> list:
            """取 baseline 行之后 dmesg 中的报错行原文（只看压测期间的新增日志）"""
            rc, out = exec_fn(f'dmesg | tail -n +{baseline + 1} | grep -iE "{err_pat}"')
            return [ln.strip() for ln in (out or '').splitlines()
                    if re.search(err_pat, ln, re.I)]

        def dmesg_baseline(exec_fn) -> int:
            """记录当前 dmesg 行数，作为"压测前"基线"""
            rc, out = exec_fn('dmesg | wc -l')
            n = next((int(ln) for ln in (out or '').splitlines()
                      if ln.strip().isdigit()), 0)
            return n

        self.logStep("S1.在L1虚拟机中启动L2虚拟机")
        self.start_l2_vm(L2_INSTANCE)

        self.logStep("E1.可以成功启动L2虚拟机，内核加载成功，日志记录相关信息")
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, f"启动后 L2 ({self.l2_ip}) ping 不通，网络未就绪")
        self.logInfo(f"L2 ({self.l2_ip}) ping 连通性正常")
        rc, out = self.l2_ssh_exec('uname -r')
        self.assertEqual(rc, 0, "L2 内执行 uname -r 失败，内核可能未加载成功")
        kernel_ver = out.splitlines()[-1].strip() if out else ''
        self.logInfo(f"L2 内核加载成功，版本: {kernel_ver}")

        self.logStep("S2.在L2虚拟机中使用内存读写测试工具进行读写测试、构造一定读写压力混合读写几分钟")
        # 记录压测前两层 dmesg 基线行数，压测后只检查期间新增的日志
        baseline_l1 = dmesg_baseline(self.console_exec)
        baseline_l2 = dmesg_baseline(self.l2_ssh_exec)
        # rootfs 已集成 stress-ng：2 CPU Worker + 1 VM Worker(2G) 混合压力，运行 60 秒
        rc, out = self.l2_ssh_exec(
            'stress-ng --cpu 2 --vm 1 --vm-bytes 2G --timeout 60s --metrics-brief',
            timeout=180)

        self.logStep("E2.读写功能正常，L1和L2虚拟机功能不受影响，两层虚拟机内核日志不出现报错")
        self.assertEqual(rc, 0,
                         f"L2 内 stress-ng 内存读写压力测试失败，输出: {out[-500:]}")
        self.logInfo(f"stress-ng 执行完成，输出尾部: {out.strip().splitlines()[-1] if out else ''}")

        # 压力后 L2 功能不受影响（仍可正常执行命令）
        rc, out = self.l2_ssh_exec('true')
        self.assertEqual(rc, 0, "压力测试后 L2 失去响应，功能受影响")
        # 压力后 L1 与 L2 网络仍连通
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, "压力测试后 L1 到 L2 网络不通，L1 功能受影响")

        # 压测期间（基线之后）两层内核日志不出现报错（失败时保留报错原文便于定位）
        errs = dmesg_errors(self.l2_ssh_exec, baseline_l2)
        self.assertEqual(len(errs), 0, f"L2 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_l1)
        self.assertEqual(len(errs), 0, f"L1 内核日志出现报错: {errs[:20]}")
        self.logInfo("压测期间两层虚拟机内核日志均无报错，L1/L2 功能不受影响")

        self.logStep("S3.删除L2虚拟机")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False

        self.logStep("E3.删除虚拟机成功")
        self.verify_l2_destroyed(L2_INSTANCE)

