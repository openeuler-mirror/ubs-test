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
L2_INSTANCES = ("0", "1", "2")    # 并发用例的 3 个 L2 实例号（VM1/VM2/VM3）
STRESS_SECS = 120                 # 压测时长（秒）；recv/轮询超时会据此 + 缓冲自动放宽


class TestPVML2Vm09(PvmBaseCase):
    """验证L2层虚拟机并发生命周期与混合压力下的并发隔离功能正常

    CaseNumber:
        test_pvm_L2_vm_09
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证L2层虚拟机并发生命周期与混合压力下的并发隔离功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.VM1运行压力期间，并发对VM2/VM3执行创建与删除（生命周期混合工作负载并发）
        S2.并发（并行）创建3个L2虚拟机后再并发删除，验证并发创建竞态下功能正常
        S3.3个L2虚拟机并发执行差异化压力（CPU/内存/IO），验证并发隔离功能正常
        S4.L2执行MMU/影子页表churn压力后删除，验证MMU teardown路径无crash
        S5.L2执行触发KVM退出/仿真的压力（fork/sigsegv/timer）后删除，验证退出处理路径正常
        S6.多个L2并发执行"创建→安全负载→删除"churn，验证并发init/teardown无竞态
        S7.某个L2虚拟机重启，其他L2虚拟机跑业务正常，重启的L2虚拟机也正常启动
        S8.删除L2虚拟机
    ExpectedResult:
        E1.并发生命周期操作不影响VM1工作负载，VM1功能正常，两层虚拟机内核日志不出现报错
        E2.并发创建/删除3个L2虚拟机均成功，无竞态失败
        E3.差异化并发压力下3个L2虚拟机功能正常，两层虚拟机内核日志不出现报错
        E4.MMU churn后删除L2，L1虚拟机无crash/内核报错，VM正常销毁
        E5.退出压力后删除L2，L1虚拟机无crash/内核报错
        E6.并发churn下各L2创建/删除均成功，无init/teardown竞态失败，L1无crash
        E7.重启L2不影响其他L2虚拟机业务
        E8.删除虚拟机成功
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

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_L2_vm_09(self):
        """测试L2层虚拟机并发生命周期与混合压力下的并发隔离功能正常"""

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

        # ── S1: VM1 压力期间并发对 VM2/VM3 创建/删除（生命周期混合工作负载）──
        self.logStep("S1.VM1运行压力期间，并发对VM2/VM3执行创建与删除（生命周期混合工作负载并发）")
        self.start_l2_vm("0")
        vm1_ip = self.l2_vms["0"]
        baseline_l1 = dmesg_baseline(self.console_exec)
        baseline_vm1 = dmesg_baseline(l2_exec("0"))
        # VM1 压力后台跑（subshell 避免 &; 语法，disowned，靠轮询 VM1 内 stress 进程判活）
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm1_ip} "
            f"'stress --cpu 2 --vm 1 --vm-bytes 512M --timeout {STRESS_SECS}' "
            f"> /tmp/p1_vm1.log 2>&1 & )")
        # VM1 压力在后台跑期间，sync 对 VM2/VM3 做 创建->删除（与 VM1 压力并发）
        self.start_l2_vm("1")
        self.destroy_l2_vm("1")
        self.start_l2_vm("2")
        self.destroy_l2_vm("2")
        # 轮询 VM1 内 stress 结束（避免残留压力影响后续 S2）
        done = False
        deadline = time.time() + STRESS_SECS + 30
        while time.time() < deadline:
            _, o = self.l2_ssh_exec('pgrep -x stress | wc -l', instance="0", timeout=15)
            cnt = next((ln.strip() for ln in (o or '').splitlines()
                        if ln.strip().isdigit()), None)
            if cnt == '0':
                done = True
                break
            time.sleep(3)
        self.assertTrue(done, "VM1 压力未在预期时间内结束")

        # E1: VM1 功能正常 + 两层内核日志无报错
        self.logStep("E1.并发生命周期操作不影响VM1工作负载，VM1功能正常，"
                     "两层虚拟机内核日志不出现报错")
        rc, out = self.l2_ssh_exec('ls -al', instance="0")
        self.assertEqual(rc, 0, f"VM1 压力后 ls -al 失败: {out[-300:]}")
        self.assertIn('total', out, f"VM1 ls -al 输出异常: {out[-300:]}")
        errs = dmesg_errors(l2_exec("0"), baseline_vm1)
        self.assertEqual(len(errs), 0, f"VM1 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_l1)
        self.assertEqual(len(errs), 0, f"L1 内核日志出现报错: {errs[:20]}")
        self.logInfo("VM1 压力期间并发 lifecycle 对 VM2/VM3，VM1 不受影响")
        # S1 收尾：删除 VM1，清空 l2_vms（VM2/VM3 期间已删）
        self.destroy_l2_vm("0")
        self.l2_vms.clear()

        # ── S2: 并发（并行）创建 3 个 VM + 并发删除（竞态）──
        self.logStep("S2.并发（并行）创建3个L2虚拟机后再并发删除，验证并发创建竞态下功能正常")
        # 并行起 3 个（后台 + wait，单条命令避免 &; 语法问题）
        starts = [f'bash {self.L2_HANDLE_SCRIPT} --start {inst} '
                  f'> /tmp/p2_start_{inst}.log 2>&1 &' for inst in L2_INSTANCES]
        rc, out = self.console_exec(' '.join(starts) + ' wait', timeout=300)
        self.assertNotEqual(rc, -1, f"并发创建未正常结束: {out[-500:]}")

        # E2: 并发创建/删除 3 个 VM 均成功
        self.logStep("E2.并发创建/删除3个L2虚拟机均成功，无竞态失败")
        for inst in L2_INSTANCES:
            _, lout = self.console_exec(f'cat /tmp/p2_start_{inst}.log')
            self.assertNotIn('FAILED:', lout,
                             f"并发创建 VM{inst} 失败（竞态）: {lout[-300:]}")
            m = re.search(r'SUCCESS: (\d+\.\d+\.\d+\.\d+)', lout)
            self.assertTrue(m, f"并发创建 VM{inst} 未报告 SUCCESS: {lout[-300:]}")
            self.l2_vms[inst] = m.group(1)
            rc, _ = self.console_exec(f'ping -c 2 -W 2 {self.l2_vms[inst]}')
            self.assertEqual(rc, 0,
                             f"并发创建后 VM{inst} ({self.l2_vms[inst]}) ping 不通")
        self.logInfo("并行创建 3 个 VM 成功，无竞态失败")
        # 并发删除 3 个
        deletes = [f'bash {self.L2_HANDLE_SCRIPT} --delete {inst} '
                   f'> /tmp/p2_del_{inst}.log 2>&1 &' for inst in L2_INSTANCES]
        self.console_exec(' '.join(deletes) + ' wait', timeout=120)
        for inst in L2_INSTANCES:
            self.verify_l2_destroyed(inst)
        self.l2_vms.clear()
        self.logInfo("并行删除 3 个 VM 成功")

        # ── S3: 3 VM 差异化并发压力（CPU/内存/IO）──
        self.logStep("S3.3个L2虚拟机并发执行差异化压力（CPU/内存/IO），"
                     "验证并发隔离功能正常")
        for inst in L2_INSTANCES:
            self.start_l2_vm(inst)
        baseline_l1 = dmesg_baseline(self.console_exec)
        baseline_l2 = {inst: dmesg_baseline(l2_exec(inst)) for inst in L2_INSTANCES}
        # 3 个差异化压力源并发（VM1=CPU, VM2=内存, VM3=IO）
        stressors = {
            "0": f'stress --cpu 4 --timeout {STRESS_SECS}',                         # CPU 压
            "1": f'stress --vm 2 --vm-bytes 512M --timeout {STRESS_SECS}',          # 内存压
            "2": f'stress --io 2 --hdd 2 --hdd-bytes 64M --timeout {STRESS_SECS}',  # IO 压
        }
        launches = [f"ssh {ssh_opts} root@{self.l2_vms[inst]} '{stressors[inst]}' "
                    f"> /tmp/p3_vm{inst}.log 2>&1 &" for inst in L2_INSTANCES]
        rc, out = self.console_exec(' '.join(launches) + ' wait', timeout=STRESS_SECS + 60)
        self.assertNotEqual(rc, -1, f"差异化并发压力未正常结束: {out[-500:]}")

        # E3: 各 VM 功能正常 + 两层内核日志无报错
        self.logStep("E3.差异化并发压力下3个L2虚拟机功能正常，"
                     "两层虚拟机内核日志不出现报错")
        for inst in L2_INSTANCES:
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0, f"VM{inst} 压力后 ls -al 失败: {out[-300:]}")
            self.assertIn('total', out, f"VM{inst} ls -al 输出异常: {out[-300:]}")
            errs = dmesg_errors(l2_exec(inst), baseline_l2[inst])
            self.assertEqual(len(errs), 0,
                             f"VM{inst} 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_l1)
        self.assertEqual(len(errs), 0, f"L1 内核日志出现报错: {errs[:20]}")
        self.logInfo("差异化并发压力下 3 个 VM 功能正常，内核日志无报错")
        # S3 收尾：销毁 3 个 VM，为后续安全负载 churn 角度腾出干净状态
        for inst in L2_INSTANCES:
            self.destroy_l2_vm(inst)
        self.l2_vms.clear()
        # 复核干净：S3 的 3 个 VM 都已销毁，且无任何 cube-hypervisor 残留
        for inst in L2_INSTANCES:
            self.verify_l2_destroyed(inst)
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"S3 后仍残留 cube-hypervisor: {(out or '')[-300:]}")

        # ===== 安全负载 churn 角度（对准客户"用完删除重建+执行安全进程"真实路径）=====
        # 共用 dmesg 基线：S4/S5/S6 任一 teardown 若致 L1 Oops/panic 都能在此后被检出
        baseline_sec = dmesg_baseline(self.console_exec)

        # ── S4: MMU/影子页表 churn + destroy（直击已知 MMU teardown bug 路径，靠负载触发）──
        self.logStep("S4.L2执行MMU/影子页表churn压力后删除，验证MMU teardown路径无crash")
        self.start_l2_vm("0")
        rc, out = self.l2_ssh_exec(
            'stress-ng --mmap 2 --mremap 2 --mprotect 2 --timeout 60 --metrics-brief',
            instance="0", timeout=120)
        self.assertEqual(rc, 0, f"L2 内 MMU churn 压力失败: {out[-500:]}")
        self.logInfo("MMU churn 完成，开始 destroy（触发 MMU teardown）")
        self.destroy_l2_vm("0")
        self.verify_l2_destroyed("0")
        self.logStep("E4.MMU churn后删除L2，L1虚拟机无crash/内核报错，VM正常销毁")
        errs = dmesg_errors(self.console_exec, baseline_sec)
        self.assertEqual(len(errs), 0,
                         f"MMU churn teardown 后 L1 内核报错: {errs[:20]}")
        self.logInfo("MMU churn 后 destroy，L1 无 crash")

        # ── S5: KVM 退出/仿真路径压力 + destroy（fork/sigsegv/timer 触发退出）──
        self.logStep("S5.L2执行触发KVM退出/仿真的压力（fork/sigsegv/timer）后删除，"
                     "验证退出处理路径正常")
        self.start_l2_vm("0")
        rc, out = self.l2_ssh_exec(
            'stress-ng --fork 2 --sigsegv 2 --timer 2 --timeout 30 --metrics-brief',
            instance="0", timeout=90)
        self.assertEqual(rc, 0, f"L2 内退出/仿真压力失败: {out[-500:]}")
        self.logInfo("退出/仿真压力完成，开始 destroy")
        self.destroy_l2_vm("0")
        self.verify_l2_destroyed("0")
        self.logStep("E5.退出/仿真压力后删除L2，L1无crash/内核报错")
        errs = dmesg_errors(self.console_exec, baseline_sec)
        self.assertEqual(len(errs), 0,
                         f"退出/仿真 teardown 后 L1 内核报错: {errs[:20]}")
        self.logInfo("退出压力后 destroy，L1虚拟机无 crash")

        # ── S6: 多 L2 并发"创建→安全负载→删除"churn（产品侧 init/teardown 交织）──
        self.logStep("S6.多个L2并发执行'创建→安全负载→删除'churn，"
                     "验证并发init/teardown无竞态")
        # 每个 L2: start → 安全短负载 → delete，3 个并发；IP 用 handle_l2.sh 固定公式
        sec_load = 'stress-ng --mmap 1 --mremap 1 --fork 1 --sigsegv 1 --timeout 20'
        churns = []
        for inst in L2_INSTANCES:
            ip = f"192.168.249.{int(inst) + 2}"
            cmd = (f'bash {self.L2_HANDLE_SCRIPT} --start {inst} && '
                   f"ssh {ssh_opts} root@{ip} '{sec_load}' && "
                   f'bash {self.L2_HANDLE_SCRIPT} --delete {inst}')
            churns.append(f'{{ {cmd}; }} > /tmp/s6_churn_{inst}.log 2>&1 &')
        rc, out = self.console_exec(' '.join(churns) + ' wait', timeout=300)
        self.assertNotEqual(rc, -1, f"并发 churn 未正常结束: {out[-500:]}")
        self.logStep("E6.并发churn下各L2创建/删除均成功，无init/teardown竞态失败，"
                     "L1无crash")
        for inst in L2_INSTANCES:
            _, lout = self.console_exec(f'cat /tmp/s6_churn_{inst}.log')
            self.assertNotIn('FAILED:', lout,
                             f"并发 churn VM{inst} 失败: {lout[-300:]}")
            self.assertIn('SUCCESS:', lout,
                          f"并发 churn VM{inst} 未起: {lout[-300:]}")
            self.assertIn('DELETED:', lout,
                          f"并发 churn VM{inst} 未删: {lout[-300:]}")
            self.verify_l2_destroyed(inst)
        errs = dmesg_errors(self.console_exec, baseline_sec)
        self.assertEqual(len(errs), 0,
                         f"并发 churn 后 L1虚拟机 内核报错: {errs[:20]}")
        self.logInfo("多 L2 并发 churn，无竞态失败，L1虚拟机无 crash")
        # S6→S7 之间：复核无任何 cube-hypervisor 残留（确保 S7 起的是干净的 3 个新 VM）
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"S6 后仍残留 cube-hypervisor（S7 将在不干净状态起 VM）: "
                         f"{(out or '')[-300:]}")

        # ── S7: 某个 L2 重启，其他 L2 跑 stress-ng 业务正常，重启的 L2 也正常启动 ──
        self.logStep("S7.某个L2虚拟机重启，其他L2虚拟机跑业务正常，重启的L2虚拟机也正常启动")
        # 起回 3 个 L2（S6 已全部销毁）
        for inst in L2_INSTANCES:
            self.start_l2_vm(inst)
        baseline_l1 = dmesg_baseline(self.console_exec)
        # VM0/VM1（业务 VM）的 dmesg 基线；VM3 重启后 dmesg 会重置，单独不比基线
        baseline_biz = {inst: dmesg_baseline(l2_exec(inst)) for inst in ("0", "1")}
        # VM0/VM1 后台跑 stress-ng 业务（CPU/内存/IO 混合），覆盖 VM3 重启期间
        biz_load = ('stress-ng --cpu 2 --vm 1 --vm-bytes 512M --io 2 '
                    '--hdd 2 --hdd-bytes 64M --timeout 90 --metrics-brief')
        for inst in ("0", "1"):
            ip = self.l2_vms[inst]
            self.console_exec(
                f"( ssh {ssh_opts} root@{ip} '{biz_load}' "
                f"> /tmp/s7_biz_{inst}.log 2>&1 & )")
        # 重启 VM3（instance 2）via cloud-hypervisor vm.reboot（curl -sf 失败时 rc!=0）
        # 若 vm.reboot 不 in-place 重启（VM3 不恢复），改用 shutdown_l2_vm+boot_l2_vm
        rc, out = self.console_exec(
            'curl -sf -o /dev/null --unix-socket /tmp/ch-2.sock '
            '-X PUT http://localhost/api/v1/vm.reboot', timeout=30)
        self.assertEqual(rc, 0, f"VM3 vm.reboot 失败: {out[-300:]}")
        # 轮询 VM3 重启后 SSH 就绪（重启的 L2 正常启动）
        back = False
        deadline = time.time() + 120
        while time.time() < deadline:
            rc, _ = self.l2_ssh_exec('true', instance="2", timeout=15)
            if rc == 0:
                back = True
                break
            time.sleep(3)
        self.assertTrue(back, "VM3 重启后未在预期时间内恢复 SSH（未正常启动）")
        # 轮询 VM0/VM1 业务 stress-ng 结束（业务不被 VM3 重启打断）
        biz_done = False
        deadline = time.time() + 120
        while time.time() < deadline:
            _, o0 = self.l2_ssh_exec('pgrep -x stress-ng | wc -l', instance="0", timeout=15)
            _, o1 = self.l2_ssh_exec('pgrep -x stress-ng | wc -l', instance="1", timeout=15)
            c0 = next((ln.strip() for ln in (o0 or '').splitlines()
                       if ln.strip().isdigit()), None)
            c1 = next((ln.strip() for ln in (o1 or '').splitlines()
                       if ln.strip().isdigit()), None)
            if c0 == '0' and c1 == '0':
                biz_done = True
                break
            time.sleep(3)
        self.assertTrue(biz_done,
                        "VM0/VM1 业务 stress-ng 未在预期时间内结束（被 VM3 重启影响）")

        # E7: 业务 VM0/VM1 stress-ng 跑完且功能正常 + 重启的 VM3 正常启动
        self.logStep("E7.重启L2不影响其他L2虚拟机业务")
        # 业务 VM0/VM1：stress-ng 跑完 + 功能正常（不受 VM3 重启影响）
        for inst in ("0", "1"):
            ip = self.l2_vms[inst]
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0,
                             f"VM3 重启后 VM{inst} 业务 ls -al 失败: {out[-300:]}")
            self.assertIn('total', out, f"VM{inst} ls -al 输出异常: {out[-300:]}")
            rc, _ = self.console_exec(f'ping -c 2 -W 2 {ip}')
            self.assertEqual(rc, 0,
                             f"VM3 重启后 L1 到 VM{inst} ({ip}) 网络不通")
        # 重启的 L2（VM3）正常启动
        rc, out = self.l2_ssh_exec('ls -al', instance="2")
        self.assertEqual(rc, 0, f"重启后 VM3 ls -al 失败: {out[-300:]}")
        self.assertIn('total', out, f"重启后 VM3 ls -al 输出异常: {out[-300:]}")
        # 两层内核日志无报错（VM3 dmesg 重启后已重置，只查 L1 + 业务 VM0/VM1）
        for inst in ("0", "1"):
            errs = dmesg_errors(l2_exec(inst), baseline_biz[inst])
            self.assertEqual(len(errs), 0,
                             f"VM3 重启期间 VM{inst} 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"VM3 重启期间 L1 内核日志出现报错: {errs[:20]}")
        self.logInfo("VM3 重启，VM0/VM1 业务 stress-ng 正常跑完，重启的 VM3 正常启动，无内核报错")
        # S7 收尾：销毁 3 个 L2
        for inst in L2_INSTANCES:
            self.destroy_l2_vm(inst)

        # ── S8: 复核全部已删除 ──
        self.logStep("S8.删除L2虚拟机")
        for inst in L2_INSTANCES:
            self.verify_l2_destroyed(inst)
        # 兜底：任何 cube-hypervisor 都不能残留（比按实例名查更严，抓别的 socket/泄漏）
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"测试结束仍残留 cube-hypervisor 进程: {(out or '')[-300:]}")

        self.logStep("E8.删除虚拟机成功")
        self.l2_started = False
        self.l2_vms.clear()
        self.logInfo("全部 L2 虚拟机已删除，VMM 进程均已退出（含兜底复核无残留）")
