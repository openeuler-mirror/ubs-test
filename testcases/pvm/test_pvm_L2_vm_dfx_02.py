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
L2_INSTANCES = ("0", "1")        # S1 先启动的 L2 实例号（VM1/VM2）
L2_INSTANCE_OVERSPEC = "2"       # S3 超规格创建的 L2 实例号（VM3）
L2_OVERSPEC_MEM = "8G"


class TestPVML2VmDfx02(PvmBaseCase):
    """验证L2层虚拟机并发读写内存功能正常

    CaseNumber:
        test_pvm_L2_vm_dfx_02
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证L2层虚拟机并发读写内存功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在各个L2虚拟机使用内存读写测试工具进行读写测试，构造一定读写压力并发写、并发读、并发混合读写几分钟
        P3.成功编译L2层虚拟机镜像，镜像中集成内存读写工具（stress、lmbench等）
    TestStep:
        S1.在L1虚拟机中启动多个L2虚拟机（不超过L1虚拟机资源限制）
        S2.读写功能正常，L1和L2虚拟机功能不受影响，两层虚拟机内核日志不出现报错
        S3.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动多个L2虚拟机，内核加载成功
        E2.各个虚拟机ls -al执行结果正常，可以正常回显
        E3.删除虚拟机成功
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
    def test_pvm_L2_vm_dfx_02(self):
        """测试L2层虚拟机并发读写内存功能正常"""

        # 内核日志报错关键字（方括号技巧避免 grep 回显被误判，同 test_pvm_L2_vm_05）
        err_pat = '[O]ops:|[B]UG:|[K]ernel panic|[C]all trace|[I]/O error'

        def dmesg_baseline(exec_fn) -> int:
            """记录当前 dmesg 行数，作为压测前基线"""
            rc, out = exec_fn('dmesg | wc -l')
            return next((int(ln) for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), 0)

        def dmesg_errors(exec_fn, baseline: int) -> list:
            """取 baseline 行之后 dmesg 中的报错行原文（只看压测期间新增日志）"""
            rc, out = exec_fn(f'dmesg | tail -n +{baseline + 1} | grep -iE "{err_pat}"')
            return [ln.strip() for ln in (out or '').splitlines()
                    if re.search(err_pat, ln, re.I)]

        def l2_exec(inst):
            """返回绑定到指定 L2 实例的 exec_fn"""
            return lambda cmd, timeout=60: self.l2_ssh_exec(cmd, timeout, instance=inst)

        all_instances = (*L2_INSTANCES, L2_INSTANCE_OVERSPEC)

        self.logStep("S1.在L1虚拟机中启动多个L2虚拟机（不超过L1虚拟机资源限制）")
        for inst in L2_INSTANCES:
            self.start_l2_vm(inst)
        self.start_l2_vm_overspec(L2_INSTANCE_OVERSPEC, memory=L2_OVERSPEC_MEM)

        self.logStep("E1.可以成功启动多个L2虚拟机，内核加载成功")
        for inst in all_instances:
            ip = self.l2_vms[inst]
            rc, out = self.console_exec(f'ping -c 3 -W 2 {ip}')
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} ({ip}) ping 不通，网络未就绪: {out[-300:]}")
            rc, out = self.l2_ssh_exec('uname -r', instance=inst)
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} 内核未加载（uname -r 失败）: {out[-300:]}")
        self.logInfo("3 个 L2 虚拟机均已启动且内核加载成功")

        self.logStep("S2.读写功能正常，L1和L2虚拟机功能不受影响，两层虚拟机内核日志不出现报错")

        # 压测前记录 L1 + 各 L2 的 dmesg 基线行数，压测后只看期间新增日志
        baseline_l1 = dmesg_baseline(self.console_exec)
        baseline_l2 = {inst: dmesg_baseline(l2_exec(inst)) for inst in all_instances}

        # 确认各 L2 已集成 stress / stress-ng 工具
        for inst in all_instances:
            rc, out = self.l2_ssh_exec('command -v stress && command -v stress-ng',
                                       instance=inst)
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} 缺少 stress/stress-ng 工具: {out[-300:]}")

        # 每个 L2 同时跑 stress 与 stress-ng（均 --timeout 300），6 个 ssh 后台并发，
        # wait 等全部结束（cmd 末尾是 wait 而非 &，避免 &; 语法问题）
        stress_cmd = ('stress --cpu 2 --vm 2 --vm-bytes 512M --io 2 '
                      '--hdd 2 --hdd-bytes 64M --timeout 300')
        stressng_cmd = 'stress-ng --vm 3 --vm-bytes 128M --vm-method all --timeout 300'
        ssh_opts = ('-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
                    '-o ConnectTimeout=5')
        launches = []
        for inst in all_instances:
            ip = self.l2_vms[inst]
            launches.append(
                f"ssh {ssh_opts} root@{ip} '{stress_cmd}' > /tmp/stress_{inst}.log 2>&1 &")
            launches.append(
                f"ssh {ssh_opts} root@{ip} '{stressng_cmd}' > /tmp/stressng_{inst}.log 2>&1 &")
        launch_cmd = ' '.join(launches) + ' wait'
        t0 = time.time()
        rc, out = self.console_exec(launch_cmd, timeout=360)
        elapsed = time.time() - t0
        self.assertNotEqual(rc, -1, f"并发压力测试超时未结束（未捕获结束标记）: {out[-500:]}")
        self.assertGreaterEqual(
            elapsed, 180,
            f"并发压力测试仅耗时 {elapsed:.0f}s，stress/stress-ng 可能未正常执行")
        self.logInfo(f"3 个 L2 并发 stress + stress-ng 已结束，耗时 {elapsed:.0f}s")

        # 压测后各 L2 仍可执行命令、L1->L2 网络仍连通（功能不受影响）
        for inst in all_instances:
            ip = self.l2_vms[inst]
            rc, _ = self.l2_ssh_exec('true', instance=inst)
            self.assertEqual(rc, 0, f"压测后 L2 实例 {inst} 失去响应，功能受影响")
            rc, out = self.console_exec(f'ping -c 3 -W 2 {ip}')
            self.assertEqual(rc, 0,
                             f"压测后 L1 到 L2 实例 {inst} ({ip}) 网络不通，L1 功能受影响")
        self.logInfo("压测后 3 个 L2 功能正常，L1/L2 网络连通")

        # 压测期间（基线之后）L1 + 各 L2 内核日志均无报错（失败时保留报错原文便于定位）
        for inst in all_instances:
            errs = dmesg_errors(l2_exec(inst), baseline_l2[inst])
            self.assertEqual(len(errs), 0,
                             f"压测期间 L2 实例 {inst} 内核日志出现报错: {errs[:20]}")
        errs = dmesg_errors(self.console_exec, baseline_l1)
        self.assertEqual(len(errs), 0, f"压测期间 L1 内核日志出现报错: {errs[:20]}")
        self.logInfo("压测期间 L1 与 3 个 L2 内核日志均无报错")

        self.logStep("E2.各个虚拟机ls -al执行结果正常，可以正常回显")
        # 删除前各 L2 执行 ls -al，确认功能正常
        for inst in all_instances:
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0, f"L2 实例 {inst} 内执行 ls -al 失败: {out[-300:]}")
            self.assertIn('total', out, f"L2 实例 {inst} ls -al 输出异常: {out[-300:]}")
        self.logInfo("删除前 3 个 L2 虚拟机 ls -al 均正常")

        self.logStep("S3.删除L2虚拟机")
        for inst in all_instances:
            self.destroy_l2_vm(inst)

        self.logStep("E3.删除虚拟机成功")
        for inst in all_instances:
            self.verify_l2_destroyed(inst)
        self.l2_started = False
        self.l2_vms = {}
        self.logInfo("全部 L2 虚拟机已删除，VMM 进程均已退出")