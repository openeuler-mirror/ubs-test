import os
import re
import tarfile
import time
from datetime import datetime, timezone
from typing import List, Dict

from libs.core.basecase.ubturbo.smap_container_host import SmapContainerNode
from libs.core.basecase.ubturbo.smap_node_executor import SmapNodeExecutor
from libs.core.basecase.ubturbo.smap_params import SmapAddr, ObmmDeviceInfo
from libs.core.basecase.ubturbo.smap_vm_host import SmapVmNode


class MemoryNode(SmapNodeExecutor):
    def __init__(self, ssh_host, install_path, *args):
        super().__init__(ssh_host)
        self._install_path = install_path

    def check_smap_alive(self) -> bool:
        # 检查smap 进程是否存在
        sma_pids = self.get_process_id("smap_client")
        return len(sma_pids) >= 1

    def _get_numa_node_position(self, numa_node: int) -> int:
        output = self.run("numastat -c | head -n 3 | tail -n 1")
        if self._get_rc(output) != 0:
            raise RuntimeError("failed to execute numastat")
        matches = re.findall(r"Node \d+", self._get_stdout(output))
        target = f"Node {numa_node}"
        for i, match in enumerate(matches, start=1):
            if match == target:
                return i
        raise RuntimeError("failed to get numa node position")

    def watch_proc_mem(self, pid: int, numa_node: int, mem_size: int, timeout: int, is_equal: bool = False) -> bool:
        flag = "eq" if is_equal else "gt"
        node_col = self._get_numa_node_position(numa_node) + 1
        cmd = f"while true; do value=$(numastat -c -p {pid} | awk \"NR==10 {{print \\${node_col}}}\"); if [ \"$value\" -{flag} {mem_size} ]; then echo \"mem:$value\"; exit 0; fi; sleep 1; done"
        output = self.run(f"timeout {timeout} bash -c \'{cmd}\'", timeout=timeout + 30)
        self.show_proc_numa_stat(pid)  # 方便观察上一条命令是否判断正确
        return self._get_rc(output) == 0

    def watch_proc_mem_sum(self, pid: int, numa_node_list: List[int], mem_size: int, timeout: int,
                           is_equal: bool = False) -> bool:
        if len(numa_node_list) == 0:
            return False
        flag = "eq" if is_equal else "gt"
        node_col_expr = '+'.join(
            list(map(lambda nid: r"\$" + str(self._get_numa_node_position(nid) + 1), numa_node_list)))
        cmd = f"while true; do value=$(numastat -c -p {pid} | awk \"NR==10 {{print {node_col_expr}}}\"); if [ \"$value\" -{flag} {mem_size} ]; then echo \"mem:$value\"; exit 0; fi; sleep 1; done"
        output = self.run(f"timeout {timeout} bash -c \'{cmd}\'", timeout=timeout + 30)
        self.show_proc_numa_stat(pid)  # 方便观察上一条命令是否判断正确
        return self._get_rc(output) == 0

    def get_remote_numa(self) -> List[int]:
        result = self.run("lscpu | grep --color=never \"NUMA\"")
        matchs = re.findall(r"NUMA\s+node(\d+)\s+CPU\(s\):\s*$", self._get_stdout(result), re.MULTILINE)
        return [int(match) for match in matchs]

    def get_local_numa(self) -> List[int]:
        result = self.run("lscpu | grep --color=never \"NUMA\"")
        matchs = re.findall(r"NUMA\s+node(\d+)\s+CPU\(s\):\s*[0-9-]+\s*$", self._get_stdout(result), re.MULTILINE)
        return [int(match) for match in matchs]

    def get_proc_mem_topo_total(self, pid: int) -> List[int]:
        output = self.run(f"numastat -c -p {pid}")
        std_out = self._get_stdout(output)
        match = re.search(r'Total\s+([0-9\s]+\d)', std_out)
        if not match:
            return []
        numbers_str = match.group(1)
        mem_topo_list = [int(number) for number in numbers_str.split()][:-1]

        matches = re.findall(r"Node\s+\d+", std_out)

        if len(matches) != len(mem_topo_list):
            raise RuntimeError("failed to parse numa node")
        mem_map = dict()
        max_node_id = 0
        for index, match in enumerate(matches):
            node_id = str(match).replace("Node", "").replace(" ", "")
            mem_map[node_id] = mem_topo_list[index]
            max_node_id = max(max_node_id, int(node_id))
        proc_mem_topo_total = []
        for index in range(max_node_id + 1):
            proc_mem_topo_total.append(mem_map[str(index)] if mem_map.get(str(index)) is not None else 0)
        return proc_mem_topo_total

    def upload_resource(self, destination):
        project_path = os.path.abspath(__file__).split('libs')[0]
        resource_path = os.path.join(project_path, 'resource', 'ubturbo', 'smap')
        tar_file = f"{resource_path}.abc"

        # 使用 tarfile 模块创建压缩文件（会自动覆盖同名文件）
        with tarfile.open(tar_file, f'w:gz') as tar:
            for root, _, files in os.walk(resource_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    tar.add(file_path, arcname=os.path.relpath(file_path, os.path.dirname(resource_path)))
        self.mkdir("/tmp")
        self._ssh_host.putFile(tar_file, f"/tmp/smap_test_resources.abc")
        self.mkdir(destination)
        self.extract_tar(f"/tmp/smap_test_resources.abc", f"{destination}")

    def start_smap_client(self) -> bool:
        # 启动或重启进程
        self.stop_smap_client()
        time.sleep(1)
        start_log = f"{self._install_path}/bin/smap_start.log"
        self.run(f"stdbuf -oL -eL {self._install_path}/bin/smap_client > {start_log} 2>&1 & disown")
        content = "Smap client daemon start success"
        for _ in range(10):  # 等待smap 进程完全启动
            output = self.grep_file(content, start_log)
            if content in output:
                return True
            self.logger.info("Smap_client is not ready, Keep waiting...")
            time.sleep(30)
        raise RuntimeError("Smap_client start failed")

    def stop_smap_client(self):
        self.kill_process("smap_client", True)

    def install_hist_tracking_ko(self, restart_smap_client: bool = True):
        require_restart = restart_smap_client and self.check_smap_alive()
        res = self.histogram_tracking_ctl(True)
        if require_restart:
            self.start_smap_client()
        return res

    def histogram_tracking_ctl(self, enable: bool) -> bool:
        self.stop_smap_client()
        self.run("rmmod -f smap_tiering")
        self.run("rmmod -f smap_access_tracking")
        smap_install_path = "/lib/modules/smap"
        self.run(f"insmod {smap_install_path}/smap_access_tracking.ko smap_scene=2 enable_hist={1 if enable else 0}")
        self.run(f"insmod {smap_install_path}/smap_tiering.ko")
        return True

    def remove_hist_tracking_ko(self, restart_smap_client: bool = True) -> bool:
        require_restart = restart_smap_client and self.check_smap_alive()
        res = self.histogram_tracking_ctl(False)
        if require_restart:
            self.start_smap_client()
        return res

    def watch_proc_mem_strict_mig_out_ratio(self, pid: int, numa_node: int, vm_size: int, ratio: int,
                                            timeout: int) -> bool:
        mig_out_size = 2 * (vm_size // 2 - ((vm_size // 2) * (100 - ratio)) // 100)
        if not self.watch_proc_mem(pid, numa_node, mig_out_size, timeout, True):
            return False
        return not self.watch_proc_mem(pid, numa_node, mig_out_size, max(10, timeout - 30), False)

    def watch_proc_mem_strict_mig_back(self, pid: int, numa_node: int, timeout: int) -> bool:
        if not self.watch_proc_mem(pid, numa_node, 0, timeout, True):
            return False
        return not self.watch_proc_mem(pid, numa_node, 0, max(10, timeout - 30), False)


class SmapHost(MemoryNode):
    def __init__(self, package_path: str, ssh_host, node_id: int):
        self._install_path = package_path
        super().__init__(ssh_host, self._install_path, node_id)
        self.redis_path = f"{package_path}/redis"
        self.container_name_list_4u8g = [f"smap-container-{index}" for index in range(1, 5)]
        self.containers = [SmapContainerNode(self, ssh_host, name, self._install_path) for name in
                           self.container_name_list_4u8g]
        self.max_vm_count = 40  # 最大支持40个虚拟机

        self.vm_name_list_2u4g = [f"smap-vm-{index}" for index in range(1, self.max_vm_count + 1)]
        self.vm_nodes_2u4g = [SmapVmNode(self, ssh_host, name, self._install_path) for name in self.vm_name_list_2u4g]

        self.vm_name_list = self.vm_name_list_2u4g
        self.vm_nodes = self.vm_nodes_2u4g

    def start_redis(self, cpu: int = 0) -> bool:
        self.kill_process("redis-server", True)
        time.sleep(1)
        start_log = f"{self.redis_path}/redis_start.log"
        output = self.run(
            f"taskset -c {cpu} {self.redis_path}/redis-server {self.redis_path}/redis.conf > {start_log} 2>&1 & disown")
        time.sleep(1)
        self.read_file(start_log)
        return self._get_rc(output) == 0

    def start_redis_with_numa_nodes(self, numa_nodes: List[int], port: int) -> bool:
        if not self.copy_file(f"{self.redis_path}/redis.conf", f"/tmp/redis_{port}.conf"):
            return False
        if not self.update_config_item(f"/tmp/redis_{port}.conf", "bind", "0.0.0.0", " "):
            return False
        if not self.update_config_item(f"/tmp/redis_{port}.conf", "port", f"{port}", " "):
            return False
        cmd_prefix = ""
        if len(numa_nodes) != 0:
            cpu_list = self.get_cpu_list(numa_nodes)
            if len(cpu_list) == 0:
                raise RuntimeError("There are no CPUs available")
            cmd_prefix = "taskset -c " + ','.join(list(map(lambda _: str(_), cpu_list)))
        redis_log = f"/tmp/redis_{port}" + datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H:%M:%S") + ".log"
        output = self.run(
            f"{cmd_prefix} {self.redis_path}/redis-server /tmp/redis_{port}.conf >> {redis_log} 2>&1 & disown")
        return self._get_rc(output) == 0

    def start_redis_benchmark(self, data_size: int = 2048) -> bool:
        self.kill_process("redis-benchmark", True)
        output = self.run(
            f"{self.redis_path}/redis-benchmark -t set,get -n 10000000 -c 8 -r 1640000 -h 127.0.0.1 -p 6379 -d {data_size} --threads 8 > /dev/null 2>&1 & disown")
        return self._get_rc(output) == 0

    def start_redis_benchmark_full_param(self, requests: int, clients: int, size: int, keyspace: int, threads: int,
                                         ip: str, port: int) -> bool:
        cmd = f"{self.redis_path}/redis-benchmark -t set -n {requests} -c {clients} -r {keyspace} -h {ip} -p {port} -d {size} --threads {threads}"
        output = self.run(f"{cmd} > /dev/null 2>&1 & disown")
        return self._get_rc(output) == 0

    def stop_redis_benchmark(self):
        self.kill_process("redis-benchmark", True)
        time.sleep(1)

    def stop_redis_server(self):
        self.kill_process("redis-server", True)
        time.sleep(1)

    def get_smap_out_addrs(self, remote_node: int) -> List[SmapAddr]:
        output = self.run(f"grep -arP '.*' /sys/devices/obmm  2>/dev/null | sort | uniq")
        if self._get_stdout(output) is None:
            return []
        obmm_device_map: Dict[int, ObmmDeviceInfo] = dict()
        device_pattern = '^obmm_shmdev([0-9]+)(.*)'
        for device_info_meta in self._get_stdout(output).split('/sys/devices/obmm/'):
            match = re.match(device_pattern, device_info_meta)
            if not match:
                continue
            mem_id = match.group(1)
            meta_content = match.group(2)
            if obmm_device_map.get(mem_id) is None:
                obmm_device_map[mem_id] = ObmmDeviceInfo(mem_id, -1, -1, -1)
            if f"import_info/numa_id:{remote_node}" in meta_content:
                obmm_device_map[mem_id].numa_id = remote_node
            if f"import_info/pa:" in meta_content:
                obmm_device_map[mem_id].pa = int(meta_content.split('0x')[-1], 16)
            if f"/size:" in meta_content:
                obmm_device_map[mem_id].size = int(meta_content.split('0x')[-1], 16)
        addr_list = []
        for device_info in obmm_device_map.values():
            if device_info.numa_id == -1:
                continue
            addr_list.append(SmapAddr(device_info.pa, device_info.pa + device_info.size))
        return addr_list

    def create_vms(self, start_index: int, end_index: int) -> bool:
        for index in range(start_index, end_index + 1):
            if not self.vm_nodes[index].create():
                return False
        return True

    def check_smap_config_file(self) -> bool:
        expected_hex = "0000000 01 00 08 00"
        output = self.run(f"od -N 4 -t x1 /dev/shm/smap_config | sed -n '1p'")
        std_out = self._get_stdout(output, 0, 1)
        return std_out == expected_hex

    def kill_process_by_id(self, process_id: int) -> bool:
        result = self.run(f"kill -9 {process_id}")
        return self._get_rc(result) == 0

    def log_memory_usage(self, log_path: str, flag: str):
        self.run(f"bash -c \"date '+[%Y-%m-%d %H:%M:%S][{flag}]' ;free -m\" >> {log_path}")

    def stress_ng(self, cpu_num, ratio, timeout: int = 60, cpu_set: str = "") -> bool:
        self.kill_process("stress-ng")
        time.sleep(1)
        if cpu_set:
            cmd = f"stress-ng --taskset {cpu_set} --cpu {cpu_num} --cpu-load {ratio} --timeout {timeout}s"
        else:
            cmd = f"stress-ng --cpu {cpu_num} --cpu-load {ratio} --timeout {timeout}s"
        output = self.run(f"{cmd} > /dev/null 2>&1 & disown")
        return self._get_rc(output) == 0