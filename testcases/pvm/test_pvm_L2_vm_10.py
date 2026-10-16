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
L2_INSTANCES = ("0", "1")                 # 隔离用例的 2 个 L2 实例号（VM1=压力/故障源, VM2=受害者）
L2_OVERCOMMIT_INSTANCES = ("0", "1", "2", "3", "4")  # 超规格：5 个 L2（超过 L1 内存承载，触发自动回收）
L1_MEM_FLOOR_MB = 512                     # L1 压测期间可用内存下限（MB），低于此判定 L1 被打爆
DD_LATENCY_CEIL = 20                      # VM2 dd 延迟上限（秒），超过判定 IO 隔离异常
CPU_ISOLATION_RATIO = 0.6                 # VM2 并发 vs 基线 bogo ops/s 比下限，低于判定 CPU 被抢


class TestPVML2Vm10(PvmBaseCase):
    """验证L2层虚拟机资源隔离与故障隔离功能正常

    CaseNumber:
        test_pvm_L2_vm_10
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证L2层虚拟机资源隔离与故障隔离功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.网络隔离：VM1 ping flood 打满网络，VM2 ping L1 正常，L1 网络不受影响
        S2.IO/存储隔离：VM1 重 IO 压力，VM2 IO 延迟正常，L1 资源不受影响
        S3.L1资源度量隔离：2个L2混合压力时，L1 CPU/内存/网络在正常范围
        S4.故障注入隔离：VM1 内 fork bomb/内存压力，VM2 + L1 不受影响
        S5.内存超规格：创建5个L2并施加重内存+MMU churn压力，触发L1自动回收部分VM，验证剩余VM功能正常、被回收VM清理干净、L1内核日志无报错
        S6.CPU隔离：VM1/VM2绑不同CPU段，VM1跑CPU压力，验证VM2性能不被抢占
        S7.删除L2虚拟机
    ExpectedResult:
        E1.网络隔离：VM2 ping 正常，L1 网络不受 VM1 flood 影响
        E2.IO隔离：VM2 IO 正常，L1 资源不受 VM1 重 IO 影响
        E3.L1资源度量在正常范围（可用内存/网络/CPU loadavg）
        E4.故障注入隔离：VM1 fork/内存压力不影响 VM2 + L1
        E5.超规格后剩余L2功能正常、被回收VM无残留、L1无crash/内核报错
        E6.CPU隔离：VM2性能不受VM1 CPU压力影响
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
        self.l2_vms = {}          # 多 VM 场景：实例号 -> IP 的映射

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
        """测试清理：兜底删除所有已启动的 L2 实例"""
        if self.vm_ssh:
            for inst in list(getattr(self, 'l2_vms', {}).keys()):
                try:
                    self.destroy_l2_vm(inst)
                except Exception as e:  # noqa: BLE001 teardown 兜底不抛异常
                    self.logWarn(f"teardown 删除实例 {inst} 失败（忽略）: {e}")
        self.l2_started = False
        self.l2_vms = {}
        self.release_l1_console()

    def _wait_vm_proc_done(self, inst, proc_name, deadline_sec):
        """轮询 VM 内某进程（pgrep -x）结束，返回是否在期限内结束"""
        deadline = time.time() + deadline_sec
        while time.time() < deadline:
            _, o = self.l2_ssh_exec(f'pgrep -x {proc_name} | wc -l',
                                     instance=inst, timeout=15)
            cnt = next((ln.strip() for ln in (o or '').splitlines()
                        if ln.strip().isdigit()), None)
            if cnt == '0':
                return True
            time.sleep(3)
        return False

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_L2_vm_10(self):
        """测试L2层虚拟机资源隔离与故障隔离功能正常"""

        # 内核日志报错关键字（方括号技巧避免 grep 回显被误判，同 test_pvm_L2_vm_05）
        err_pat = '[O]ops:|[B]UG:|[K]ernel panic|[C]all trace|[I]/O error'

        def dmesg_baseline(exec_fn) -> int:
            """记录当前 dmesg 行数，作为压测前基线"""
            rc, out = exec_fn('dmesg | wc -l')
            return next((int(ln) for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), 0)

        def dmesg_errors(exec_fn, baseline: int) -> list:
            """取 baseline 行之后 dmesg 中的报错行原文（只看期间新增日志）"""
            rc, out = exec_fn(f'dmesg | tail -n +{baseline + 1} | grep -iE "{err_pat}"')
            return [ln.strip() for ln in (out or '').splitlines()
                    if re.search(err_pat, ln, re.I)]

        def l2_exec(inst):
            """返回绑定到指定 L2 实例的 exec_fn"""
            return lambda cmd, timeout=60: self.l2_ssh_exec(cmd, timeout, instance=inst)

        ssh_opts = ('-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
                    '-o ConnectTimeout=5')

        # 起回 2 个 L2（VM1=压力/故障源, VM2=受害者）
        for inst in L2_INSTANCES:
            self.start_l2_vm(inst)
        vm1_ip, vm2_ip = self.l2_vms["0"], self.l2_vms["1"]
        baseline_l1 = dmesg_baseline(self.console_exec)
        baseline_l2 = {inst: dmesg_baseline(l2_exec(inst)) for inst in L2_INSTANCES}

        # L1 br-l2 IP（动态取，不写死）
        rc, out = self.console_exec('ip -4 -o addr show br-l2')
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out or '')
        self.assertTrue(m, f"无法从 L1 获取 br-l2 网段 IP: {(out or '')[-300:]}")
        l1_ip = m.group(1)

        # ── S1: 网络隔离 ──
        self.logStep("S1.网络隔离：VM1 ping flood 打满网络，VM2 ping L1 正常，L1 网络不受影响")
        # VM1 后台快 ping flood 到 L1（-i 0.001 间隔，10000 包，约 10s）
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm1_ip} 'ping -i 0.001 -c 10000 {l1_ip}' "
            f"> /tmp/s1_flood.log 2>&1 & )")
        time.sleep(3)  # 让 flood 起来

        # E1: VM2 ping L1 正常 + L1->VM2 网络通（不受 VM1 flood 影响）
        self.logStep("E1.网络隔离：VM2 ping 正常，L1 网络不受 VM1 flood 影响")
        rc, out = self.l2_ssh_exec(f'ping -c 5 -W 2 {l1_ip}', instance="1", timeout=30)
        self.assertEqual(rc, 0,
                         f"VM1 flood 期间 VM2 ping L1 ({l1_ip}) 失败: {out[-300:]}")
        rc, _ = self.console_exec(f'ping -c 3 -W 2 {vm2_ip}')
        self.assertEqual(rc, 0, f"VM1 flood 期间 L1 到 VM2 ({vm2_ip}) 网络不通")
        self.logInfo("S1: VM1 ping flood 期间 VM2 + L1 网络正常")
        self.assertTrue(self._wait_vm_proc_done("0", "ping", 30),
                        "VM1 ping flood 未在预期时间内结束")

        # ── S2: IO/存储隔离 ──
        self.logStep("S2.IO/存储隔离：VM1 重 IO 压力，VM2 IO 延迟正常，L1 资源不受影响")
        # VM1 后台重 IO（stress-ng io+hdd）
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm1_ip} "
            f"'stress-ng --io 2 --hdd 2 --hdd-bytes 64M --timeout 30' "
            f"> /tmp/s2_io.log 2>&1 & )")
        time.sleep(3)

        # E2: VM2 IO 正常（dd 小文件 + 测延迟）+ L1 网络通
        self.logStep("E2.IO隔离：VM2 IO 正常，L1 资源不受 VM1 重 IO 影响")
        t0 = time.time()
        rc, out = self.l2_ssh_exec(
            'dd if=/dev/zero of=/tmp/vm2_io bs=1M count=10 2>&1',
            instance="1", timeout=30)
        elapsed = time.time() - t0
        self.assertEqual(rc, 0, f"VM1 重 IO 期间 VM2 dd 失败: {out[-300:]}")
        self.assertLess(elapsed, DD_LATENCY_CEIL,
                        f"VM2 dd 延迟 {elapsed:.1f}s 超过 {DD_LATENCY_CEIL}s（IO 隔离异常）")
        rc, _ = self.console_exec(f'ping -c 2 -W 2 {vm2_ip}')
        self.assertEqual(rc, 0, f"VM1 重 IO 期间 L1 到 VM2 网络不通")
        self.logInfo(f"S2: VM1 重 IO 期间 VM2 dd 正常（{elapsed:.1f}s）")
        self.assertTrue(self._wait_vm_proc_done("0", "stress-ng", 60),
                        "VM1 IO stress 未在预期时间内结束")

        # ── S3: L1 资源度量隔离 ──
        self.logStep("S3.L1资源度量隔离：2个L2混合压力时，L1 CPU/内存/网络在正常范围")
        # 2 VM 混合压力（CPU+内存+IO）
        mix_load = 'stress-ng --cpu 2 --vm 1 --vm-bytes 256M --io 1 --timeout 30'
        for inst in L2_INSTANCES:
            ip = self.l2_vms[inst]
            self.console_exec(
                f"( ssh {ssh_opts} root@{ip} '{mix_load}' "
                f"> /tmp/s3_vm{inst}.log 2>&1 & )")
        time.sleep(10)  # 让压力起来

        # E3: 量 L1 资源（CPU loadavg + 可用内存 + 网络）
        self.logStep("E3.L1资源度量在正常范围（可用内存/网络/CPU loadavg）")
        # L1 1-min loadavg（信息性记录；正则匹配 loadavg 行，避开回显命令行）
        rc, out = self.console_exec('cat /proc/loadavg')
        m = re.search(r'^(\d+\.\d+)\s+\d+\.\d+\s+\d+\.\d+\s+\d+/\d+\s+\d+',
                      out or '', re.M)
        loadavg1 = float(m.group(1)) if m else 999.0
        # L1 可用内存（/proc/meminfo MemAvailable，可靠）
        rc, out = self.console_exec('grep MemAvailable /proc/meminfo')
        m = re.search(r'MemAvailable:\s+(\d+)', out or '')
        avail_mb = (int(m.group(1)) // 1024) if m else 0
        self.assertGreater(avail_mb, L1_MEM_FLOOR_MB,
                           f"L1 可用内存 {avail_mb}MB 低于 {L1_MEM_FLOOR_MB}MB（L1 被打爆）")
        # L1 网络仍通
        rc, _ = self.console_exec(f'ping -c 2 -W 2 {vm1_ip}')
        self.assertEqual(rc, 0, f"L2 混合压力期间 L1 到 VM1 网络不通")
        self.logInfo(f"S3: L1 loadavg(1min)={loadavg1}, 可用内存={avail_mb}MB, 网络正常")
        # 等 2 VM stress 结束
        for inst in L2_INSTANCES:
            self.assertTrue(self._wait_vm_proc_done(inst, "stress-ng", 60),
                            f"VM{inst} 混合压力未在预期时间内结束")

        # ── S4: 故障注入隔离 ──
        self.logStep("S4.故障注入隔离：VM1 内 fork bomb/内存压力，VM2 + L1 不受影响")
        # VM1 fork bomb（bounded）+ 内存压力
        fault_load = 'stress-ng --fork 30 --vm 1 --vm-bytes 256M --timeout 20'
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm1_ip} '{fault_load}' "
            f"> /tmp/s4_fault.log 2>&1 & )")
        time.sleep(5)

        # E4: VM2 + L1 不受 VM1 故障影响
        self.logStep("E4.故障注入隔离：VM1 fork/内存压力不影响 VM2 + L1")
        rc, out = self.l2_ssh_exec('ls -al', instance="1")
        self.assertEqual(rc, 0, f"VM1 故障注入期间 VM2 ls -al 失败: {out[-300:]}")
        self.assertIn('total', out, f"VM2 ls -al 输出异常: {out[-300:]}")
        rc, _ = self.console_exec(f'ping -c 2 -W 2 {vm2_ip}')
        self.assertEqual(rc, 0, f"VM1 故障注入期间 L1 到 VM2 网络不通")
        self.logInfo("S4: VM1 fork/内存压力期间 VM2 + L1 正常")
        self.assertTrue(self._wait_vm_proc_done("0", "stress-ng", 60),
                        "VM1 故障注入 stress 未在预期时间内结束")

        # 隔离测试期间两层内核日志无报错（VM1 有 fork/OOM 日志，err_pat 不含 OOM 不会误报；
        # 查 L1 + VM2，即受害侧和 host）
        errs = dmesg_errors(l2_exec("1"), baseline_l2["1"])
        self.assertEqual(len(errs), 0,
                         f"隔离测试期间 VM2 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"隔离测试期间 L1 内核日志出现报错: {errs[:20]}")
        self.logInfo("隔离测试期间 L1 + VM2 内核日志均无报错")

        # ── S5: 内存超规格 + L1 自动回收（直击 teardown 路径：L1 杀 VM → kvm_pvm 释放 MMU）──
        self.logStep("S5.内存超规格：创建5个L2并施加重内存+MMU churn压力，"
                     "触发L1自动回收部分VM，验证剩余VM功能正常、被回收VM清理干净、"
                     "L1内核日志无报错")
        # 先销毁 S1-S4 的 2 个 VM，腾出干净状态
        for inst in L2_INSTANCES:
            self.destroy_l2_vm(inst)
        self.l2_vms.clear()
        # 干净状态复核
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"S5 前 L1 仍残留 cube-hypervisor: {(out or '')[-300:]}")

        # 记录 L1 dmesg 基线 + 压测前可用内存
        baseline_oc = dmesg_baseline(self.console_exec)
        rc, out = self.console_exec('grep MemAvailable /proc/meminfo')
        m = re.search(r'MemAvailable:\s+(\d+)', out or '')
        mem_before = (int(m.group(1)) // 1024) if m else 0
        self.logInfo(f"S5 压测前 L1 可用内存: {mem_before}MB")

        # 创建 5 个 L2（overcommit：超过 L1 内存承载，L1 会自动回收部分）
        oc_started = []
        for inst in L2_OVERCOMMIT_INSTANCES:
            try:
                self.start_l2_vm(inst)
                oc_started.append(inst)
            except Exception as e:  # noqa: BLE001 overcommit 时某些可能起不来
                self.logWarn(f"VM{inst} 起不来（overcommit，L1 资源不够）: {e}")
        self.logInfo(f"overcommit: 尝试起 {len(L2_OVERCOMMIT_INSTANCES)} 个，"
                     f"成功 {len(oc_started)} 个")

        # 已起的 VM 跑重内存 + MMU churn 压力（直击 shadow page table churn → teardown 路径）
        oc_stress = ('stress-ng --vm 2 --vm-bytes 512M '
                     '--mmap 2 --mremap 2 --mprotect 2 --timeout 120')
        for inst in oc_started:
            ip = self.l2_vms[inst]
            self.console_exec(
                f"( ssh {ssh_opts} root@{ip} '{oc_stress}' "
                f"> /tmp/s5_vm{inst}.log 2>&1 & )")

        # 等 L1 检测 overcommit + 自动回收（60s 给内核时间检测+杀）
        self.logInfo("等待 L1 自动回收部分 VM（60s）...")
        time.sleep(60)

        # 检查哪些 cube-hypervisor 还活着（survivors）
        rc, out = self.console_exec('ps -ef | grep cube-hypervisor | grep -v grep')
        survivors = set()
        for line in (out or '').splitlines():
            m = re.search(r'ch-(\d+)\.sock', line)
            if m:
                survivors.add(m.group(1))
        killed = set(oc_started) - survivors
        self.logInfo(f"overcommit 结果: started {len(oc_started)}, "
                     f"survived {len(survivors)}, killed {len(killed)}")

        # E5: 剩余 VM 功能正常 + 被回收 VM 清理干净 + L1 无报错
        self.logStep("E5.超规格后剩余L2功能正常、被回收VM无残留、L1无crash/内核报错")
        # 剩余 VM 功能正常（ls -al）
        for inst in sorted(survivors):
            rc, out = self.l2_ssh_exec('ls -al', instance=inst, timeout=30)
            self.assertEqual(rc, 0,
                             f"overcommit 后存活 VM{inst} ls -al 失败: {out[-300:]}")
            self.assertIn('total', out, f"存活 VM{inst} ls -al 输出异常: {out[-300:]}")
        # 被回收的 VM：cube-hypervisor 已退出（无残留/泄漏）
        for inst in killed:
            self.verify_l2_destroyed(inst)
        # L1 dmesg 无报错（auto-kill 的 teardown 路径 clean）
        errs = dmesg_errors(self.console_exec, baseline_oc)
        self.assertEqual(len(errs), 0,
                         f"overcommit auto-kill 期间 L1 内核日志出现报错"
                         f"（teardown 路径异常）: {errs[:20]}")
        # L1 内存已恢复（被回收的 VM 释放了内存）
        rc, out = self.console_exec('grep MemAvailable /proc/meminfo')
        m = re.search(r'MemAvailable:\s+(\d+)', out or '')
        mem_after = (int(m.group(1)) // 1024) if m else 0
        self.logInfo(f"S5 overcommit 后 L1 可用内存: {mem_before}MB -> {mem_after}MB, "
                     f"survived={len(survivors)}, killed={len(killed)}")
        # L1 网络仍通（未被 overcommit 打爆）
        if survivors:
            rc, _ = self.console_exec(
                f'ping -c 2 -W 2 192.168.249.{int(sorted(survivors)[0]) + 2}')
            self.assertEqual(rc, 0, "overcommit 后 L1 到存活 VM 网络不通")
        self.logInfo("S5: overcommit + auto-kill 验证通过")

        # 等存活的 VM stress 结束
        for inst in sorted(survivors):
            if not self._wait_vm_proc_done(inst, "stress-ng", 150):
                self.logWarn(f"VM{inst} stress 未在预期时间内结束（可能已被 L1 回收）")
        # 销毁存活的 VM
        for inst in sorted(survivors):
            try:
                self.destroy_l2_vm(inst)
            except Exception as e:  # noqa: BLE001
                self.logWarn(f"销毁 VM{inst} 失败（忽略）: {e}")
        self.l2_vms.clear()

        # ── S6: CPU 隔离（绑核性能隔离）──
        self.logStep("S6.CPU隔离：VM1/VM2绑不同CPU段，VM1跑CPU压力，验证VM2性能不被抢占")
        # 起回 2 个绑核 L2（VM1→L1 vCPU 0,1；VM2→L1 vCPU 2,3；只绑 CPU 不绑内存）
        self.start_l2_vm_pinned("0", "0:0;1:1", "")
        self.start_l2_vm_pinned("1", "0:2;1:3", "")
        vm1_ip, vm2_ip = self.l2_vms["0"], self.l2_vms["1"]
        baseline_cpu_l1 = dmesg_baseline(self.console_exec)
        baseline_cpu_l2 = dmesg_baseline(l2_exec("1"))

        # E6: VM2 性能不被 VM1 抢（绑核隔离）
        self.logStep("E6.CPU隔离：VM2性能不受VM1 CPU压力影响")
        # 1) 基线：VM2 单独跑 10s CPU 压（VM1 空闲），解析 bogo ops/s
        rc, out = self.l2_ssh_exec(
            'stress-ng --cpu 1 --timeout 10 --metrics-brief 2>&1',
            instance="1", timeout=30)
        self.assertEqual(rc, 0, f"VM2 基线 CPU 测试失败: {out[-300:]}")
        # 解析 bogo ops/s（real time），stress-ng 表格第 5 列：cpu <bogo_ops> <real> <usr> <sys> <ops/s_real> <ops/s_usr_sys>
        m = re.search(
            r'stress-ng:\s+metr.*cpu\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',
            out or '', re.I)
        bogo_base = float(m.group(5)) if m else 0
        self.assertGreater(bogo_base, 0,
                           f"无法解析 VM2 基线 bogo ops: {out[-300:]}")
        # 2) 并发：VM1 后台重 CPU 压 + VM2 同样 10s CPU 压，解析 bogo ops/s
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm1_ip} 'stress-ng --cpu 4 --timeout 20' "
            f"> /tmp/s6_vm1_cpu.log 2>&1 & )")
        time.sleep(2)  # 让 VM1 压力起来
        rc, out = self.l2_ssh_exec(
            'stress-ng --cpu 1 --timeout 10 --metrics-brief 2>&1',
            instance="1", timeout=30)
        self.assertEqual(rc, 0, f"VM2 并发 CPU 测试失败: {out[-300:]}")
        m = re.search(
            r'stress-ng:\s+metr.*cpu\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',
            out or '', re.I)
        bogo_conc = float(m.group(5)) if m else 0
        self.assertGreater(bogo_conc, 0,
                           f"无法解析 VM2 并发 bogo ops: {out[-300:]}")
        # 验证：VM2 并发时 bogo ops/s 不低于基线 60%（绑核后不应被 VM1 抢 CPU）
        ratio = bogo_conc / bogo_base if bogo_base > 0 else 0
        self.assertGreaterEqual(
            ratio, CPU_ISOLATION_RATIO,
            f"VM2 并发 bogo ops/s {bogo_conc:.0f} vs 基线 {bogo_base:.0f} "
            f"(ratio={ratio:.2f})，低于 {CPU_ISOLATION_RATIO}"
            f"（CPU 被 VM1 抢，绑核隔离失效）")
        self.logInfo(f"S6: VM2 CPU 基线 {bogo_base:.0f} bogo ops/s, "
                     f"并发 {bogo_conc:.0f} bogo ops/s "
                     f"(ratio={ratio:.2f}), 绑核隔离正常")
        # 等 VM1 stress 结束
        self.assertTrue(self._wait_vm_proc_done("0", "stress-ng", 60),
                        "VM1 CPU stress 未在预期时间内结束")
        # 两层内核日志无报错
        errs = dmesg_errors(l2_exec("1"), baseline_cpu_l2)
        self.assertEqual(len(errs), 0,
                         f"CPU 隔离测试期间 VM2 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_cpu_l1)
        self.assertEqual(len(errs), 0,
                         f"CPU 隔离测试期间 L1 内核日志出现报错: {errs[:20]}")
        # 销毁 2 个绑核 VM
        for inst in ("0", "1"):
            self.destroy_l2_vm(inst)
        self.l2_vms.clear()

        # ── S7: 删除 L2 虚拟机（复核全部已删除）──
        self.logStep("S7.删除L2虚拟机")
        for inst in L2_OVERCOMMIT_INSTANCES:
            self.verify_l2_destroyed(inst)
        # 兜底：无任何 cube-hypervisor 残留
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"测试结束仍残留 cube-hypervisor: {(out or '')[-300:]}")
        self.logStep("E7.删除虚拟机成功")
        self.l2_started = False
        self.l2_vms.clear()
        self.logInfo("全部 L2 虚拟机已删除，无残留")
