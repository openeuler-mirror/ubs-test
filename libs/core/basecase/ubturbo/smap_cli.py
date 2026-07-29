import re
import time
from typing import Optional, List

from libs.core.basecase.ubturbo.smap_node_executor import SmapNodeExecutor
from libs.core.basecase.ubturbo.smap_params import EnableNodeMsg, \
    MigrateOutMsg, MigrateOutSizeMsg, MigrateBackMsg, RemoveMsg, \
    MigrateBackPayload, MigratePidNumaMsg, \
    SmapAddr, QueryMsg, QueryPayload, MigrateNumaMsg, ProcessConfigPayload, ProcessConfig, SmapTrackInfo


class SmapCli(SmapNodeExecutor):
    def __init__(self, package_path: str, ssh_host):
        super().__init__(ssh_host)

    def _cli_run(self, cmd: str, timeout=600) -> str:
        result = self._ssh_host.run({"command": [f"echo {cmd} | nc -U /tmp/smap_nc_socket.sock"], "timeout":timeout})
        if result['stderr']:
            raise Exception("cli命令执行失败:%s" % result)
        return self._split_stdout(result['stdout'], 0)

    @staticmethod
    def _get_func_ret_code(output: str) -> int:
        match = re.search(r'ret\((-?\d+)\)', output)
        if not match:
            raise RuntimeError(f"Failed to match the return value.")
        return int(match.group(1))

    def smap_init(self, page_type: int) -> int:
        output = self._cli_run(f"smap smap_init {page_type}")
        return self._get_func_ret_code(output)

    def smap_set_runmode(self, run_mode: int) -> int:
        output = self._cli_run(f"smap set_smap_run_mode {run_mode}")
        return self._get_func_ret_code(output)

    def set_smap_remote_numa_info(self, src_nid: Optional[int], dst_nid: Optional[int],
                                  available_mem: Optional[int]) -> int:
        if src_nid is None:
            output = self._cli_run(f"smap set_smap_remote_numa_info")
        else:
            output = self._cli_run(f"smap set_smap_remote_numa_info {src_nid} {dst_nid} {available_mem}")
        return self._get_func_ret_code(output)

    def smap_stop(self) -> int:
        output = self._cli_run(f"smap smap_stop")
        return self._get_func_ret_code(output)

    def smap_mig_out(self, msg: Optional[MigrateOutMsg], pid_type) -> int:
        if msg:
            output = self._cli_run(f"smap smap_mig_out {str(msg)} {pid_type}")
        else:
            output = self._cli_run(f"smap smap_mig_out {pid_type}")
        return self._get_func_ret_code(output)

    def smap_mig_out_memsize(self, msg: Optional[MigrateOutSizeMsg], pid_type) -> int:
        if msg:
            output = self._cli_run(f"smap smap_mig_out_memsize {str(msg)} {pid_type}")
        else:
            output = self._cli_run(f"smap smap_mig_out_memsize {pid_type}")
        return self._get_func_ret_code(output)

    def smap_mig_out_memsize_sync(self, msg: Optional[MigrateOutSizeMsg], pid_type, wait_time) -> int:
        if msg:
            output = self._cli_run(f"smap smap_mig_out_sync {str(msg)} {pid_type} {wait_time}")
        else:
            output = self._cli_run(f"smap smap_mig_out_sync {pid_type}")
        return self._get_func_ret_code(output)

    def smap_migrate_back(self, msg: Optional[MigrateBackMsg]):
        if msg:
            output = self._cli_run(f"smap smap_mig_back {str(msg)}", timeout=600)
        else:
            output = self._cli_run(f"smap smap_mig_back")
        return self._get_func_ret_code(output)

    def smap_remove(self, msg: Optional[RemoveMsg], pid_type: int) -> int:
        if msg:
            output = self._cli_run(f"smap smap_remove {str(msg)} {pid_type}")
        else:
            output = self._cli_run(f"smap smap_remove {pid_type}")
        return self._get_func_ret_code(output)

    def smap_black(self, proc_name: str) -> int:
        output = self._cli_run(f"smap smap_black {proc_name}")
        return self._get_func_ret_code(output)

    def smap_unblack(self, proc_name: str) -> int:
        output = self._cli_run(f"smap smap_unblack {proc_name}")
        return self._get_func_ret_code(output)

    def smap_enable_node(self, msg: Optional[EnableNodeMsg]) -> int:
        if msg:
            output = self._cli_run(f"smap smap_enable {str(msg)}")
        else:
            output = self._cli_run(f"smap smap_enable")
        return self._get_func_ret_code(output)

    def batch_mig_back(self, src_node: int, dst_node: int, addr_list: List[SmapAddr]) -> bool:
        is_success = False
        for addr in addr_list:
            for _ in range(4):
                msg = MigrateBackMsg([MigrateBackPayload(src_node, dst_node, addr.pa_start, addr.pa_end)])
                rc = self.smap_migrate_back(msg)
                if rc == -11:  # -11 表示等待远端numa 可用时超时, 需要重试
                    self.logger.info("waiting for remote numa be available timed out")
                    time.sleep(15)
                    continue
                if rc == 0:
                    is_success = True
                break
        return is_success

    def smap_query_vms_mem(self, flag: int) -> QueryMsg:
        output = self._cli_run(f"smap smap_query_vms_mem {flag}")
        rc = self._get_func_ret_code(output)
        query_msg = QueryMsg(rc, [])
        matches = re.findall(r'ratio (\d+\.\d+)% of VM pid\((\d+)\)', output)
        for match in matches:
            query_msg.payload.append(QueryPayload(float(match[0]), int(match[1])))
        return query_msg

    def smap_query_vm_freq(self, pid: int, data_flag: int, length: int) -> int:
        output = self._cli_run(f"smap smap_query_vm_freq {pid} {data_flag} {length}")
        return self._get_func_ret_code(output)

    def smap_query_vm_freq_statistic_hits(self, pid: int, data_flag: int, length: int, no_print: int,
                                          page_start: int, page_end: int, datasource: int) -> int:
        output = self._cli_run(
            f"smap smap_query_vm_freq_statistic {pid} {data_flag} {length} {no_print} {page_start} {page_end} {datasource}")
        rc = self._get_func_ret_code(output)
        if rc != 0:
            return rc
        match = re.search(r"nr_freq0: (\d+), hits: (\d+)", output)
        if not match:
            return -1
        return int(match.group(2))

    def smap_query_vm_cold_pages(self, pid: int, data_flag: int, length: int, no_print: int, page_start: int,
                                 page_end: int) -> int:
        """
        返回指定页面范围的冷页数量
        :param pid: 进程号
        :param data_flag: 用于构造数组空指针
        :param length: 总的页面数量
        :param no_print: 不打印详情，默认1
        :param page_start: 页面起始，如8G虚拟机迁出2G，起始就是3072，终止就是4095
        :param page_end: 页面终止
        :return: 返回冷热页数量
        """
        output = self._cli_run(f"smap smap_query_vm_freq {pid} {data_flag} {length} {no_print} {page_start} {page_end}")
        rc = self._get_func_ret_code(output)
        if rc != 0:
            return rc
        match = re.search(r"nr_freq0: (\d+), hits: (\d+)", output)
        if not match:
            self.logger.error("failed to get cold pages")
            return -1
        return int(match.group(1))

    def smap_enable_process_migrate(self, pid_list: List[int], length: int, enable: int, flags: int):
        pid_str = " ".join([str(pid) for pid in pid_list])
        output = self._cli_run(f"smap smap_enable_process_migrate {enable} {flags} {length} {pid_str}")
        return self._get_func_ret_code(output)

    def smap_migrate_pid_remote_numa(self, msg: Optional[MigratePidNumaMsg], migMode: int):
        if msg:
            output = self._cli_run(f"smap smap_migrate_pid_remote_numa {str(msg)} {migMode}")
        else:
            output = self._cli_run(f"smap smap_migrate_pid_remote_numa")
        return self._get_func_ret_code(output)

    def smap_migrate_remote_numa(self, msg: Optional[MigrateNumaMsg]) -> int:
        if msg:
            output = self._cli_run(f"smap smap_migrate_remote_numa {str(msg)}")
        else:
            output = self._cli_run(f"smap smap_migrate_remote_numa")
        return self._get_func_ret_code(output)

    def smap_add_process_tracking(self, pid_list: List[int], pid_time: List[int], length: int, scanType: int):
        pid_str = " ".join([str(pid) for pid in pid_list])
        pid_time = " ".join([str(pid) for pid in pid_time])
        output = self._cli_run(f"smap smap_add_process_tracking {pid_str} {pid_time} {length} {scanType}")
        return self._get_func_ret_code(output)

    def smap_add_process_statistic_tracking(self, pid_list: List[int], scan_time: List[int], duration: List[int],
                                            length: int, scan_type: int):
        pid_str = " ".join([str(pid_item) for pid_item in pid_list])
        scan_time_str = " ".join([str(scan_time_item) for scan_time_item in scan_time])
        duration_str = " ".join([str(duration_item) for duration_item in duration])
        output = self._cli_run(
            f"smap smap_add_process_statistic_tracking {pid_str} {scan_time_str} {duration_str} {length} {scan_type}")
        return self._get_func_ret_code(output)

    def smap_remove_process_tracking(self, pid_list: List[int], length: int, flag: int):
        pid_str = " ".join([str(pid) for pid in pid_list])
        output = self._cli_run(f"smap smap_remove_process_tracking {pid_str} {length} {flag}")
        return self._get_func_ret_code(output)

    def smap_query_process_config(self, nid: int, flag: int, in_len: int, out_len: int) -> ProcessConfig:
        output = self._cli_run(f"smap smap_query_process_config {nid} {flag} {in_len} {out_len}")
        rc = self._get_func_ret_code(output)
        match = re.search(r'outLen:\s*(\d+)', output)
        if not match:
            out_len = 0
        else:
            out_len = int(match.group(1))
        process_config = ProcessConfig(rc, out_len, [])
        matches = re.findall(
            r'pid: (\d+), type: (\d+), state: (\d+), ratio: (\d+), l1: (\d+), l2: (\d+), scanType: (\d+), '
            r'scanTime: (\d+)', output)
        for match in matches:
            process_config.payload.append(ProcessConfigPayload(int(match[0]), int(match[1]), int(match[2]),
                                                               int(match[3]), int(match[4]), int(match[5]),
                                                               int(match[6])))
        return process_config

    def smap_set_smap_run_mode(self, mode: int):
        output = self._cli_run(f"smap set_smap_run_mode {mode}")
        return "Set run mode success!" in output

    def read_proc_tracking_info(self, pid) -> List[SmapTrackInfo]:
        time.sleep(10)
        output = self._cli_run(f"smap smap_query_freq_info {pid}")
        if output is None:
            return []
        track_info_list = []
        array_size = 0
        for info in output.split('\n'):
            if 'failed' in info:
                raise RuntimeError(f"Failed to read tracking info: {info}")
            if info.startswith('array size is '):
                array_size = int(str(info).split('array size is ')[1])
            elif info.startswith('addr '):
                track_info_list.append(SmapTrackInfo(int(str(info).split(" ")[1], 16), int(str(info).split(" ")[3])))

        if array_size != len(track_info_list):
            raise RuntimeError(f"array size from reader: {array_size} not equal "
                               f"to size of tracking info: {len(track_info_list)}")
        return track_info_list

    def smap_enable_adapt_mem(self, mode: int) -> bool:
        output = self._cli_run(f"smap smap_enable_adapt_mem {mode}")
        return f"Setup adapt mem {mode} succeed!" in output

    def smap_query_numa_freq(self, length: int, numa_list: List[int]):
        numa_str = " ".join([str(numa) for numa in numa_list])
        output = self._cli_run(f"smap smap_query_numa_freq {length} {numa_str}")
        rc = self._get_func_ret_code(output)
        if rc != 0:
            return rc
        match = re.search(r"freq: (\d+)", output)
        if not match:
            self.logger.error("failed to get freq")
            return -1
        return int(match.group(1))