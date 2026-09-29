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
L2_INSTANCES = ("0", "1")        # S1 先启动的 L2 实例号（VM1/VM2）
L2_INSTANCE_OVERSPEC = "2"       # 超规格创建的 L2 实例号（VM3）
L2_OVERSPEC_MEM = "8G"           # VM3 超规格 VM 的内存规格
REPEAT_COUNT = 10               # S2 反复 删除->再次创建 的次数


class TestPVML2VmDfx04(PvmBaseCase):
    """验证L2层虚拟机反复创建删除功能正常

    CaseNumber:
        test_pvm_L2_vm_dfx_04
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证L1层可以启动多个L2层虚拟机且功能正常
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.在L1虚拟机中启动多个L2虚拟机（不超过L1虚拟机资源限制）
        S2.删除L2虚拟机，再次创建L2虚拟机，反复10次
        S3.关闭L2层虚拟机
        S4.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动多个L2虚拟机，内核加载成功
        E2.各个虚拟机ls -al执行结果正常，可以正常回显
        E3.关闭成功
        E4.删除虚拟机成功
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
    def test_pvm_L2_vm_dfx_04(self):
        """测试L2层虚拟机反复创建删除功能正常"""

        self.logStep("S1.在L1虚拟机中启动多个L2虚拟机（不超过L1虚拟机资源限制）")
        for inst in L2_INSTANCES:
            self.start_l2_vm(inst)
        self.start_l2_vm_overspec(L2_INSTANCE_OVERSPEC, memory=L2_OVERSPEC_MEM)

        self.logStep("E1.可以成功启动多个L2虚拟机，内核加载成功")
        for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
            ip = self.l2_vms[inst]
            rc, out = self.console_exec(f'ping -c 3 -W 2 {ip}')
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} ({ip}) ping 不通，网络未就绪: {out[-300:]}")
            rc, out = self.l2_ssh_exec('uname -r', instance=inst)
            self.assertEqual(rc, 0,
                             f"L2 实例 {inst} 内核未加载（uname -r 失败）: {out[-300:]}")
        self.logInfo("3 个 L2 虚拟机均已启动且内核加载成功")

        self.logStep("E2.各个虚拟机ls -al执行结果正常，可以正常回显")
        for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0, f"L2 实例 {inst} ls -al 失败: {out[-300:]}")
            self.assertIn('total', out, f"L2 实例 {inst} ls -al 输出异常: {out[-300:]}")
        self.logInfo("3 个 L2 虚拟机 ls -al 均正常")

        self.logStep("S2.删除L2虚拟机，再次创建L2虚拟机，反复10次")
        for i in range(1, REPEAT_COUNT + 1):
            # 删除全部 3 个 L2
            for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
                self.destroy_l2_vm(inst)
            # 重新创建全部（VM1/VM2 普通 + VM3 超规格 8G）
            for inst in L2_INSTANCES:
                self.start_l2_vm(inst)
            self.start_l2_vm_overspec(L2_INSTANCE_OVERSPEC, memory=L2_OVERSPEC_MEM)
            # 每次创建后验证各 L2 功能正常（ls -al）
            for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
                rc, out = self.l2_ssh_exec('ls -al', instance=inst)
                self.assertEqual(rc, 0,
                                 f"第 {i} 次重建后 L2 实例 {inst} ls -al 失败: {out[-300:]}")
                self.assertIn('total', out,
                              f"第 {i} 次重建后 L2 实例 {inst} ls -al 输出异常: {out[-300:]}")
            self.logInfo(f"第 {i} 次重建 3 个 L2 虚拟机完成，各 ls -al 正常")
        self.logInfo(f"反复 {REPEAT_COUNT} 次删除/重建，每次各 L2 ls -al 均正常")

        self.logStep("S3.关闭L2层虚拟机")
        for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
            self.shutdown_l2_vm(inst)

        self.logStep("E3.关闭成功")
        for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
            state = self.l2_status(inst)
            self.assertEqual(state, 'Created',
                             f"L2 实例 {inst} 关闭后状态异常: {state}（期望 Created）")
        self.logInfo("3 个 L2 虚拟机均已关闭")

        self.logStep("S4.删除L2虚拟机")
        for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
            self.destroy_l2_vm(inst)

        self.logStep("E4.删除虚拟机成功")
        for inst in (*L2_INSTANCES, L2_INSTANCE_OVERSPEC):
            self.verify_l2_destroyed(inst)
        self.l2_started = False
        self.l2_vms = {}
        self.logInfo("全部 L2 虚拟机反复创建/删除验证通过，已删除")