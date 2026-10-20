#!/usr/local/python
# -*- coding: utf-8 -*-
'''
用例说明：
1. L1镜像部署时已经备好，/root目录下自带pvm代码，ko在/root/pvm/arch/arm64/kvm/kvm-pvm.ko
2. L2虚机生命周期由/home/handle_l2.sh管理：--start拉起（bash /home/handle_l2.sh --start 0拉起0号实例，实例ip可通过回显获取）
3. L2虚机快照/恢复由/home/handle_l2_snap.sh管理：--full全量快照/--inc增量快照/--restore恢复
   （机器可读回显 SNAPSHOT_OK: <name> | RESTORE_OK: <name> | FAILED: <reason>）
   注意：快照动作会把VM置为Paused且不自动恢复，需 handle_l2.sh --resume 后才能继续操作L2
'''

import re
import time

import pytest

from libs.modules.pvm.basecase.pvm_basecase import PvmBaseCase

# ===== 本用例可按需调整的参数 =====
L2_INSTANCE = "0"               # 传给脚本的参数：实例号 N 或显式 IP（192.168.249.0/24）


class TestPVML2Vm04(PvmBaseCase):
    """验证L2层虚拟机制作快照并恢复虚拟机成功

    CaseNumber:
        test_pvm_L2_vm_04
    RunLevel:
        Level 1
    EnvType:

    CaseName:
        验证L2层虚拟机制作快照并恢复虚拟机成功
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.在L1虚拟机中启动L2虚拟机
        S2.保存全量快照
        S3.root目录touch文件test1，保存增量快照
		S4.删除L2虚拟机，使用全量快照恢复虚拟机
		S5.使用增量快照恢复虚拟机
		S6.快照恢复后时钟验证：记录恢复前后guest时间，验证时间不倒退不冻结、定时器恢复正常
		S7.删除L2虚拟机
    ExpectedResult:
        E1.可以成功启动L2虚拟机，内核加载成功，日志记录相关信息
        E2.全量快照保存成功
        E3.文件创建成功，增量快照保存正常
		E4.删除虚拟机后恢复的虚拟机root目录没有test1文件
		E5.再次使用增量快照恢复的虚拟机root目录有test1文件
		E6.快照恢复后guest时间正常前进（不倒退/不冻结），定时器继续运行
		E7.删除虚拟机成功
    Author:
        handongkang
    """

    # ===== 前置资源路径 =====
    PVM_KO = "/root/pvm/arch/arm64/kvm/kvm-pvm.ko"  # L1镜像自带 pvm 代码及 ko
    L2_ROOTFS = "/home/rootfs.cpio.gz"              # L2 虚拟机根文件系统镜像
    SNAP_SCRIPT = "/home/handle_l2_snap.sh"         # L2 快照/恢复管理脚本
    TEST_FILE = "/root/test1"                       # S3 在 L2 内创建的验证文件
    FULL_SNAP = "pvm04_full"                        # 全量快照名
    INC_SNAP = "pvm04_inc"                          # 增量快照名（base=FULL_SNAP）

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
    def test_pvm_L2_vm_04(self):
        """测试L2层虚拟机制作快照并恢复虚拟机成功"""

        # ===== S1.在L1虚拟机中启动L2虚拟机 =====
        self.logStep("S1.在L1虚拟机中启动L2虚拟机")
        self.start_l2_vm(L2_INSTANCE)

        self.logStep("E1.可以成功启动L2虚拟机，内核加载成功，日志记录相关信息")
        rc, out = self.console_exec(f'ping -c 3 -W 2 {self.l2_ip}')
        self.assertEqual(rc, 0, f"L2 ({self.l2_ip}) ping 不通，网络未就绪")
        rc, out = self.l2_ssh_exec('uname -r')
        self.assertEqual(rc, 0, f"L2 内核未加载（uname 失败）: {out[-300:]}")
        self.logInfo(f"L2 ({self.l2_ip}) 启动成功，内核已加载: {out.splitlines()[-1].strip() if out else ''}")

        # ===== S2.保存全量快照 =====
        self.logStep("S2.保存全量快照")
        # 清理上次运行遗留的同名快照（脚本对已存在目录会报 dest_exists）
        rc, out = self.console_exec(f'rm -rf /home/snap-{self.FULL_SNAP} /home/snap-{self.INC_SNAP}')
        self.assertEqual(rc, 0, f"清理遗留快照目录失败: {out[-300:]}")
        rc, out = self.console_exec(f'bash {self.SNAP_SCRIPT} --full {L2_INSTANCE} {self.FULL_SNAP}',
                                    timeout=300)
        self._assert_handle_ok(rc, out, '--full 全量快照', 'SNAPSHOT_OK')
        # 快照动作会把 VM 置为 Paused，恢复运行供 S3 在 L2 内创建文件
        self.resume_l2_vm(L2_INSTANCE)

        self.logStep("E2.全量快照保存成功")
        rc, out = self.console_exec(f'ls -l /home/snap-{self.FULL_SNAP}/')
        self.assertEqual(rc, 0, f"全量快照目录 /home/snap-{self.FULL_SNAP}/ 不存在")
        self.logInfo(f"全量快照 {self.FULL_SNAP} 保存成功（/home/snap-{self.FULL_SNAP}/）")

        # ===== S3.root目录touch文件test1，保存增量快照 =====
        self.logStep("S3.root目录touch文件test1，保存增量快照")
        rc, out = self.l2_ssh_exec(f'touch {self.TEST_FILE}')
        self.assertEqual(rc, 0, f"L2 内创建 {self.TEST_FILE} 失败: {out[-300:]}")
        rc, out = self.console_exec(f'bash {self.SNAP_SCRIPT} --inc {L2_INSTANCE} '
                                    f'{self.INC_SNAP} {self.FULL_SNAP}', timeout=300)
        self._assert_handle_ok(rc, out, '--inc 增量快照', 'SNAPSHOT_OK')
        self.resume_l2_vm(L2_INSTANCE)  # 恢复运行，保证 S4 可优雅删除

        self.logStep("E3.文件创建成功，增量快照保存正常")
        rc, out = self.l2_ssh_exec(f'ls -l {self.TEST_FILE}')
        self.assertEqual(rc, 0, f"L2 内 {self.TEST_FILE} 应存在但未找到: {out[-300:]}")
        self.logInfo(f"{self.TEST_FILE} 创建成功，增量快照 {self.INC_SNAP} 保存成功")

        # ===== S4.删除L2虚拟机，使用全量快照恢复虚拟机 =====
        self.logStep("S4.删除L2虚拟机，使用全量快照恢复虚拟机")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False
        rc, out = self.console_exec(f'bash {self.SNAP_SCRIPT} --restore {L2_INSTANCE} {self.FULL_SNAP}',
                                    timeout=300)
        self._assert_handle_ok(rc, out, '--restore 全量恢复', 'RESTORE_OK')
        self.l2_started = True  # 恢复出的 L2 同样纳入 teardown 兜底清理

        self.logStep("E4.删除虚拟机后恢复的虚拟机root目录没有test1文件")
        rc, out = self.l2_ssh_exec(f'ls -l {self.TEST_FILE}')
        self.assertNotEqual(rc, 0,
                            f"全量快照恢复后 {self.TEST_FILE} 不应存在（快照早于文件创建）: {out[-300:]}")
        self.logInfo(f"全量快照恢复成功，{self.TEST_FILE} 不存在，符合预期")

        # ===== S5.使用增量快照恢复虚拟机 =====
        self.logStep("S5.使用增量快照恢复虚拟机")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False
        rc, out = self.console_exec(f'bash {self.SNAP_SCRIPT} --restore {L2_INSTANCE} {self.INC_SNAP}',
                                    timeout=300)
        self._assert_handle_ok(rc, out, '--restore 增量恢复', 'RESTORE_OK')
        self.l2_started = True

        self.logStep("E5.再次使用增量快照恢复的虚拟机root目录有test1文件")
        rc, out = self.l2_ssh_exec(f'ls -l {self.TEST_FILE}')
        self.assertEqual(rc, 0, f"增量快照恢复后 {self.TEST_FILE} 应存在但未找到: {out[-300:]}")
        self.logInfo(f"增量快照恢复成功，{self.TEST_FILE} 存在，符合预期")

        # ===== S6.快照恢复后时钟验证 =====
        self.logStep("S6.快照恢复后时钟验证：记录恢复前后guest时间，"
                     "验证时间不倒退不冻结、定时器恢复正常")
        # 记录恢复后 guest 当前时间戳（秒）
        rc, out = self.l2_ssh_exec('date +%s')
        self.assertEqual(rc, 0, f"获取 guest 时间戳失败: {out[-300:]}")
        guest_time_after_restore = next(
            (int(ln.strip()) for ln in (out or '').splitlines()
             if ln.strip().isdigit()), 0)
        self.assertGreater(guest_time_after_restore, 0,
                           f"无法解析 guest 时间戳: {out[-300:]}")
        # 在 guest 内启动一个后台 sleep（验证定时器恢复后是否正常推进）
        rc, out = self.l2_ssh_exec('sleep 10 & echo $!')
        self.assertEqual(rc, 0, f"启动 sleep 失败: {out[-300:]}")
        # 回显里 PID 是中间的纯数字行（123），不是首行（ssh 命令回显）也不是尾行（CMDEXEC_DONE_0）
        sleep_pid = next(
            (ln.strip() for ln in (out or '').splitlines()
             if ln.strip().isdigit() and ln.strip() != '0'), '')
        self.assertTrue(sleep_pid.isdigit(), f"未获取到 sleep PID: {out[-300:]}")
        # 等 12s（sleep 10 应该已完成）
        time.sleep(12)
        # 记录此时 guest 时间戳（应该比恢复后前进 ~12s）
        rc, out = self.l2_ssh_exec('date +%s')
        self.assertEqual(rc, 0, f"获取 guest 时间戳失败: {out[-300:]}")
        guest_time_after_wait = next(
            (int(ln.strip()) for ln in (out or '').splitlines()
             if ln.strip().isdigit()), 0)
        # 验证：时间正常前进（不冻结）
        time_diff = guest_time_after_wait - guest_time_after_restore
        self.assertGreater(time_diff, 5,
                          f"恢复后 guest 时间仅前进 {time_diff}s（疑似时钟冻结）"
                          f"（恢复后={guest_time_after_restore}, "
                          f"等待后={guest_time_after_wait}）")
        # 验证：时间没倒退
        self.assertGreaterEqual(guest_time_after_wait, guest_time_after_restore,
                                f"guest 时间倒退（恢复后={guest_time_after_restore}, "
                                f"等待后={guest_time_after_wait}）")
        # 验证：sleep 进程已完成（定时器恢复正常推进）
        rc, out = self.l2_ssh_exec(f'kill -0 {sleep_pid} 2>/dev/null && '
                                    f'echo RUNNING || echo DONE')
        # 回显里 marker 行是 CMDEXEC_DONE_0，命令回显行含 RUNNING/DONE 字面量，
        # 只取恰好等于 RUNNING 或 DONE 的行
        done_check = next(
            (ln.strip() for ln in (out or '').splitlines()
             if ln.strip() in ('RUNNING', 'DONE')), '')
        self.assertEqual(done_check, 'DONE',
                        f"恢复后 sleep {sleep_pid} 未在预期时间内完成"
                        f"（定时器可能未恢复）: {out[-300:]}")

        self.logStep("E6.快照恢复后guest时间正常前进（不倒退/不冻结），定时器继续运行")
        self.logInfo(f"S6: 时钟验证通过（恢复后={guest_time_after_restore}, "
                     f"等待后={guest_time_after_wait}, 前进 {time_diff}s, "
                     f"sleep 已完成=定时器正常）")

        # ===== S7.删除L2虚拟机 =====
        self.logStep("S7.删除L2虚拟机")
        self.destroy_l2_vm(L2_INSTANCE)
        self.l2_started = False

        self.logStep("E7.删除虚拟机成功")
        self.verify_l2_destroyed(L2_INSTANCE)
        self.logInfo("L2 已删除，VMM 进程退出")
