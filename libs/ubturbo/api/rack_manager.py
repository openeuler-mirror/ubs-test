#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import time
import re
from collections import namedtuple
from typing import Tuple, Literal
from libs.ubturbo.common.string_utils import STR_ENTER
from libs.ubturbo.common import basic, file_transport
import libs.ubturbo.api.os_turbo as os_turbo
import libs.ubturbo.api.system as system

RACK_TYPE_SCRIPT = 'script'
RACK_TYPE_RPM = 'rpm'
DEFAULT_PATH_RACK_START_SH = '/home/RackManager/scripts/start.sh'

# UBSE服务基础路径
PROCESS_NAME_RACK = 'ubse'
SERVICE_NAME_SCBUS_DAEMON = 'ubse'  # rpm方式安装rackmanager 服务名称
RACK_INSTALL_PATH = "/etc/ubse"
RACK_CONF_PATH = "/etc/ubse/"
RACK_PLUGIN_CONF_PATH = "/etc/ubse/plugins/"
# ubse主程序相关文件
RACK_CONF = "ubse.conf"
RACK_PLUGIN_ADIMISSION_CONF = "ubse_plugin_admission.conf"
# mempooling插件相关文件
MEMPOOLNG_PLUGIN_CONF = 'plugin_mempooling.conf'

ROLE_MASTER = 'master'
ROLE_STANDBY = 'standby'
ROLE_AGENT = 'agent'
rack_node_identities = [ROLE_MASTER, ROLE_STANDBY, ROLE_AGENT]  # rack节点类型
# 具名元组，储存rack节点，方便调用
ClusterNode = namedtuple('ClusterNode', ['slot_id', 'role'])

QUERY_CLUSTER_INFO_CMD = 'sudo -u ubse ubsectl display cluster'
QUERY_MEM_STATUS_CMD = 'sudo -u ubse ubsectl check memory'
QUERY_NUMA_STATUS_CMD = 'sudo -u ubse ubsectl display memory -t numa_status'


def detect_rack_manager(node) -> Tuple[str, bool, str]:
    """
    检测rackmanger类型（文件或rpm安装）、是否运行
    """
    rack_type = None
    rack_on = False
    path_start_sh = None

    basic.logger.info('检测RackManager安装类型、状态')
    res = basic.run(node, f'systemctl status {SERVICE_NAME_SCBUS_DAEMON} --no-pager')
    if 'service could not be found.' in res.output:
        basic.logger.error(f'不存在该服务: {SERVICE_NAME_SCBUS_DAEMON}')
    elif 'active (running)' in res.output:
        rack_type = RACK_TYPE_RPM
        basic.logger.info('rpm方式安装的rack_manager已启动')
        rack_on = True
    else:
        rack_type = RACK_TYPE_RPM
        basic.logger.info('rpm方式安装的rack_manager（未启动）')

    if not rack_type:
        basic.logger.info('非RPM安装方式，检测RackManager启动路径')
        pid = system.find_process(node, 'ubse')
        if pid:
            basic.logger.info('当前有运行中的RackManager，检测启动脚本路径')
            cmd = system.get_cmd_by_pid(node, pid)
            # 回显(cmd)示例：/usr/local/softbus/ctrlbus/bin/rack_manager -f /usr/local/softbus/ctrlbus/expand_conf/
            executable = cmd.split(' ')[0]
            path_start_sh = executable.replace('bin/rack_manager', 'scripts/start.sh')
            rack_type = RACK_TYPE_SCRIPT
            rack_on = True
        else:
            basic.logger.info(f'当前无运行中的RackManager，检查是否存在默认启动脚本{DEFAULT_PATH_RACK_START_SH}')
            if system.is_path_exist(node, DEFAULT_PATH_RACK_START_SH):
                path_start_sh = DEFAULT_PATH_RACK_START_SH
                rack_type = RACK_TYPE_SCRIPT
                rack_on = False

    return rack_type, rack_on, path_start_sh


def activate_rack_manager(node, sync=False) -> bool:
    """
    启动rackmanager
    :param node:
    :param sync: 是否等待至能查询到主节点(真正启动而不是服务启动)
    :return: 启动前状态
    """
    _, rack_on, _ = detect_rack_manager(node)
    if rack_on:
        basic.logger.info('rack_manager已启动，无需再次启动')
        return rack_on

    basic.run(node, f'systemctl start {SERVICE_NAME_SCBUS_DAEMON}'),

    if sync:
        if not query_master(node):
            raise RuntimeError(f'rack_manager启动异常，找不到主节点')

    return rack_on


def shut_down_rack_manager(node, force=False) -> bool:
    """
    关闭RackManager
    :param node:
    :param force: kill对应进程后再停服务，加快停止速度
    :return: 关闭前状态
    """
    rack_on = detect_rack_manager(node)[1]
    if not rack_on:
        basic.logger.info(f'rack_manager已关闭')
        return rack_on

    basic.logger.info(f'关闭rack_manager')
    if force:
        basic.run(node, f'kill -9  $(pidof {SERVICE_NAME_SCBUS_DAEMON}) && '
                        f'systemctl stop {SERVICE_NAME_SCBUS_DAEMON};', timeout=5 * 60)
    else:
        basic.run(node, f'systemctl stop {SERVICE_NAME_SCBUS_DAEMON}', timeout=5 * 60)

    return rack_on


def restart_cluster_scbus(node_list, force=False, sync=True, time_sleep=10):
    """
    重启集群ubse
    :return:
    """
    for node in reversed(node_list):
        _ = shut_down_rack_manager(node, force)
        time.sleep(time_sleep)
    for node in list(node_list):
        _ = activate_rack_manager(node, sync)
        time.sleep(time_sleep)


def set_rack_plugin_admission(node, content=None, fn='/usr/local/softbus/ctrlbus/conf/rack_plugin_admission.conf'):
    """
    设置/usr/local/softbus/ctrlbus/conf/rack_plugin_admission.conf
    默认参数为：还原标准配置
    :param node:
    :param content: 文件内容
    :param fn: 文件路径
    :return:
    """
    default_content = 'memExport=201\n' \
                      'vm=205\n' \
                      'memMaster=901\n' \
                      'memAgent=902\n' \
                      'rackMetric=206\n' \
                      'mempooling=777\n'
    content = content or default_content
    file_transport.dump_text(node, content, fn)


def reset_rack_turbo(node):
    """
    功能：重启osturbo和ubse
    """
    _ = shut_down_rack_manager(node, True)
    basic.wait_until(lambda: detect_rack_manager(node)[1], expect_times=0, timeout=60)

    basic.logger.info("清理Rack数据目录 /var/lib/ubse/data ...")
    basic.run(node, 'rm -rf /var/lib/ubse/data')

    basic.logger.info("重置OS Turbo配置...")
    os_turbo.reset_osturbo(node)

    basic.logger.info("启动Rack Manager服务...")
    pre_state = activate_rack_manager(node, True)
    if not pre_state:
        raise RuntimeError("启动Rack Manager失败")
    basic.wait_until(lambda: detect_rack_manager(node)[1], timeout=60)


def query_master_standby_status(node, status, timeout: int = 300):
    """
    查询主节点（代称nodeA）、备节点，返回槽号
    使用的查询命令sudo -u ubse /usr/bin/ubsectl display cluster的回显：
    -----------------------------------------------------------------------------
    node                  role          bonding-eid
    -----------------------------------------------------------------------------
    computer01(1)         master        4245:4944:0000:0000:0000:0000:0100:0000
    computer02(2)         standby       4245:4944:0000:0000:0000:0000:0200:0000
    computer03(3)         agent         4245:4944:0000:0000:0000:0000:0300:0000
    computer04(4)         agent         4245:4944:0000:0000:0000:0000:0400:0000
    -----------------------------------------------------------------------------
    :param node:执行命令的节点
    :param status:查询主节点则填'master',查询备节点则填'standby'
    :return res:返回节点在ubse集群中的slotId槽号，如"1","2","3","4"
    """
    result = basic.run(node,
                       f'sudo -u ubse /usr/bin/ubsectl display cluster | grep {status}',
                       timeout=timeout).stdout.strip(STR_ENTER)
    res = result.split('(')[1].split(')')[0]
    basic.logger.info(f"{status}:{res}")
    return res


def wait_for_master_consistency(nodes, timeout_minutes=15, interval_seconds=5, origin_master_str="1", flag=False):
    """
    循环检查各节点主节点一致性，直到一致或超时
    :param nodes: 节点列表
    :param timeout_minutes: 最大等待时间（分钟）
    :param interval_seconds: 每次轮询间隔（秒）
    :param origin_master_str: 表示切换主备前的主节点 这个入参和flag=True一起使用，使用情形：当主节点mxe服务停止后，此时立刻在其他节点上查主，可能主还没有来得及变化的情况
    :param flag:默认False，当取值True时，表示循环检查各节点主节点一致性，并且不是原来的主节点
    :return: (bool, str) -> (是否一致, master节点名或None)
    """
    timeout = timeout_minutes * 60
    start_time = time.time()
    times = 0
    hostname_list = []
    for node in nodes:
        hostname_list.append(system.get_hostname(node))
    basic.logger.info(hostname_list)

    def get_master_map_and_role_list():
        '''
        遍历每个节点，只有当该节点能够查询到完整的集群信息时，才会去检查信息中的主节点并添加到字典master_map中，字典元素：key为当前节点，value为在当前节点查询到的主节点
        '''
        master_map = {}
        num_of_nodes = 0
        for node in nodes:
            role_list = []
            num_of_nodes += 1
            basic.logger.info(f"环境上有{len(nodes)}个节点，这是第{times}次循环中遍历第{num_of_nodes}个节点")
            basic.run(node, "systemctl status ubse --no-pager")
            cmd = "sudo -u ubse /usr/bin/ubsectl display cluster"
            result = basic.run(node, cmd, timeout=300).stdout
            if result is None:
                basic.logger.info(f"[{node}] 查询失败")
                if time.time() - start_time > timeout:
                    raise Exception("等待超时，节点查询失败")
                continue
            lines = [line.strip() for line in result.strip().splitlines()]
            # 只保留包含 主机名 的数据行
            data_lines = [line for line in lines if any(hostname in line for hostname in hostname_list)]
            basic.logger.info(f"{data_lines}")
            master_str = ""
            num_of_ready_node = 0
            for line in data_lines:
                # 以空白符分隔
                parts = re.split(r"\s+", line)
                node_field = parts[0]  # computer01(1)
                role = parts[1]  # master / standby / agent
                basic.logger.info(f"role:{role}")
                if role == "master" or role == "standby" or role == "agent":
                    num_of_ready_node += 1
                    role_list.append(role)
                if role == "master":
                    master_str = re.search(r"\(([^)]+)\)", node_field).group(1)
            unique_role_list = list(set(role_list))
            num_of_role = 3
            if len(nodes) == 2:
                num_of_role = 2
            basic.logger.info(f"num_of_ready_node:{num_of_ready_node},len(self.nodes):{len(nodes)}")
            if num_of_ready_node == len(nodes) and len(unique_role_list) == num_of_role:
                master_map[node] = master_str
        return master_map

    def get_node_str_list():
        '''
        获取节点的字符串列表，如果flag等于True,表示不包含原来的主节点
        '''
        node_str_list = [str(nodeId + 1) for nodeId in range(len(nodes))]
        if flag is True:
            node_str_list = [node_str for node_str in node_str_list if node_str not in [origin_master_str]]
        return node_str_list

    while True:
        times += 1
        basic.logger.info(f"这是第{times}次循环")
        master_map = get_master_map_and_role_list()
        if not master_map:
            basic.logger.info("所有节点查询失败，等待重试...")
            time.sleep(interval_seconds)
            if time.time() - start_time > timeout:
                raise Exception("等待超时，节点查询失败")
            continue
        # 判断是否一致
        masters = set(master_map.values())
        basic.logger.info(f"len(master)={len(masters)},len(master_map)={len(master_map)},len(nodes)={len(nodes)}")
        if len(masters) == 1 and len(master_map) == len(nodes):
            master_val = next(iter(masters))
            master_node = masters.pop()
            basic.logger.info(f"所有节点主一致: master={master_node}")
            node_str_list = get_node_str_list()
            if master_val in node_str_list:
                return True, master_node
        else:
            basic.logger.info("主不一致，各节点结果：", master_map)
        # 超时检查
        if time.time() - start_time > timeout:
            raise Exception("等待超时，节点查询失败")
        # 等待下一轮
        time.sleep(interval_seconds)


def check_mxe(node):
    """
    检查{node}节点的rack服务是否开启
    :param node:检查{node}节点的rack服务的状态（Active）
    :return state:如果开启返回True;如果没有开启，返回False
    """
    # 获取mxe服务状态
    res = basic.run(node, "SYSTEMD_COLORS=0 systemctl status ubse --no-pager | grep 'Active: active'", timeout=60)
    if res.rc != 0:
        return False
    return True


def wait_until_mxe_active(
        node,
        check_sep=10,
        timeout=600,
        if_active=True
) -> bool:
    """
    等待{node}节点上的mxe服务启动/停止
    :param node:
    :param check_sep: 检测间隔
    :param timeout: 超时时间
    :param if_active:True表示预期启动mxe服务，False表示预期停止mxe服务
    :return: 当mxe服务启动/停止，返回True
    """
    if if_active:
        msg = '预期启动mxe服务'
    else:
        msg = '预期停止mxe服务'

    start_time = time.time()

    def check_mxe_active():
        if time.time() - start_time > timeout:
            raise Exception(f'{msg},等待超时')
        return detect_rack_manager(node)[1] == if_active

    return basic.wait_until(check_mxe_active, timeout=timeout, check_sep=check_sep, msg=f'{msg}') > 0


def bakup_rack_confs(node, rack_conf_files, plugin=False, mode: Literal['mv', 'cp'] = 'mv'):
    """
    备份{rack_conf_files}列表中的文件,备份文件形如xxx.mp.bak，当当mode选择cp时，默认复制属主和文件权限
    :param rack_conf_files:ubse的配置文件名列表
    :param plugin:False表示是{RACK_CONF_PATH}目录下的配置文件，True表示是{RACK_PLUGIN_CONF_PATH}目录下的配置文件
    :param mode:可选项，默认剪切
    :return bak_path:返回备份文件路径
    """
    rack_conf_path = RACK_CONF_PATH
    if plugin:
        rack_conf_path = RACK_PLUGIN_CONF_PATH
    basic.run(node, "ll " + rack_conf_path, timeout=20)
    for conf_file in rack_conf_files:
        ret = basic.run(node, f"test -e {rack_conf_path + conf_file}.mp.bak && echo 1 || echo 0 ", timeout=120).stdout
        if int(ret):
            # 已备份，跳过
            continue
        else:
            # 未备份
            basic.logger.info(f"备份{conf_file}中")
            bak_path = f"{rack_conf_path + conf_file}.mp.bak"
            basic.run(node, f"{mode} {rack_conf_path + conf_file} {bak_path}", timeout=120)
            if mode == 'cp':
                system.set_chown_and_permission(node, file_path=rack_conf_path + conf_file,
                                                dest_file_path=f"{rack_conf_path + conf_file}.mp.bak")
    basic.run(node, "ll " + rack_conf_path, timeout=20)


def upload_rack_confs(node, local_path, remote_tmp_path, rack_conf_files, plugin=False,
                      set_conf_chown='root:root', permission=644):
    """
    从本地上传文件到远程临时目录后，再复制到服务的对应配置文件目录下的，并设置属主与文件权限
    :param node:节点
    :param local_path:待传输目录，该目录将作为压缩包顶层目录（目录末尾不要放路径分隔符）
    :param remote_tmp_path:传输目标目录父路径 确保是目录（目录末尾不要放路径分隔符）
    :param rack_conf_files:待传输的文件名列表
    :param plugin:False表示是{RACK_CONF_PATH}目录下的配置文件，True表示是{RACK_PLUGIN_CONF_PATH}目录下的配置文件
    :param set_conf_chown:文件的属主
    :param permission:文件的权限
    """
    rack_conf_path = RACK_CONF_PATH
    if plugin:
        rack_conf_path = RACK_PLUGIN_CONF_PATH
    for conf_file in rack_conf_files:
        local_file_path = f"{local_path}/{conf_file}"
        remote_file_tmp_path = f"{remote_tmp_path}/{conf_file}"
        work_file_path = f"{rack_conf_path + conf_file}"

        file_transport.send2remote(node, local_file_path, remote_tmp_path)
        system.rm(node, work_file_path)
        basic.run(node, f"cp {remote_file_tmp_path} {work_file_path}",
                  timeout=120)
        basic.run(node, f"chown {set_conf_chown} {work_file_path}")
        basic.run(node, f"chmod {permission} {work_file_path}")
    basic.run(node, "ll " + rack_conf_path, timeout=20)


def restore_rack_confs(node, rack_conf_files, plugin=False):
    """
    使用强制覆盖的方式恢复ubturbo相关conf文件，与lib.api.os_turbo.py中的bakup_ubturbo_confs一起使用
    :param rack_conf_files:ubse的配置文件名列表
    :param plugin:False表示是{RACK_CONF_PATH}目录下的配置文件，True表示是{RACK_PLUGIN_CONF_PATH}目录下的配置文件
    """
    rack_conf_path = RACK_CONF_PATH
    if plugin:
        rack_conf_path = RACK_PLUGIN_CONF_PATH
    for conf_file in rack_conf_files:
        basic.run(node, f"mv -f {rack_conf_path + conf_file}.mp.bak {rack_conf_path + conf_file}", timeout=120)
    basic.run(node, "ll " + rack_conf_path, timeout=20)


def get_valid_cputopo_list(node):
    '''
    :return:返回列表，列表元素为字典，形如：{'link-id':'1/36/0-2/36/0','node_slotId':'1','socket':36,'port':'0','peer_node_slotId':'2','peer-socket':‘36’,'peer-port':'0'}
    通过cli指令，Ubse能够获取全量各节点信息场景(如图)
    ------------------------------------------------------------------------------------------------------------------------
    link-id        node            socket  port  interface-name    peer-node       peer-socket peer-port peer-interface-name
    ------------------------------------------------------------------------------------------------------------------------
    -              computer1(1)    36      0     400GUB1/1/1       -               -           -          -
    -              computer1(1)    36      1     400GUB1/1/2       -               -           -          -
    1/36/2-3/36/0  computer1(1)    36      2     400GUB1/1/3       computer3(3)    36          0          400GUB3/1/1
    1/36/3-3/36/1  computer1(1)    36      3     400GUB1/1/4       computer3(3)    36          1          400GUB3/1/2
    -              computer1(1)    376     0     400GUB1/2/1       -               -           -          -
    -              computer1(1)    376     1     400GUB1/2/2       -               -           -          -
    1/376/2-3/376/0 computer1(1)   376     2     400GUB1/2/3       computer3(3)    376         0          400GUB3/2/1
    1/376/3-3/376/1 computer1(1)   376     3     400GUB1/2/4       computer3(3)    376         1          400GUB3/2/2
    -              -               -       -     -                 computer3(3)    36          2          400GUB3/1/3
    -              -               -       -     -                 computer3(3)    36          3          400GUB3/1/4
    -              -               -       -     -                 computer3(3)    376         2          400GUB3/2/3
    -              -               -       -     -                 computer3(3)    376         3          400GUB3/2/4
    ------------------------------------------------------------------------------------------------------------------------
    Total Links: 12
    Available Links: 4
    '''
    ret = basic.run(node, 'sudo -u ubse ubsectl display topo -t cpu').stdout
    lines = [line.strip() for line in ret.strip().split(STR_ENTER)]

    total_links = [line.split(':')[-1].strip() for line in lines if 'Total Links' in line][0]
    available_links = [line.split(':')[-1].strip() for line in lines if 'Available Links' in line][0]
    if total_links != available_links:
        raise Exception(f'error:total_links is {total_links},available_links is {available_links}')

    lines = [line.split() for line in lines if re.search(r'\d+-\d+', line)]
    len_of_lines = len(lines)
    valid_cputopo_list = []
    for i in range(len_of_lines):
        dic = {}
        dic['link-id'] = lines[i][0].strip()
        dic['node_slotId'] = lines[i][1].strip().split('(')[-1].strip().split(')')[0].strip()
        dic['socket'] = lines[i][2].strip()
        dic['port'] = lines[i][3].strip()
        dic['peer_node_slotId'] = lines[i][5].strip().split('(')[-1].strip().split(')')[0].strip()
        dic['peer-socket'] = lines[i][6].strip()
        dic['peer-port'] = lines[i][7].strip()
        valid_cputopo_list.append(dic)
    basic.logger.info(valid_cputopo_list)
    return valid_cputopo_list


def create_mem(borrow_in_node, borrow_in_node_slotid_str, lent_node_slotid_str, borrow_in_node_socketid_str,
               lent_node_socketid_str, borrow_mem, mem_name):
    """
    借用内存
    :borrowInNode:借入节点
    :borrowInNode_slotId_str:通过ubsectl display cluster可以查看到借入节点的槽位号，形如"1"
    :lentNode_slotId_str:通过ubsectl display cluster可以查看到借出节点的槽位号，形如"1"
    :borrowInNode_socketId_str:借入numa的socketId
    :lentNode_socketId_str:借出numa的socketId
    :borrow_mem_M_G:借用内存，需要是128M的倍数，单位是M或者G
    :mem_name:对内存借用的命名
    :return remote_numaId：返回远端numaId,数据类型int
    回显：
    $ ubsectl create memory -t numa -l 1/36/0-2/36/0 -s 128M -n testName
    name:testName
    size:128M
    numa-id:5
    import-node:1
    export-node:2
    """
    def check_cputopo(cputopo_dict):
        check = (borrow_in_node_slotid_str == cputopo_dict.get('node_slotId') and
                 lent_node_slotid_str == cputopo_dict.get('peer_node_slotId') and
                 borrow_in_node_socketid_str == cputopo_dict.get('socket') and
                 lent_node_socketid_str == cputopo_dict.get('peer-socket')
                 ) or (
                borrow_in_node_slotid_str == cputopo_dict.get('peer_node_slotId') and
                lent_node_slotid_str == cputopo_dict.get('node_slotId') and
                borrow_in_node_socketid_str == cputopo_dict.get('peer-socket') and
                lent_node_socketid_str == cputopo_dict.get('socket'))
        return check

    cputopo_list = get_valid_cputopo_list(borrow_in_node)
    check_cputopo_list = [cputopo_dict for cputopo_dict in cputopo_list if check_cputopo(cputopo_dict)]
    if len(check_cputopo_list) == 0:
        raise Exception("couldn't find expected cputopo")
    link_id = check_cputopo_list[0].get('link-id')
    res = basic.run(borrow_in_node,
                    f'sudo -u ubse ubsectl create memory -t numa -l {link_id} -s {borrow_mem} -n {mem_name}',
                    timeout=60).stdout
    if 'ERROR' in res:
        raise Exception("create mem failed")

    lines = res.strip().split(STR_ENTER)
    flag = False
    for line in lines:
        if 'numa-id' in line:
            flag = True
            remote_numaId_str = line.split(':')[-1].strip()
            return int(remote_numaId_str)
    if not flag:
        raise Exception('the keyword "numaId" not in output')


def delete_mem(borrowInNode, mem_name_list):
    """
    numa类型归还内存
    :param borrowInNode:借入节点
    :param mem_name_list:对内存借用的命名
    """
    for mem_name in mem_name_list:
        ret = basic.run(borrowInNode, f'sudo -u ubse ubsectl delete memory -t numa -n {mem_name}').stdout
        if 'Delete successfully' not in ret:
            raise Exception(f'delete mem failed,the mem_name is {mem_name}')


def query_master(node, timeout=15 * 60, check_sep=20) -> bool:
    """
    查询指定节点是否能在规定时间内查到 UBSE master
    作为 rack 完全启动的判断条件
    :param node:节点
    :param timeout:查询时长
    :param check_sep:查询间隔
    :return:True或者False
    """
    cmd = "sudo -u ubse ubsectl display cluster | grep master"
    pattern = re.compile(r"\(([^)]+)\)")

    def has_master() -> bool:
        try:
            res = basic.run(node, cmd, timeout=240)
        except Exception as e:
            basic.logger.debug(f"{node} 查询 master 失败: {e}")
            return False

        return bool(pattern.search(res.stdout))

    ok = basic.wait_until(
        has_master,
        check_sep=check_sep,
        timeout=timeout
    )

    return bool(ok)


def restart_rack_no_delete_data_8p(nodes, heart_beat=30):
    for node in nodes:
        basic.run(node, f'systemctl stop {SERVICE_NAME_SCBUS_DAEMON}')
    # 重启间隔需要超过三个心跳周期，节点才能确保下线，仿真环境一个心跳周期30s
    time.sleep(3*heart_beat)
    for node in nodes:
        basic.run(node, f'systemctl start {SERVICE_NAME_SCBUS_DAEMON}')


def wait_topo_links_ready(node, timeout=300):
    """
    等待 topo 链路全部可用：重启ubse后，即使都能查到主，还需要一段时间才能建链完成
    """
    def condition():
        res = basic.run(node, "sudo -u ubse ubsectl display topo -t cpu").stdout

        total_links = 0
        available_links = 0

        for line in res.splitlines():
            line = line.strip()

            if line.startswith("Total Links"):
                total_links = int(line.split(":")[-1].strip())

            elif line.startswith("Available Links"):
                available_links = int(line.split(":")[-1].strip())

        # 判断条件
        if total_links > 0 and total_links == available_links:
            return True

        return False

    times = basic.wait_until(condition_func=condition, check_sep=10, timeout=timeout)

    if times == 0:
        raise Exception("topo links not ready: Total Links != Available Links or == 0")

    return True


def confirm_role_online(node, role=ROLE_MASTER, timeout=10 * 60):
    """
    是否能够查询到主/备节点，以此作为rack完全启动的标志
    :param node:
    :param role: 填master / standby
    :param timeout: 超时时间
    :return:
    """
    def online_condition():
        res_str = basic.run(node, QUERY_CLUSTER_INFO_CMD, timeout=40)
        if role in res_str.stdout:
            return True
        return False

    res_times = basic.wait_until(online_condition, check_sep=20, timeout=timeout)
    if res_times == 0:
        return False
    return True


def get_cluster_info(node_list, timeout=10 * 60):
    """
    查询集群中各节点的角色，并返回一个字典
    :param node_list: 确定参与组网且在线的节点列表(如果有故障节点，需要提前过滤后传入)
    :param timeout: 超时时间
    :return:
    """
    # 等待查主归一
    wait_master_consistent(node_list, timeout)

    return _get_cluster_info_from_node(node_list[0])


def wait_master_consistent(node_list, timeout=15 * 60):
    """
    等待集群查主归一(一主一备X从)
    :param node_list: 参与ubse组网的节点
    :param timeout: 等待超时时间
    """
    cluster_nodes_nums = len(node_list)
    basic.logger.info("等待集群查主归一")

    def query_master_consistent():
        res = basic.run(node_list[0], QUERY_CLUSTER_INFO_CMD).stdout

        if (res.count(ROLE_MASTER) == 1 and res.count(ROLE_STANDBY) == 1
                and res.count(ROLE_AGENT) == cluster_nodes_nums - 2):
            return True
        return False

    res_times = basic.wait_until(condition_func=query_master_consistent, check_sep=15, timeout=timeout)
    if res_times == 0:
        raise Exception("集群查主未归一")


def wait_node_to_target_role(node, target_role: Literal['master', 'standby', 'agent'], node_list, timeout=10 * 60):
    """
    主备倒换场景，等待目标节点变为期望的角色
    :param node: 目标节点
    :param target_role: 目标角色
    :param node_list: 全量集群节点
    :param timeout: 超时时间
    :return:
    """

    def node_to_target_role():
        cluster_map = get_cluster_info(node_list, timeout)
        node_hostname = basic.run(node, 'hostname').stdout.strip()
        if cluster_map[node_hostname].role == target_role:
            return True
        return False

    basic.wait_until(condition_func=node_to_target_role, check_sep=15, timeout=timeout)


def confirm_mem_ready(node_list, timeout=10 * 60):
    """
    :param node_list: 预期内存OK的节点列表(如果有故障节点，需要提前过滤后传入node_list)
    :param timeout: 超时时间
    :return:
    """
    node_nums = len(node_list)

    def condition():
        res = basic.run(node_list[0], QUERY_MEM_STATUS_CMD)
        output = res.stdout + res.stderr
        if output.count(" ok") == node_nums * 4:  # sysSentry状态也检测
            return True
        if output.count("cluster state: ok; obmm: ok") == node_nums:  # sysSentry不OK 也不影响基础功能
            return True
        return False

    res_time = basic.wait_until(condition, check_sep=20, timeout=timeout)
    if res_time == 0:
        basic.logger.warn("集群存在内存子系统未就绪的节点")
        return False
    basic.logger.info("这个节点内存子系统OK了")
    return True


def _get_cluster_info_from_node(node):
    """
    节点执行QUERY_CLUSTER_INFO_CMD获取集群组网信息并解析返回
    -----------------------------------------------------------------------------
    node                  role          bonding-eid
    -----------------------------------------------------------------------------
    computer01(1)         master        4245:4944:0000:0000:0000:0000:0100:0000
    test02(2)             standby       4245:4944:0000:0000:0000:0000:0200:0000
    hostname03(3)         agent         4245:4944:0000:0000:0000:0000:0300:0000
    -----------------------------------------------------------------------------
    :param node: 执行QUERY_CMD的节点
    :return: {'computer01': ClusterNode(slot_id='1', role='master'),
              'test02': ClusterNode(slot_id='2', role='standby'),
              'hostname03': ClusterNode(slot_id='3', role='agent'),...}
    """
    cluster_map = {}

    # 按行拆分查询回显并去掉空行
    res = basic.run(node, QUERY_CLUSTER_INFO_CMD).stdout
    lines = [line.strip() for line in res.strip().splitlines()]

    # 只保留包含 master/standby/agent 的数据行
    data_lines = [line for line in lines if any(k in line for k in rack_node_identities)]

    for line in data_lines:
        # 以空白符分隔
        parts = re.split(r"\s+", line)
        node_field = parts[0]  # computer01(1)
        role = parts[1]  # master / standby / agent

        match_hostname = re.match(r"^([^(]+)\(", node_field)
        match_slot = re.search(r"\(([^)]+)\)", node_field)  # 提取括号中的内容
        if match_hostname and match_slot:
            hostname = match_hostname.group(1)
            slot_id = match_slot.group(1)
            cluster_map[hostname] = ClusterNode(slot_id, role)

    basic.logger.info(f"cluster_map = {cluster_map}")

    return cluster_map


def query_numa_status(node):
    """
    节点执行QUERY_NUMA_STATUS_CMD从ubse获取集群内存信息(只需要used_percent字段)并解析返回
    ---------------------------------------------------------------
      node            numa   total   used    free    used_percent
    ---------------------------------------------------------------
      computer01(1)   0      64254   14403   49851   22.4

      computer01(1)   1      63967   17625   46342   27.6

      computer02(2)   1      63967   16862   47105   26.4

      computer02(2)   0      64254   17165   47089   26.7
    ---------------------------------------------------------------
    :param node: 执行QUERY_NUMA_STATUS_CMD的节点
    :return: {'1': {'0': 32.5, '1': 12.4}, '2': {'1': 94.0, '0': 95.0}}
    """
    res = basic.run(node, QUERY_NUMA_STATUS_CMD)
    table_dict = {}

    lines = [line.strip() for line in res.stdout.strip().splitlines()]
    data_lines = [line for line in lines if re.match(r"^([^(]+)\(", line)]

    for line in data_lines:
        parts = re.split(r"\s+", line)
        node_field = parts[0]  # node-1(1)
        numa = parts[1]
        used_percent = float(parts[-1])

        # 提取 node 括号里的数字
        match = re.search(r"\((\d+)\)", node_field)
        if match:
            node_id = match.group(1)
            table_dict.setdefault(node_id, {})
            table_dict[node_id].setdefault(numa, {})
            table_dict[node_id][numa] = used_percent

    basic.logger.info(f"numa_status = {table_dict}")
    return table_dict
