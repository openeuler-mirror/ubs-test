import re
import time
from datetime import datetime, timezone
from enum import Enum
from time import sleep

from libs.core.basecase.ubturbo.smap_node_executor import SmapNodeExecutor


class VmStatus(Enum):
    STOP = 0
    RUNNING = 1
    PAUSED = 2
    SAVING = 3


class VmNode(SmapNodeExecutor):

    def __init__(self, host_node: SmapNodeExecutor, ssh_host, vm_name: str, install_path):
        super().__init__(ssh_host)
        self._host_node = host_node
        self.name = vm_name
        self._vm_path = f"{install_path}/vm"
        self._vm_conf = f"{self._vm_path}/xml/{self.name}.xml"
        self._pid = -1
        self._node_control_ip = ""
        self._node_data_ip = ""
        self._vm_status_dic = {"running": VmStatus.RUNNING,
                               "paused": VmStatus.PAUSED,
                               "saving": VmStatus.SAVING}
        self._local_numa_nodes = []

    def _reset(self):
        self._pid = -1
        self._node_control_ip = ""

    def run(self, cmd: str, timeout=180, work_dir: str = ""):
        if self._node_data_ip == "":
            raise RuntimeError("VM's date ip is invalid")
        # 先检查ip是否可以登录
        # 循环三次 防止虚机卡顿造成 ping不通
        for action_index in range(3):
            if self._host_node.ping_ip(self._node_data_ip):
                break
            if action_index == 2:
                raise RuntimeError("VM's date ip is unreachable")
        ssh_command = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {self._node_data_ip}"
        output = self._ssh_host.run({"command": [ssh_command],
                                     "waitstr": "password:",
                                     "input": ["openEuler12#$", "]#", cmd, "]#", "exit"],
                                     "timeout": timeout,
                                     "directory": f"{work_dir}"})
        if self._get_rc(output) == 0:  # 去掉ssh登录带来的干扰信息
            return self.remove_prompt_message(output, cmd)
        return output

    def _get_vm_control_ip(self) -> str:
        # 此处会做ip的有效性检查 禁止返回虚假ip
        for _ in range(0, 3):
            output = self._host_node.run(f"virsh domifaddr {self.name}")
            if self._get_rc(output) != 0:
                raise RuntimeError("Failed to get vm ip!")
            match = re.search(r'ipv4\s+(\d{1,3}\.){3}\d{1,3}', self._get_stdout(output))
            if not match:
                sleep(10)
                continue
            ip = match.group(0).split()[1]
            ip_available = self._host_node.ping_ip(ip)
            if ip_available:
                return ip
        raise RuntimeError("Failed to get vm ip!")

    def _get_vm_status(self) -> VmStatus:
        output = self._host_node.run(f"virsh list --all | grep --color=never \"{self.name}\"")
        if self._get_rc(output) == 0:
            match = re.search(rf'{re.escape(self.name)}\s+(\S+)', self._get_stdout(output))
            if match and self._vm_status_dic.get(match.group(1)) is not None:
                return self._vm_status_dic[match.group(1)]
        return VmStatus.STOP

    def _get_vm_pid(self) -> int:
        output = self._host_node.run(f"pgrep -f \"qemu.*{self.name},\"")
        if self._get_rc(output) != 0:
            return -1
        return int(self._get_stdout(output, 0, 1))

    def _create_vm(self) -> bool:
        output = self._host_node.run(f"virsh create {self._vm_conf}")
        return self._get_rc(output) == 0

    def _destroy_vm(self) -> bool:
        output = self._host_node.run(f"virsh destroy {self.name}")
        return self._get_rc(output) == 0

    def create(self, time: int = 1500) -> bool:
        if self._get_vm_status() != VmStatus.RUNNING:
            if self._get_vm_status() == VmStatus.PAUSED:
                self.resume()
            elif not self._create_vm():
                self.logger.error("Failed to create vm")
                return False
            sleep(5)  # 暂停5秒
            if self._get_vm_status() != VmStatus.RUNNING:
                self.logger.error("Failed to check vm status")
                return False
        start_time = int(datetime.now(tz=timezone.utc).timestamp())
        while int(datetime.now(tz=timezone.utc).timestamp()) < start_time + time:
            try:
                self._pid = self._get_vm_pid()
                self._node_control_ip = self._get_vm_control_ip()
                self._node_data_ip = self._get_vm_control_ip()
            except RuntimeError as e:
                self.logger.warning(f"{e} wait time: {int(datetime.now(tz=timezone.utc).timestamp()) - start_time}s")
                sleep(10)  # 默认暂停10s
                continue
            return True
        raise RuntimeError("vm not available")

    def destroy(self) -> bool:
        res = self._destroy_vm()
        if not res:
            return False
        self._reset()
        return True

    def reboot(self) -> bool:
        output = self._host_node.run(f"virsh reboot {self.name}")
        return self._get_rc(output) == 0

    def suspend(self) -> bool:
        output = self._host_node.run(f"virsh suspend {self.name}")
        return self._get_rc(output) == 0

    def resume(self) -> bool:
        output = self._host_node.run(f"virsh resume {self.name}")
        return self._get_rc(output) == 0

    def get_pid(self) -> int:
        if self._pid == -1:
            return self._get_vm_pid()
        return self._pid

    def get_data_ip(self) -> str:
        if self._node_data_ip == "":
            return self._get_vm_control_ip()
        return self._node_data_ip

    def check_vm_running_status(self) -> bool:
        return self._get_vm_status() == VmStatus.RUNNING

    def check_vm_paused_status(self) -> bool:
        return self._get_vm_status() == VmStatus.PAUSED

    def check_vm_real_status(self) -> bool:
        # 能进入虚拟机执行ip a命令
        result = self.run("ip a")
        return self._node_data_ip in self._get_stdout(result)

    def get_unique_numa_node(self) -> int:
        if len(self._local_numa_nodes) != 0:
            return self._local_numa_nodes[0]
        output = self._host_node.run(f"virsh numatune {self.name} | grep --color=never numa_nodeset")
        if self._get_rc(output) != 0:
            return -2
        pattern = r"numa_nodeset\s+:\s+(\d+)"
        matcher = re.search(pattern, self._get_stdout(output))
        if matcher is None:
            return -2
        self._local_numa_nodes = [int(matcher.group(1))]
        return self._local_numa_nodes[0]

    def in_use(self) -> bool:
        return self._pid != -1

    def get_vm_mem_size(self) -> int:
        output = self._host_node.run(f"virsh dominfo {self.name} | grep --color=never 'Max memory:'")
        if self._get_rc(output) != 0:
            return -1
        match = re.search(r"Max memory:\s+(\d+)", self._get_stdout(output))
        if not match:
            return -1
        return int(int(match.group(1)) / 1024)

    @staticmethod
    def remove_prompt_message(output, cmd: str):
        # 为硬分区和虚拟机获取执行命令的结果
        std_out = SmapNodeExecutor._get_stdout(output)
        out_lines = std_out.split("\n")
        expected_line = "]# " + cmd
        for index, line in enumerate(out_lines):
            if expected_line in line:
                output['stdout'] = SmapNodeExecutor._get_stdout(output, index + 1, -4)
                return output
        raise RuntimeError("Failed to remove prompt message, invalid command line")

    def get_vm_mem_topo(self):
        return self._host_node.get_proc_mem_nodes(self.get_pid())


class SmapVmNode(VmNode):
    def __init__(self, host_node: SmapNodeExecutor, ssh_host, vm_name: str, install_path):
        super().__init__(host_node, ssh_host, vm_name, install_path)
        self._redis_path = f"/home/redis"

    def update_redis_ip(self, ip: str) -> bool:
        return self.update_config_item(f"{self._redis_path}/redis.conf", "bind", ip, " ")

    def start_redis(self) -> bool:
        self.kill_process("redis-server", True)
        time.sleep(1)
        output = self.run(
            f"taskset -c 0 {self._redis_path}/redis-server {self._redis_path}/redis.conf > /dev/null 2>&1 & disown")
        return self._get_rc(output) == 0

    @staticmethod
    def _get_time_string() -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H:%M:%S")

    def run_redis_benchmark(self, requests: int, clients: int, size: int, keyspace: int, threads: int, ip: str):
        self.kill_process("redis-benchmark", True)
        time.sleep(1)
        self.redis_result_log = f"{self._redis_path}/" + "result_" + SmapVmNode._get_time_string() + ".log"
        cmd = f"{self._redis_path}/redis-benchmark -t set,get -n {requests} -c {clients} -r {keyspace} -h {ip} -p 6379 -d {size} --threads {threads}"
        output = self.run(f"{cmd} > {self.redis_result_log} 2>&1 & disown")
        return self._get_rc(output) == 0