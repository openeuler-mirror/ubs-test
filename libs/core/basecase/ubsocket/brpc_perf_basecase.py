"""BRPCPerfBaseCase - Base class for BRPC performance tests.

Migrated from: legency/testcase/ubscomm/ubsocket/lib/basecase/ubsocket/BRPCPerfBaseCase.py
"""

import ast
import json
import re
import pytest
import time
import random
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from libs.core.basecase.ubsocket.ubsocket_basecase import UBSocketBaseCase
from libs.ubsocket import brpc_utils
from libs.ubsocket import k8s_api as k8s
from libs.ubsocket.ubsocket_model import Client_result
from libs.ubsocket.result_verify import verify
from libs.utils.logger_compat import Log

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def inject_brpc_perf_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    if not isinstance(instance, BRPCPerfBaseCase):
        return
    
    instance.nodes = nodes
    instance.resource = resource
    instance.custom_params = custom_params
    
    instance.worker_list = []
    instance.node_detail = []
    for node in nodes:
        if node.detail:
            host_role = node.detail.get("host_role")
            if host_role == "master":
                instance.master = node
            if "worker" in host_role:
                instance.worker_list.append(node)
            instance.node_detail.append(host_role)
    
    instance.test_scene = ast.literal_eval(custom_params.get('test_scene', '{}'))
    instance.pairnums = []
    instance.brpc_tool_dir = custom_params.get('brpc_tool_dir', '/home/share/autotest')
    if instance.test_scene != {""}:
        instance.pairnum = int(instance.test_scene.get('pairnum', 1))
        instance.client_num_per_server = int(instance.test_scene.get('client_num_per_server', 1))
        instance.client_num_per_node = int(instance.test_scene.get('client_num_per_node', 1))
    else:
        instance.pairnum = 1
        instance.client_num_per_server = 1
        instance.client_num_per_node = 1
    instance.title_cmd = ""
    instance.autotest_logs = f"{brpc_utils.autotest_log_dir}/{brpc_utils.get_timestamp()}"
    instance.expected_qps = 100
    instance.observe_info = None
    instance.bgm_info = []
    instance.perf_file = None
    instance.pods_info = None
    
    instance.logger = Log.getLogger(instance.__class__.__name__)
    
    logger.info(f"BRPCPerfBaseCase initialized: {len(nodes)} nodes, class={instance.__class__.__name__}")


class BRPCPerfBaseCase(UBSocketBaseCase):
    """Base class for BRPC performance tests."""
    
    def preTestCase(self):
        super().preTestCase()
        brpc_utils.create_dir(self.master, brpc_utils.AUTOTEST_DIR)
        if self.perf_file and not brpc_utils.doesPathExist(self.master, self.perf_file):
            self.master.createFile(self.perf_file)
            title_cmd = self.title_cmd if self.title_cmd else "test_scene,server_num,client_num_each_server,client_num,num_threads_server,thread_num_client,queue_depth,data_size,expected_qps,server_qps,client_qps(avg),client_qps_all,throughput(MB/s),client cpu(max),server cpu(max),avg,p99"
            self.master.run({'command': [f"echo '{title_cmd}' > {self.perf_file}"], "timeout": 10})

    def postTestCase(self):
        super().postTestCase()
        self.clear_brpc_proc()

    def set_bgm_info(self, bgm_pair, pods_info, port, data_size, expected_qps=100):
        """Set background flow info."""
        conA, conB = bgm_pair
        return {
            "s_cmd": k8s.get_exec_cmd(conA, brpc_utils.gene_cmd_server(port=port, rsp_size=data_size)),
            "c_cmd": k8s.get_exec_cmd(conB, brpc_utils.gene_cmd_client(ip=pods_info.get(conA).get("ip"), port=port, queue_depth=1, req_size=data_size, expected_qps=expected_qps, initial_tokens=100))
        }

    def set_observe_info(self, observe_pair, pods_info, num_threads, thread_num, queue_depth, data_size, expected_qps,
                         port=8900, server_ubsocket_enable="true", server_use_ub="true", client_ubsocket_enable="true", client_use_ub="true"):
        """Set observe flow info."""
        conA, conB = list(observe_pair.keys())
        return {
            "s_cmd": k8s.get_exec_cmd(conA, brpc_utils.gene_cmd_server(cpu=observe_pair.get(conA).get("cpu_bind"), port=port, num_threads=num_threads, rsp_size=data_size, ubsocket_enable=server_ubsocket_enable, use_ub=server_use_ub)),
            "c_cmd": k8s.get_exec_cmd(conB, brpc_utils.gene_cmd_client(ip=pods_info.get(conA).get("ip"), cpu=observe_pair.get(conB).get("cpu_bind"), port=port, thread_num=thread_num, queue_depth=queue_depth, req_size=data_size, expected_qps=expected_qps, initial_tokens=100, ubsocket_enable=client_ubsocket_enable, use_ub=client_use_ub))
        }

    def get_server_qps(self, ret):
        """Get server QPS from result."""
        std = ret.result()["stderr"].split("\r\n")
        qps_line = [line for line in std if "QPS" in line]
        self.logInfo(f"server test result: {qps_line}")
        return float(qps_line[0].split(':')[1]) if qps_line else 0

    def get_client_results(self, ret):
        """Get client results from result."""
        std = ret.result()["stdout"].split("\r\n") if ret.result()["stdout"] else ret.result()["stderr"].split("\r\n")
        res_line = [line for line in std if "Avg-Latency:" in line]
        res_list = res_line[0].split(',')
        self.logInfo(f"client test result: {res_list}")
        return Client_result.collect_info(res_list)

    def clear_brpc_proc(self, proc_name=None):
        """Clear BRPC processes."""
        if proc_name is None:
            proc_name = brpc_utils.brpc_tool_dir
        self.logStep(f"Clear processes: {proc_name}")
        brpc_utils.clear_proc(self.master, proc_name)
        for node in self.worker_list:
            brpc_utils.clear_proc(node, proc_name)

    def set_linux_info(self, server: Any, pairnum: int, num_in_pair: int = None) -> tuple:
        """Create pairnum groups of Linux SSH connection replicas for parallel performance testing.
        
        Original semantics: Create independent SSH connection replicas for each server-client pair,
        enabling parallel execution of multiple performance test flows.
        
        Legacy equivalent: create_new_linux(server) -> server.copy()
        
        Args:
            server: Server Linux object (from libs.host.Linux)
            pairnum: Number of SSH connection pairs to create
            num_in_pair: Number of replicas per pair for N-to-1 scenarios (default: None for 1-to-1)
        
        Returns:
            tuple: (observer_ssh, bgm_ssh) or (server_ssh, client_ssh)
                - Without num_in_pair: observer_ssh=[server_copy, server_copy], bgm_ssh=[[server_copy, server_copy], ...]
                - With num_in_pair: server_ssh=[server_copy, ...], client_ssh=[[server_copy], ...]
        """
        linux_pair = []
        for i in range(pairnum):
            if num_in_pair:
                # N-to-1 scenario: create num_in_pair copies per pair
                copies = [server.copy() for _ in range(num_in_pair)]
                linux_pair.append(copies)
            else:
                # 1-to-1 scenario: create server_copy and client_copy (both from server)
                linux_pair.append([server.copy(), server.copy()])
        
        return linux_pair[0], linux_pair[1:]

    def run_rdma_performance_repeat(self, observer_ssh: list, observe_info: dict, 
                                      autotest_logs: str, count: int) -> tuple:
        server_futures = []
        client_futures = []
        
        s_cmd = brpc_utils.cmd_restore(observe_info["s_cmd"], f"{autotest_logs}/server_observe.log")
        server_future = observer_ssh[0].run({'command': [s_cmd], "timeout": 60})
        server_futures.append(server_future)
        time.sleep(3)
        
        for i in range(count):
            c_cmd = brpc_utils.cmd_restore(observe_info["c_cmd"], f"{autotest_logs}/client_{i}.log")
            client_future = observer_ssh[1].run({'command': [c_cmd], "timeout": 120})
            client_futures.append(client_future)
        
        time.sleep(15)
        return server_futures, client_futures

    def run_rdma_performance_1snc(self, observer_ssh: list, bgm_ssh: list, 
                                   observe_info: dict, bgm_info: list, 
                                   autotest_logs: str) -> tuple:
        return self.run_rdma_performance_1s1c(observer_ssh, bgm_ssh, observe_info, bgm_info, autotest_logs)

    def run_rdma_performance_1s1c(self, observer_ssh, bgm_ssh, observe_info, bgm_info, record_dir=None):
        """Run 1 server-1 client performance test."""
        if not record_dir:
            record_dir = self.autotest_logs
        with ThreadPoolExecutor(max_workers=self.pairnum * self.client_num_per_server * 2) as executor:
            self.logStep("Start server programs")
            bgm_server_futures = []
            for i, info in enumerate(bgm_info):
                s_cmd = brpc_utils.cmd_restore(info["s_cmd"], f"{record_dir}/server_{i}.log")
                future = executor.submit(bgm_ssh[i][0].run, {'command': [s_cmd], "timeout": 60})
                bgm_server_futures.append(future)
            self.logInfo("Start observe server")
            s_cmd = brpc_utils.cmd_restore(observe_info["s_cmd"], f"{record_dir}/server_observe.log")
            server_future = executor.submit(observer_ssh[0].run, {'command': [s_cmd], "timeout": 60})
            time.sleep(3)

            self.logStep("Start client programs")
            bgm_client_futures = []
            for i, info in enumerate(bgm_info):
                c_cmd = brpc_utils.cmd_restore(info["c_cmd"], f"{record_dir}/client_{i}.log")
                future = executor.submit(bgm_ssh[i][1].run, {'command': [c_cmd], "timeout": 120})
                bgm_client_futures.append(future)
            self.logInfo("Start observe client")
            c_cmd = brpc_utils.cmd_restore(observe_info["c_cmd"], f"{record_dir}/client_observe.log")
            client_future = executor.submit(observer_ssh[1].run, {'command': [c_cmd], "timeout": 120})
            time.sleep(15)
            return server_future, client_future

    def record_perf_result(self, test_scene, queue_depth, data_size, server_futures, client_futures,
                           pairnum=None, client_num_per_server=None, expected_qps=None, num_threads=32, thread_num=1):
        """Record performance result to file."""
        if not pairnum:
            pairnum = self.pairnum
        if not client_num_per_server:
            client_num_per_server = self.client_num_per_server
        if not expected_qps:
            expected_qps = self.expected_qps

        s_qps_result = self.get_server_qps(server_futures) if not isinstance(server_futures, list) else sum([self.get_server_qps(f) for f in server_futures]) / len(server_futures)
        
        if isinstance(client_futures, list):
            single_client_result = [self.get_client_results(f) for f in client_futures]
            client_qps = sum(item.qps for item in single_client_result)
            client_cpu = [item.client_cpu for item in single_client_result]
            server_cpu = [item.server_cpu for item in single_client_result]
            avg_lat = sum(item.avg_lat for item in single_client_result)
            p99_lat = sum(item.p99_lat for item in single_client_result)
            throughput = sum(item.throughput for item in single_client_result)
            test_report = f"{test_scene},{pairnum},{client_num_per_server},{pairnum * client_num_per_server},{num_threads},{thread_num},{queue_depth},{data_size},{expected_qps},{s_qps_result},{client_qps/len(single_client_result)},{client_qps},{throughput},{max(client_cpu)},{max(server_cpu)},{avg_lat/len(single_client_result)},{p99_lat/len(single_client_result)}"
        else:
            client_result = self.get_client_results(client_futures)
            test_report = f"{test_scene},{pairnum},{client_num_per_server},{pairnum * client_num_per_server},{num_threads},{thread_num},{queue_depth},{data_size},{expected_qps},{s_qps_result},{client_result.qps},{client_result.qps},{client_result.throughput},{client_result.client_cpu},{client_result.server_cpu},{client_result.avg_lat},{client_result.p99_lat}"
        
        self.logStep(f"Test scene: {pairnum} server-client pairs, each server with {client_num_per_server} clients, server threads={num_threads}, queue_depth={queue_depth}, thread_num={thread_num}, data size: {data_size}, expected_qps: {expected_qps}")
        self.logInfo(f"Test result: {test_report}")
        self.master.run({'command': [f"echo '{test_report}' >> {self.perf_file}"], "timeout": 10})

    def get_client_pat(self, ret, pat):
        """Extract lines containing pattern from client/server result.
        
        Args:
            ret: client future or server future
            pat: pattern string to search
            
        Returns:
            list: Split result line containing the pattern
        """
        if ret.result()["stdout"]:
            std = ret.result()["stdout"].split("\r\n")
        else:
            std = ret.result()["stderr"]
            self.logWarn(f"stderr 中取数据")
            std = std.split("\r\n")
        res_line = [line for line in std if pat in line]
        if len(res_line) > 0:
            res_list = res_line[0].split(',')
            self.logInfo(f"测试结果: {res_list}")
        else:
            res_list = []
        return res_list

    def check_log(self, ret):
        """通用校验，检验是否存在error和failed.
        
        Args:
            ret: client future or server future
            
        Returns:
            list: List of error/failed results found (empty if none)
        """
        self.logStep("通用校验，检验是否存在error和failed")
        error_list = self.get_client_pat(ret, "error")
        fail_list = self.get_client_pat(ret, "failed")
        result_list = []
        if len(error_list) > 0:
            result_list.append(error_list)
        if len(fail_list) > 0:
            result_list.append(fail_list)
        if len(result_list) > 0:
            self.logWarn(f"存在error或failed")
            self.assertEqual(len(result_list), 0)
        self.logInfo("校验通过，不存在error和failed")
        return result_list

    def check_extra(self, ret, swi=0):
        """额外校验，根据swi参数执行不同校验逻辑.
        
        Args:
            ret: client future or server future
            swi: 校验模式选择
                0: 只校验时延等信息可正常显示，通信成功
                1: UB通信 → 校验出现 "UB connection has been successfully established new fd"
                2: TCP通信 → 校验不出现上述UB日志
                3: 原生brpc → 校验无UB相关日志 (UBSOCKET, URMA, UMQ)
                4: 降级TCP → 校验出现 "Auto fallback to TCP"
                5: UB建链失败 → 校验出现 "Fatal error occurred, fallback to TCP/IP"
        """
        AvgLatency_list = self.get_client_pat(ret, "Avg-Latency:")
        self.assertGreater(Client_result.collect_info(AvgLatency_list).p99_lat, 0)
        self.logInfo("时延等信息可正常显示，通信成功")
        if swi != 0:
            log_desc = {
                1: "UB通信 校验server/client打印UB connection has been successfully established new fd",
                2: "TCP通信 校验server/client不打印UB connection has been successfully established new fd",
                3: "原生brpc 校验client无ub相关打印",
                4: "降级tcp 校验server打印Auto fallback to TCP",
                5: "ub建链失败 校验client打印Fatal error occurred, fallback to TCP/IP"
            }
            self.logStep(log_desc[swi])
            patterns = {
                1: ["UB connection has been successfully established new fd"],
                2: ["UB connection has been successfully established new fd"],
                3: ["UBSOCKET", "URMA", "UMQ"],
                4: ["Auto fallback to TCP"],
                5: ["Fatal error occurred", "fallback to TCP/IP"]
            }
            matched_patterns = []
            for pattern in patterns[swi]:
                matched = self.get_client_pat(ret, pattern)
                if matched:
                    matched_patterns.append(pattern)
            if swi == 1:
                self.assertGreater(len(matched_patterns), 0, f"未找到预期日志: {patterns[1]}")
            elif swi == 2:
                self.assertEqual(len(matched_patterns), 0, f"不应出现日志: {patterns[2]}")
            elif swi == 3:
                self.assertEqual(len(matched_patterns), 0, f"不应出现UB相关日志: {patterns[3]}")
            elif swi == 4:
                self.assertGreater(len(matched_patterns), 0, f"未找到降级日志: {patterns[4]}")
            elif swi == 5:
                self.assertGreater(len(matched_patterns), 0, f"未找到建链失败日志: {patterns[5]}")

    def check_expected(self, ret, expect_log):
        """校验预期日志出现.
        
        Args:
            ret: client future or server future
            expect_log: 预期出现的日志内容
        """
        if ret.result()["stderr"]:
            self.assertTrue(verify(ret.result()["stderr"], expect_log))
        else:
            self.assertTrue(verify(ret.result()["stdout"], expect_log))

    def get_client_pat_assert(self, ret, pat):
        """提取并断言pattern存在.
        
        Args:
            ret: client future or server future
            pat: pattern string to search
            
        Returns:
            list: Split result line containing the pattern
        """
        if ret.result()["stdout"]:
            std = ret.result()["stdout"].split("\r\n")
        else:
            std = ret.result()["stderr"]
            self.logWarn(f"stderr 中取数据")
            std = std.split("\r\n")
        res_line = [line for line in std if pat in line]
        res_list = res_line[0].split(',')
        self.logInfo(f"client 测试结果: {res_list}")
        return res_list

    def set_linux_node(self, node: Any, client_node: int, server_node: int) -> tuple:
        """创建linux对象，server端server_node个，client端client_node个.
        
        Args:
            node: Linux对象
            server_node: 需要生成的server linux数量
            client_node: 需要生成的client linux数量
            
        Returns:
            tuple: (server对象组，client对象组)
        """
        linux_server = []
        for i in range(server_node):
            linux_server.append(node.copy())
        linux_client = []
        for i in range(client_node):
            linux_client.append(node.copy())
        return linux_server, linux_client

    def run_ub_performance_nsnc(self, server_ssh, server_info, client_ssh, client_info, record_dir=None, 
                                  wait_time=60, inject_fault=False, server_timeout=120, client_timeout=300):
        """Run N server - N client performance test.
        
        Args:
            server_ssh: Server SSH connection list
            server_info: Server info dict list
            client_ssh: Client SSH connection list
            client_info: Client info dict list
            record_dir: Log directory
            wait_time: Wait time after starting clients
            inject_fault: Whether to inject fault
            server_timeout: Server timeout
            client_timeout: Client timeout
            
        Returns:
            tuple: (server_futures, client_futures)
        """
        if not record_dir:
            record_dir = self.autotest_logs
        with ThreadPoolExecutor(max_workers=len(server_info) + len(client_info)) as executor:
            self.logStep("启动 server 端程序")
            server_futures = []
            for i, info in enumerate(server_info):
                s_cmd = brpc_utils.cmd_restore(info["s_cmd"], f"{record_dir}/server_{i}.log")
                s_future = executor.submit(server_ssh[i].run, {'command': [s_cmd], "timeout": server_timeout})
                server_futures.append(s_future)
            time.sleep(10)

            self.logStep(f"启动 {len(client_info)} 个 client 端程序")
            client_futures = []
            for i, info in enumerate(client_info):
                c_cmd = brpc_utils.cmd_restore(info["c_cmd"], f"{record_dir}/client_{i}.log")
                c_future = executor.submit(client_ssh[i].run, {'command': [c_cmd], "timeout": client_timeout})
                client_futures.append(c_future)
            if inject_fault:
                time.sleep(10)
                self.operator_dcat_ub_fault_host = client_ssh[1]
                self.operator_dcat_ub_fault(client_ssh[1], operator='inject')

            time.sleep(wait_time)

            return server_futures, client_futures

    def analyze_traffic_metrics(self, file_path: str) -> dict:
        """分析维测监控日志文件，返回所有指标的最大值.
        
        Args:
            file_path: Log file path
            
        Returns:
            dict: {pid_count: int, pid_stats: dict}
        """
        ret = self.master.run({'command': [f"cat {file_path}"], "timeout": 10})
        messages = ret.get("stdout")
        pid_stats = defaultdict(lambda: {
            'totalConnections': 0,
            'activeConnections': 0,
            'sendPackets': 0,
            'receivePackets': 0,
            'sendBytes': 0,
            'receiveBytes': 0,
            'errorPackets': 0,
            'lostPackets': 0
        })

        lines = messages.strip().split('\n')

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                pid = data.get('pid')

                if not pid:
                    continue

                traffic = data.get('trafficRecords', {})

                for metric in ['totalConnections', 'activeConnections', 'sendPackets',
                               'receivePackets', 'sendBytes', 'receiveBytes',
                               'errorPackets', 'lostPackets']:
                    current_value = traffic.get(metric, 0)
                    if current_value > pid_stats[pid][metric]:
                        pid_stats[pid][metric] = current_value

            except json.JSONDecodeError as e:
                self.logStep(f"第 {line_num} 行解析失败: {e}")
                continue

        return {
            'pid_count': len(pid_stats),
            'pid_stats': dict(pid_stats)
        }

    def get_ubep_dev_eid_info(self, container_name=None) -> dict:
        """获取URMA endpoint EID信息.
        
        Args:
            container_name: 容器名称（可选）
            
        Returns:
            dict: EID信息
        """
        if container_name:
            res = self.master.run({'command': [f"kubectl exec -it -n default {container_name} -- bash -c 'urma_admin show -a'"]})
        else:
            res = self.master.run({'command': ["urma_admin show -a"]})
        return brpc_utils.parse_urma_admin_show_output(res["stdout"])

    def run_rdma_performance_1snc_cli(self, server_ssh, server_info, client_ssh, client_info, record_dir=None):
        """Run 1 server - N client performance test with CLI stat collection.
        
        Args:
            server_ssh: Server SSH connection list
            server_info: Server info dict
            client_ssh: Client SSH connection list
            client_info: Client info dict list
            record_dir: Log directory
            
        Returns:
            tuple: (server_future, client_futures, cli_stdout)
        """
        if not record_dir:
            record_dir = self.autotest_logs
        with ThreadPoolExecutor(max_workers=len(server_info) + len(client_info) + 1) as executor:
            self.logStep("启动 server 端程序")
            s_cmd = brpc_utils.cmd_restore(server_info["s_cmd"], f"{record_dir}/server.log")
            server_future = executor.submit(server_ssh[0].run, {'command': [s_cmd], "timeout": 120})
            time.sleep(3)

            self.logStep(f"启动 {len(client_info)} 个 client 端程序")
            client_futures = []
            for i, info in enumerate(client_info):
                c_cmd = brpc_utils.cmd_restore(info["c_cmd"], f"{record_dir}/client_{i}.log")
                future = executor.submit(client_ssh[i][0].run, {'command': [c_cmd], "timeout": 120})
                client_futures.append(future)
            cli_cmd = brpc_utils.get_stat(self.master)
            cli_ssh, _ = self.set_linux_info(self.master, 1, num_in_pair=1)
            result_cli = executor.submit(cli_ssh[0].run, {'command': [cli_cmd], "timeout": 120})
            time.sleep(15)
            return server_future, client_futures, result_cli.result()["stdout"]

    def run_rdma_performance_1snc_cli_help(self, server_ssh, server_info, client_ssh, client_info, record_dir=None):
        """Run 1 server - N client performance test with CLI help command.
        
        Args:
            server_ssh: Server SSH connection list
            server_info: Server info dict
            client_ssh: Client SSH connection list
            client_info: Client info dict list
            record_dir: Log directory
            
        Returns:
            tuple: (server_future, client_futures, cli_stdout)
        """
        if not record_dir:
            record_dir = self.autotest_logs
        with ThreadPoolExecutor(max_workers=len(server_info) + len(client_info) + 1) as executor:
            self.logStep("启动 server 端程序")
            s_cmd = brpc_utils.cmd_restore(server_info["s_cmd"], f"{record_dir}/server.log")
            server_future = executor.submit(server_ssh[0].run, {'command': [s_cmd], "timeout": 120})
            time.sleep(3)

            self.logStep(f"启动 {len(client_info)} 个 client 端程序")
            client_futures = []
            for i, info in enumerate(client_info):
                c_cmd = brpc_utils.cmd_restore(info["c_cmd"], f"{record_dir}/client_{i}.log")
                future = executor.submit(client_ssh[i][0].run, {'command': [c_cmd], "timeout": 120})
                client_futures.append(future)
            cli_cmd = brpc_utils.get_ubstat_help(self.master)
            cli_ssh, _ = self.set_linux_info(self.master, 1, num_in_pair=1)
            result_cli = executor.submit(cli_ssh[0].run, {'command': [cli_cmd], "timeout": 120})
            time.sleep(15)
            return server_future, client_futures, result_cli.result()["stdout"]

    def run_rdma_performance_1snc_topo(self, server_ssh, server_info, client_ssh, client_info,
                                       record_dir=None, s_eid=None, c_eid=None, container_name="auto-worker1-brpc1"):
        """Run 1 server - N client performance test with topology collection.
        
        Args:
            server_ssh: Server SSH connection list
            server_info: Server info dict
            client_ssh: Client SSH connection list
            client_info: Client info dict list
            record_dir: Log directory
            s_eid: Server EID
            c_eid: Client EID
            container_name: Container name for PID lookup
            
        Returns:
            tuple: (server_future, client_futures, topo_stdout)
        """
        if not record_dir:
            record_dir = self.autotest_logs
        with ThreadPoolExecutor(max_workers=len(server_info) + len(client_info) + 1) as executor:
            self.logStep("启动 server 端程序")
            s_cmd = brpc_utils.cmd_restore(server_info["s_cmd"], f"{record_dir}/server.log")
            server_future = executor.submit(server_ssh[0].run, {'command': [s_cmd], "timeout": 120})
            time.sleep(3)

            self.logStep(f"启动 {len(client_info)} 个 client 端程序")
            client_futures = []
            for i, info in enumerate(client_info):
                c_cmd = brpc_utils.cmd_restore(info["c_cmd"], f"{record_dir}/client_{i}.log")
                future = executor.submit(client_ssh[i][0].run, {'command': [c_cmd], "timeout": 120})
                client_futures.append(future)
            topo_cmd = brpc_utils.get_topo(self.master, container_name,
                                           brpc_utils.get_serverpid(self.master, container_name), s_eid=s_eid, c_eid=c_eid)
            topo_ssh, _ = self.set_linux_info(self.master, 1, num_in_pair=1)
            result_topo = executor.submit(topo_ssh[0].run, {'command': [topo_cmd], "timeout": 120})
            time.sleep(15)
            return server_future, client_futures, result_topo.result()["stdout"]