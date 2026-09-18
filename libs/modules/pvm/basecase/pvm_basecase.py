"""pvm 模块基类：承载嵌套虚拟化（L1 虚机内启动 L2 虚机）测试的公共能力。

pvm 下的用例类继承 PvmBaseCase 后可直接使用：
    - self.node / self.nodes / self.resource / self.customParam（fixture 注入）
    - self.console_exec(cmd, timeout)      在 L1 console 内执行命令
    - self.l2_ssh_exec(cmd)                通过 ssh 到 L2 执行命令（需先启动 L2）

约定（与框架其他 basecase 一致）：
    - inject fixture 定义在 basecase 模块内，conftest.py 只做 import 导出
"""
import os
import re
import tempfile
from typing import Any, Dict, List, Tuple

import paramiko
import pytest

from libs.core.base import TestCase
from libs.modules.ubsvirt.common.node_manager import get_new_sshconnect


class PvmBaseCase(TestCase):
    """pvm 测试基类。

    子类约定：
        - setup_method 中初始化各自状态，但 console 连接请用 self.l1_connect()
          或 self.enter_l1_vm() 建立（结果存 self.vm_ssh）
        - teardown_method 中如已启动 L2，调用 self.destroy_l2_vm() 兜底清理
    """

    # ===== L1 环境（子类可按环境覆盖）=====
    L1_VM_NAME: str = "pvm-test"     # 一层虚机名称
    L1_HOSTNAME: str = "pvm-test"    # 一层虚机内 hostname（用于确认命令确实跑在 L1 里）
    L1_USER: str = "root"           # 一层虚机 console 登录用户
    L1_PASSWORD: str = "huawei"     # 一层虚机 console 登录密码

    # ===== L1 console 交互 =====

    # L1 环境探测命令：读内核提供的 hostname，不依赖任何外部命令
    # （L1 精简环境可能没有 hostname 命令，rc=127 会被误判为未登录）
    PROBE_CMD = "cat /proc/sys/kernel/hostname"

    # ===== L1 辅助脚本自动补齐 =====
    # 本地 resource/pvm/ 下的脚本，登录 L1 后缺失则自动上传到 L1_SCRIPT_DIR
    L1_SCRIPTS: Tuple[str, ...] = ("handle_l2.sh", "handle_l2_snap.sh")
    L1_SCRIPT_DIR: str = "/home"  # 脚本在 L1 内的存放目录

    def _probe_l1_logged_in(self) -> bool:
        """探测 console 是否已附着到 L1 且处于登录状态。

        不用 true 探测：true 在宿主机 shell 上同样 rc=0，当 virsh console
        未附着成功（如上一会话未断开）时会误判"已登录"，后续命令全部
        打在宿主机上。改读 /proc/sys/kernel/hostname：输出含 L1_HOSTNAME
        仅在 L1 内成立，可区分"宿主机 shell"和"L1 登录 shell"两种 rc=0
        场景；在 login: 提示下探测串被当作用户名吞掉，收不到标记（rc=-1）。
        """
        rc, out = self.console_exec(self.PROBE_CMD, timeout=15)
        return rc == 0 and self.L1_HOSTNAME in (out or '')

    def _ensure_l1_scripts(self) -> None:
        """确保 L1 的 L1_SCRIPT_DIR 下存在 handle_l2.sh / handle_l2_snap.sh。

        缺哪个补哪个：本地 resource/pvm/<脚本> 借宿主机 paramiko transport
        开 direct-tcpip 通道，测试机直连 L1 sshd（root/huawei）走 SFTP 写入，
        并设置执行位。virsh console 是交互通道传不了文件，故走 SSH 跳板；
        脚本在 Windows 侧维护，上传前统一转 LF 行尾，避免 bash 报 '\\r' 错。
        """
        missing = [f for f in self.L1_SCRIPTS
                   if self.console_exec(f'test -f {self.L1_SCRIPT_DIR}/{f}')[0] != 0]
        if not missing:
            self.logInfo(f"L1 {self.L1_SCRIPT_DIR} 下脚本齐全，跳过上传")
            return

        # L1 的 IP：console 内取全局作用域 IPv4（handle_l2.sh 依赖 ip 命令，必存在）
        rc, out = self.console_exec('ip -4 -o addr show scope global')
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out or '')
        self.assertTrue(m, f"无法从 L1 console 获取 L1 IP，输出: {(out or '')[-300:]}")
        l1_ip = m.group(1)

        # 跳板用 self.vm_ssh 的 transport：它是登录成功后的活跃连接。
        # 不能用 self.node —— fixture 注入的 node 从未 login，transport 为 None
        transport = getattr(self.vm_ssh, 'transport', None)
        self.assertTrue(transport is not None and transport.is_active(),
                        "宿主机 SSH transport 不可用，无法建立到 L1 的跳板通道")
        chan = transport.open_channel('direct-tcpip', (l1_ip, 22), ('127.0.0.1', 0))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(l1_ip, username=self.L1_USER, password=self.L1_PASSWORD,
                           sock=chan, look_for_keys=False, allow_agent=False,
                           timeout=15)
            sftp = client.open_sftp()
            project_root = os.path.abspath(__file__).split('libs')[0]
            for fname in missing:
                with open(os.path.join(project_root, 'resource', 'pvm', fname), 'rb') as f:
                    data = f.read().replace(b'\r\n', b'\n')
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.sh')
                tmp.write(data)
                tmp.close()
                dst = f'{self.L1_SCRIPT_DIR}/{fname}'
                sftp.put(tmp.name, dst)
                sftp.chmod(dst, 0o755)
                os.unlink(tmp.name)
                self.logInfo(f"{fname} 已上传至 L1({l1_ip}):{dst}")
            sftp.close()
        finally:
            client.close()

        # 上传后复检，仍缺则报错（脚本缺失用例必然无法执行）
        still_missing = [f for f in self.L1_SCRIPTS
                         if self.console_exec(f'test -f {self.L1_SCRIPT_DIR}/{f}')[0] != 0]
        self.assertFalse(still_missing, f"L1 脚本上传后仍缺失: {still_missing}")

    def enter_l1_vm(self) -> None:
        """通过 virsh console 登录一层虚机（账号密码见类常量）。

        不使用 client.enter_vm，因其密码硬编码为框架默认值。
        成功后 self.vm_ssh 持有 L1 的交互式 console 连接。

        是否已登录不用回显文本判断（console 提示符可能被 TCP 分片截断，
        如尾部只剩 "[root@xx ~" 无 #，导致误判为未登录），而是用
        _probe_l1_logged_in 命令探测。
        """
        self.vm_ssh = get_new_sshconnect(self.node)
        self.vm_ssh.run({'command': [f'virsh console {self.L1_VM_NAME}'], 'timeout': 60,
                         'waitstr': 'Escape character', 'returnCode': False})
        # 回车唤醒 console（本次回显形态不作任何判定）
        self.vm_ssh.run({'command': ['\r'], 'timeout': 30, 'waitstr': r'login:|[>#]',
                         'returnCode': False, 'raise_exception_if_timeout': False})

        if self._probe_l1_logged_in():
            self.logInfo(f"{self.L1_VM_NAME} console 已处于登录状态，跳过登录")
            self._ensure_l1_scripts()
            return

        # 未登录或仍停留在宿主机 shell（virsh console 未附着成功，
        # 典型原因：上一次 console 会话未断开）。逐次重试：先重新附着
        # console，再 Ctrl+C + 回车复位到 login: 走正常登录
        for attempt in range(3):
            rc, out = self.console_exec(self.PROBE_CMD, timeout=15)
            if rc == 0 and self.L1_HOSTNAME not in (out or ''):
                self.logWarn(f"当前仍在宿主机 shell（hostname={out.strip()}），"
                             f"重新附着 {self.L1_VM_NAME} console")
                self.vm_ssh.run({'command': [f'virsh console {self.L1_VM_NAME}'],
                                 'timeout': 60, 'waitstr': 'Escape character',
                                 'returnCode': False, 'raise_exception_if_timeout': False})
                self.vm_ssh.send('\r', timeout=10)

            self.vm_ssh.send('\x03', timeout=10)
            self.vm_ssh.run({'command': ['\r'], 'timeout': 30, 'waitstr': r'login:',
                             'returnCode': False, 'raise_exception_if_timeout': False})
            self.vm_ssh.run({'command': [self.L1_USER], 'waitstr': 'Password',
                             'timeout': 30, 'returnCode': False})
            res = self.vm_ssh.run({'command': [self.L1_PASSWORD],
                                   'waitstr': r'[>#]|Login incorrect', 'timeout': 60,
                                   'returnCode': False})
            out = (res.get('stdout') or '') + (res.get('stderr') or '')
            if 'Login incorrect' not in out:
                if self._probe_l1_logged_in():
                    self._ensure_l1_scripts()
                    return
                self.logWarn(f"{self.L1_VM_NAME} 第{attempt + 1}次登录后命令探测未通过，重试")
            else:
                self.logWarn(f"{self.L1_VM_NAME} 第{attempt + 1}次 console 登录失败，重试")
        raise RuntimeError(
            f"{self.L1_VM_NAME} console 登录失败（密码错误或无回显，"
            f"或 virsh console 被其他会话占用）")

    def release_l1_console(self) -> None:
        """释放 L1 console 会话，供 teardown 调用。

        virsh console 是域级互斥资源：libvirt 只允许一个 console 客户端。
        若用例结束时不释放（既不退出 virsh console 也不断开 SSH），
        下一个用例的 enter_l1_vm 会报 "Active console session exists"
        而无法附着。处理：Ctrl+]（\\x1d）退出 virsh console 回到宿主机
        shell，再关闭 SSH 连接。任一步失败仅告警，不影响 teardown 其余清理。
        """
        if not self.vm_ssh:
            return
        try:
            self.vm_ssh.send('\x1d', timeout=10)
            self.vm_ssh.send('\r', timeout=10)
            if self.vm_ssh.channel:
                self.vm_ssh.close()
                self.logInfo(f"{self.L1_VM_NAME} console 会话已释放")
        except Exception as e:  # noqa: BLE001 teardown 兜底不抛异常
            self.logWarn(f"释放 {self.L1_VM_NAME} console 时异常（忽略）: {e}")
        finally:
            self.vm_ssh = None

    def console_exec(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        """在 L1 console 内执行命令并同步等待结束，返回 (rc, output)。

        直接使用 send()/recv() 而非框架 run()：run() 会把默认提示符
        字符类 [#|>] OR 进 waitstr（见 node_adapter.run:
        cmd_item[1] + '|' + default_waitstr），console 回显延迟不定，
        残留缓冲里的 # 或 > 会随机提前命中，导致"一会成功一会失败"。
        recv() 只等 CMDEXEC_DONE_\\d+ 标记，残留回显无影响，
        因此也无需排水。发送回显里 CMDEXEC'_'DONE 带引号不命中标记。
        """
        self.vm_ssh.clear_channel = True
        if not self.vm_ssh.send(f"{cmd}; echo CMDEXEC'_'DONE_$?", timeout=30):
            return -1, f"发送命令失败: {cmd}"

        out, is_match, _ = self.vm_ssh.recv(r'CMDEXEC_DONE_\d+', timeout=timeout)
        out = out or ''
        m = re.search(r'CMDEXEC_DONE_(\d+)', out)
        return (int(m.group(1)) if m else -1), out

    # ===== L2 生命周期（统一由 handle_l2.sh 管理）=====
    L2_HANDLE_SCRIPT: str = "/home/handle_l2.sh"  # L2 生命周期管理脚本

    def _handle_l2(self, action: str, instance: str = None,
                   timeout: int = 300) -> Tuple[int, str]:
        """执行 handle_l2.sh <action> [N|IP]，返回 (rc, output)。

        action: --start / --shutdown / --boot / --pause / --resume / --delete / --status
        instance 不传 = 对 --delete 表示删除全部，其他 action 默认实例 0。
        脚本机器可读回显：SUCCESS/SHUTDOWN/BOOTED/PAUSED/RESUMED/DELETED: xxx | FAILED: <reason>
        """
        arg = '' if instance is None else f' {instance}'
        return self.console_exec(f'bash {self.L2_HANDLE_SCRIPT} {action}{arg}', timeout)

    def _assert_handle_ok(self, rc: int, out: str, action: str,
                          expect_tag: str, timeout_used: bool = False) -> None:
        """校验 handle_l2.sh 执行结果：rc=0 且含预期成功标记、无 FAILED。"""
        self.assertNotEqual(rc, -1,
                            f"{action} 未捕获到脚本结束标记（超时），输出: {out[-500:]}")
        self.assertNotIn('Permission denied', out, f"{action} 执行被拒绝（权限不足）")
        self.assertNotIn('No such file', out, f"脚本不存在: {self.L2_HANDLE_SCRIPT}")
        self.assertNotIn('FAILED:', out, f"{action} 失败（rc={rc}），输出: {out[-500:]}")
        self.assertEqual(rc, 0, f"{action} 执行失败（rc={rc}），输出: {out[-500:]}")
        self.assertIn(expect_tag, out,
                      f"{action} 未报告 {expect_tag}，输出: {out[-500:]}")

    def start_l2_vm(self, instance: str, timeout: int = 300) -> str:
        """handle_l2.sh --start：创建 + 开机 + 等待 SSH 就绪，返回 L2 IP。

        Args:
            instance: 实例号 N（"0","1"...，IP=192.168.249.(N+2)）或显式 IP（192.168.249.0/24）
            timeout:  脚本执行超时（秒）
        """
        rc, out = self._handle_l2('--start', instance, timeout)
        self._assert_handle_ok(rc, out, '--start', 'SUCCESS:')
        m = re.search(r'SUCCESS: (\d+\.\d+\.\d+\.\d+)', out)
        self.l2_ip = m.group(1) if m else None
        self.l2_started = True
        self.logInfo(f"L2 已就绪（--start），IP: {self.l2_ip}")
        return self.l2_ip

    def shutdown_l2_vm(self, instance: str, timeout: int = 120) -> str:
        """handle_l2.sh --shutdown：优雅关机，VM 保持 Created 状态（可再 --boot）。"""
        rc, out = self._handle_l2('--shutdown', instance, timeout)
        self._assert_handle_ok(rc, out, '--shutdown', 'SHUTDOWN:')
        m = re.search(r'SHUTDOWN: (\d+\.\d+\.\d+\.\d+)', out)
        self.logInfo(f"L2 已优雅关机（--shutdown）: {m.group(1) if m else out.strip()}")
        return m.group(1) if m else None

    def boot_l2_vm(self, instance: str, timeout: int = 300) -> str:
        """handle_l2.sh --boot：开机已 shutdown 的 Created 虚机，等待 SSH 就绪。"""
        rc, out = self._handle_l2('--boot', instance, timeout)
        self._assert_handle_ok(rc, out, '--boot', 'BOOTED:')
        m = re.search(r'BOOTED: (\d+\.\d+\.\d+\.\d+)', out)
        self.l2_started = True
        self.logInfo(f"L2 已开机（--boot）: {m.group(1) if m else out.strip()}")
        return m.group(1) if m else None

    def pause_l2_vm(self, instance: str, timeout: int = 60) -> None:
        """handle_l2.sh --pause：暂停 Running 虚机（快照前置动作）。"""
        rc, out = self._handle_l2('--pause', instance, timeout)
        self._assert_handle_ok(rc, out, '--pause', 'PAUSED:')
        self.logInfo(f"L2 已暂停（--pause {instance}）")

    def resume_l2_vm(self, instance: str, timeout: int = 60) -> None:
        """handle_l2.sh --resume：恢复 Paused 虚机继续运行。

        handle_l2_snap.sh 快照动作会把 VM 置为 Paused 且不自动恢复；
        暂停状态下 L2 无法响应 SSH，也无法被 --shutdown 优雅删除。
        """
        rc, out = self._handle_l2('--resume', instance, timeout)
        self._assert_handle_ok(rc, out, '--resume', 'RESUMED:')
        self.logInfo(f"L2 已恢复运行（--resume {instance}）")

    def l2_status(self, instance: str) -> str:
        """handle_l2.sh --status：返回 VM 状态字符串（Running/Created/absent 等）。"""
        rc, out = self._handle_l2('--status', instance, 60)
        m = re.search(r'state=(\S+)', out)
        state = m.group(1) if m else 'unknown'
        self.logInfo(f"L2 实例 {instance} 状态: {state}")
        return state

    def destroy_l2_vm(self, instance: str = None, timeout: int = 120) -> None:
        """handle_l2.sh --delete：销毁 VM + VMM + tap。

        instance 不传 = 删除全部实例（脚本无参语义）；
        传实例号 N 或 IP = 只删对应实例。
        脚本失败时兜底按实例 socket 强杀 VMM。
        """
        rc, out = self._handle_l2('--delete', instance, timeout)
        if rc != 0:
            if instance is None:
                # 兜底：脚本失败时强杀全部 VMM（本就要求删全部）
                self.logWarn(f"--delete 全部实例失败（rc={rc}），兜底 pkill 全部 VMM")
                self.console_exec("pkill -9 -f 'api-socket /tmp/ch-'", timeout=15)
            else:
                # 兜底：脚本缺失/执行失败时按实例 socket 强杀本实例 VMM
                name = self._instance_sock_name(str(instance))
                self.logWarn(f"--delete {instance} 失败（rc={rc}），兜底 pkill 实例 {name} 的 VMM")
                self.console_exec(f'pkill -9 -f "api-socket /tmp/ch-{name}.sock"',
                                  timeout=15)
            return
        self.assertNotIn('FAILED:', out, f"--delete 失败，输出: {out[-500:]}")
        self.assertIn('DELETED:', out, f"--delete 未报告 DELETED，输出: {out[-500:]}")
        self.logInfo(f"L2 已删除（--delete {instance if instance is not None else 'all'}）")

    def l2_ssh_exec(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        """在 L1 内通过 ssh 到 L2 执行命令（脚本已打通 root 免密）。

        Args:
            cmd: 要在 L2 内执行的命令（单条，不含单引号；$ 变量在 L2 侧展开）
            timeout: 命令超时（秒）
        """
        self.assertTrue(getattr(self, 'l2_ip', None), "L2 尚未启动（先调用 start_l2_vm）")
        # 单引号包裹：避免 $ 变量/反引号在 L1 shell 提前展开
        ssh_cmd = (f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
                   f'-o ConnectTimeout=5 root@{self.l2_ip} \'{cmd}\'')
        return self.console_exec(ssh_cmd, timeout)

    def _instance_sock_name(self, arg: str) -> str:
        """复现 handle_l2.sh 的实例命名逻辑：IP -> ip<末八位组>，实例号原样。"""
        if re.fullmatch(r'\d+\.\d+\.\d+\.\d+', arg):
            return f"ip{arg.rsplit('.', 1)[1]}"
        return str(arg)

    def verify_l2_destroyed(self, instance: str = None) -> None:
        """校验本实例 VMM 进程已退出（--delete 后 socket 应不存在）。"""
        name = self._instance_sock_name(instance if instance is not None
                                        else getattr(self, 'l2_instance', '0'))
        rc, out = self.console_exec(
            f'ps -ef | grep "api-socket /tmp/ch-{name}.sock" | grep -v grep | wc -l')
        count = next((line.strip() for line in out.splitlines()
                      if line.strip().isdigit()), None)
        self.assertEqual(count, '0', f"实例 {name} 的 VMM 进程未退出，L2 可能仍在运行")


@pytest.fixture(autouse=True)
def inject_pvm_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any],
) -> None:
    """注入 PvmBaseCase 外部依赖。

    仅对 PvmBaseCase 及其子类进行注入。
    """
    if not hasattr(request, 'instance'):
        return

    instance = request.instance

    if not isinstance(instance, PvmBaseCase):
        return

    instance.nodes = nodes if nodes else []
    instance.node = instance.nodes[0] if instance.nodes else None
    instance.resource = resource
    instance.customParam = custom_params or {}
