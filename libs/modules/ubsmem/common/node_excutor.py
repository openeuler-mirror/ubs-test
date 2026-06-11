#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from libs.modules.ubsmem.common.command_excutor import CommandExecutor, ExecuteResult
from libs.modules.ubsmem.common.node_models import FileStat, UserIdentity, FileMate


class NodeExecutor(CommandExecutor):
    _user_map: Dict[str, UserIdentity] = {}

    def __init__(self, ssh_host):
        super().__init__(ssh_host)
        self.node_ip = self._ssh_host.localIP
        self.node_port = self._ssh_host.port
        self.user_name = self._ssh_host.username
        self.password = self._ssh_host.password

    def run(self, cmd: str, timeout=600, work_dir: str = "") -> ExecuteResult:
        result = self._ssh_host.run({"command": [cmd],
                                     "waitstr": "]#",
                                     "timeout": timeout,
                                     "directory": f"{work_dir}"})
        return ExecuteResult(result['rc'], result['stdout'], result['stderr'])

    def run_by_user(self, env: str, cmd: str, uid: int, gid: int, groups: str):
        """
        :param env 环境变量
        :param cmd 要执行的命令
        :param uid 指定的uid
        :param gid 指定gid
        :param groups 辅助组
        """
        if groups != "":
            return self.run(f"{env} setpriv --reuid {uid} --regid {gid} --groups {groups} {cmd}")
        else:
            return self.run(f"{env} setpriv --reuid {uid} --regid {gid} --clear-groups {cmd}")

    def remove_file(self, path: str) -> bool:
        if path == "/":
            raise RuntimeError("Could not remove root directory")
        self.logger.info(f"Removing file:{path}")
        return self.run(f"rm -rf {path}").std_rc == 0

    def mkdir(self, path: str):
        self.logger.info(f"Creating directory:{path}")
        return self.run(f"mkdir -p {path}")

    def chmod(self, path: str, mode: int, recursive: bool = False):
        if recursive:
            self.run(f"chmod -R {mode:o} {path}")
        else:
            self.run(f"chmod {mode:o} {path}")

    def chown(self, path: str, usr: str, group: str, recursive: bool = False):
        if recursive:
            output = self.run(f"chown -R {usr}:{group} {path}")
        else:
            output = self.run(f"chown {usr}:{group} {path}")
        return output.std_rc == 0

    def check_file_exists(self, path: str) -> bool:
        output = self.run(f"stat {path}")
        return output.std_rc == 0

    def copy_file(self, src: str, dst: str, force: bool = True) -> bool:
        if force:
            output = self.run(f"/bin/cp --preserve=mode,ownership,timestamps -rf {src} {dst}")
        else:
            output = self.run(f"/bin/cp --preserve=mode,ownership,timestamps -r {src} {dst}")
        return output.std_rc == 0

    def rename_file(self, src: str, dst: str) -> bool:
        output = self.run(f"/bin/mv {src} {dst}")
        return output.std_rc == 0

    def create_random_file(self, output_file: str, size: int, unit: str = "M", input_file: str = "/dev/urandom",
                           other_params: str = "") -> bool:
        self.logger.info(f"Creating a {size}MB random data file:{output_file}")
        result = self.run(f"dd if={input_file} of={output_file} bs=1{unit} count={size} {other_params}")
        self.chmod(output_file, 0o777)
        return result.std_rc == 0

    def read_file(self, path: str) -> str:
        result = self.run(f"cat {path}")
        if result.std_rc != 0:
            return ""
        output_lines = result.std_out
        return output_lines

    def write_file(self, path: str, contents: str) -> bool:
        result = self.run(f"echo -e \"{contents}\" > {path}")
        return result.std_rc == 0

    def append_file(self, path: str, contents: str) -> bool:
        result = self.run(f"echo -e \"{contents}\" >> {path}")
        return result.std_rc == 0

    def update_file(self, file_path: str, new_content: str, line_num: int) -> bool:
        result = self.run(f"sed -i '{line_num}s/.*/{new_content}/' {file_path}")
        return result.std_rc == 0

    def update_config_item(self, config_path: str, config_key: str, new_value: str, separator: str,
                           flag: str = "/") -> bool:
        """
        修改key:value格式的配置文件
        """
        result = self.run(
            f"sed -i 's{flag}^{config_key}\s*{separator}\s*.*${flag}{config_key}{separator}{new_value}{flag}g' {config_path}")
        self.logger.info(f"check config change...")
        output = self.run(f"cat {config_path}")
        return result.std_rc == 0 and output.std_rc == 0

    def comment_config(self, config_path: str, key: str) -> bool:
        result = self.run(f"sed -i 's/^{key}\s*=/# &/' {config_path}")
        return result.std_rc == 0

    def uncomment_config(self, config_path: str, key: str) -> bool:
        result = self.run(f"sed -i 's/^#\s*{key}\s*=/{key}=/' {config_path}")
        return result.std_rc == 0

    def get_config_value(self, cfg_file: str, key: str) -> str:
        result = self.read_file(cfg_file)
        match = re.search(f"{key}\s*=\s*(\S+)\s+", result)
        if not match:
            return ""
        return match.group(1)

    def get_disk_capacity(self, disk_name: str) -> int:
        result = self.run(f"fdisk -l {disk_name}")
        match = re.search(r'(\d+) bytes, ', result.std_out)
        if match:
            bytes_value = match.group(1)
            return int(bytes_value)
        else:
            return -1

    def get_process_id(self, process_name: str) -> List[int]:
        result = self.run(f"ps -ef | grep --color=never {process_name}")
        if result.std_rc != 0:
            return []
        result = self.run(f"pidof {process_name}")
        if result.std_rc != 0:
            return []
        pid_str = self._split_stdout(result.std_out, 0, 1)
        return [int(pid) for pid in pid_str.split(" ")]

    def pgrep_process_id(self, grep_name: str) -> List[int]:
        cmd = f"pgrep -f {grep_name}"
        result = self.run(cmd)
        if result.std_rc != 0:
            return []
        pid_str = self._split_stdout(result.std_out, 0, 1)
        return [int(pid) for pid in pid_str.split(" ")]

    def kill_process(self, process_name: str, force: bool = True) -> bool:
        flag = "-9" if force else ""
        result = self.run(f"pkill -f {flag} {process_name}")
        return result.std_rc == 0

    def kill_process_by_signal(self, process_name: str, signal: int) -> bool:
        result = self.run(f"pkill -f -{signal} {process_name}")
        return result.std_rc == 0

    def kill_process_by_pid(self, pid: int):
        result = self.run(f"kill -9 {pid}")
        return result.std_rc == 0

    def stop_process(self, process_name: str) -> bool:
        output = self.run(f"kill -19 {process_name}")
        return output.std_rc == 0

    def get_file_md5(self, path: str) -> str:
        result = self.run(f"md5sum {path}")
        if result.std_rc != 0:
            self.logger.error(f"Failed to get md5 for {path}]")
            return ""
        match = re.search(rf"(\S+)\s+{path}", result.std_out)
        return match.group(1)

    def get_file_part_md5(self, path: str, start: int, count: int, unit: str = "M") -> str:
        result = self.run(f"dd if={path} bs=1{unit} skip={start} count={count} | md5sum")
        if result.std_rc != 0:
            self.logger.error(f"Failed to get md5 for {path}]")
            return ""
        match = re.search(rf"(\S+)\s+-", result.std_out)
        return match.group(1)

    def bet_batch_file_md5(self, files: List[str]) -> List[str]:
        file_list = " ".join(files)
        result = self.run(f"md5sum {file_list}")
        if result.std_rc != 0:
            self.logger.error(f"Failed to get md5]")
            return []
        matches = re.findall(r"([a-f0-9]{32})", result.std_out)
        return matches

    def wait_file_content(self, file_name: str, content: str, timeout: int = 60) -> bool:
        result = self.run(f"timeout {timeout} tail -f {file_name} | grep --color=never -i -m 1 \"{content}\"")
        return result.std_rc == 0

    def wait_file_new_content(self, file_name: str, content: str, timeout: int = 60) -> bool:
        result = self.run(f"timeout {timeout} tail -n 0 -f -F {file_name} | grep --color=never -i -m 1 \"{content}\"")
        return result.std_rc == 0

    def wait_file_content_async(self, file_name: str, content: str, result_file: str, timeout: int = 60) -> bool:
        rc = self.kill_process(f"\"tail -n 0 -f -F {file_name}\"")
        if not rc:
            self.logger.warn("Process does not exist.")
        result = self.run(
            f"timeout {timeout} tail -n 0 -f -F {file_name} | grep --color=never -i -m 1 \"{content}\" > {result_file} 2>&1 & disown")
        return result.std_rc == 0

    def stat_file(self, path: str) -> Optional[FileStat]:
        output = self.run(f"stat -c \"%a %i %d %r %h %u %g %s %X %Y %Z %B %b\" {path}")
        if output.std_rc != 0:
            return None
        param_str_list = self._split_stdout(output.std_out, 0, 1).split(" ")
        param_list = [int(param_str_list[0][-3:], 8)] + [int(val) for val in param_str_list[1:]]
        return FileStat(*param_list)

    def stat_batch_file(self, file_list: List[str]) -> List[FileStat]:
        file_str = " ".join(file_list)
        output = self.run(f"stat -c \"%a %i %d %r %h %u %g %s %X %Y %Z %B %b\" {file_str}")
        result = []
        if output.std_rc != 0:
            return result
        stat_list = self._split_stdout(output.std_out, 0, len(file_list)).split("\n")
        for stat in stat_list:
            param_str_list = stat.split(" ")
            param_list = [int(param_str_list[0][-3:], 8)] + [int(val) for val in param_str_list[1:]]
            result.append(FileStat(*param_list))
        return result

    def check_progress_running(self, progress_name) -> bool:
        pid_list = self.get_process_id(progress_name)
        return len(pid_list) != 0

    def grep_file(self, content: str, file_name: str) -> str:
        result = self.run(f"grep --color=never -i \"{content}\" {file_name}")
        if result.std_rc != 0:
            return ""
        return result.std_out

    def extract_tar(self, tar_path: str, dist_path: str = "") -> bool:
        if dist_path == "":
            result = self.run(f"tar -zxf {tar_path}")
        else:
            result = self.run(f"tar -zxf {tar_path} -C {dist_path} --strip-components=1")
        return result.std_rc == 0

    def tar_package(self, dst_package: str, src_path: str):
        self.run(f"tar -zcf {dst_package} {src_path}")

    def unzip(self, tar_path, dist_path: str = "") -> bool:
        if dist_path == "":
            result = self.run(f"unzip -o {tar_path}")
        else:
            result = self.run(f"unzip -o {tar_path} -d {dist_path}")
        return result.std_rc == 0

    def show_numa_stat(self):
        self.run("numastat -c -vm")

    def show_proc_numa_stat(self, pid: int):
        self.run(f"numastat -c -p {pid}")

    def set_core_file_format(self, fmt: str):
        self.write_file("/proc/sys/kernel/core_pattern", fmt)

    def get_now_time_str(self) -> str:
        result = self.run(f"date +\"%Y-%m-%d_%H:%M:%S\"")
        if result.std_rc != 0:
            return ""
        pattern = r"\b\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}\b"
        match = re.search(pattern, result.std_out)
        if not match:
            self.logger.error("Failed to extract the timestamp.")
            return ""
        return match.group(0)

    def get_npu_process_id(self) -> List[List[int]]:
        result = self.run("npu-smi info | awk '{print $5}'")
        process_section = result.std_out.split("Process", 1)[-1].strip()
        groups = []
        current_group = []
        for line in process_section.splitlines():
            stripped = line.strip()
            if stripped:
                current_group.append(stripped)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
        pid_list = []
        for group in groups:
            if 'found' in group:
                pid_list.append([])
            else:
                pid_list.append([int(pid) for pid in group])
        return pid_list

    def sftp(self, src_path: str, dts_node: NodeExecutor, dst_path: str, recursive: bool):
        if recursive:
            self._ssh_host.scp(dts_node.node_ip, dst_path, src_path, "output", dts_node.user_name, dts_node.password,
                               option="-r")
        else:
            self._ssh_host.scp(dts_node.node_ip, dst_path, src_path, "output", dts_node.user_name, dts_node.password)

    def get_whl_name(self, path: str) -> str:
        cmd = f"ls -al {path}/*.whl"
        result = self.run(cmd)
        if result.std_rc != 0:
            return ""
        else:
            match = re.search(f"python/(\S+)", result.std_out)
            return match.group(1)

    def systemctl_stop(self, service_name: str) -> bool:
        output = self.run(f"time systemctl stop {service_name}")
        return output.std_rc == 0

    def systemctl_start(self, service_name: str) -> bool:
        output = self.run(f"time systemctl start {service_name}")
        return output.std_rc == 0

    def systemctl_restart(self, service_name: str) -> bool:
        output = self.run(f"time systemctl restart {service_name}")
        return output.std_rc == 0

    def systemctl_check_active(self, service_name: str) -> bool:
        output = self.run(f"systemctl is-active {service_name}")
        if output.std_rc != 0:
            return False
        if "inactive" in output.std_out:
            return False
        if "active" in output.std_out:
            return True
        return False

    def set_core_dumped_dir(self, dir_path: str) -> bool:
        result = self.run("echo \"* soft core unlimited\" >> /etc/security/limits.conf")
        if result.std_rc != 0:
            return False
        result = self.mkdir(dir_path)
        if result.std_rc != 0:
            self.logger.error(f"failed to mkdir {dir_path}")
        self.chmod(dir_path, 0o777)
        result = self.run(f"echo \"kernel.core_pattern={dir_path}/core-%e-%p-%t\" | tee /etc/sysctl.d/99-core.conf;sysctl -p /etc/sysctl.d/99-core.conf")
        return result.std_rc == 0

    def set_history_timestamp(self):
        result = self.run(f"grep HISTTIMEFORMAT ~/.bashrc || echo 'export HISTTIMEFORMAT=\"%F %T \"' >> ~/.bashrc")
        self.logger.info(f"Command output: {result.std_rc}")

    def get_core_dumped_num(self) -> int:
        result = self.run("dirname $(cat /proc/sys/kernel/core_pattern | sed 's/[%|].*//')")
        if result.std_rc != 0:
            core_dir = "/var/lib/systemd/coredump/"
        else:
            core_dir = self._split_stdout(result.std_out, 0, 1)
        result = self.run(f"ls -1 {core_dir} | wc -l")
        if result.std_rc != 0:
            self.logger.error("failed to get core dumped number")
            return 0
        num_str = self._split_stdout(result.std_out, 0, 1)
        return int(num_str)

    def env_top(self, count: int):
        result = self.run(f"for i in {{1..{count}}}; do top -b -n 1 | head -n 10; sleep 2; done")
        if result.std_rc != 0:
            self.logger.error(f"top command failed: {result.std_out}")

    def get_host_name(self) -> str:
        output = self.run("hostname")
        if output.std_rc != 0:
            self.logger.error("Failed to get hostname")
            return ""
        return output.std_out.split()[0]

    def get_user_identity(self, user: str) -> Optional[UserIdentity]:
        if user in self._user_map:
            return self._user_map[user]
        result = self.run(f"id {user}")
        if result.std_rc != 0:
            return None
        match = re.search(rf"uid=(\d+)\({user}\) gid=(\d+)\({user}\)", result.std_out)
        if not match:
            raise RuntimeError("failed to get user identity")
        return UserIdentity(user, match.group(1), match.group(2))

    def iterate_check_files(self, parent: str, file: FileMate) -> bool:
        for child in file.child:
            return self.iterate_check_files(file.file_name, child)
        file_path = f"{parent}/{file.file_name}"
        file_stat = self.stat_file(file_path)
        if file_stat is None:
            self.logger(f"file:{file} is not exist")
            return False
        if file_stat.st_mode != file.file_mode:
            self.logger(f"file:{file} mode is Incorrect")
            return False
        file_id = self.get_user_identity(file.user_name)
        if file_stat.st_uid != file_id.uid:
            self.logger(f"file:{file} uid is Incorrect")
            return False
        if file_stat.st_gid != file_id.gid:
            self.logger(f"file:{file} gid is Incorrect")
            return False

    def reboot(self):
        self._ssh_host.reboot(wait=True)

    def assign_huge_pages(self, node: int, pg_size: int, count: int) -> bool:
        result = self.run(f"echo {count} > /sys/devices/system/node/node{node}/hugepages/hugepages-{pg_size}kB/nr_hugepages")
        return result.std_rc == 0

    def get_cpu_num(self) -> int:
        result = self.run("lscpu | grep --color=never CPU\(s\)")
        match = re.search(r'CPU\(s\):\s+(\d+)', result.std_out)
        if not match:
            return -1
        return int(match.group(1))

    def get_cpu_topo(self) -> List[List[int]]:
        result = self.run("lscpu | grep --color=never \"NUMA node\"")
        matches = re.findall(r'NUMA node\d+ CPU\(s\):\s+(\d+)-(\d+)', result.std_out)
        if not matches:
            raise RuntimeError("Failed to get cpu topology")
        cpu_topo = []
        for match in matches:
            cpu_topo.append([i for i in range(int(match[0]), int(match[1]) + 1)])
        return cpu_topo

    def create_symbolic_link(self, src: str, dst: str) -> bool:
        result = self.run(f"ln -sf {src} {dst}")
        return result.std_rc == 0

    def update_sys_time(self):
        utc_timestamp = time.time()
        beijing_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
        time_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
        result = self.run(f"date -s \"{time_str}\"; hwclock --systohc")
        self.logger.info(f"Command output: {result.std_rc}")