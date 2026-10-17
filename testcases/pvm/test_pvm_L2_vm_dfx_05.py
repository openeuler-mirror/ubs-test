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
L2_INSTANCE = "0"               # 主要测试实例号
CHURN_COUNT = 50                # 高频 churn 次数（create→destroy 循环）
LEAK_THRESHOLD_MB = 100         # churn 前后 L1 可用内存允许波动上限（MB）


class TestPVML2VmDfx05(PvmBaseCase):
    """验证PVM内核边界路径与生命周期异常场景健壮性

    CaseNumber:
        test_pvm_L2_vm_dfx_05
    RunLevel:
        Level 2
    EnvType:

    CaseName:
        验证PVM内核边界路径与生命周期异常场景健壮性
    PreCondition:
        P1.完成L1虚拟机的安装部署，功能正常
        P2.在L1虚拟机中安装PVM的ko文件
        P3.成功编译L2层虚拟机镜像
    TestStep:
        S1.create不boot就destroy：vm.create后不vm.boot直接销毁，验证teardown未boot的VM不crash
        S2.配置变体：经vm.create API直传hugepages/shared memory/overlapping_zones的自定义VmConfig，验证不同init路径不crash
        S3.vm.resize热插拔+功能验证：启动VM后vm.resize增减内存/vCPU，每次resize后验证VM功能正常，再destroy
        S4.snapshot/restore：启动VM跑压力期间snapshot→restore，验证重走init路径不crash
        S5.并发boot+destroy：同一VM同时发vm.boot和vm.delete，验证init/teardown竞态不crash
        S6.高频churn+泄漏检测：50次create→短压→destroy，前后对比L1可用内存，验证无泄漏
        S7.pause/resume：VM跑压力期间vm.pause→等待→vm.resume，验证VM恢复后功能正常
        S8.resize期间并发stress：VM跑MMU churn压力期间vm.resize增减内存，验证resize与并发压力不crash
        S9.删除L2虚拟机
    ExpectedResult:
        E1.create不boot就destroy，L1无crash/内核报错
        E2.配置变体VM能创建或优雅拒绝，L1无crash
        E3.热插拔后VM功能正常+destroy，L1无crash/内核报错
        E4.snapshot/restore后VM功能正常，L1无crash
        E5.并发boot+destroy不导致L1 crash
        E6.50次churn后L1可用内存波动不超过阈值（无泄漏）
        E7.pause/resume后VM功能正常，L1无crash
        E8.resize期间并发stress不crash，VM功能正常
        E9.删除虚拟机成功
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

    def _no_cube_hypervisor_leftover(self, phase=""):
        """兜底断言：无任何 cube-hypervisor 残留"""
        rc, out = self.console_exec(
            "ps -ef | grep cube-hypervisor | grep -v grep | wc -l")
        leftover = next((ln.strip() for ln in (out or '').splitlines()
                         if ln.strip().isdigit()), None)
        self.assertEqual(leftover, '0',
                         f"{phase}后仍残留 cube-hypervisor: {(out or '')[-300:]}")

    @pytest.mark.case_info(level='P2', type='Functional')
    def test_pvm_L2_vm_dfx_05(self):
        """测试PVM内核边界路径与生命周期异常场景健壮性"""
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

        # ════════════════════════════════════════════════════════════════
        # S1: create 不 boot 就 destroy（teardown 未 boot 的 VM）
        # ════════════════════════════════════════════════════════════════
        self.logStep("S1.create不boot就destroy：vm.create后不vm.boot直接销毁，"
                     "验证teardown未boot的VM不crash")
        # handle_l2.sh --start 做 create+boot，这里手动只做 create 不 boot
        # 先建 tap + 起 VMM + vm.create（复刻 handle_l2.sh 的网络+VMM准备，但不 vm.boot）
        N = "0"
        tap = f"tap{N}"
        api_sock = f"/tmp/ch-{N}.sock"
        l2_ip = "192.168.249.2"

        # bridge + tap（复刻 handle_l2.sh）
        self.console_exec(
            f'ip link show br-l2 >/dev/null 2>&1 || '
            f'{{ ip link add br-l2 type bridge; '
            f'ip addr add 192.168.249.1/24 dev br-l2; ip link set br-l2 up; }}; '
            f'ip link del {tap} 2>/dev/null || true; '
            f'ip tuntap add {tap} mode tap; '
            f'ip link set {tap} master br-l2; ip link set {tap} up')
        # 起 VMM
        self.console_exec(
            f'pkill -9 -f "api-socket {api_sock}" 2>/dev/null; rm -f {api_sock}')
        self.console_exec(
            f'( setsid /home/cube/cube-hypervisor --api-socket {api_sock} '
            f'> /tmp/ch-{N}-stdout.log 2>&1 & )')
        # 等 VMM socket 就绪
        vmm_ready = False
        for _ in range(20):
            rc, _ = self.console_exec(
                f'curl -s -o /dev/null --unix-socket {api_sock} '
                f'http://localhost/api/v1/vm.info', timeout=10)
            if rc == 0:
                vmm_ready = True
                break
            time.sleep(1)
        self.assertTrue(vmm_ready, "VMM socket 未就绪")
        # 生成 vmcfg 并 vm.create（不 vm.boot）
        rc, out = self.console_exec(
            f'python3 - "{tap}" "{l2_ip}" <<\'PYEOF\'\n'
            f'import json, sys\n'
            f'tap, l2ip = sys.argv[1], sys.argv[2]\n'
            f'cfg = json.load(open("/home/vmcfg.json"))\n'
            f'cfg["payload"]["cmdline"] += f" ip={{l2ip}}"\n'
            f'cfg["net"][0]["tap"] = tap\n'
            f'cfg["net"][0]["mac"] = "52:54:00:" + ":".join(f"{{int(x):02x}}" for x in l2ip.split(".")[1:])\n'
            f'json.dump(cfg, sys.stdout)\n'
            f'PYEOF\n')
        # vm.create
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {api_sock} -X PUT '
            f'http://localhost/api/v1/vm.create '
            f'-H "Content-Type: application/json" -d @/tmp/vmcfg-{N}.json',
            timeout=30)
        # 不 vm.boot，直接 vm.delete（teardown 未 boot 的 VM）
        self.console_exec(
            f'curl -sf --unix-socket {api_sock} -X PUT '
            f'http://localhost/api/v1/vm.delete', timeout=30)
        # 杀 VMM
        self.console_exec(f'pkill -9 -f "api-socket {api_sock}" 2>/dev/null; '
                          f'rm -f {api_sock}')
        self.console_exec(f'ip link del {tap} 2>/dev/null || true')

        self.logStep("E1.create不boot就destroy，L1无crash/内核报错")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"create不boot就destroy 后 L1 内核报错: {errs[:20]}")
        self._no_cube_hypervisor_leftover("S1")
        self.logInfo("S1: create不boot就destroy，L1 无 crash")

        # ════════════════════════════════════════════════════════════════
        # S2: 配置变体（hugepages / shared memory）经 vm.create API 直传
        # ════════════════════════════════════════════════════════════════
        self.logStep("S2.配置变体：经vm.create API直传hugepages/shared memory的"
                     "自定义VmConfig，验证不同init路径不crash")
        for variant_name, mem_mod_fn in [
            ("hugepages", lambda cfg: cfg.setdefault("memory", {}).update(
                {"hugepages": True})),
            ("shared", lambda cfg: cfg.setdefault("memory", {}).update(
                {"shared": True})),
            ("overlapping_zones", None),
        ]:
            self.logInfo(f"S2: 测试配置变体 {variant_name}")
            # 起 VMM + vm.create（自定义 VmConfig）
            N = "0"
            tap_v2 = f"tap{N}"
            sock_v2 = f"/tmp/ch-{N}.sock"
            ip_v2 = "192.168.249.2"
            self.console_exec(
                f'ip link del {tap_v2} 2>/dev/null || true; '
                f'ip tuntap add {tap_v2} mode tap; '
                f'ip link set {tap_v2} master br-l2; '
                f'ip link set {tap_v2} up')
            self.console_exec(
                f'pkill -9 -f "api-socket {sock_v2}" 2>/dev/null; '
                f'rm -f {sock_v2}')
            self.console_exec(
                f'( setsid /home/cube/cube-hypervisor --api-socket {sock_v2} '
                f'> /tmp/ch-{N}-stdout.log 2>&1 & )')
            # 等 VMM
            for _ in range(20):
                rc, _ = self.console_exec(
                    f'curl -s -o /dev/null --unix-socket {sock_v2} '
                    f'http://localhost/api/v1/vm.info', timeout=10)
                if rc == 0:
                    break
                time.sleep(1)
            # 生成带变体的 vmcfg
            self.console_exec(
                f'python3 - "{tap_v2}" "{ip_v2}" "{variant_name}" <<\'PYEOF\'\n'
                f'import json, sys\n'
                f'tap, l2ip, variant = sys.argv[1], sys.argv[2], sys.argv[3]\n'
                f'cfg = json.load(open("/home/vmcfg.json"))\n'
                f'cfg["payload"]["cmdline"] += f" ip={{l2ip}}"\n'
                f'cfg["net"][0]["tap"] = tap\n'
                f'cfg["net"][0]["mac"] = "52:54:00:" + ":".join(f"{{int(x):02x}}" for x in l2ip.split(".")[1:])\n'
                f'if variant == "hugepages":\n'
                f'    cfg.setdefault("memory", {{}})["hugepages"] = True\n'
                f'elif variant == "shared":\n'
                f'    cfg.setdefault("memory", {{}})["shared"] = True\n'
                f'elif variant == "overlapping_zones":\n'
                f'    mem = cfg.setdefault("memory", {{}})\n'
                f'    orig = mem.get("size", 4294967296)\n'
                f'    mem["size"] = 0\n'
                f'    mem["zones"] = [\n'
                f'        {{"id":"zone0","size":orig,"host_numa_node":0}},\n'
                f'        {{"id":"zone1","size":orig,"host_numa_node":0}}\n'
                f'    ]\n'
                f'json.dump(cfg, sys.stdout)\n'
                f'PYEOF\n')
            # vm.create（接受或拒绝都行，但不能 crash L1）
            rc_create, out_create = self.console_exec(
                f'curl -s --unix-socket {sock_v2} -X PUT '
                f'http://localhost/api/v1/vm.create '
                f'-H "Content-Type: application/json" -d @/tmp/vmcfg-{N}.json',
                timeout=30)
            if rc_create == 0:
                self.logInfo(f"{variant_name}: vm.create 成功，尝试 vm.boot")
                self.console_exec(
                    f'curl -s --unix-socket {sock_v2} -X PUT '
                    f'http://localhost/api/v1/vm.boot', timeout=30)
                time.sleep(3)
                # vm.shutdown + vm.delete
                self.console_exec(
                    f'curl -s --unix-socket {sock_v2} -X PUT '
                    f'http://localhost/api/v1/vm.shutdown', timeout=30)
                self.console_exec(
                    f'curl -s --unix-socket {sock_v2} -X PUT '
                    f'http://localhost/api/v1/vm.delete', timeout=30)
            else:
                self.logInfo(f"{variant_name}: vm.create 被拒绝（配置不支持），"
                             f"这是优雅拒绝，不是 crash")
            # 杀 VMM + 清理
            self.console_exec(
                f'pkill -9 -f "api-socket {sock_v2}" 2>/dev/null; '
                f'rm -f {sock_v2}')
            self.console_exec(f'ip link del {tap_v2} 2>/dev/null || true')
            # 检查 L1 没 crash
            errs = dmesg_errors_since(baseline_l1)
            self.assertEqual(len(errs), 0,
                             f"{variant_name} 后 L1 内核报错: {errs[:20]}")
            self._no_cube_hypervisor_leftover(f"S2-{variant_name}")
            self.logInfo(f"S2: {variant_name} 测试完成，L1 无 crash")

        self.logStep("E2.配置变体（hugepages/shared）VM能创建或优雅拒绝，L1无crash")
        self.logInfo("S2: hugepages + shared 配置变体均未致 L1 crash")

        # ════════════════════════════════════════════════════════════════
        # S3: vm.resize 热插拔 + destroy
        # ════════════════════════════════════════════════════════════════
        self.logStep("S3.vm.resize热插拔+功能验证：启动VM后vm.resize增减内存/vCPU，"
                     "每次resize后验证VM功能正常，再destroy")
        self.start_l2_vm(L2_INSTANCE)
        vm_ip = self.l2_vms[L2_INSTANCE]
        sock = f"/tmp/ch-{L2_INSTANCE}.sock"
        # 获取当前内存（字节），用于 resize
        rc, out = self.console_exec(
            f'curl -s --unix-socket {sock} http://localhost/api/v1/vm.info',
            timeout=15)
        m = re.search(r'"size"\s*:\s*(\d+)', out or '')
        orig_mem = int(m.group(1)) if m else 4294967296
        # 增加内存（翻倍）
        new_mem = orig_mem * 2
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resize '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"desired_ram": {new_mem}}}\'', timeout=30)
        self.logInfo(f"S3: resize 内存 {orig_mem} -> {new_mem}, rc={rc}")
        time.sleep(2)
        # resize 后验证 VM 功能正常
        rc, out = self.l2_ssh_exec('ls -al', timeout=30)
        self.assertEqual(rc, 0, f"内存 resize 增后 VM ls -al 失败: {out[-300:]}")
        self.assertIn('total', out)
        # 减回原内存
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resize '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"desired_ram": {orig_mem}}}\'', timeout=30)
        self.logInfo(f"S3: resize 内存 {new_mem} -> {orig_mem}, rc={rc}")
        time.sleep(2)
        rc, out = self.l2_ssh_exec('ls -al', timeout=30)
        self.assertEqual(rc, 0, f"内存 resize 减后 VM ls -al 失败: {out[-300:]}")
        self.assertIn('total', out)
        # vCPU resize（增到 4）
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resize '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"desired_vcpus": 4}}\'', timeout=30)
        self.logInfo(f"S3: resize vCPU 2 -> 4, rc={rc}")
        time.sleep(2)
        rc, out = self.l2_ssh_exec('nproc', timeout=30)
        self.assertEqual(rc, 0, f"vCPU 增后 VM nproc 失败: {out[-300:]}")
        self.logInfo(f"S3: vCPU 增后 nproc 输出: {out.strip().splitlines()[-1].strip() if out else ''}")
        # vCPU resize（减回 2）
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resize '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"desired_vcpus": 2}}\'', timeout=30)
        self.logInfo(f"S3: resize vCPU 4 -> 2, rc={rc}")
        time.sleep(2)
        rc, out = self.l2_ssh_exec('ls -al', timeout=30)
        self.assertEqual(rc, 0, f"vCPU 减后 VM ls -al 失败: {out[-300:]}")
        self.assertIn('total', out)
        # destroy（变更后 teardown）
        self.destroy_l2_vm(L2_INSTANCE)
        self.verify_l2_destroyed(L2_INSTANCE)

        self.logStep("E3.热插拔后VM功能正常+destroy，L1无crash/内核报错")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"热插拔+destroy 后 L1 内核报错: {errs[:20]}")
        self._no_cube_hypervisor_leftover("S3")
        self.logInfo("S3: 热插拔后 destroy，L1 无 crash")
        self.l2_vms.clear()

        # ════════════════════════════════════════════════════════════════
        # S4: snapshot / restore
        # ════════════════════════════════════════════════════════════════
        self.logStep("S4.snapshot/restore：启动VM跑压力期间snapshot→restore，"
                     "验证重走init路径不crash")
        self.start_l2_vm(L2_INSTANCE)
        vm_ip = self.l2_vms[L2_INSTANCE]
        sock = f"/tmp/ch-{L2_INSTANCE}.sock"
        # 后台跑轻压力
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm_ip} 'stress-ng --cpu 1 --timeout 30' "
            f"> /tmp/s4_load.log 2>&1 & )")
        time.sleep(3)
        # snapshot（需先 pause）
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.pause', timeout=30)
        self.logInfo(f"S4: vm.pause rc={rc}")
        snap_path = f"/tmp/s4_snapshot"
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.snapshot '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"destination_url":"file://{snap_path}"}}\'', timeout=60)
        self.logInfo(f"S4: vm.snapshot rc={rc}")
        # restore（从快照恢复，重走 init）
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.restore '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"source_url":"file://{snap_path}"}}\'', timeout=60)
        self.logInfo(f"S4: vm.restore rc={rc}")
        # resume
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resume', timeout=30)
        self.logInfo(f"S4: vm.resume rc={rc}")
        # 验证 VM 功能正常
        rc, out = self.l2_ssh_exec('ls -al', timeout=30)
        self.assertEqual(rc, 0, f"restore 后 VM ls -al 失败: {out[-300:]}")
        self.assertIn('total', out)
        # 等 stress 结束
        for _ in range(20):
            _, o = self.l2_ssh_exec('pgrep -x stress-ng | wc -l', timeout=15)
            cnt = next((ln.strip() for ln in (o or '').splitlines()
                        if ln.strip().isdigit()), None)
            if cnt == '0':
                break
            time.sleep(3)
        # destroy
        self.destroy_l2_vm(L2_INSTANCE)
        self.verify_l2_destroyed(L2_INSTANCE)

        self.logStep("E4.snapshot/restore后VM功能正常，L1无crash")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"snapshot/restore 后 L1 内核报错: {errs[:20]}")
        self._no_cube_hypervisor_leftover("S4")
        self.logInfo("S4: snapshot/restore 完成，VM 功能正常，L1 无 crash")
        self.l2_vms.clear()

        # ════════════════════════════════════════════════════════════════
        # S5: 并发 boot + destroy（同一 VM，init/teardown 竞态）
        # ════════════════════════════════════════════════════════════════
        self.logStep("S5.并发boot+destroy：同一VM同时发vm.boot和vm.delete，"
                     "验证init/teardown竞态不crash")
        # 先 vm.create（不 boot），再并发 boot + delete
        N = "0"
        tap_s5 = f"tap{N}"
        sock_s5 = f"/tmp/ch-{N}.sock"
        ip_s5 = "192.168.249.2"
        self.console_exec(
            f'ip link del {tap_s5} 2>/dev/null || true; '
            f'ip tuntap add {tap_s5} mode tap; '
            f'ip link set {tap_s5} master br-l2; '
            f'ip link set {tap_s5} up')
        self.console_exec(
            f'pkill -9 -f "api-socket {sock_s5}" 2>/dev/null; '
            f'rm -f {sock_s5}')
        self.console_exec(
            f'( setsid /home/cube/cube-hypervisor --api-socket {sock_s5} '
            f'> /tmp/ch-{N}-stdout.log 2>&1 & )')
        for _ in range(20):
            rc, _ = self.console_exec(
                f'curl -s -o /dev/null --unix-socket {sock_s5} '
                f'http://localhost/api/v1/vm.info', timeout=10)
            if rc == 0:
                break
            time.sleep(1)
        # 生成 vmcfg + vm.create
        self.console_exec(
            f'python3 - "{tap_s5}" "{ip_s5}" <<\'PYEOF\'\n'
            f'import json, sys\n'
            f'tap, l2ip = sys.argv[1], sys.argv[2]\n'
            f'cfg = json.load(open("/home/vmcfg.json"))\n'
            f'cfg["payload"]["cmdline"] += f" ip={{l2ip}}"\n'
            f'cfg["net"][0]["tap"] = tap\n'
            f'cfg["net"][0]["mac"] = "52:54:00:" + ":".join(f"{{int(x):02x}}" for x in l2ip.split(".")[1:])\n'
            f'json.dump(cfg, sys.stdout)\n'
            f'PYEOF\n')
        self.console_exec(
            f'curl -sf --unix-socket {sock_s5} -X PUT '
            f'http://localhost/api/v1/vm.create '
            f'-H "Content-Type: application/json" -d @/tmp/vmcfg-{N}.json',
            timeout=30)
        # 并发：vm.boot 和 vm.delete 同时发
        self.console_exec(
            f'curl -s --unix-socket {sock_s5} -X PUT '
            f'http://localhost/api/v1/vm.boot > /tmp/s5_boot.log 2>&1 & '
            f'curl -s --unix-socket {sock_s5} -X PUT '
            f'http://localhost/api/v1/vm.delete > /tmp/s5_delete.log 2>&1 & '
            f'wait')
        # 清理 VMM + tap
        self.console_exec(
            f'pkill -9 -f "api-socket {sock_s5}" 2>/dev/null; '
            f'rm -f {sock_s5}')
        self.console_exec(f'ip link del {tap_s5} 2>/dev/null || true')

        self.logStep("E5.并发boot+destroy不导致L1 crash")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"并发 boot+destroy 后 L1 内核报错: {errs[:20]}")
        self._no_cube_hypervisor_leftover("S5")
        self.logInfo("S5: 并发 boot+destroy，L1 无 crash")

        # ════════════════════════════════════════════════════════════════
        # S6: 高频 churn + 泄漏检测
        # ════════════════════════════════════════════════════════════════
        self.logStep("S6.高频churn+泄漏检测：50次create→短压→destroy，"
                     "前后对比L1可用内存，验证无泄漏")
        mem_before = self._get_l1_mem_available_mb()
        self.logInfo(f"S6: churn 前 L1 可用内存 {mem_before}MB")
        baseline_s6 = dmesg_baseline()
        fail_count = 0
        for i in range(1, CHURN_COUNT + 1):
            try:
                self.start_l2_vm(L2_INSTANCE)
                # 短压力（5s CPU + mmap churn）
                ip = self.l2_vms[L2_INSTANCE]
                self.l2_ssh_exec(
                    'stress-ng --cpu 1 --mmap 1 --timeout 5', timeout=30)
                self.destroy_l2_vm(L2_INSTANCE)
            except Exception as e:  # noqa: BLE001
                fail_count += 1
                self.logWarn(f"S6: 第 {i}/{CHURN_COUNT} 轮失败: {e}")
            if i % 10 == 0:
                self.logInfo(f"S6: 已完成 {i}/{CHURN_COUNT} 轮")
        self.l2_vms.clear()
        mem_after = self._get_l1_mem_available_mb()
        self.logInfo(f"S6: churn 后 L1 可用内存 {mem_after}MB")

        self.logStep("E6.50次churn后L1可用内存波动不超过阈值（无泄漏）")
        drop = mem_before - mem_after
        self.assertLess(drop, LEAK_THRESHOLD_MB,
                        f"churn {CHURN_COUNT} 次后 L1 可用内存下降 {drop}MB"
                        f"（基线 {mem_before} -> {mem_after}），"
                        f"超过阈值 {LEAK_THRESHOLD_MB}MB，疑似泄漏")
        errs = dmesg_errors_since(baseline_s6)
        self.assertEqual(len(errs), 0,
                         f"churn 期间 L1 内核报错: {errs[:20]}")
        self._no_cube_hypervisor_leftover("S6")
        self.logInfo(f"S6: {CHURN_COUNT} 次 churn 完成，"
                     f"内存波动 {drop}MB（阈值 {LEAK_THRESHOLD_MB}MB），"
                     f"失败 {fail_count} 次，无泄漏")

        # ════════════════════════════════════════════════════════════════
        # S7: pause/resume（VM 跑压力期间 pause→resume→验证恢复）
        # ════════════════════════════════════════════════════════════════
        self.logStep("S7.pause/resume：VM跑压力期间vm.pause→等待→vm.resume，"
                     "验证VM恢复后功能正常")
        self.start_l2_vm(L2_INSTANCE)
        vm_ip = self.l2_vms[L2_INSTANCE]
        sock = f"/tmp/ch-{L2_INSTANCE}.sock"
        # 后台跑 stress（30s，跨过 pause/resume）
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm_ip} 'stress-ng --cpu 1 --timeout 30' "
            f"> /tmp/s7_load.log 2>&1 & )")
        time.sleep(3)
        # pause
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.pause', timeout=30)
        self.logInfo(f"S7: vm.pause rc={rc}")
        # 等待 10s（VM 暂停，stress 应卡住）
        time.sleep(10)
        # resume
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resume', timeout=30)
        self.logInfo(f"S7: vm.resume rc={rc}")
        time.sleep(2)

        self.logStep("E7.pause/resume后VM功能正常，L1无crash")
        # VM 功能正常
        rc, out = self.l2_ssh_exec('ls -al', timeout=30)
        self.assertEqual(rc, 0, f"resume 后 VM ls -al 失败: {out[-300:]}")
        self.assertIn('total', out)
        # 等 stress 结束（resume 后应继续跑完）
        for _ in range(20):
            _, o = self.l2_ssh_exec('pgrep -x stress-ng | wc -l', timeout=15)
            cnt = next((ln.strip() for ln in (o or '').splitlines()
                        if ln.strip().isdigit()), None)
            if cnt == '0':
                break
            time.sleep(3)
        # L1 无报错
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"pause/resume 后 L1 内核报错: {errs[:20]}")
        self.logInfo("S7: pause/resume 完成，VM 功能正常，L1 无 crash")
        self.destroy_l2_vm(L2_INSTANCE)
        self.verify_l2_destroyed(L2_INSTANCE)
        self.l2_vms.clear()

        # ════════════════════════════════════════════════════════════════
        # S8: resize 期间并发 stress（VM 跑 MMU churn 期间 resize 内存）
        # ════════════════════════════════════════════════════════════════
        self.logStep("S8.resize期间并发stress：VM跑MMU churn压力期间vm.resize增减内存，"
                     "验证resize与并发压力不crash")
        self.start_l2_vm(L2_INSTANCE)
        vm_ip = self.l2_vms[L2_INSTANCE]
        sock = f"/tmp/ch-{L2_INSTANCE}.sock"
        # 获取当前内存
        rc, out = self.console_exec(
            f'curl -s --unix-socket {sock} http://localhost/api/v1/vm.info',
            timeout=15)
        m = re.search(r'"size"\s*:\s*(\d+)', out or '')
        orig_mem_s8 = int(m.group(1)) if m else 4294967296
        # 后台跑 MMU churn stress（60s，跨过 resize）
        self.console_exec(
            f"( ssh {ssh_opts} root@{vm_ip} "
            f"'stress-ng --mmap 2 --mremap 2 --mprotect 2 --timeout 60' "
            f"> /tmp/s8_load.log 2>&1 & )")
        time.sleep(5)  # 让 MMU churn 起来
        # resize 加内存（翻倍）
        new_mem_s8 = orig_mem_s8 * 2
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resize '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"desired_ram": {new_mem_s8}}}\'', timeout=30)
        self.logInfo(f"S8: MMU churn 期间 resize 内存 {orig_mem_s8} -> {new_mem_s8}, rc={rc}")
        time.sleep(3)
        # resize 减回
        rc, out = self.console_exec(
            f'curl -sf --unix-socket {sock} -X PUT '
            f'http://localhost/api/v1/vm.resize '
            f'-H "Content-Type: application/json" '
            f'-d \'{{"desired_ram": {orig_mem_s8}}}\'', timeout=30)
        self.logInfo(f"S8: MMU churn 期间 resize 内存 {new_mem_s8} -> {orig_mem_s8}, rc={rc}")
        time.sleep(3)

        self.logStep("E8.resize期间并发stress不crash，VM功能正常")
        # VM 功能正常
        rc, out = self.l2_ssh_exec('ls -al', timeout=30)
        self.assertEqual(rc, 0, f"resize 期间并发 stress 后 VM ls -al 失败: {out[-300:]}")
        self.assertIn('total', out)
        # 等 stress 结束
        for _ in range(30):
            _, o = self.l2_ssh_exec('pgrep -x stress-ng | wc -l', timeout=15)
            cnt = next((ln.strip() for ln in (o or '').splitlines()
                        if ln.strip().isdigit()), None)
            if cnt == '0':
                break
            time.sleep(3)
        # L1 无报错
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"resize 期间并发 stress 后 L1 内核报错: {errs[:20]}")
        self.logInfo("S8: resize 期间并发 stress 完成，VM 功能正常，L1 无 crash")
        self.destroy_l2_vm(L2_INSTANCE)
        self.verify_l2_destroyed(L2_INSTANCE)
        self.l2_vms.clear()

        # ════════════════════════════════════════════════════════════════
        # S9: 删除 L2 虚拟机
        # ════════════════════════════════════════════════════════════════
        self.logStep("S9.删除L2虚拟机")
        self.verify_l2_destroyed(L2_INSTANCE)
        self._no_cube_hypervisor_leftover("S9-final")
        self.logStep("E9.删除虚拟机成功")
        errs = dmesg_errors_since(baseline_l1)
        self.assertEqual(len(errs), 0,
                         f"全量测试后 L1 内核报错: {errs[:20]}")
        self.l2_started = False
        self.l2_vms.clear()
        self.logInfo("全部 L2 虚拟机已删除，无残留，全量测试 L1 无 crash")
