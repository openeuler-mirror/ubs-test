"""BRPC utilities migrated from legency/testcase/ubscomm/ubsocket/lib/common/brpc_utils.py"""

import time
import logging

from libs.ubsocket import k8s_api as k8s

logger = logging.getLogger(__name__)

BRPC_DIR = "/home/brpc"
brpc_tool_dir = "/home/share/autotest"
cli_tool_dir = brpc_tool_dir
rdma_performance_server = f"{brpc_tool_dir}/ub_performance_server"
rdma_performance_client = f"{brpc_tool_dir}/ub_performance_client"
rdma_performance_server_new = f"{brpc_tool_dir}/ub_performance_server"
rdma_performance_client_new = f"{brpc_tool_dir}/ub_performance_client"

AUTOTEST_DIR = "/home/autotest"
autotest_log_dir = f"{AUTOTEST_DIR}/logs"
K8S_DIR = "/home/K8s"
yaml_list = f"{K8S_DIR}/yaml_list"


def parse_output(output):
    """Parse kubectl output to list of dicts."""
    lines = output.strip().split('\r\n')
    headings = [item.strip() for item in lines[0].split("  ") if item != ""]
    pod_list = []
    for line in lines[1:]:
        if not line.strip():
            continue
        columns = [item.strip() for item in line.split("  ") if item != ""]
        line_dict = {}
        for i in range(len(columns)):
            value = columns[i].strip()
            line_dict[headings[i]] = value
        pod_list.append(line_dict)
    return pod_list


def doesPathExist(node, path):
    """Check if path exists on node."""
    ret = node.run({'command': [f'ls -l {path}'], "timeout": 10})
    return bool(ret.get("stdout"))


def get_cpubind_groups(core_num, cpu_groups):
    """Generate CPU binding groups."""
    cpubind_groups = []
    group_data = []
    for group in cpu_groups:
        left, right = group.split("-")
        left_int = int(left)
        right_int = int(right)
        nums = (right_int - left_int + 1) // core_num
        core_groups = []
        for n in range(nums):
            i = left_int + n * core_num
            core_groups.append((i, i + core_num - 1))
        group_data.append(core_groups)

    max_rounds = min(len(groups) for groups in group_data)
    for round_num in range(max_rounds):
        for group in group_data:
            start, end = group[round_num]
            cpubind_groups.append(f"{start}-{end}")
    return cpubind_groups


def bind_cpu_pod(node, cpu, pod_id):
    """Bind CPU to pod."""
    node.run({'command': [f"nerdctl -n k8s.io update --cpuset-cpus='{cpu}' {pod_id}"], "timeout": 10})


def get_container_cpu(node, container_name):
    """Get container CPU info."""
    ret = node.run({'command': [k8s.get_exec_cmd(container_name, "cat /proc/self/status | grep Cpus_allowed_list")], "timeout": 10})
    return ret.get("stdout").split("\r\n")[0].split("\t")[1]


def get_container_device(node, container_name):
    """Get container URMA device info."""
    ret = node.run({'command': [k8s.get_exec_cmd(container_name, "urma_admin show")], "timeout": 10})
    if ret.get("rc") == 1:
        node.run({'command': [f"cd {yaml_list}"], "timeout": 10})
        file_name = f"{container_name}.yaml"
        k8s.delete_container(node, container_name)
        k8s.create_container(node, file_name)
        k8s.install_numactl(node, container_name)
        ret = node.run({'command': [k8s.get_exec_cmd(container_name, "urma_admin show")], "timeout": 10})
    res = parse_output(ret.get("stdout").split("\r\nroot@#>")[0])
    urma_dev = {}
    for info_dict in res:
        if '--' in info_dict.get("eid"):
            continue
        else:
            eid_num, eid = info_dict.get("eid").split()
            ubep_dev = info_dict.get("ubep_dev")
            if ubep_dev not in urma_dev:
                urma_dev[ubep_dev] = {}
            urma_dev[ubep_dev][eid_num] = eid
    return urma_dev


def gene_amd_cmd_server(rdma_perf_path, mem=None, cpu=None, numa=None, port=8002, num_threads=16, max_concurrency=16,
                        server_bthread_concurrency=16, rsp_size=None, use_rdma="false"):
    """Generate AMD server command."""
    mem_cmd = "" if not mem else f"ulimit -m {mem}; "
    cpu_cmd = "" if not cpu else f"numactl -C {cpu} --membind={numa} "
    rsp_cmd = "" if not rsp_size else f"--rsp_size={rsp_size} "
    server_cmd = mem_cmd + cpu_cmd + f'{rdma_perf_path} --port={port} --num_threads={num_threads} --max_concurrency={max_concurrency} --server_bthread_concurrency={server_bthread_concurrency} --use_rdma={use_rdma}' + rsp_cmd
    return server_cmd


def gene_amd_cmd_client(rdma_perf_path, ip, mem=None, cpu=None, numa=None, port=8002, attachment_size=None,
                        thread_num=1, rpc_timeout_ms=25000, connect_timeout_ms=30000,
                        use_rdma="false", queue_depth=1, req_size=None, expected_qps=None):
    """Generate AMD client command."""
    mem_cmd = "" if not mem else f"ulimit -m {mem}; "
    cpu_cmd = "" if not cpu else f"numactl -C {cpu} --membind={numa} "
    expected_qps_str = "" if not expected_qps else f'--expected_qps={expected_qps} '
    req_cmd = "" if not req_size else f"--req_size={req_size} "
    attachment_cmd = "" if not attachment_size else f"--attachment_size={attachment_size} --echo_attachment=true "
    client_cmd = mem_cmd + cpu_cmd + f'{rdma_perf_path} --servers={ip}:{port} --thread_num={thread_num} --rpc_timeout_ms={rpc_timeout_ms} --connect_timeout_ms={connect_timeout_ms} --use_rdma={use_rdma} --queue_depth={queue_depth} ' + attachment_cmd + req_cmd + expected_qps_str
    return client_cmd


def gene_cmd_server(mem=None, cpu=None, port=8002, num_threads=16, max_concurrency=0, server_bthread_concurrency=32,
                    rsp_size=1024, use_rdma="false", pool_initial_size=1024, ubsocket_enable="true", use_ub="true"):
    """Generate server command for rdma_performance."""
    mem_cmd = "" if not mem else f"ulimit -m {mem}; "
    cpu_cmd = "" if cpu is None else f"numactl --cpubind={cpu} "
    rsp_cmd = "" if not rsp_size else f"--rsp_size={rsp_size} "
    ubsocket_enable_cmd = "" if not ubsocket_enable else f"--ubsocket_enable={ubsocket_enable} "
    use_ub_cmd = "" if not use_ub else f"--use_ub={use_ub} "
    server_cmd = mem_cmd + cpu_cmd + f'{rdma_performance_server} --port={port} --num_threads={num_threads} --max_concurrency={max_concurrency} --server_bthread_concurrency={server_bthread_concurrency} --use_rdma={use_rdma} --ubsocket_pool_initial_size={pool_initial_size} --ubsocket_log_use_printf=true --ubsocket_enable_share_jfr=true ' + rsp_cmd + ubsocket_enable_cmd + use_ub_cmd
    return server_cmd


def gene_cmd_client(ip, mem=None, cpu=None, port=8002, dummy_port=8100, thread_num=1, rpc_timeout_ms=25000,
                    connect_timeout_ms=30000, use_rdma="false", queue_depth=1, attachment_size=None, req_size=1024,
                    expected_qps=None, initial_tokens=None, pool_initial_size=1024, ubsocket_enable="true",
                    use_ub="true"):
    """Generate client command for rdma_performance."""
    mem_cmd = "" if not mem else f"ulimit -m {mem}; "
    cpu_cmd = "" if not cpu else f"numactl --cpubind={cpu} "
    expected_qps_str = "" if not expected_qps else f"--expected_qps={expected_qps} "
    req_cmd = "" if not req_size else f"--req_size={req_size} "
    attachment_cmd = "" if not attachment_size else f"--attachment_size={attachment_size} --echo_attachment=true "
    initial_tokens_cmd = "" if not initial_tokens else f"--initial_tokens={initial_tokens} "
    ubsocket_enable_cmd = "" if not ubsocket_enable else f"--ubsocket_enable={ubsocket_enable} "
    use_ub_cmd = "" if not use_ub else f"--use_ub={use_ub} "
    client_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/ub_performance_client --servers={ip}:{port} --dummy_port={dummy_port} --rpc_timeout_ms={rpc_timeout_ms} --connect_timeout_ms={connect_timeout_ms} --use_rdma={use_rdma} --thread_num={thread_num} --queue_depth={queue_depth} --ubsocket_pool_initial_size=4096 --ubsocket_share_jfr_rx_queue_depth=102400 --ubsocket_enable=true --use_ub=true --ubsocket_log_use_printf=true --ubsocket_enable_share_jfr=true --max_body_size=2147483648 --ubsocket_tx_depth=1024 --ubsocket_rx_depth=1024 --socket_max_unwritten_bytes=10737418240 ' + attachment_cmd + req_cmd + expected_qps_str + initial_tokens_cmd
    return client_cmd


def gene_cmd_server_tcp(mem=None, cpu=None, port=8002, num_threads=32, max_concurrency=32,
                         server_bthread_concurrency=32, rsp_size=1024, use_rdma="false", pool_initial_size=1024, ubsocket_ub_force="false"):
    """Generate TCP server command."""
    mem_cmd = "" if not mem else f"ulimit -m {mem}; "
    cpu_cmd = "" if not cpu else f"numactl --cpubind={cpu} "
    rsp_cmd = "" if not rsp_size else f"--rsp_size={rsp_size} "
    ub_force_cmd = "" if not ubsocket_ub_force else f"--ubsocket_ub_force={ubsocket_ub_force} "
    server_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/ub_performance_server --port={port} --num_threads={num_threads} --max_concurrency={max_concurrency} --server_bthread_concurrency={server_bthread_concurrency} --use_rdma={use_rdma} --ubsocket_enable=false --use_ub=false --max_body_size=2147483648 --server_ignore_oc=true --socket_max_unwritten_bytes=10737418240 ' + ub_force_cmd + rsp_cmd
    return server_cmd


def gene_cmd_client_tcp(ip, mem=None, cpu=None, port=8002, dummy_port=8100, thread_num=1, rpc_timeout_ms=25000,
                         connect_timeout_ms=30000, use_rdma="false", queue_depth=1, attachment_size=None, req_size=1024,
                         expected_qps=None, initial_tokens=None, pool_initial_size=1024, ubsocket_ub_force="false"):
    """Generate TCP client command."""
    mem_cmd = "" if not mem else f"ulimit -m {mem}; "
    cpu_cmd = "" if not cpu else f"numactl --cpubind={cpu} "
    expected_qps_str = "" if not expected_qps else f"--expected_qps={expected_qps} "
    req_cmd = "" if not req_size else f"--req_size={req_size} "
    attachment_cmd = "" if not attachment_size else f"--attachment_size={attachment_size} --echo_attachment=true "
    initial_tokens_cmd = "" if not initial_tokens else f"--initial_tokens={initial_tokens} "
    ub_force_cmd = "" if not ubsocket_ub_force else f"--ubsocket_ub_force={ubsocket_ub_force} "
    client_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/ub_performance_client --servers={ip}:{port} --rpc_timeout_ms={rpc_timeout_ms} --connect_timeout_ms={connect_timeout_ms} --use_rdma={use_rdma} --thread_num={thread_num} --queue_depth={queue_depth} --ubsocket_enable=false --use_ub=false --max_body_size=2147483648 --socket_max_unwritten_bytes=10737418240 ' + ub_force_cmd + attachment_cmd + req_cmd + expected_qps_str + initial_tokens_cmd
    return client_cmd


def gene_echo_cmd_server(mem=None, cpu=None, port=8002, pool_initial_size=1024, ubsocket_degrade="true", use_ub="true"):
    """Generate echo C++ server command."""
    mem_cmd = "" if mem is None else f"ulimit -m {mem}; "
    cpu_cmd = "" if cpu is None else f"numactl --cpubind={cpu} "
    server_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/echo_c++_server --port={port} --ubsocket_enable=true --ubsocket_degrade={ubsocket_degrade} --ubsocket_pool_initial_size={pool_initial_size} --use_ub={use_ub} '
    return server_cmd


def gene_echo_cmd_client(ip, mem=None, cpu=None, port=8002, dummy_port=8100, rpc_timeout_ms=25000, use_ub="true",
                         connect_timeout_ms=30000, pool_initial_size=1024, max_retry=1, ubsocket_enable="true",
                         health_check_timeout_ms=30000):
    """Generate echo C++ client command."""
    mem_cmd = "" if mem is None else f"ulimit -m {mem}; "
    cpu_cmd = "" if cpu is None else f"numactl --cpubind={cpu} "
    client_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/echo_c++_client --server={ip}:{port} --timeout_ms={rpc_timeout_ms} --connect_timeout_ms={connect_timeout_ms} --ubsocket_enable={ubsocket_enable} --use_ub={use_ub} --ubsocket_pool_initial_size={pool_initial_size} --max_retry={max_retry} --health_check_timeout_ms={health_check_timeout_ms}'
    return client_cmd


def gene_1ton_cmd_server(mem=None, cpu=None, port=8002, rsp_size=1024, ubsocket_enable="true", use_ub="true",
                         num_threads=16, max_concurrency=0, server_bthread_concurrency=12, use_rdma="false",
                         pool_initial_size=1024, share_jfr_rx_queue_depth=102400, log_use_printf="true",
                         enable_share_jfr="true", tx_depth=1024, rx_depth=1024):
    """Generate 1-to-n server command."""
    mem_cmd = "" if mem is None else f"ulimit -m {mem}; "
    cpu_cmd = "" if cpu is None else f"numactl --cpubind={cpu} "
    rsp_cmd = "" if not rsp_size else f"--rsp_size={rsp_size} "
    server_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/ub_performance_server --port {port} --num_threads={num_threads} --max_concurrency={max_concurrency} --server_bthread_concurrency={server_bthread_concurrency} --use_rdma={use_rdma} --ubsocket_pool_initial_size={pool_initial_size} --ubsocket_share_jfr_rx_queue_depth={share_jfr_rx_queue_depth} --ubsocket_enable={ubsocket_enable} --use_ub={use_ub} --ubsocket_log_use_printf={log_use_printf} --ubsocket_enable_share_jfr={enable_share_jfr} --server_ignore_oc=true --max_body_size=21474836480 --ubsocket_tx_depth={tx_depth} --ubsocket_rx_depth={rx_depth} --socket_max_unwritten_bytes=107374182400 ' + rsp_cmd
    return server_cmd


def gene_1ton_cmd_client(ip, mem=None, cpu=None, dummy_port=8100, ubsocket_enable="true", use_ub="true", thread_num=1,
                         rpc_timeout_ms=400000, connect_timeout_ms=400000, use_rdma="false", queue_depth=1,
                         pool_initial_size=2048, share_jfr_rx_queue_depth=102400, log_use_printf="true",
                         enable_share_jfr="true", tx_depth=1024, rx_depth=1024, test_seconds=None,
                         attachment_size=None, req_size=1024, expected_qps=None, initial_tokens=None):
    """Generate 1-to-n client command."""
    mem_cmd = "" if mem is None else f"ulimit -m {mem}; "
    cpu_cmd = "" if cpu is None else f"numactl --cpubind={cpu} "
    expected_qps_str = "" if expected_qps is None else f"--expected_qps={expected_qps} "
    test_seconds_cmd = "" if test_seconds is None else f"--test_seconds={test_seconds} "
    size_cmd = f"--attachment_size={attachment_size} --echo_attachment=true " if attachment_size is not None else f"--req_size={req_size} "
    initial_tokens_cmd = "" if initial_tokens is None else f"--initial_tokens={initial_tokens} "
    client_cmd = mem_cmd + cpu_cmd + f'{brpc_tool_dir}/ub_performance_client --servers={ip} --rpc_timeout_ms={rpc_timeout_ms} --connect_timeout_ms={connect_timeout_ms} --use_rdma={use_rdma} --thread_num={thread_num} --queue_depth={queue_depth} --ubsocket_pool_initial_size={pool_initial_size} --ubsocket_share_jfr_rx_queue_depth={share_jfr_rx_queue_depth} --ubsocket_enable={ubsocket_enable} --use_ub={use_ub} --ubsocket_log_use_printf={log_use_printf} --ubsocket_enable_share_jfr={enable_share_jfr} --max_body_size=21474836480 --ubsocket_tx_depth={tx_depth} --ubsocket_rx_depth={rx_depth} --socket_max_unwritten_bytes=107374182400 ' + size_cmd + expected_qps_str + initial_tokens_cmd + test_seconds_cmd
    return client_cmd


def clear_proc(node, proc):
    """Clear process on node."""
    node.run({'command': ["ps -ef | grep '" + proc + "' | grep -v grep | awk '{print $2}' | xargs kill -9"], "timeout": 5})


def get_timestamp():
    """Get current timestamp string."""
    current_time = time.time()
    local_time = time.localtime(current_time)
    return time.strftime("%Y%m%d%H%M%S", local_time)


def cmd_restore(cmd, restore_file):
    """Add tee to command for logging."""
    return cmd + f" | tee {restore_file}"


def create_dir(node, dir):
    """Create directory on node if not exists."""
    if not doesPathExist(node, dir):
        node.run({'command': [f'mkdir -p {dir}'], "timeout": 10})


def get_container_cmd(node, container_name, cmd):
    """Execute command in container and return first line of stdout."""
    ret = node.run(
        {'command': [
            f"kubectl exec -it -n default {container_name} -- bash -c '{cmd}'"],
            "timeout": 10})
    return ret.get("stdout").split("\r\n")[0]


def get_cli(node, container_name):
    """Check if ubstat CLI tool exists in container."""
    ret = node.run(
        {'command': [
            f"kubectl exec -it -n default {container_name} -- bash -c 'ls {cli_tool_dir} |grep 'ubstat'|wc -l'"],
            "timeout": 10})
    return ret.get("stdout").split("\r\n")[0]


def get_serverpid(node, container_name):
    """Get server process PID in container."""
    ret = node.run(
        {'command': [
            f"kubectl exec -it -n default {container_name} -- bash -c 'ps -ef | grep {rdma_performance_server_new} |awk 'NR==1''"]})
    return ret.get("stdout").split()[1]


def get_stat(node, container_name="auto-worker1-brpc1"):
    """Get ubstat stat command with PID."""
    pid = node.run(
        {'command': [
            f"kubectl exec -it -n default {container_name} -- bash -c 'ps -ef | grep {rdma_performance_server_new} |awk 'NR==1''"]}).get(
        "stdout").split()[1]
    return f"kubectl exec -it -n default {container_name} -- bash -c 'cd {cli_tool_dir} && ./ubstat stat -p {pid}'"


def get_stat_pid(node, container_name="auto-worker1-brpc1", pid=0):
    """Get ubstat stat command with specific PID."""
    return f"kubectl exec -it -n default {container_name} -- bash -c 'cd {cli_tool_dir} && ./ubstat stat -p {pid}'"


def get_ubstat_help(node, container_name="auto-worker1-brpc1"):
    """Get ubstat help command."""
    return f"kubectl exec -it -n default {container_name} -- bash -c 'cd {cli_tool_dir} && ./ubstat -h'"


def get_topo(node, container_name, pid, c_eid=None, s_eid=None):
    """Get ubstat topo command with EID parameters."""
    ret_server = node.run(
        {'command': [
            f"kubectl exec -it -n default {container_name} -- bash -c 'urma_admin show | grep 'UB''"],
            "timeout": 10})
    rett_server = ret_server.get("stdout").split("\r\n")[0]
    server_eid = rett_server.split()[-2]
    ret_client = node.run(
        {'command': [
            f"kubectl exec -it -n default auto-worker1-brpc2 -- bash -c 'urma_admin show | grep 'UB''"],
            "timeout": 10})
    rett_client = ret_client.get("stdout").split("\r\n")[0]
    client_eid = rett_client.split()[-2]
    if c_eid:
        client_eid = c_eid
    if s_eid:
        server_eid = s_eid
    return f"kubectl exec -it -n default {container_name} -- bash -c 'cd {cli_tool_dir} && ./ubstat topo -p {pid} -s  {client_eid} -d {server_eid}'"


def cli_check(ret_out):
    """Check CLI output and extract socket info from last data line."""
    lines = ret_out.strip().split('\n')
    data_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[0].isdigit():
            data_count += 1
    if data_count < 1:
        return ""
    for line in reversed(lines):
        stripped = line.strip()
        if stripped and stripped[0].isdigit():
            parts = line.split('|')
            if len(parts) >= 5:
                return parts[3].strip(), parts[4].strip()
            break
    return "", ""


def cli_get_totalsockets(ret_out):
    """Extract total sockets count from CLI output."""
    lines = ret_out.strip().split('\n')
    data_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[0].isdigit():
            data_count += 1
    if data_count < 1:
        return ""
    for line in reversed(lines):
        stripped = line.strip()
        if "Total Sockets" in line:
            parts = line.split(':')
            return parts[-1].strip()
            break
    return "", ""


def parse_urma_admin_show_output(output_str):
    """Parse urma_admin show output to list of dicts."""
    if not output_str:
        return None
    result = []
    lines = [line.strip() for line in output_str.splitlines() if line.strip()]
    data_lines = [line for line in lines if not line.startswith('---')]
    if not data_lines:
        return result
    headers = [header.strip() for header in data_lines[0].split()]
    for line in data_lines[1:]:
        if line.startswith('root@#'):
            continue
        fields = [field.strip() for field in line.split()]
        row_dict = dict(zip(headers, fields))
        result.append(row_dict)
    return result


def gene_cmd_server_cli(mem=None, cpu=None, port=8002, num_threads=1, max_concurrency=16,
                         server_bthread_concurrency=1, rsp_size=1024, use_rdma="false",
                         pool_initial_size=2048, ubsocket_enable="true", use_ub="true",
                         ubsocket_trace_enable="true", ubsocket_stats_cli="false", extra_params=None):
    """Generate server CLI command for ubstat testing."""
    server_cmd = ""
    if mem:
        server_cmd = server_cmd + f"ulimit -m {mem}; "
    if cpu is not None:
        server_cmd = server_cmd + f"numactl --cpubind={cpu} "
    server_cmd = server_cmd + f'{rdma_performance_server_new} '
    if port:
        server_cmd = server_cmd + f'--port={port} '
    if num_threads:
        server_cmd = server_cmd + f'--num_threads={num_threads} '
    if max_concurrency:
        server_cmd = server_cmd + f'--max_concurrency={max_concurrency} '
    if server_bthread_concurrency:
        server_cmd = server_cmd + f'--server_bthread_concurrency={server_bthread_concurrency} '
    if use_rdma:
        server_cmd = server_cmd + f'--use_rdma={use_rdma} '
    if pool_initial_size:
        server_cmd = server_cmd + f'--ubsocket_pool_initial_size={pool_initial_size} '
    server_cmd = server_cmd + f'--ubsocket_pool_max_size=4096 '
    if ubsocket_enable:
        server_cmd = server_cmd + f"--ubsocket_enable={ubsocket_enable} "
    if use_ub:
        server_cmd = server_cmd + f"--use_ub={use_ub} "
    server_cmd = server_cmd + f'--ubsocket_log_use_printf=true '
    server_cmd = server_cmd + f'--ubsocket_enable_share_jfr=true '
    if rsp_size:
        server_cmd = server_cmd + f'--rsp_size={rsp_size} '
    if ubsocket_trace_enable:
        server_cmd = server_cmd + f"--ubsocket_trace_enable={ubsocket_trace_enable} "
    if ubsocket_stats_cli:
        server_cmd = server_cmd + f"--ubsocket_stats_cli={ubsocket_stats_cli} "
    if extra_params:
        for key, value in extra_params.items():
            server_cmd = server_cmd + f"--{key}={value} "
    return server_cmd


def gene_cmd_client_cli(ip, mem=None, cpu=None, port=8002, thread_num=4, rpc_timeout_ms=25000,
                         connect_timeout_ms=30000, use_rdma="false", queue_depth=1, initial_tokens=100,
                         pool_initial_size=2048, req_size=1024, ubsocket_enable="true", use_ub="true",
                         ubsocket_trace_enable="true", ubsocket_stats_cli="false", extra_params=None):
    """Generate client CLI command for ubstat testing."""
    client_cmd = ""
    if mem:
        client_cmd = client_cmd + f"ulimit -m {mem}; "
    if cpu is not None:
        client_cmd = client_cmd + f"numactl --cpubind={cpu} "
    client_cmd = client_cmd + f'{brpc_tool_dir}/ub_performance_client'
    if ip and port:
        client_cmd = client_cmd + f'--servers={ip}:{port} '
    if rpc_timeout_ms:
        client_cmd = client_cmd + f'--rpc_timeout_ms={rpc_timeout_ms} '
    if connect_timeout_ms:
        client_cmd = client_cmd + f'--connect_timeout_ms={connect_timeout_ms} '
    if use_rdma:
        client_cmd = client_cmd + f'--use_rdma={use_rdma} '
    if thread_num:
        client_cmd = client_cmd + f'--thread_num={thread_num} '
    if queue_depth:
        client_cmd = client_cmd + f'--queue_depth={queue_depth} '
    if pool_initial_size:
        client_cmd = client_cmd + f'--ubsocket_pool_initial_size={pool_initial_size} '
    client_cmd = client_cmd + f'--ubsocket_pool_max_size=4096 '
    client_cmd = client_cmd + f'--ubsocket_share_jfr_rx_queue_depth=102400 '
    client_cmd = client_cmd + f'--ubsocket_log_use_printf=true '
    client_cmd = client_cmd + f'--ubsocket_enable_share_jfr=true '
    client_cmd = client_cmd + f'--max_body_size=2147483648 '
    client_cmd = client_cmd + f'--ubsocket_tx_depth=1024 '
    client_cmd = client_cmd + f'--ubsocket_rx_depth=1024 '
    client_cmd = client_cmd + f'--socket_max_unwritten_bytes=10737418240 '
    if req_size:
        client_cmd = client_cmd + f'--req_size={req_size} '
    if initial_tokens:
        client_cmd = client_cmd + f"--initial_tokens={initial_tokens} "
    if ubsocket_enable:
        client_cmd = client_cmd + f"--ubsocket_enable={ubsocket_enable} "
    if use_ub:
        client_cmd = client_cmd + f"--use_ub={use_ub} "
    if ubsocket_trace_enable:
        client_cmd = client_cmd + f"--ubsocket_trace_enable={ubsocket_trace_enable} "
    if ubsocket_stats_cli:
        client_cmd = client_cmd + f"--ubsocket_stats_cli={ubsocket_stats_cli} "
    if extra_params:
        for key, value in extra_params.items():
            client_cmd = client_cmd + f"--{key}={value} "
    return client_cmd