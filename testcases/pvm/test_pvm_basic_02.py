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
LOOP_COUNT = 30                 # ko 安装/卸载循环次数
MEM_LEAK_THRESHOLD_MB = 50      # 循环前后 available 内存允许波动上限（MB），超过判定为泄漏


class TestPvmBasic02(PvmBaseCase):
    """验证PVM模块反复安装与卸载成功且不出现内存泄漏

    CaseNumber:
        test_pvm_basic_02
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证PVM模块反复安装与卸载成功且不出现内存泄漏
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
    TestStep:
        S1.在L1虚拟机rmmod kvm-pvm后 insmod多次
        S2.多次安装卸载前后使用free查看有没有内存泄漏
        S3.创建启动L2虚拟机
    ExpectedResult:
        E1.多次安装卸载ko文件都正常
        E2.不存在内存泄漏
        E3.启动L2虚拟机运行正常
    Author:
        yangfan
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

    def _parse_free_avail(self, out):
        """从 `free -m` 输出解析 Mem 行 available 内存（MB）。

        util-linux free 的 Mem 行列为 total/used/free/shared/buff/cache/available，
        取 available（parts[6]）；精简 busybox free 无 available 列时回退取 free。
        """
        for line in (out or '').splitlines():
            if line.strip().startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 7:
                    return int(parts[6])      # available
                if len(parts) >= 4:
                    return int(parts[3])      # free（回退）
        return None

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_basic_02(self):
        """测试PVM基本模块安装与卸载成功"""
        self.logStep("S1.在L1虚拟机rmmod kvm-pvm后 insmod多次")
        # 清理残留 ko，保证首轮 rmmod+insmod 真实执行；insmod 建立已加载基线
        self.console_exec(f'rmmod {self.PVM_KO} 2>/dev/null')
        rc, out = self.console_exec(f'insmod {self.PVM_KO}; lsmod | grep -w kvm_pvm')
        self.assertEqual(rc, 0, f"初始 insmod kvm-pvm.ko 失败: {out[-300:]}")
        self.logInfo("初始 rmmod+insmod 成功，kvm-pvm 已加载")

        self.logStep("S2.多次安装卸载前后使用free查看有没有内存泄漏")
        # 循环前记录 available 基线（ko 已加载），循环后 ko 仍处于加载态，二者可比
        rc, out = self.console_exec('free -m')
        self.assertEqual(rc, 0, f"执行 free -m 失败: {(out or '')[-300:]}")
        self.logInfo(f"循环前 free -m:\n{(out or '').strip()[-400:]}")
        mem_before = self._parse_free_avail(out)
        self.assertTrue(mem_before is not None,
                        f"无法解析 free -m 基线内存: {(out or '')[-300:]}")
        self.logInfo(f"循环前 available 内存: {mem_before} MB")

        # 每轮：rmmod（容忍失败，模块可能未加载）+ insmod（须成功）+ lsmod 校验
        fail = 0
        for i in range(1, LOOP_COUNT + 1):
            rc, out = self.console_exec(
                f'rmmod {self.PVM_KO} 2>/dev/null; '
                f'insmod {self.PVM_KO} && lsmod | grep -w kvm_pvm >/dev/null '
                f'&& echo CYCLE_OK || echo CYCLE_FAIL', timeout=30)
            if 'CYCLE_OK' in (out or ''):
                if i % 10 == 0:
                    self.logInfo(f"已完成 {i}/{LOOP_COUNT} 轮 安装/卸载")
            else:
                fail += 1
                self.logWarn(f"第 {i}/{LOOP_COUNT} 轮 安装/卸载失败: {(out or '')[-200:]}")

        rc, out = self.console_exec('free -m')
        self.assertEqual(rc, 0, f"执行 free -m 失败: {(out or '')[-300:]}")
        self.logInfo(f"循环后 free -m:\n{(out or '').strip()[-400:]}")
        mem_after = self._parse_free_avail(out)
        self.assertTrue(mem_after is not None,
                        f"无法解析 free -m 循环后内存: {(out or '')[-300:]}")
        self.logInfo(f"循环后 available 内存: {mem_after} MB")

        # ===== E1.多次安装卸载ko文件都正常 =====
        self.logStep("E1.多次安装卸载ko文件都正常")
        self.assertEqual(fail, 0,
                         f"{fail}/{LOOP_COUNT} 轮安装/卸载失败")

        self.logStep("E2.不存在内存泄漏")
        drop = mem_before - mem_after
        self.assertLess(drop, MEM_LEAK_THRESHOLD_MB,
                        f"循环后 available 内存下降 {drop} MB（基线 {mem_before} -> "
                        f"{mem_after}），超过阈值 {MEM_LEAK_THRESHOLD_MB} MB，疑似内存泄漏")
        self.logInfo(f"循环前后 available 内存波动 {drop} MB，未超过阈值，无内存泄漏")

        self.logStep("S3.创建启动L2虚拟机")
        # 最后一轮 insmod 已加载 ko，直接启动 L2
        self.start_l2_vm(L2_INSTANCE)

        self.logStep("E3.启动L2虚拟机运行正常")
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, f"启动后 L2 ({self.l2_ip}) ping 不通，运行异常")
        self.logInfo(f"L2 ({self.l2_ip}) 启动成功，运行正常")