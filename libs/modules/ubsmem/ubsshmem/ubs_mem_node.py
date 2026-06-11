#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import re
import sys
import time
from typing import List, Optional, Dict

from libs.modules.ubsmem.common.node_excutor import NodeExecutor
from libs.modules.ubsmem.ubsshmem.ubs_mem_cli import UbsMemHttpClient
from libs.modules.ubsmem.ubsshmem.ubs_mem_models import ShmAccount, BorrowAccount, UbsMemPerfTp, PerfLatency, NodeCluster, CpuTopo


class UbsMemNode(NodeExecutor):
    _user_identity = None

    def __init__(self, ssh_host, install_path: str, node_id: int):
        super().__init__(ssh_host)
        self._init_ubsmd_identity()
        self._install_path = install_path
        self.node_id = node_id
        self.default_app_num = 16
        self._app_ids = range(5123, 5199)
        self.host_name = ""
        self.apps: List[UbsMemHttpClient] = [UbsMemHttpClient(ssh_host, self._install_path, app_id)
                                      for app_id in self._app_ids]
        self.app_name = "ubs_mem_test"
        self.log_path = f"{self._install_path}/log"
        self.stress_ng_path = f"{self._install_path}/bin/stress-ng"
        self._app_path = f"{self._install_path}/bin/{self.app_name}"
        self._app_dependency = "UBSM_SDK_TRACE_ENABLE=1 MXM_CHANNEL_TIMEOUT=610 LD_LIBRARY_PATH=/usr/local/ubs_mem/lib/:$LD_LIBRARY_PATH prlimit --nofile=4096:4096"
        self.ubsm_service = "ubsmd.service"
        self.ubsm_service_proc_name = "/usr/local/ubs_mem/bin/ubsmd"
        self.ubsm_service_log = "/var/log/ubsm/ubsmd.log"
        self.ubsm_filter_log = f"{self._install_path}/bin/ubsmd_filter.log"
        self.app_filter_log = f"{self._install_path}/bin/app_filter.log"
        self.ubse_service = "ubse.service"
        self.ubsm_start_log = f"{self._install_path}/bin/ubsmd_start.log"
        self.ubsmd_service_proc_name = "/usr/local/ubs_mem/bin/ubsmd"
        self.ubse_service_proc_name = "/usr/bin/ubse"
        self.ubsmd_conf = "/usr/local/ubs_mem/config/ubsmd.conf"
        self.ubse_conf = "/etc/ubse/ubse.conf"
        self.rack_uds_user_conf = "/etc/ubse/ubse_uds_user_verify.conf"
        self.rack_plugin_admission_conf = "/etc/ubse/ubse_plugin_admission.conf"
        self.fault_exe = f"{self._install_path}/*/dcat/dcat"
        self.ubsm_records_path = "/dev/shm/ubsm_records"
        self.core_dir = "/home/corefile"
        self.ubsmd_core_prefix = "core-ubsmd-"
        self.app_uid = 65536
        self.app_gid = 65536

    def get_ubsmd_identity(self):
        if self._user_identity is None:
            self._init_ubsmd_identity()
        return self._user_identity

    def set_host_name(self, name: str):
        self.host_name = name

    def set_node_id(self, node_id: str):
        self.node_id = node_id

    def start_apps(self, count: int):
        self.clear_all_app()
        start_cmd = f"do {self._app_dependency} setpriv --reuid {self.app_uid} --regid {self.app_gid} --groups $(id -g ubsmd) {self._app_path} -p $i -l {self.log_path}/mem_test_$i.log"
        self.run(f"for i in {{{self._app_ids[0]}..{self._app_ids[0] + count}}}; {start_cmd} > {self.log_path}/http_$i.log 2>&1 & disown; done")
        self.sleep(3)

    def start_app_by_index(self, app_index: int):
        self.start_app_by_user(self.app_uid, self.app_gid, app_index)

    def get_active_app_num(self) -> int:
        result = self.run(f"ps -ef | grep {self._app_path} | grep -v 'grep' | wc -l")
        match = re.search(r"(\d+)", result.std_out)
        return int(match.group(1))

    def start_app_by_user(self, uid: int, gid: int, app_index: int):
        self.kill_app_by_index(app_index)
        app_id = self._app_ids[app_index]
        http_log = f"{self.log_path}/diagnose{app_id}.log"
        cmd = f"{self._app_path} -p {app_id} -l {self.log_path}/mem_test_$i.log > {http_log} 2>&1 & disown"
        self.run_by_user(self._app_dependency, cmd, uid, gid, f"{self.get_ubsmd_identity().gid}")

    def clear_all_app(self):
        self.kill_process(f"{self.app_name}")
        self.sleep(0.5)

    def kill_app_by_index(self, app_index):
        app_id = self._app_ids[app_index]
        kill_param = f"\"{self.app_name} -p {app_id}\""
        self.kill_process(kill_param, True)
        self.sleep(0.5)

    def kill_ubsmem_by_sigal(self, signal: int) -> bool:
        return self.kill_process_by_signal(self.ubsm_service_proc_name, signal)

    def kill_ubse_by_sigal(self, signal: int) -> bool:
        return self.kill_process_by_signal(self.ubse_service_proc_name, signal)

    def kill_app_by_sigal(self, signal: int) -> bool:
        return self.kill_process_by_signal(self.app_name, signal)

    def get_app_pid(self, app_index: int) -> int:
        app_id = self._app_ids[app_index]
        pid_list = self.pgrep_process_id(f"\"{self.app_name} -p {app_id}\"")
        if len(pid_list) != 0:
            return pid_list[0]
        return -1

    def get_ubsmd_pid(self) -> int:
        pid_list = self.get_process_id(self.ubsmd_service_proc_name)
        return pid_list[0]

    def app_is_alive(self, count: int) -> bool:
        for app_id in self._app_ids[:count]:
            pids = self.pgrep_process_id(f"\"{self.app_name} {app_id}\"")
            if len(pids) == 0:
                self.logger.error(f"The process with ID:{app_id} does not exist. ")
                return False
        return True

    def ubsm_service_active(self) -> bool:
        if not self.systemctl_check_active(self.ubsm_service):
            return False
        output = self.run(f"systemctl status ubsmd | grep --color=never \"Status: \\\"available\\\"\"")
        self.run("systemctl status ubsmd")
        return output.std_rc == 0

    def ubsm_service_stop(self) -> bool:
        return self.systemctl_stop(self.ubsm_service)

    def ubsm_service_start(self) -> bool:
        return self.systemctl_start(self.ubsm_service)

    def ubsm_service_restart(self) -> bool:
        return self.systemctl_restart(self.ubsm_service)

    def ubse_service_active(self):
        return self.systemctl_check_active(self.ubse_service)

    def ubse_service_stop(self) -> bool:
        return self.systemctl_stop(self.ubse_service)

    def ubse_service_start(self) -> bool:
        return self.systemctl_start(self.ubse_service)

    def record_start_log(self):
        self.wait_file_content_async(self.ubsm_service_log, "ubsmd is started", self.ubsm_start_log, 180)

    def wait_ubsm_started(self, timeout: int) -> bool:
        return self.wait_file_content(self.ubsm_start_log, "ubsmd is started", timeout)

    def find_ubse_master(self) -> str:
        output = self.run(f"sudo -u ubse /usr/bin/ubsectl display cluster")
        match = re.search(r"(\S+)\(\d+\)\s+master", output.std_out)
        if not match:
            return ""
        return match.group(1)

    def wait_ubsmem_active(self, timeout: int) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.ubsm_service_active():
                return True
            self.sleep(20)
        return False

    def ubsm_service_failed(self) -> bool:
        result = self.run(f"systemctl status {self.ubsm_service}")
        self.logger.info(f"check ubsm failed{result.std_out}")
        output = self.run(f"systemctl status {self.ubsm_service} | grep --color=never code=exited")
        return output.std_rc == 0

    def wait_ubse_active(self, timeout: int) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.ubse_service_active():
                return True
            self.sleep(20)
        return False

    def get_obmm_device_count(self) -> int:
        result = self.run("ll /dev/obmm* | wc -l")
        if result.std_rc != 0:
            return 0
        match = re.search(r"(\d+)", result.std_out)
        if not match:
            return -1
        return int(match.group(1)) - 1

    def get_remote_numa(self) -> List[int]:
        result = self.run("lscpu | grep --color=never \"NUMA\"")
        matchs = re.findall(r"NUMA\s+node(\d+)\s+CPU\(s\):\s*$", result.std_out, re.MULTILINE)
        return [int(match) for match in matchs]

    def get_loacl_numa(self) -> List[int]:
        result = self.run("lscpu | grep --color=never \"NUMA\"")
        matchs = re.findall(r"NUMA\s+node(\d+)\s+CPU\(s\):\s*\d+", result.std_out, re.MULTILINE)
        return [int(match) for match in matchs]

    def get_numa_node_memory(self) -> List[int]:
        """
        获取每个numa的内存量
        :return: 内存大小的列表，MB为单位
        """
        result = self.run(f"numastat -c -vm")
        match = re.search(r'MemTotal\s+(.*)', result.std_out)
        if not match:
            return []
        numbers_str = match.group(1)
        return [int(mem) for mem in numbers_str.split()][:-1]

    def get_numa_node_huge_memory(self) -> List[int]:
        """
        获取每个numa的空闲大页内存量
        :return: 内存大小的列表，MB为单位
        """
        if self.is_borrow_from_1G_huge():
            local_numa_list = self.get_loacl_numa()
            size_list = []
            for numa in local_numa_list:
                result = self.run(f"cat /sys/devices/system/node/node{numa}/hugepages/hugepages-1048576kB/free_hugepages")
                size_g = self._split_stdout(result.std_out, 0, 1)
                size_list.append(int(size_g) * 1024)
            return size_list
        result = self.run(f"numastat -c -vm")
        match = re.search(r'HugePages_Free\s+(.*)', result.std_out)
        if not match:
            return []
        numbers_str = match.group(1)
        return [int(mem) for mem in numbers_str.split()][:-1]

    def get_shm_account(self, shm_name: str) -> Optional[ShmAccount]:
        """
        获取账本共享内存中的：name, 1borrow_node、2provider导出节点、5size、3导出numa，4导出socket,6shm_status、7handle
        """
        result = self.run("sudo -u ubse ubsectl display memory -t borrow_detail")
        if len(shm_name) <= 30:
            match = re.search(
                rf"{shm_name}\s*share\s*(\S+\(\d+\))?\s*\S+\((\d+)\)\s*(\d+)\((\d+)\)\s*(\d+)\s*(\S+)\s*(\S+)",
                result.std_out)
        else:
            shm_name_pre = shm_name[0:30]
            shm_name_post = shm_name[30:]
            match = re.search(
                rf"{shm_name_pre}\s*share\s*(\S+\(\d+\))?\s*\S+\((\d+)\)\s*(\d+)\((\d+)\)\s*(\d+)\s*(\S+)\s*(\S+)\s*{shm_name_post}",
                result.std_out)
        if not match:
            self.logger.info(f"Failed to find shm account for {shm_name}")
            return None
        if match.group(1) is not None:
            match_bracket = re.search(r"\((\d+)\)", match.group(1))
            borrow_node = int(match_bracket.group(1))
        else:
            borrow_node = -1
        return ShmAccount(shm_name, borrow_node, int(match.group(2)), int(match.group(5)), int(match.group(3)),
                          int(match.group(4)), match.group(6))

    def get_borrow_account(self, borrow_node_name: str) -> List[BorrowAccount]:
        """
        获取账本中借用内存的：size、导出节点、导出numa，导出socket
        """
        result = self.run(f"sudo -u ubse ubsectl display memory -t borrow_detail")
        matches = re.findall(rf"(numa|fd)\s*{borrow_node_name}\((\d+)\)\s*\S*\((\d+)\)\s*(\d+)\((\d+)\)\s*(\d+)\s*(\S+)",
                             result.std_out)
        if not matches:
            self.logger.error(f"Failed to find borrow account for {borrow_node_name}")
            return []
        account_list = []
        for match in matches:
            account_list.append(
                BorrowAccount(int(match[5]), int(match[1]), int(match[2]), int(match[3]), int(match[4])))
        return account_list

    def wait_shm_account_clear(self, shm_name: str, timeout: int):
        """
        :param shm_name: 共享内存名字
        :param timeout: 等待时间
        等待共享内存中的特定账户信息被清除
        :return: True已经自动释放,False未释放
        """
        start_time = time.time()
        while time.time() - start_time < timeout + 35:
            if self.get_shm_account(shm_name) is None:
                return True
            self.sleep(30)
        return False

    def modify_ubsmd_config(self, key: str, new_value: str) -> bool:
        return self.update_config_item(self.ubsmd_conf, key, new_value, "=", flag="|")

    def modify_rack_config(self, key: str, new_value: str) -> bool:
        return self.update_config_item(self.ubse_conf, key, new_value, "=", flag="|")

    def modify_rack_uds_config(self, key: str, new_value: str) -> bool:
        return self.update_config_item(self.rack_uds_user_conf, key, new_value, "=", flag="|")

    def get_rack_config(self, config_item: str) -> str:
        result = self.get_config_value(self.ubse_conf, config_item)
        return result

    def comment_rack_config(self, key: str):
        return self.comment_config(self.ubse_conf, key)

    def uncomment_rack_config(self, key: str):
        return self.uncomment_config(self.ubse_conf, key)

    def backup_ubse_config(self):
        self.copy_file(self.ubse_conf, f"{self.ubse_conf}_bak")

    def get_ubsmd_config(self, config_item: str) -> str:
        result = self.get_config_value(self.ubsmd_conf, config_item)
        return result

    def backup_config(self):
        self.copy_file(self.ubsmd_conf, f"{self.ubsmd_conf}_bak")

    def recover_ubse_config(self):
        self.copy_file(f"{self.ubse_conf}_bak", self.ubse_conf)

    def recover_config(self):
        self.copy_file(f"{self.ubsmd_conf}_bak", self.ubsmd_conf)

    def get_node_id(self, host_name: str) -> int:
        result = self.run(f"sudo -u ubse ubsectl display cluster")
        if result.std_rc != 0:
            return -1
        match = re.search(rf"{host_name}\((\d+)\)", result.std_out)
        if not match:
            return -1
        return int(match.group(1))

    def is_lock_master(self) -> bool:
        master_ip = self.apps[0].query_master_node()
        if master_ip == self.node_ip:
            return True
        return False

    def is_lock_client(self) -> bool:
        client_ip = self.apps[0].query_client_node()
        if client_ip == self.node_ip:
            return True
        return False

    def get_borrow_huge_limit(self) -> List[int]:
        """返回字节为单位"""
        numa_mem_list = self.get_numa_node_huge_memory()
        numa_mem_list = [size if size < 256 * 1024 else 256 * 1024 for size in numa_mem_list]
        return [size * 1024 * 1024 for size in numa_mem_list]

    def get_urma_eid(self) -> str:
        result = self.run("urma_admin show")
        match = re.search(rf"\d+\s+bonding_dev_0\s+UB\s+eid0\s+(\S+:\S+:\S+:\S+:\S+:\S+:\S+:\S+)", result.std_out)
        if not match:
            raise RuntimeError("Failed to get urma eid")
        return match.group(1)

    def check_rack_mem_ok_by_id(self, node_list: List[int]) -> bool:
        result = self.run("sudo -u ubse /usr/bin/ubsectl check memory")
        if result.std_out is None:
            return False
        for node_id in node_list:
            match = re.search(rf"\S+\({node_id}\)\s+\S+\s+cluster state:\s*ok;\s+obmm:\s*ok", result.std_out)
            if not match:
                return False
        return True

    def check_rack_mem_ok_by_name(self, node_name_list: List[str]) -> bool:
        result = self.run("sudo -u ubse /usr/bin/ubsectl check memory")
        if result.std_out is None:
            return False
        for node_name in node_name_list:
            match = re.search(rf"{node_name}\(\d+\)\s+\S+\s+cluster state:\s*ok;\s+obmm:\s*ok", result.std_out)
            if not match:
                return False
        return True

    def stress_cpu(self, cpu_num: int, load: int):
        self.kill_process("stress-ng")
        self.run(f"{self.stress_ng_path} --cpu {cpu_num} --cpu-load {load} > {self._install_path}/bin/stress.log 2>&1 & disown")
        self.sleep(3)
        self.run(f"top -1 -n 1 | col -b")

    def clear_stress(self):
        self.run(f"top -1 -n 1 | col -b")
        self.kill_process("stress-ng")

    def get_perf_data(self, pid: int, tp: UbsMemPerfTp) -> PerfLatency:
        """
        获取指定打点的时延
        :param pid: 进程号
        :param tp: 打点枚举
        :return: 返回时延，ms单位
        """
        perf_file = f"/tmp/ptracer_{pid}.dat"
        perf_data = self.read_file(perf_file)
        if not perf_data:
            raise RuntimeError("Failed to read perf file")
        matches = re.findall(rf"{tp.name}\s+(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\.?\d*\s+\d+\.?\d*\s+(\d+\.?\d*)\s+\d+\.?\d*\s+(\d+\.?\d*)", perf_data)
        if not matches:
            raise RuntimeError("Failed to match perf data")
        count = 0
        latency_total = 0.0
        latency_max = sys.float_info.min
        for match in matches:
            count = count + int(match[0])
            latency_max = max(latency_max, float(match[1]))
            latency_total = latency_total + float(match[2])

        latency_avg = latency_total / count / 1000
        latency_total = latency_total / 1000
        latency_max = latency_max / 1000
        self.logger.info(f"{'borrow' if tp == UbsMemPerfTp.TP_UBSM_MALLOC else 'shm'} count: {count}, total latency: {latency_total}ms, "
                         f"max latency: {latency_max}ms, average latency: {latency_avg}ms")
        return PerfLatency(latency_total, latency_max, latency_avg)

    def is_borrow_from_huge(self) -> bool:
        output = self.read_file("/proc/cmdline")
        return "pmd_mapping=100%" in output

    def is_borrow_from_1G_huge(self) -> bool:
        output = self.read_file("/proc/cmdline")
        return "hugepagesz=1G" in output

    def injection_fault(self, mode, *args) -> bool:
        """
        TODO: dcat_entry模块缺失,故障注入功能需要重新实现
        """
        self.logger.warn("injection_fault not implemented - dcat_entry module missing")
        return False

    def recover_fault(self, mode, *args):
        """
        TODO: dcat_entry模块缺失,故障恢复功能需要重新实现
        """
        self.logger.warn("recover_fault not implemented - dcat_entry module missing")
        return False

    def clear_tls_files(self):
        self.remove_file("/usr/local/ubs_mem/.pkey")

    def generate_tls_ca_path(self, ca_path: str) -> str:
        self.run(f"openssl genrsa -out {ca_path}/ca.key.pem 2048")
        self.run(f"openssl req -x509 -new -nodes -key {ca_path}/ca.key.pem  -sha256 -days 3650 -out {ca_path}/ca.pem "
                 f"-subj \"/C=CN/ST=Test/L=Test/O=TEST_CA/OU=Dev/CN=Test Root CA\"")
        return f"{ca_path}/ca.pem"

    def generate_tls_cert_path(self, ca_path: str, cert_path: str) -> List[str]:
        cert = f"{cert_path}/cert.pem"
        cert_key = f"{cert_path}/cert.key.pem"
        cert_csr = f"{cert_path}/cert.csr"
        self.run(f"openssl genrsa -out {cert_key} 2048")
        self.run(f"openssl req -new -key {cert_key} -out {cert_csr} -subj "
                 f"\"/C=CN/ST=Test/L=Test/O=Test/OU=Dev/CN=Cert\"")
        self.run(f"openssl x509 -req -in {cert_csr} -CA {ca_path}/ca.pem -CAkey {ca_path}/ca.key.pem "
                 f"-CAcreateserial -out {cert} -days 7 -sha256")
        self.remove_file(f"{cert_csr}")
        return [cert, cert_key]

    def generate_tls_revoked_cert_path(self, ca_path: str, cert_path: str) -> str:
        revoked_cert = f"{cert_path}/cert_revoked.pem"
        revoked_cert_key = f"{cert_path}/cert_revoked.key.pem"
        revoked_cert_csr = f"{cert_path}/cert_revoked.csr"
        self.run(f"openssl genrsa -out {revoked_cert_key} 2048")
        self.run(f"openssl req -new -key {revoked_cert_key} -out {revoked_cert_csr} -subj "
                 f"\"/C=CN/ST=Test/L=Test/O=Test/OU=Dev/CN=CertRevoked\"")
        self.run(f"openssl x509 -req -in {revoked_cert_csr} -CA {ca_path}/ca.pem -CAkey {ca_path}/ca.key.pem "
                 f"-CAcreateserial -out {revoked_cert} -days 365 -sha256")

        self.remove_file(f"{revoked_cert_csr}")
        return revoked_cert

    def generate_tls_crl_path(self, crl_path: str, ca_path: str, revoked_cert_file: str) -> str:
        cnf = f"""[ ca ]
default_ca = CA_default

[ CA_default ]
dir             = {crl_path}
        database        = $dir/index.txt
        new_certs_dir   = $dir
        certificate     = {ca_path}/ca.pem
        serial          = $dir/serial
        crlnumber       = $dir/crlnumber
        crl             = $dir/ca.crl.pem
private_key     = {ca_path}/ca.key.pem
default_md      = sha256
default_crl_days= 3650
policy          = policy_any

[ policy_any ]
commonName              = supplied"""
        self.write_file(f"{crl_path}/openssl.cnf", cnf)
        self.run(f"touch {crl_path}/index.txt")
        self.write_file(f"{crl_path}/serial", "1000")
        self.write_file(f"{crl_path}/crlnumber", "1000")

        self.run(f"openssl ca -config {crl_path}/openssl.cnf -revoke {revoked_cert_file} -keyfile {ca_path}/ca.key"
                 f".pem -cert {ca_path}/ca.pem -batch")
        self.run(f"openssl ca -gencrl -config {crl_path}/openssl.cnf -out {crl_path}/ca.crl.pem -batch")
        return f"{crl_path}/ca.crl.pem"

    def generate_private_key(self, encryptor_path: str, tools_cfg_path) -> List[str]:
        passwd_repeat = "test123\\ntest123"
        key_pass_file = f"{tools_cfg_path}/key.pass"
        self.run("ipcrm -S 0x20161227")
        self.run(
            f"echo -e \"{passwd_repeat}\" | sudo -u ubsmd LD_LIBRARY_PATH=/usr/local/ubs_mem/lib "
            f"{encryptor_path}/crypto_tool --encrypt 0 3 |grep -oP 'encrypted: \\K.*' >"
            f" {key_pass_file}"
        )
        self.run("ipcrm -S 0x20161227")
        ksfa_path = f"{tools_cfg_path}/ksfa"
        ksfb_path = f"{tools_cfg_path}/ksfb"
        return [key_pass_file, ksfa_path, ksfb_path]

    def get_ubsmd_start_time(self) -> int:
        result = self.run("ps -p $(systemctl show ubsmd --property=MainPID --value) -o etimes")
        second_time = re.search(r"ELAPSED\s*(\d+)", result.std_out)
        return int(second_time.group(1))

    def get_node_cluster(self) -> [NodeCluster]:
        result = self.run("sudo -u ubse /usr/bin/ubsectl display cluster")
        match = re.findall(r"\S*\((\d+)\)\s*(?!-)(\S+)", result.std_out)
        if not match:
            raise RuntimeError("Failed to get node cluster")
        node_cluster = []
        for m in match:
            node_cluster.append(NodeCluster(int(m[0]), m[1]))
        return node_cluster

    def get_process_fd(self, process_name: int) -> int:
        result = self.run(f"ls -l /proc/{process_name}/fd |wc -l")
        match = re.search(r"(\d+)", result.std_out)
        return int(match.group(0))

    def get_node_cpu_topo(self) -> Dict[str, List[CpuTopo]]:
        result = self.run(f"sudo -u ubse ubsectl display topo -t cpu")
        matches = re.findall(r"\s+(\S+)\((\d+)\)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\((\d+)\)\s+(\d+)\s+(\d+)\s+(\S+)",
                             result.std_out)
        topo: Dict[str, List[CpuTopo]] = {}
        for match in matches:
            val = CpuTopo(match[0], int(match[1]), int(match[2]), int(match[3]), match[4], match[5], int(match[6]),
                          int(match[7]), int(match[8]), match[9])
            if match[0] in topo:
                topo[match[0]].append(val)
            else:
                topo[match[0]] = [val]
        for match in matches:
            val = CpuTopo(match[5], int(match[6]), int(match[7]), int(match[8]), match[9], match[0], int(match[1]),
                          int(match[2]), int(match[3]), match[4])
            if match[5] in topo:
                topo[match[5]].append(val)
            else:
                topo[match[5]] = [val]
        return topo

    def clear_ubsm_records(self):
        self.remove_file(f"{self.ubsm_records_path}")

    def monitor_log(self):
        """
        与verify_log_correctness配合使用，检查是否有不应该出现的日志出现
        :param level: 日志级别
        :return: 无
        """
        self.run(f"tail -F -n 0 {self.ubsm_service_log}  > {self.ubsm_filter_log} 2>&1 & disown")

    def verify_log_correctness(self, level: str = "error") -> bool:
        """
        与monitor_log配合使用，检查是否有不应该出现的日志出现
        :param level: 日志级别
        :return: 不存在则返回True
        """
        self.kill_process(f"\"tail -F -n 0 {self.ubsm_service_log}\"")
        result = self.run(f"grep -i {level} {self.ubsm_filter_log} ")
        return result.std_rc != 0

    def _init_ubsmd_identity(self):
        if self._user_identity is None:
            self._user_identity = self.get_user_identity("ubsmd")

    def ubse_link_down(self, interface_name) -> bool:
        """
        与get_node_cpu_topo配合使用，获取interface_name，对链路进行断开
        :interface_name: 连接的链路名
        :return: True断开成功，False断开失败
        """
        result = self.run(f"echo 'set-port-simulate-task port-name {interface_name} link-simulate down' | mdcli")
        matches = re.findall("Error", result.std_out)
        if matches is not None:
            return True
        else:
            return False

    def ubse_link_restart(self, interface_name) -> bool:
        """
        与get_node_cpu_topo配合使用，获取interface_name，对链路进行恢复
        :interface_name: 连接的链路名
        :return: True恢复成功，False恢复失败
        """
        result = self.run(f"echo 'set-port-simulate-task port-name {interface_name} link-simulate stop' | mdcli")
        matches = re.findall("Error", result.std_out)
        if matches is not None:
            return True
        else:
            return False

    def clear_obmm(self):
        self.run(f"{self._app_path} --clear_obmm")