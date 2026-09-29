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
L2_INSTANCE_OVERSPEC = "2"       # S3 超规格创建的 L2 实例号（VM3）
L2_OVERSPEC_MEM = "8G"           # S3 超规格 VM 的内存规格
L2_KILL_INSTANCE = L2_INSTANCE_OVERSPEC  # S2 被强杀的 L2 实例号（默认杀超规格 VM3）


class TestPVML2VmDfx03(PvmBaseCase):
    """验证L2层虚拟机崩溃不影响L1与其他虚拟机

    CaseNumber:
        test_pvm_L2_vm_dfx_03
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证L2层虚拟机崩溃不影响L1与其他虚拟机
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.在L1虚拟机中启动多个L2虚拟机（不超过L1虚拟机资源限制）
        S2.在各个L2虚拟机选一个虚拟机，杀死虚拟机
        S3.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动多个L2虚拟机，内核加载成功
        E2.被杀死的虚拟机不影响其他虚拟机功能
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
    def test_pvm_L2_vm_dfx_03(self):
        """测试L2层虚拟机崩溃不影响L1与其他虚拟机"""

        all_instances = (*L2_INSTANCES, L2_INSTANCE_OVERSPEC)
        survivors = [i for i in all_instances if i != L2_KILL_INSTANCE]

        # 启动 3 个 L2 虚拟机（VM1/VM2 普通 + VM3 超规格 8G）
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
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0, f"L2 实例 {inst} ls -al 失败: {out[-300:]}")
            self.assertIn('total', out, f"L2 实例 {inst} ls -al 输出异常: {out[-300:]}")
        self.logInfo("3 个 L2 虚拟机均已启动、内核加载成功且功能正常")

        self.logStep("S2.在各个L2虚拟机选一个虚拟机，杀死虚拟机")
        self.kill_l2_vm(L2_KILL_INSTANCE)

        self.logStep("E2.被杀死的虚拟机不影响其他虚拟机功能")
        killed_ip = self.l2_vms[L2_KILL_INSTANCE]
        # 被杀 VM 的 VMM 已退出（kill_l2_vm 内部已轮询确认），复核一次进程数
        self.verify_l2_destroyed(L2_KILL_INSTANCE)
        # 被杀 VM 不再可达（ping 应失败）
        rc, out = self.console_exec(f'ping -c 3 -W 2 {killed_ip}')
        self.assertNotEqual(rc, 0,
                            f"被杀的 L2 实例 {L2_KILL_INSTANCE} ({killed_ip}) 仍可 ping 通，"
                            f"未真正杀死")
        # 其余 VM 仍可执行命令、L1->L2 网络仍连通（功能不受影响）
        for inst in survivors:
            ip = self.l2_vms[inst]
            rc, out = self.l2_ssh_exec('ls -al', instance=inst)
            self.assertEqual(rc, 0,
                             f"杀死其他 VM 后，L2 实例 {inst} ls -al 失败: {out[-300:]}")
            self.assertIn('total', out,
                          f"杀死其他 VM 后，L2 实例 {inst} ls -al 输出异常: {out[-300:]}")
            rc, out = self.console_exec(f'ping -c 3 -W 2 {ip}')
            self.assertEqual(rc, 0,
                             f"杀死其他 VM 后，L1 到 L2 实例 {inst} ({ip}) 网络不通")
        self.logInfo(f"杀死 L2 实例 {L2_KILL_INSTANCE} 后，其余 {len(survivors)} 个 L2 功能正常")

        self.logStep("S3.删除L2虚拟机")
        for inst in all_instances:
            self.destroy_l2_vm(inst)

        self.logStep("E3.删除虚拟机成功")
        for inst in all_instances:
            self.verify_l2_destroyed(inst)
        self.l2_started = False
        self.l2_vms = {}
        self.logInfo("全部 L2 虚拟机已删除，VMM 进程均已退出")