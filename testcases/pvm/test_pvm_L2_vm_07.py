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
L2_INSTANCES = ("0", "1", "2")    # soak 用例的 3 个 L2 实例号
SOAK_DURATION = 1800              # soak 总时长（秒，默认 30 分钟）
CHECK_INTERVAL = 300              # 定时检查间隔（秒，每 5 分钟检查一次）
LEAK_THRESHOLD_MB = 1500             # soak 期间 L1 可用内存允许波动上限（MB，实测 3 VM 重 MMU churn 30min 约 1.2GB shadow page 增长）
LEAK_DESTROY_THRESHOLD_MB = 500      # destroy 后 L1 可用内存应回升到接近基线（真泄漏检测）


class TestPVML2Vm07(PvmBaseCase):
    """验证PVM长时间混合负载稳定性（soak测试）

    CaseNumber:
        test_pvm_L2_vm_07
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证PVM长时间混合负载稳定性（soak测试）
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.启动3个L2虚拟机
        S2.3个L2并发持续混合负载（CPU/内存/IO/MMU churn）30分钟，定时检查L1资源与内核日志
        S3.删除L2虚拟机
    ExpectedResult:
        E1.3个L2虚拟机启动成功，内核加载成功
        E2.30分钟持续负载期间，L1无crash/内核报错，可用内存无持续下降（无泄漏），各L2功能正常
        E3.删除虚拟机成功，无残留
    Author:
        yangfan
    """

    # ===== 前置资源路径 =====
    PVM_KO = "/root/pvm/arch/arm64/kvm/kvm-pvm.ko"  # L1镜像自带 pvm 代码及 ko
    L2_ROOTFS = "/home/rootfs.cpio.gz"              # L2 虚拟机根文件系统镜像

    def setup_method(self):
        """测试前置设置（对应 PreCondition P1~P3）"""
        self.vm_ssh = None
        self.l2_started = False
        self.l2_ip = None
        self.l2_vms = {}

        self.logStep("P1.完成L1虚拟机的安装部署，功能正常")
        self.enter_l1_vm()

        self.logStep("P2.在L1虚拟机中安装PVM的ko文件")
        rc, out = self.console_exec(f'insmod {self.PVM_KO} 2>/dev/null; '
                                    f'lsmod | grep -w kvm_pvm')
        self.assertEqual(rc, 0,
                         f"kvm-pvm.ko 加载失败: {self.PVM_KO}")
        self.logInfo(f"kvm-pvm.ko 已加载: {out.splitlines()[0].strip() if out else ''}")

        self.logStep("P3.成功编译L2层虚拟机镜像")
        rc, out = self.console_exec(f'ls -l {self.L2_ROOTFS}')
        self.assertEqual(rc, 0, f"L2 根文件系统镜像不存在: {self.L2_ROOTFS}")

    def teardown_method(self):
        """测试清理：兜底删除所有已启动的 L2 实例"""
        if self.vm_ssh:
            for inst in list(getattr(self, 'l2_vms', {}).keys()):
                try:
                    self.destroy_l2_vm(inst)
                except Exception as e:  # noqa: BLE001
                    self.logWarn(f"teardown 删除实例 {inst} 失败（忽略）: {e}")
        self.l2_started = False
        self.l2_vms = {}
        self.release_l1_console()

    def _get_l1_mem_available_mb(self):
        """获取 L1 /proc/meminfo MemAvailable（MB）"""
        rc, out = self.console_exec('grep MemAvailable /proc/meminfo')
        m = re.search(r'MemAvailable:\s+(\d+)', out or '')
        return (int(m.group(1)) // 1024) if m else 0

    def _get_l1_loadavg(self):
        """获取 L1 1-min loadavg"""
        rc, out = self.console_exec('cat /proc/loadavg')
        m = re.search(r'^(\d+\.\d+)\s+\d+\.\d+\s+\d+\.\d+\s+\d+/\d+\s+\d+',
                      out or '', re.M)
        return float(m.group(1)) if m else 999.0

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_L2_vm_07(self):
        """测试PVM长时间混合负载稳定性（soak测试）"""

        err_pat = '[O]ops:|[B]UG:|[K]ernel panic|[C]all trace|[I]/O error'

        def dmesg_baseline():
            rc, out = self.console_exec('dmesg | wc -l')
            return next((int(ln) for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), 0)

        def dmesg_errors_since(baseline):
            rc, out = self.console_exec(
                f'dmesg | tail -n +{baseline + 1} | grep -iE "{err_pat}"')
            return [ln.strip() for ln in (out or '').splitlines()
                    if re.search(err_pat, ln, re.I)]

        ssh_opts = ('-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
                    '-o ConnectTimeout=5')

        # ── S1: 启动 3 个 L2 ──
        self.logStep("S1.启动3个L2虚拟机")
        for inst in L2_INSTANCES:
            self.start_l2_vm(inst)
        self.logInfo(f"3 个 L2 已就绪: {self.l2_vms}")

        # E1: 验证启动 + 内核加载
        self.logStep("E1.3个L2虚拟机启动成功，内核加载成功")
        for inst in L2_INSTANCES:
            ip = self.l2_vms[inst]
            rc, out = self.console_exec(f'ping -c 3 -W 2 {ip}')
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} ({ip}) ping 不通: {out[-300:]}")
            rc, out = self.l2_ssh_exec('uname -r', instance=inst)
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} uname -r 失败: {out[-300:]}")
        self.logInfo("3 个 L2 均已启动且内核加载成功")

        # ── S2: 长时间混合负载 soak ──
        self.logStep(f"S2.3个L2并发持续混合负载（CPU/内存/IO/MMU churn）"
                     f"{SOAK_DURATION // 60}分钟，定时检查L1资源与内核日志")

        baseline_l1 = dmesg_baseline()
        mem_before = self._get_l1_mem_available_mb()
        self.logInfo(f"soak 前: L1 可用内存={mem_before}MB, "
                     f"loadavg={self._get_l1_loadavg()}")

        # 每轮 stress 时长 = CHECK_INTERVAL（5 分钟）
        # 循环 SOAK_DURATION / CHECK_INTERVAL 轮
        rounds = SOAK_DURATION // CHECK_INTERVAL
        # 3 个 VM 差异化负载：VM0=CPU+MMU, VM1=内存+IO, VM2=CPU+fork
        loads = {
            "0": ('stress-ng --cpu 2 --mmap 2 --mremap 1 --mprotect 1 '
                  f'--timeout {CHECK_INTERVAL}'),
            "1": ('stress-ng --vm 2 --vm-bytes 256M --io 2 --hdd 1 '
                  f'--hdd-bytes 32M --timeout {CHECK_INTERVAL}'),
            "2": ('stress-ng --cpu 2 --fork 2 --timer 1 '
                  f'--timeout {CHECK_INTERVAL}'),
        }

        for rnd in range(1, rounds + 1):
            self.logInfo(f"soak 第 {rnd}/{rounds} 轮 "
                         f"({rnd * CHECK_INTERVAL // 60}/"
                         f"{SOAK_DURATION // 60} 分钟)")
            # 并发启动 3 VM 的压力（bg + wait）
            launches = []
            for inst in L2_INSTANCES:
                ip = self.l2_vms[inst]
                launches.append(
                    f"ssh {ssh_opts} root@{ip} '{loads[inst]}' "
                    f"> /tmp/soak_vm{inst}_r{rnd}.log 2>&1 &")
            self.console_exec(' '.join(launches) + ' wait',
                              timeout=CHECK_INTERVAL + 60)

            # 定时检查：L1 内核日志 + 可用内存 + loadavg + 各 VM 功能
            errs = dmesg_errors_since(baseline_l1)
            self.assertEqual(len(errs), 0,
                             f"soak 第 {rnd} 轮后 L1 内核报错: {errs[:20]}")
            mem_now = self._get_l1_mem_available_mb()
            load_now = self._get_l1_loadavg()
            self.logInfo(f"soak 第 {rnd} 轮检查: "
                         f"可用内存={mem_now}MB (起始 {mem_before}MB), "
                         f"loadavg={load_now}")
            # 各 VM 功能正常（ls -al）
            for inst in L2_INSTANCES:
                rc, out = self.l2_ssh_exec('ls -al', instance=inst, timeout=30)
                self.assertEqual(rc, 0,
                                 f"soak 第 {rnd} 轮后 VM{inst} ls -al 失败: "
                                 f"{out[-300:]}")
                self.assertIn('total', out)

        # E2: soak 结束验证
        self.logStep("E2.30分钟持续负载期间，L1无crash/内核报错，"
                     "可用内存无持续下降（无泄漏），各L2功能正常")
        mem_after = self._get_l1_mem_available_mb()
        drop = mem_before - mem_after
        self.logInfo(f"soak 结束: L1 可用内存 {mem_before}MB -> {mem_after}MB "
                     f"(下降 {drop}MB)")
        self.assertLess(drop, LEAK_THRESHOLD_MB,
                        f"soak {SOAK_DURATION // 60} 分钟后 L1 可用内存下降 "
                        f"{drop}MB（基线 {mem_before} -> {mem_after}），"
                        f"超过阈值 {LEAK_THRESHOLD_MB}MB，疑似泄漏")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"soak 全程 L1 内核报错: {errs[:20]}")
        # 最终功能验证
        for inst in L2_INSTANCES:
            ip = self.l2_vms[inst]
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0, f"soak 后 VM{inst} ls -al 失败: {out[-300:]}")
            self.assertIn('total', out)
            rc, _ = self.console_exec(f'ping -c 3 -W 2 {ip}')
            self.assertEqual(rc, 0, f"soak 后 L1 到 VM{inst} 网络不通")
        self.logInfo(f"soak {SOAK_DURATION // 60} 分钟完成，"
                     f"L1 无 crash，内存波动 {drop}MB（阈值 {LEAK_THRESHOLD_MB}MB），"
                     f"各 VM 功能正常")

        # ── S3: 删除 L2 虚拟机 ──
        self.logStep("S3.删除L2虚拟机")
        for inst in L2_INSTANCES:
            self.destroy_l2_vm(inst)

        self.logStep("E3.删除虚拟机成功，无残留")
        for inst in L2_INSTANCES:
            self.verify_l2_destroyed(inst)
        # 真泄漏检测：destroy 后 L1 可用内存应回升到接近 soak 前基线
        # （soak 期间的 shadow page 增长在 destroy 时被 kvm_mmu_zap_all 释放）
        mem_after_destroy = self._get_l1_mem_available_mb()
        leak_drop = mem_before - mem_after_destroy
        self.logInfo(f"destroy 后 L1 可用内存 {mem_after_destroy}MB "
                     f"(soak 前基线 {mem_before}MB, 差 {leak_drop}MB)")
        self.assertLess(leak_drop, LEAK_DESTROY_THRESHOLD_MB,
                        f"VM destroy 后 L1 可用内存仍低 {leak_drop}MB"
                        f"（soak 前 {mem_before} -> destroy 后 {mem_after_destroy}），"
                        f"超过阈值 {LEAK_DESTROY_THRESHOLD_MB}MB，"
                        f"shadow page 未被完全释放，疑似真泄漏")
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"测试结束仍残留 cube-hypervisor: {(out or '')[-300:]}")
        self.l2_started = False
        self.l2_vms.clear()
        self.logInfo("全部 L2 虚拟机已删除，soak 测试完成")
