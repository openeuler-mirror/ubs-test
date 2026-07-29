import re
import time
from typing import List

from libs.modules.ubsmem.common.command_excutor import ExecuteResult
from libs.modules.ubsmem.common.node_excutor import NodeExecutor


class SmapNodeExecutor(NodeExecutor):

    @staticmethod
    def _get_stdout(result, start_index: int = 0, end_index: int = None) -> str:
        """
        对stdout输出进行切片
        @param result: 命令执行结果对象
        @param start_index: stdout的起始行数
        @param end_index: stdout的结束函数(不包含)
        """
        if isinstance(result, ExecuteResult):
            stdout_str = result.std_out
            return '\n'.join([x.strip() for x in stdout_str.split('\n')][start_index:end_index])
        elif isinstance(result, dict):
            if not result['stdout']:
                return ""
            return '\n'.join([x.strip() for x in result['stdout'].split('\n')][start_index:end_index])
        else:
            return ""

    @staticmethod
    def _get_rc(result) -> int:
        if isinstance(result, ExecuteResult):
            return result.std_rc if result.std_rc is not None else -1
        elif isinstance(result, dict):
            return int(result.get('rc', -1))
        else:
            return -1

    def ping_ip(self, ip: str) -> bool:
        result = self.run(f"ping -c 1 -w 3 {ip}")
        return self._get_rc(result) == 0

    def get_cpu_list(self, numa_nodes: List[int]) -> List[int]:
        numa_pattern = ""
        if len(numa_nodes) != 0:
            numa_pattern = f"[{'|'.join(list(map(lambda _: str(_), numa_nodes)))}]"
        cmd = f"lscpu | grep -E 'NUMA node{numa_pattern}' | grep -oE [0-9]+-[0-9]+ |" \
              "awk -F '-' '{print \"seq \" $1 \" \" $2}' | xargs -i bash -c {} | xargs echo"
        output = self.run(cmd)
        if self._get_rc(output) != 0:
            return []
        matches = re.findall(r'(\d+)\s*', self._get_stdout(output))
        return [int(match) for match in matches]

    def get_proc_mem_nodes(self, pid: int) -> List[int]:
        mem_topo = self.get_proc_mem_topo(pid)
        if not mem_topo:
            return []
        nodes = []
        for i, mem in enumerate(mem_topo):
            if mem != 0:
                nodes.append(i)
        return nodes

    def get_proc_mem_topo(self, pid: int) -> List[int]:
        output = self.run(f"numastat -c -p {pid}")
        std_out = self._get_stdout(output)
        # 使用正则表达式匹配以 'Huge' 开头的行中的所有数字, 用于查看虚拟机内存分布
        match = re.search(r'Huge\s+(.*)', std_out)
        if not match:
            return []
            # 提取出所有数字并分割成列表
        numbers_str = match.group(1)
        return [int(number) for number in numbers_str.split()][:-1]

    def get_proc_mem(self, proc_name: str) -> int:
        """
        获取进程的占用内存，以KB为单位
        """
        pid_list = self.get_process_id(proc_name)
        result = self.run(f"grep --color=never VmRSS /proc/{pid_list[0]}/status")
        output = self._get_stdout(result)
        match = re.search(r'VmRSS:\s*(\d+)', output)
        if not match:
            self.logger.warn("Failed to get process memory")
            return -1
        return match.group(1)

    def get_mem_total_size(self) -> int:
        # 返回MB
        result = self.run("cat /proc/meminfo | grep MemTotal")
        match = re.search(r"MemTotal:\s+(\d+)", self._get_stdout(result))
        if not match:
            return -1
        return int(int(match.group(1)) / 1024)

    def stress_ng_mem(self, thread_num: int, size: int):
        self.kill_process("stress-ng")
        time.sleep(1)
        cmd = f"stress-ng --vm {thread_num} --vm-bytes {size}M --vm-keep"
        self.run(f"{cmd} > /dev/null 2>&1 & disown")

    def stop_stress_ng(self):
        if self.kill_process("stress-ng"):
            time.sleep(1)

    def update_config_item(self, config_path: str, config_key: str, new_value: str, separator: str) -> bool:
        """
        修改key:value格式的配置文件
        """
        return self.change_config_line(config_path, config_key, f"{config_key}{separator}{new_value}", separator)

    def copy_file(self, src: str, dst: str, force: bool = True) -> bool:
        if force:
            output = self.run(f"/bin/cp --preserve=mode,ownership,timestamps -rf {src} {dst}")
        else:
            output = self.run(f"/bin/cp --preserve=mode,ownership,timestamps -r {src} {dst}")
        return self._get_rc(output) == 0

    def change_config_line(self, config_path: str, key: str, new_line: str, separator: str) -> bool:
        """
        修改配置文件，将包含config_key的整行替换为new_value
        """
        result = self.run(f"sed -i 's/{key} *{separator}.*$/{new_line}/g' {config_path}")
        return self._get_rc(result) == 0

    def kill_process(self, process_name: str, force: bool = True) -> bool:
        flag = "-9" if force else ""
        result = self.run(f"pkill -f {flag} {process_name}")
        return self._get_rc(result) == 0

    def get_process_id(self, process_name: str) -> List[int]:
        result = self.run(f"ps -ef | grep --color=never {process_name}")
        if self._get_rc(result) != 0:
            return []
        result = self.run(f"pidof {process_name}")
        if self._get_rc(result) != 0:
            return []
        pid_str = self._get_stdout(result, 0, 1)
        return [int(pid) for pid in pid_str.split(" ")]