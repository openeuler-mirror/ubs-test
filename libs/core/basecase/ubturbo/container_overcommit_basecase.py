"""ContainerOvercommitBaseCase - Base class for container overcommit test cases.

Migrated from legacy lib/basecase/ContainerOvercommitBaseCase.py
Inherits from ATBaseCase (already migrated).

CRITICAL: This class NO LONGER has __init__ method.
pytest cannot collect test classes with __init__ (even with default args).

Initialization is handled by fixture injection (@pytest.fixture(autouse=True)).
"""

import json
import math
import re
import time
import logging
from typing import List, Tuple, Dict, Any

import pytest

from libs.core.basecase.ubturbo.at_basecase import ATBaseCase
from libs.ubturbo.common import basic, env, connect, file_transport
from libs.ubturbo.api import numa, rack_manager, virtualization, system

try:
    from libs.ubturbo.api import crictl
except ImportError:
    crictl = None

try:
    from libs.ubturbo.model.borrow import Ledger
    from libs.ubturbo.model.borrow import LedgerEntry
except ImportError:
    Ledger = None
    LedgerEntry = None

try:
    from libs.ubturbo.model.container_mgr import NodeContainerManager
except ImportError:
    NodeContainerManager = None

logger = logging.getLogger(__name__)

UB_PORT_LIST = [5100, 5101, 5102, 5103]
QMP_PORT = {'1': 51000, '2': 51001, '3': 51002, '4': 51003}

DEMON_CAT_EXEC = "/home/ctr_tools/6.6.0-1.2.20.x1.eulerx_a2.aarch64/dcat/dcat"
LOCAL_SDK_SCRIPT_PATH = f'/home/ctr_tools/sdk/ubs_virt_agent_waterline_mem_{{0}}.py'
GET_BORROW_CNA_INFO = '/home/autotest/os/test_stub/Tools/getCna.sh'
LOCAL_TOOL_PATH = "/home/ctr_tools/"
LOCAL_SDK_PATH = LOCAL_TOOL_PATH + "sdk"


def _borrow_params2json(src_node, src_socket=None, src_numa=None, borrow_sizes_gib=None):
    """填充参数borrowParam,borrowSizes,waterMark并格式化为字符串"""
    borrow_param_dict = {}
    borrow_param = {}
    
    if src_node:
        borrow_param["srcNid"] = src_node
    
    if src_socket is None or src_numa is None:
        borrow_param["srcLocations"] = []
    else:
        loc = {"socketId": src_socket, "numaId": src_numa}
        borrow_param["srcLocations"] = [loc]
    borrow_param_dict["borrowParam"] = borrow_param
    
    if borrow_sizes_gib:
        borrow_param_dict["borrowSizes"] = [int(size * 1024 ** 3) for size in borrow_sizes_gib]
    
    water_mark = {}
    water_mark["highWaterMark"] = 92
    water_mark["lowWaterMark"] = 80
    borrow_param_dict["waterMark"] = water_mark
    
    json_str = json.dumps(borrow_param_dict, indent=2)
    return json_str


def _migrate_param2json(entry_list: List[LedgerEntry], pids, ratio, numa2socket: dict, numa_bind):
    """填充参数borrowParam,borrowIds,containerParam并格式化为字符串"""
    entry = entry_list[0]
    if numa_bind:
        borrow_param = {"srcNid": str(entry.src_node),
                        "srcLocations": [{"socketId": numa2socket[entry.src_numa], "numaId": entry.src_numa}]}
    else:
        borrow_param = {"srcNid": str(entry.src_node), "srcLocations": []}
    result = {"borrowParam": borrow_param, "borrowIds": [entry.name for entry in entry_list], "containerParam": [
        {"pid": pid, "ratio": ratio, "type": 0} for pid in pids
    ]}
    
    json_str = json.dumps(result, indent=2)
    return json_str


def _return_params2json(entry: LedgerEntry, exclude_pids: List, numa2socket: dict, numa_bind):
    """填充参数borrowParam,borrowIds,pids并格式化为字符串"""
    if numa_bind:
        borrow_param = {"srcNid": str(entry.src_node),
                        "srcLocations": [{"socketId": numa2socket[entry.src_numa], "numaId": entry.src_numa}]}
    else:
        borrow_param = {"srcNid": str(entry.src_node), "srcLocations": []}
    result = {"borrowParam": borrow_param, "borrowIds": [entry.name]}
    
    if exclude_pids:
        result["pids"] = [pid for pid in exclude_pids]
    else:
        result["pids"] = []
    
    json_str = json.dumps(result, indent=2)
    return json_str


def res2json(res):
    """解析JSON响应"""
    lines = res.strip().splitlines()
    if not lines:
        return {}
    
    last_line = lines[-1].strip()
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return {}


def start_container(node, count):
    """创建count个容器"""
    container_map = {}
    ncm = NodeContainerManager(node=node)
    for i in range(1, count + 1):
        pod = ncm.create_pod()
        container_name = f"container{i}"
        container = pod.create_container()
        container_map[container_name] = container
    return container_map


def check_container(node, container_map):
    """检查容器是否存在"""
    res = 1
    for _, ctr in container_map.items():
        cid = ctr.id[:13]
        cmd = f"crictl ps -a | grep {cid}"
        res = basic.run(node=node, cmd=cmd).rc
        if res != 0:
            return 1
    return res


def delete_container(container_map):
    """删除容器"""
    if container_map:
        for _, container in container_map.items():
            container.pod.delete()


@pytest.fixture(autouse=True)
def inject_container_overcommit_basecase_dependencies(
    request: Any,
    nodes: List[Any],
    resource: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> None:
    """注入ContainerOvercommitBaseCase依赖参数.
    
    只对ContainerOvercommitBaseCase及其子类执行注入。
    """
    if not hasattr(request, 'instance'):
        return
    
    instance = request.instance
    
    from libs.core.basecase.ubturbo.container_overcommit_basecase import ContainerOvercommitBaseCase
    if not isinstance(instance, ContainerOvercommitBaseCase):
        return
    
    instance.env_type = env.get_env_type(instance.node)
    instance.simulation_host = instance.node
    instance.ub_ports = UB_PORT_LIST.copy()
    instance.ub_password = None
    
    instance.nodemaster = None
    instance.nodestandby = None
    instance.rack_ids = []
    instance.nodeagents = {}
    instance.node_dict = {}
    instance.working_nodes = []
    instance.fault_nodes = []
    instance.fail_callback = instance._fail_callback
    
    instance.cpu_count = 16
    instance.socket = []
    instance.local_numa_counts = 2
    instance.socket2numa = {}
    instance.numa2socket = {}
    instance.cna2socket = {}
    instance.ledger = Ledger()
    
    logger.info(f"ContainerOvercommitBaseCase initialized: class={instance.__class__.__name__}")


class ContainerOvercommitBaseCase(ATBaseCase):
    """Base class for container overcommit test cases.
    
    继承 ATBaseCase，提供容器超分测试的基础功能。
    
    环境支持：
    - UB仿真环境 (env.UB_simulation)
    - 物理环境
    
    节点角色：
    - self.nodemaster: rack主节点
    - self.nodestandby: rack备节点
    - self.nodeagents: rack从节点字典
    
    使用示例：
        class MyContainerTest(ContainerOvercommitBaseCase):
            def test_borrow(self):
                res, entries = self.borrow(exec_node=self.nodes[0], 
                                           src_node=self.nodes[0].slot_id,
                                           borrow_sizes_gib=[1])
    """
    
    def setup_method(self):
        """Pre-test setup hook (legacy: preTestCase)."""
        self.logStep("setup_method1、连接环境节点")
        self.init_nodes()
        self.logStep("setup_method2、初始化集群环境")
        self.init_cluster_env()
        self.logStep("setup_method3、准备SDK脚本")
        self.prepare_sdk()
        self.logStep("setup_method2、初始化集群环境")

    def teardown_method(self):
        """Post-test cleanup hook (legacy: postTestCase)."""
        self.logStep("teardown_method、xxx")
    
    def init_nodes(self):
        """初始化节点连接."""
        if self.env_type == env.UB_simulation:
            self.init_ub_nodes()
        else:
            self.init_phy_nodes()
    
    def init_phy_nodes(self):
        """初始化物理节点."""
        self.logger.info("当前为物理环境")
    
    def init_ub_nodes(self):
        """初始化UB仿真节点."""
        self.logger.info("当前为仿真环境")
        exec_env = env.get_env_info(self.node, argument='execution_environment')
        if exec_env:
            return
        self.nodes = []
        self.ub_password = env.get_env_info(self.node, 'ub_password')
        for ub_port in self.ub_ports:
            if not connect.is_port_open(self.node.getIpAddress(), ub_port):
                continue
            else:
                node_connected = connect.copy(self.node, port=ub_port, password=self.ub_password)
                self.nodes.append(node_connected)
    
    def init_cluster_env(self):
        """初始化集群环境."""
        self.clear_all_container()
        self.query_and_set_role()
        self.init_socket_numa(self.nodemaster)

    def prepare_sdk(self):
        for agent in self.nodes:
            if system.is_path_exist(agent, LOCAL_SDK_PATH):
                continue
            basic.logger.info("上传SDK脚本")
            system.mkdir(agent, LOCAL_SDK_PATH)
            file_transport.send2remote(agent, f"{file_transport.THIS_PROJECT_PATH}"
                                              f"/resource/ubsrmrs/Container_Overcommit/sdk", LOCAL_TOOL_PATH)
            basic.run(agent, f"chmod +x {LOCAL_SDK_PATH}/*")

    def update_working_nodes(self):
        """更新工作节点列表."""
        fault_node_name = [node.name for node in self.fault_nodes]
        self.logger.info(f'当前故障节点为: {fault_node_name}')
        self.working_nodes = [h for h in self.nodes if h not in self.fault_nodes]
    
    def query_and_set_role(self):
        """查询并设置节点角色."""
        self.update_working_nodes()
        rack_manager.confirm_mem_ready(self.working_nodes)
        cluster_map = rack_manager.get_cluster_info(self.nodes)
        for node in self.nodes:
            node.hostname = basic.run(node, 'hostname').stdout.strip()
            node.slot_id = cluster_map[node.hostname].slot_id
            cur_role = cluster_map[node.hostname].role
            node.role = cur_role
            if cur_role == rack_manager.ROLE_MASTER:
                basic.logger.info(f"当前集群中，MXE主节点的标识符为: {node.slot_id}")
                self.nodemaster = node
            if cur_role == rack_manager.ROLE_STANDBY:
                basic.logger.info(f"当前集群中，MXE备节点的标识符为: {node.slot_id}")
                self.nodestandby = node
            self.node_dict[node.slot_id] = node
    
    def init_socket_numa(self, node):
        """初始化socket-numa关系."""
        self.local_numa_counts = numa.get_numa_count_with_cpu(node)
        self.cpu_count = numa.get_cpu_num(node)
        self.socket = numa.get_socket_ids(node)
        self.socket2numa, self.numa2socket = numa.match_socket_numa(node)
        self.cna2socket = numa.get_cluster_cna2socket(self.nodes)
    
    def borrow(self,
               exec_node,
               src_node,
               src_socket=None,
               src_numa=None,
               borrow_sizes_gib=None,
               daemon=False
               ) -> Tuple[dict, List[LedgerEntry]]:
        """借用内存."""
        borrow_cmd = f"python3 {LOCAL_SDK_SCRIPT_PATH.format('borrow')}"
        borrow_params_str = _borrow_params2json(src_node, src_socket, src_numa, borrow_sizes_gib)
        if daemon:
            borrow_cmd += f"'{borrow_params_str}'"
            borrow_cmd = f"({borrow_cmd} &) &> /dev/null"
            basic.run(exec_node, borrow_cmd)
            return {}, []
        else:
            borrow_cmd += f" '{borrow_params_str}'" + ";echo"
        stdout = basic.run(exec_node, borrow_cmd).stdout
        res = res2json(stdout)
        borrow_ids = res.get("borrowIds", [])
        if not borrow_ids:
            return res, []
        
        if not daemon:
            _ = self.update_ledger()
        
        entry_list: List[LedgerEntry] = []
        for borrow_id in borrow_ids:
            entry_list.append(self.ledger.entries[borrow_id])
        
        return res, entry_list
    
    def get_total_borrow(self, src_node):
        """获取借用内存总量（MB）."""
        total_borrow = 0
        self.update_ledger()
        for entry in self.ledger.entries.values():
            if src_node == str(entry.src_node):
                total_borrow += entry.size
        
        return int(total_borrow) >> 10
    
    def update_ledger(self):
        """更新账本."""
        self.update_working_nodes()
        updated_ledger = Ledger.update_ledger(self.working_nodes, self.ledger)
        for entry in updated_ledger.borrow_list:
            self.fill_entry_info(self.node_dict, entry)
            self.ledger.add_entry(entry)
        for entry in updated_ledger.changed_list:
            self.fill_entry_info(self.node_dict, entry)
            self.ledger.add_entry(entry)
        return updated_ledger
    
    def migrate(self, exec_node, entry_list: List[LedgerEntry], pids, ratio, numa_bind=False):
        """迁出进程."""
        migrate_cmd = f"python3 {LOCAL_SDK_SCRIPT_PATH.format('migrate')}"
        migrate_param = _migrate_param2json(entry_list, pids, ratio, self.numa2socket, numa_bind)
        migrate_cmd += f" '{migrate_param}'" + ";echo"
        return res2json(basic.run(exec_node, migrate_cmd).stdout)
    
    def return_all_borrow(self, exec_node, clear_account=False, numa_bind=False):
        """归还所有借用内存."""
        _ = self.update_ledger()
        basic.logger.info("归还ledger中的所有借用内存")
        results = []
        for entry in list(self.ledger.entries.values()):
            results.append(self.return_one_borrow(self.node_dict[str(entry.src_node)], entry, numa_bind=numa_bind))
        if clear_account:
            _ = self.update_ledger()
        return results
    
    def return_one_borrow(self, exec_node, entry: LedgerEntry, exclude_pids=None, daemon=False, numa_bind=False):
        """归还单个借用内存."""
        self.logger.info(f"开始归还borrowId -- {entry.name}")
        return_cmd = f"python3 {LOCAL_SDK_SCRIPT_PATH.format('return')}"
        return_params = _return_params2json(entry, exclude_pids, self.numa2socket, numa_bind)
        if daemon:
            return_cmd = f"({return_cmd} &) &>/dev/null"
            basic.run(exec_node, return_cmd)
            return {}
        else:
            return_cmd += f" '{return_params}'" + ";echo"
        res = res2json(basic.run(exec_node, return_cmd).stdout)
        _ = self.update_ledger()
        return res
    
    def judge_call_res(self, res):
        """判断调用结果."""
        if not res:
            self.logger.info("无效记录")
            return 2
        if res.get("code") != 0:
            self.logger.info("调用成功，执行失败")
            return 1
        self.logger.info("调用成功执行成功")
        return 0
    
    def stress2numa(self, node, numa_id, target_percent: float):
        """对指定NUMA施加压力."""
        mem_info = virtualization.numastat_vm(node)
        mem_total = mem_info['MemTotal'][f'Node {numa_id}']
        mem_used = mem_info['MemUsed'][f'Node {numa_id}']
        stress_val = math.floor(mem_total * target_percent - mem_used)
        if stress_val <= 0:
            self.logger.warn("加压值小于0，已达到目标水线")
            return
        _, cur_pages = virtualization.get_huge_pages(node, numa_index=numa_id)
        virtualization.set_huge_pages(node, number=(stress_val // 2) + cur_pages, numa_index=numa_id)
    
    def get_local_numa_percent(self, node_name, numa_index):
        """获取本端NUMA百分比."""
        data = rack_manager.query_numa_status(self.node_dict[node_name])
        return int(data[node_name][str(numa_index)])
    
    def get_numa_info(self, node_name, numa_index, key_name):
        """获取远端NUMA信息."""
        data = (
            virtualization.numastat_vm(self.node_dict[str(node_name)])
            .get(key_name, {})
            .get(f"Node {numa_index}", 0)
        )
        return math.ceil(data)
    
    def fill_entry_info(self, node_dict, entry: LedgerEntry):
        """填充账目信息."""
        res = basic.run(node_dict[str(entry.src_node)], f'bash {GET_BORROW_CNA_INFO} {entry.src_remote_numa}')
        if 'No dev_x' in res.stdout:
            basic.logger.warn("未找到当前借用账目对应的CNA信息")
            return
        else:
            cna_info = json.loads(res.stdout)
        
        entry.src_numa = self.socket2numa[self.cna2socket[cna_info["scna"]]][0]
        entry.lent_socket = self.cna2socket[cna_info["dcna"]]
    
    def clear_all_container(self):
        """清理所有容器."""
        for node in self.nodes:
            basic.run(node, 'systemctl start containerd')
            if crictl:
                crictl.remove_all_containers(node)
                crictl.remove_all_pods(node)
            else:
                basic.run(node, 'crictl rm -a')
                basic.run(node, 'crictl rmp -a')
    
    def get_container_ip(self, node, container_id):
        """获取容器IP."""
        cmd = f'''sh -c "ifconfig eth0 | awk '/inet / {{print \$2}}'"'''
        return basic.run(node, f"crictl exec {container_id} {cmd}").stdout.strip()
    
    def stress_in_container(self, node, container_id, stress_value: str, numa_id=None):
        """在容器内施加压力."""
        if numa_id is None:
            cmd = f'sh -c "stress-ng --vm 1 --vm-bytes {stress_value} --vm-keep --timeout 10d &> /dev/null &"'
        else:
            cmd = f'sh -c "numactl -m {numa_id} -N {numa_id} stress-ng --vm 1 --vm-bytes {stress_value} --vm-keep --timeout 10d &> /dev/null &"'
        basic.run(node, f"crictl exec {container_id} {cmd}")
        pids = basic.run(node, "pgrep -f stress-ng").stdout.strip().split("\n")
        pids = [int(pid) for pid in pids]
        time.sleep(5)
        return pids
    
    def iperf_in_container(self, node, server_container_ip, server_container_id, client_container_id, numa_id=None):
        """在容器内运行iperf3."""
        if numa_id is None:
            server_cmd = f'sh -c "iperf3 -s -p 12300 &> /home/iperf3.log &"'
            client_cmd = f'sh -c "iperf3 -c {server_container_ip} -p 12300 -i 10 -t 1200 &> /home/iperf3.log &"'
        else:
            server_cmd = f'sh -c "numactl -m {numa_id} -N {numa_id} iperf3 -s -p 12300 &> /home/iperf3.log &"'
            client_cmd = (f'sh -c "numactl -m {numa_id} -N {numa_id} iperf3 -c {server_container_ip} -p 12300 -i 10 -t '
                          f'120 &> /home/iperf3.log &"')
        
        basic.run(node, f"crictl exec {server_container_id} {server_cmd}")
        basic.run(node, f"crictl exec {client_container_id} {client_cmd}")
        pids = basic.run(node, "pgrep iperf3").stdout.strip().split("\n")
        pids = [int(pid) for pid in pids]
        return pids
    
    def process_is_alive(self, node, pids):
        """检查进程是否存活."""
        for pid in pids:
            res = basic.run(node, f'ps -e -o pid,comm | grep {pid}')
            if str(pid) not in res.stdout:
                return False
        return True
    
    def kill_osturbo_exec(self, node):
        """杀死ubturbo进程."""
        result = basic.run(node, "kill -9 $(pidof ub_turbo_exec)")
        if result.rc:
            raise Exception("杀死ubturbo进程失败")
    
    def wait_osturbo_wakeup(self, node):
        """等待ubturbo唤醒."""
        basic.wait_until(condition_func=lambda: basic.run(node, "pidof ub_turbo_exec").rc == 0,
                         timeout=30, check_sep=3, timeout_callback=self.fail_callback)
    
    def inject_Dstate(self, node, pid):
        """注入D状态."""
        basic.run(node, f"{DEMON_CAT_EXEC} \"inject rProc_d (pid) values({pid})\"")
    
    def kill_mxe(self, node, stop_server=False):
        """杀死MXE进程."""
        if stop_server:
            result = basic.run(node, "kill -9 $(pidof ubse) && systemctl stop ubse")
        else:
            result = basic.run(node, "kill -9 $(pidof ubse)")
        if result.rc:
            raise Exception("杀死mxe进程失败")
    
    def wait_mxe_wakeup(self, node, start_server=False, reset_role=True):
        """等待MXE唤醒."""
        if start_server:
            basic.run(node, "systemctl start ubse")
        basic.wait_until(condition_func=lambda: basic.run(node, "pidof ubse").rc == 0,
                         timeout=60, check_sep=5, timeout_callback=self.fail_callback)
        rack_manager.confirm_role_online(node, rack_manager.ROLE_MASTER)
        if reset_role:
            self.query_and_set_role()
    
    def clean_Dstate(self, node, pid):
        """清理D状态."""
        basic.run(node, f"{DEMON_CAT_EXEC} \"clean rProc_d where pid={pid}\"")
    
    def query_pid_state(self, node, pid):
        """查询进程状态."""
        res = basic.run(node, f"{DEMON_CAT_EXEC} \"query rProc_d where pid={pid}\"").stdout
        match = re.search(r'^State:\s*(.+)', res, re.MULTILINE)
        if match:
            return match.group(1)
        else:
            return None
    
    def _fail_callback(self):
        """超时回调."""
        raise Exception("超时未匹配失败")