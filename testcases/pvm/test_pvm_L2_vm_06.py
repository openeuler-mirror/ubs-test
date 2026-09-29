#!/usr/local/python
# -*- coding: utf-8 -*-
'''
用例说明：
1. L1镜像部署时已经备好，/root目录下自带pvm代码，ko在/root/pvm/arch/arm64/kvm/kvm-pvm.ko
2. L2虚机生命周期由/home/handle_l2.sh管理：--start拉起（bash /home/handle_l2.sh --start 0拉起0号实例，实例ip可通过回显获取）
'''

import re
import time
import pytest

from libs.modules.pvm.basecase.pvm_basecase import PvmBaseCase

# ===== 本用例可按需调整的参数 =====
L2_INSTANCE = "0"               # 传给脚本的参数：实例号 N 或显式 IP（192.168.249.0/24）


class TestPVML2Vm06(PvmBaseCase):
    """验证L2层虚拟机执行复杂系统指令功能正常

    CaseNumber:
        test_pvm_L2_vm_06
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证L2层虚拟机执行复杂系统指令功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.在L1虚拟机中启动L2虚拟机
        S2.在L2虚拟机执行命令类uname -a
        S3.ip a查看虚拟机网络设备，ping localhost测试本地ping
        S4.dmesg查看内核日志
        S5.创建进程dd命令读写
        S6.验证sleep功能正常
        S7.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动L2虚拟机，内核加载成功，日志记录相关信息
        E2.可以正常看到系统的内核信息
        E3.可以查到本机ip, ping功能正常
        E4.dmesg可正常查看内核日志
        E5.进程启动成功，读写正常
        E6.sleep功能正常
        E7.删除虚拟机成功
    Author:
        yangfan
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

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_L2_vm_06(self):
        """测试L2层虚拟机执行复杂系统指令功能正常"""
        self.logStep("S1.在L1虚拟机中启动L2虚拟机")
        self.start_l2_vm(L2_INSTANCE)

        self.logStep("E1.可以成功启动L2虚拟机，内核加载成功，日志记录相关信息")
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, f"启动后 L2 ({self.l2_ip}) ping 不通，网络未就绪")
        self.logInfo(f"L2 ({self.l2_ip}) ping 连通性正常")
        rc, out = self.l2_ssh_exec('uname -r')
        self.assertEqual(rc, 0, f"L2 内核未加载（uname -r 失败）: {out[-300:]}")
        self.logInfo(f"L2 内核加载成功，版本: {out.splitlines()[-1].strip() if out else ''}")

        self.logStep("S2.在L2虚拟机执行命令类uname -a")
        rc, out = self.l2_ssh_exec('uname -a')
        self.assertEqual(rc, 0, f"L2 内执行 uname -a 失败: {out[-300:]}")
        self.assertTrue(len(out.strip()) > 0, "uname -a 无回显，输出为空")

        self.logStep("E2.可以正常看到系统的内核信息")
        self.assertIn('Linux', out, f"uname -a 未返回内核信息: {out[-300:]}")
        self.logInfo(f"uname -a 正常回显内核信息: {out.splitlines()[-1].strip() if out else ''}")

        self.logStep("S3.ip a查看虚拟机网络设备，ping localhost测试本地ping")
        rc, out = self.l2_ssh_exec('ip a')
        self.assertEqual(rc, 0, f"L2 内执行 ip a 失败: {out[-300:]}")
        self.assertIn(self.l2_ip, out,
                      f"ip a 未查到本机 IP {self.l2_ip}: {out[-300:]}")
        self.logInfo(f"ip a 查到本机 IP {self.l2_ip}，网络设备正常")
        rc, out = self.l2_ssh_exec('ping -c 3 -W 2 127.0.0.1')

        self.logStep("E3.可以查到本机ip, ping功能正常")
        self.assertEqual(rc, 0, f"L2 本地 loopback ping 失败: {out[-300:]}")
        self.logInfo("L2 本地 ping（127.0.0.1）功能正常")

        self.logStep("S4.dmesg查看内核日志")
        rc, out = self.l2_ssh_exec('dmesg', timeout=30)

        self.logStep("E4.dmesg可正常查看内核日志")
        self.assertEqual(rc, 0, f"L2 内执行 dmesg 失败: {out[-300:]}")
        self.assertTrue(len(out.strip()) > 0, "dmesg 无输出，内核日志为空")
        self.logInfo(f"L2 dmesg 可正常查看，最近日志: "
                     f"{out.strip().splitlines()[-1] if out else ''}")

        self.logStep("S5.创建进程dd命令读写")
        # nohup + 重定向：避免 dd 继承 ssh 的 fd 致 ssh 阻塞至 dd 结束，可立即返回 PID
        rc, out = self.l2_ssh_exec(
            'nohup dd if=/dev/zero of=/dev/null bs=2M count=256 '
            '>/tmp/dd_s5.log 2>&1 & echo DD_PID=$!')
        self.assertEqual(rc, 0, f"L2 内启动 dd 后台进程失败: {out[-300:]}")
        m = re.search(r'DD_PID=(\d+)', out)
        pid = m.group(1) if m else ''
        self.assertTrue(pid, f"未获取到 dd 进程 PID，输出: {out[-300:]}")
        self.logInfo(f"dd 读写进程已启动，PID: {pid}")

        # 轮询等待 dd 完成（bs=2M count=256 共 512MB 写 /dev/null，耗时较短）
        done = False
        for _ in range(20):
            rc, out = self.l2_ssh_exec(
                f'kill -0 {pid} 2>/dev/null; echo STAT=$?')
            sm = re.search(r'STAT=(\d+)', out or '')
            if sm and sm.group(1) != '0':
                done = True
                break
            time.sleep(2)

        self.logStep("E5.进程启动成功，读写正常")
        self.assertTrue(done, f"dd 进程 {pid} 未在预期时间内完成（读写异常）")
        # dd 完成后将读写统计（records in/out）写入日志，据此确认读写正常
        rc, out = self.l2_ssh_exec('cat /tmp/dd_s5.log')
        self.assertEqual(rc, 0, f"读取 dd 日志失败: {out[-300:]}")
        self.assertIn('records in', out, f"dd 未正常完成读写，日志: {out[-300:]}")
        self.assertIn('records out', out, f"dd 未正常完成读写，日志: {out[-300:]}")
        self.logInfo(f"dd 读写正常完成: "
                     f"{out.strip().splitlines()[-1] if out else ''}")

        self.logStep("S6.验证sleep功能正常")
        t0 = time.time()
        rc, out = self.l2_ssh_exec('sleep 30', timeout=60)
        elapsed = time.time() - t0

        self.logStep("E6.sleep功能正常")
        self.assertEqual(rc, 0, f"L2 内执行 sleep 30 失败: {out[-300:]}")
        self.assertGreaterEqual(elapsed, 30,
                               f"sleep 30 实际仅耗时 {elapsed:.1f}s，未正常睡眠")
        self.assertLess(elapsed, 50,
                        f"sleep 30 耗时 {elapsed:.1f}s，异常过长")
        self.logInfo(f"sleep 功能正常，实际耗时 {elapsed:.1f}s")

        self.logStep("S7.删除L2虚拟机")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False

        self.logStep("E7.删除虚拟机成功")
        self.verify_l2_destroyed(L2_INSTANCE)
        self.logInfo("L2 已删除，VMM 进程退出")