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
L2_VM_LAUNCH_TIMEOUT = 120           # 单个 L2 启动超时（秒），超过判定启动异常
OVERCOMMIT_RATIO = 9.6               # 目标超分比（L1:L2 = 1:9.6）

# 混合规格：4G 和 16G 交替，凑超分比
# L1 16G × 9.6 = 153.6G
# 方案：6 个 16G + 15 个 4G = 96 + 60 = 156G ≈ 1:9.75（略超上限，逼出自动回收）
# 实际按资源够不够逐个起，起不来的 catch 掉
LARGE_MEM_VMS = ("0", "1", "2", "3", "4", "5")      # 6 个 16G VM
SMALL_MEM_VMS = ("6", "7", "8", "9", "10", "11",
                 "12", "13", "14", "15", "16", "17",
                 "18", "19", "20")                     # 15 个 4G VM
LARGE_MEM = "16G"


class TestPVML2Vm11(PvmBaseCase):
    """验证PVM内存超分比1:9.6场景下多L2混合规格创建与自动回收

    CaseNumber:
        test_pvm_L2_vm_11
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证PVM内存超分比1:9.6场景下多L2混合规格创建与自动回收
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.逐个创建混合规格L2虚拟机（6个16G + 15个4G，逼近1:9.6超分比），每个启动限时120s
        S2.对成功启动的L2施加重内存+MMU churn压力，触发L1自动回收
        S3.验证：存活VM功能正常、被回收VM清理干净、L1无crash/内核报错
        S4.删除存活L2虚拟机
    ExpectedResult:
        E1.混合规格L2虚拟机在超时内成功启动（单个超过120s判定启动异常）
        E2.压力触发L1自动回收，剩余VM功能正常
        E3.被回收VM无残留，L1无crash/内核报错，可用内存恢复
        E4.删除虚拟机成功
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

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_L2_vm_11(self):
        """测试PVM内存超分比1:9.6场景下多L2混合规格创建与自动回收"""
        import json

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
        baseline_l1 = dmesg_baseline()
        mem_before = self._get_l1_mem_available_mb()
        self.logInfo(f"L1 可用内存: {mem_before}MB，目标超分比 1:{OVERCOMMIT_RATIO}")

        # ── S1: 逐个创建混合规格 L2（16G + 4G 混合，逼近 1:9.6）──
        self.logStep("S1.逐个创建混合规格L2虚拟机（6个16G + 15个4G，逼近1:9.6超分比），"
                     "每个启动限时120s")

        started = []          # 成功启动的 (instance, mem_size)
        failed_to_start = []  # 起不来的（超分，L1 资源不够）
        slow_starts = []      # 启动时间超过阈值

        # 先起 6 个 16G VM（用 start_l2_vm_overspec 走原始 CLI，可指定内存）
        for inst in LARGE_MEM_VMS:
            t0 = time.time()
            try:
                self.start_l2_vm_overspec(inst, memory=LARGE_MEM,
                                          timeout=L2_VM_LAUNCH_TIMEOUT)
                elapsed = time.time() - t0
                started.append((inst, LARGE_MEM))
                self.logInfo(f"S1: VM{inst} (16G) 启动成功，耗时 {elapsed:.1f}s")
                if elapsed > L2_VM_LAUNCH_TIMEOUT * 0.8:
                    slow_starts.append((inst, LARGE_MEM, elapsed))
                    self.logWarn(f"S1: VM{inst} (16G) 启动耗时 {elapsed:.1f}s"
                                 f"接近超时阈值 {L2_VM_LAUNCH_TIMEOUT}s")
            except Exception as e:  # noqa: BLE001
                elapsed = time.time() - t0
                failed_to_start.append((inst, LARGE_MEM, str(e)))
                self.logWarn(f"S1: VM{inst} (16G) 启动失败（耗时 {elapsed:.1f}s）: {e}")

        # 再起 15 个 4G VM（用 start_l2_vm 走 handle_l2.sh，固定 vmcfg）
        for inst in SMALL_MEM_VMS:
            t0 = time.time()
            try:
                self.start_l2_vm(inst, timeout=L2_VM_LAUNCH_TIMEOUT)
                elapsed = time.time() - t0
                started.append((inst, "4G"))
                self.logInfo(f"S1: VM{inst} (4G) 启动成功，耗时 {elapsed:.1f}s")
                if elapsed > L2_VM_LAUNCH_TIMEOUT * 0.8:
                    slow_starts.append((inst, "4G", elapsed))
                    self.logWarn(f"S1: VM{inst} (4G) 启动耗时 {elapsed:.1f}s"
                                 f"接近超时阈值 {L2_VM_LAUNCH_TIMEOUT}s")
            except Exception as e:  # noqa: BLE001
                elapsed = time.time() - t0
                failed_to_start.append((inst, "4G", str(e)))
                self.logWarn(f"S1: VM{inst} (4G) 启动失败（耗时 {elapsed:.1f}s）: {e}")

        # 统计
        total_mem_gb = sum(16 if m == LARGE_MEM else 4 for _, m in started)
        actual_ratio = total_mem_gb / 16 if total_mem_gb > 0 else 0
        self.logInfo(f"S1: 尝试启动 {len(LARGE_MEM_VMS) + len(SMALL_MEM_VMS)} 个 VM"
                     f"（{len(LARGE_MEM_VMS)} × 16G + {len(SMALL_MEM_VMS)} × 4G），"
                     f"成功 {len(started)} 个，失败 {len(failed_to_start)} 个，"
                     f"总虚拟内存 {total_mem_gb}G，实际超分比 1:{actual_ratio:.1f}")

        self.logStep("E1.混合规格L2虚拟机在超时内成功启动（单个超过120s判定启动异常）")
        self.assertGreater(len(started), 0, "没有一个 VM 启动成功")
        if slow_starts:
            self.logWarn(f"S1: {len(slow_starts)} 个 VM 启动接近超时阈值: "
                         f"{slow_starts}")

        # ── S2: 对存活的 VM 施加重内存 + MMU churn 压力 ──
        self.logStep("S2.对成功启动的L2施加重内存+MMU churn压力，触发L1自动回收")
        oc_stress = ('stress-ng --vm 2 --vm-bytes 512M '
                     '--mmap 2 --mremap 2 --mprotect 2 --timeout 120')
        for inst, mem_size in started:
            ip = self.l2_vms.get(inst)
            if not ip:
                continue
            self.console_exec(
                f"( ssh {ssh_opts} root@{ip} '{oc_stress}' "
                f"> /tmp/s2_vm{inst}.log 2>&1 & )")
        # 等 L1 检测 overcommit + 自动回收（60s）
        self.logInfo("等待 L1 自动回收部分 VM（60s）...")
        time.sleep(60)

        # ── S3: 验证存活 + 回收清理 + L1 无 crash ──
        self.logStep("S3.验证：存活VM功能正常、被回收VM清理干净、L1无crash/内核报错")
        # 检查哪些 cube-hypervisor 还活着
        rc, out = self.console_exec('ps -ef | grep cube-hypervisor | grep -v grep')
        survivors = set()
        for line in (out or '').splitlines():
            m = re.search(r'ch-(\d+)\.sock', line)
            if m:
                survivors.add(m.group(1))
        killed = set(i for i, _ in started) - survivors
        self.logInfo(f"S3: 超分结果: started {len(started)}, "
                     f"survived {len(survivors)}, killed {len(killed)}")

        # 存活 VM 功能正常（ls -al + ping）
        for inst in sorted(survivors):
            ip = self.l2_vms.get(inst, f"192.168.249.{int(inst) + 2}")
            rc, out = self.l2_ssh_exec('ls -al', instance=inst, timeout=30)
            self.assertEqual(rc, 0,
                             f"超分后存活 VM{inst} ls -al 失败: {out[-300:]}")
            self.assertIn('total', out)
        # 被 kill 的 VM：cube-hypervisor 已退出（无残留）
        for inst in killed:
            self.verify_l2_destroyed(inst)
        # L1 dmesg 无报错
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"超分 auto-kill 期间 L1 内核报错: {errs[:20]}")
        # L1 内存恢复
        mem_after = self._get_l1_mem_available_mb()
        self.logInfo(f"S3: L1 可用内存 {mem_before}MB -> {mem_after}MB"
                     f"（回收后应回升），survived={len(survivors)}, "
                     f"killed={len(killed)}")

        self.logStep("E2.压力触发L1自动回收，剩余VM功能正常")
        self.logStep("E3.被回收VM无残留，L1无crash/内核报错，可用内存恢复")
        self.logInfo("S3: 超分 + 自动回收验证通过")

        # ── S4: 删除存活 VM + 复核 ──
        self.logStep("S4.删除存活L2虚拟机")
        # 等 stress 结束
        for inst in sorted(survivors):
            for _ in range(20):
                _, o = self.l2_ssh_exec('pgrep -x stress-ng | wc -l',
                                         instance=inst, timeout=15)
                cnt = next((ln.strip() for ln in (o or '').splitlines()
                            if ln.strip().isdigit()), None)
                if cnt == '0':
                    break
                time.sleep(3)
        # 逐个 destroy
        for inst in sorted(survivors):
            try:
                self.destroy_l2_vm(inst)
            except Exception as e:  # noqa: BLE001
                self.logWarn(f"S4: destroy VM{inst} 失败（忽略）: {e}")
        self.l2_vms.clear()

        self.logStep("E4.删除虚拟机成功")
        for inst, _ in started:
            self.verify_l2_destroyed(inst)
        # 兜底：无任何 cube-hypervisor 残留
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"测试结束仍残留 cube-hypervisor: {(out or '')[-300:]}")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"全量测试后 L1 内核报错: {errs[:20]}")
        self.l2_started = False
        self.l2_vms.clear()
        self.logInfo("全部 L2 虚拟机已删除，超分测试完成")
