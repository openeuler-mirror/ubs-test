import json
import re
import time
from datetime import datetime, timezone, timedelta

from libs.utils.logger_compat import Log

logger = Log.getLogger("ubsvirt_client")

log_path = "/var/log/ubse"
ms_log_path = "/var/log/ubs_scheduler"


def refresh_hugePage(node, numa_info={}, restart_service=False, numa_total=2):
    # 当前仅支持一个节点设置一个numa大页，一个节点多numa大页配置需后续适配
    numa_infos = get_numaInfo(node)
    if numa_info == {}:
        return
    # default_obmm_num为obmm占用
    default_obmm_num = 1024 // numa_total
    default_page_num = default_obmm_num // 2
    # 当前大页numa设置最大支持4，避免对预上线等情况下得额外numa进行设置
    loop_num = min(numa_total, 4)
    for i in range(loop_num):
        numa_node = next((numa for numa in numa_infos if numa['name'] == 'Node ' + str(i)), None)
        if not numa_node:
            return False

        if i in numa_info.keys():
            numa_num = numa_info[i]
            numa_id = i
            if int(numa_node['HugePages_Total']) == numa_num * 2:
                continue

            if int(numa_node['MemFree']) + int(numa_node['HugePages_Total']) < numa_num * 2:
                return False

            ret = echo_hugePage(node, numa_id, numa_num)
            if ret.get('rc') != 0:
                return False
            restart_service = True
        else:
            if int(numa_node['HugePages_Total']) == 0:
                continue
            if int(numa_node['HugePages_Total']) == default_obmm_num:
                continue

            ret = echo_hugePage(node, i, default_page_num)
            if ret.get('rc') != 0:
                return False
            restart_service = True

    return True if not restart_service else node.run(
        {'command': ['systemctl restart openstack-nova-compute.service'], 'timeout': 600}).get('rc') == 0


def echo_hugePage(node, numa_id, num):
    # 变更大页前，刷新大页缓存
    node.run({'command': ['echo 3 > /proc/sys/vm/drop_caches'], "timeout": 60})
    command = f"echo {num} > /sys/devices/system/node/node{numa_id}/hugepages/hugepages-2048kB/nr_hugepages"
    return node.run({'command': [command]})


def format_output_to_json(ret):
    if ret['stdout'] is None:
        return None
    server = ret.get("stdout").replace("root@#>", '')
    return json.loads(server)


# 获取卷信息
def get_volume_available_list(node):
    """
    获取空余卷列表
    """
    res = node.run({'command': [f"openstack volume list --long -f json"]})
    server = res.get("stdout")
    server = server.replace("root@#>", '')
    ret = json.loads(server)
    volume_list = []
    for item in ret:
        if item['Status'] == 'available':
            volume_list.append(item)
    return volume_list


def create_volume_with_image(node, name, image):
    command = f"openstack volume create --size 50 --image {image} {name} -f json"
    return format_output_to_json(node.run({'command': [command]}))


def show_volume(node, volume_id):
    res = node.run({'command': [f"openstack volume show {volume_id} -f json"]})
    if res['stdout'] is None:
        return None
    server = res.get("stdout").replace("root@#>", '')
    return json.loads(server)


def list_aggregate(node):
    ret = node.run({'command': ["openstack aggregate list --long -f json"]})
    ret = ret.get("stdout")
    ret = ret.replace("root@#>", '')
    return json.loads(ret)


def create_aggregate(node, name, properties, hosts):
    cmd = "openstack aggregate create "
    if properties:
        cmd = cmd + '--property ' + ' '.join([f"{key}={value}" for key, value in properties.items()])
    cmd += ' ' + name
    node.run({'command': [cmd]})
    for host in hosts:
        node.run({'command': [f"openstack aggregate add host {name} {host}"]})


def show_aggregate(node, name):
    ret = node.run({'command': [f"openstack aggregate show {name} -f json "]})
    ret = ret.get("stdout")
    ret = ret.replace("root@#>", '')
    return json.loads(ret)


def remove_aggregate_host(node, name, hosts):
    for host in hosts:
        node.run({'command': [f"openstack aggregate remove host {name} {host}"]})


def add_aggregate_host(node, name, hosts):
    for host in hosts:
        node.run({'command': [f"openstack aggregate add host {name} {host}"]})


def delete_aggregate(node, name):
    cmd = "openstack aggregate show  " + name + " -f json"
    ret = node.run({'command': [cmd]})
    ret = ret.get("stdout")
    ret = ret.replace("root@#>", '')
    ret_json = json.loads(ret)
    aggregate_host_list = ret_json["hosts"]
    if aggregate_host_list is not []:
        for host in aggregate_host_list:
            cmd = "openstack aggregate remove host " + name + " " + host
            node.run({'command': [cmd]})
    cmd = "openstack aggregate delete  " + name
    node.run({'command': [cmd]})


def list_flavors(node):
    ret = node.run({'command': ["openstack flavor list --long -f json"]})
    ret = ret.get("stdout")
    ret = ret.replace("root@#>", '')
    return json.loads(ret)


def create_flavor(node, name, ram, disk, cpus):
    command = f"openstack flavor create --ram {ram} --disk {disk} --vcpus {cpus} {name}"
    node.run({'command': [command]})


def add_metadata_to_flavor(node, flavor, properties):
    for key, value in properties.items():
        logger.info(f"add metadata to {flavor} : {key}:{value}")
        command = f"openstack flavor set --property {key}={value} {flavor}"
        node.run({'command': [command]})


def create_server_with_volume(node, name, flavor, volume, host=None):
    command = f"openstack server create --flavor {flavor} --volume {volume} "
    if host:
        command += '--availability-zone host-name:' + host
    command = command + ' ' + name
    node.run({'command': [command]})


def delete_server(node, server_name):
    command = f"openstack server delete {server_name}"
    node.run({'command': [command], "timeout": 60})


def list_servers(node):
    command = "openstack server list -f json"
    return format_output_to_json(node.run({'command': [command]}))


def migrate_server(node, server_id, destination=None):
    """
    将虚机热迁移至指定节点
    @server_id：迁移的虚机的id
    @destination：目标迁移的节点
    """
    if destination:
        command = f"nova live-migration {server_id} {destination}"
    else:
        command = f"nova live-migration {server_id}"
    return node.run({'command': [command]})


def get_server_detail(node, server_name):
    """
    获取节点上的instance_name
    """
    command = f"openstack server show {server_name} -f json"
    ret = node.run({'command': [command]})
    if isinstance(ret, dict) and ret.get('rc', 0) != 0:
        list_servers(node)
    ret = ret.get("stdout") if isinstance(ret, dict) else ret
    if not ret:
        return {}
    ret = ret.replace("root@#>", '')
    return json.loads(ret)


def get_date_timestamp(node):
    res = node.run({'command': [f'date +%s'], 'waitstr': '#'})
    return int(res.get("stdout").replace("root@#>", "").strip())


def get_ubs_scheduler_decisions(node, current_time):
    pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})'
    res = node.run({'command': [f'grep -a "The escape strategy result is" /var/log/ubs_scheduler/ubs-scheduler-controller.log | tail -n 20'],
                    'waitstr': '#'})
    if res['stdout'] is None:
        return None
    server = res.get("stdout").replace("root@#>", "")
    lines = server.split('\n')
    decisions = []
    for index in range(0, len(lines), 1):
        line = lines[index]
        match = re.search(pattern, line)
        if not match:
            continue

        log_time = match.group(1)
        timestamp = datetime.strptime(log_time[:23], "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if timestamp <= current_time or (index + 1) >= len(lines) + 1:
            continue

        match1 = re.search(r"'action_type':\s*(True|False)", line)
        if not match1:
            continue
        else:
            decision_res = match1.group(1)
            decisions.append(decision_res)
    formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("{}时间点后的策略有 {}".format(formatted_time, decisions))
    return decisions


def get_decision(node, current_time, positive=True, decision_node=None, ubs_scheduler_decision=False):
    if ubs_scheduler_decision:
        # 获取ubs-scheduler-controller.log日志中的逃生策略
        formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S.%f")
        decisions = get_ubs_scheduler_decisions(node, current_time)
        if not decisions:
            return None
        else:
            for cur_strategy in decisions:
                logger.info("{}时间点后返回的策略是 {}".format(formatted_time, cur_strategy))
        logger.info("{}时间点后返回的策略是{}".format(formatted_time, decisions[-1]))
        return decisions[-1]
    # 获取vm_plugin.log日志中的逃生策略
    formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
    decisions = get_decisions(node, current_time)
    if not decisions:
        return None
    else:
        return_decision = []
        if decision_node:
            for i in decisions:
                if i[2] == decision_node:
                    return_decision.append(i)
            logger.info("{}时间点后返回的{}节点上的策略是{}".format(formatted_time, decision_node, return_decision))
            decisions = return_decision
    logger.info("{}时间点后返回的策略是{}".format(formatted_time, decisions[0] if positive else decisions[-1]))
    # 0 借用 1 归还 2 无操作
    return decisions[0] if positive else decisions[-1]


def get_decisions(node, current_time):
    pattern = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}[+\-]\d{2}:\d{2})\].*?FinalDecision actionType = (\d+)"
    res = node.run({'command': [f'grep -a "actionType =" /var/log/ubse/virt_agent_plugin.log | tail -n 20'], 'waitstr': '#'})
    if res['stdout'] is None:
        return None
    server = res.get("stdout").replace("root@#>", "")
    lines = server.split('\n')
    decisions = []
    for index in range(0, len(lines) - 1, 1):
        line = lines[index]
        match = re.search(pattern, line)
        if not match:
            continue

        log_time = match.group(1)
        timestamp = datetime.strptime(log_time[:-6], "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if timestamp <= current_time or (index + 1) >= len(lines):
            continue

        last_line = lines[index]
        match1 = re.search(r".*actionType = (\w+)", last_line)
        if not match1:
            continue
        match2 = re.search(r'AlarmNumaLoc=\["(\w+)"', last_line)
        if not match2:
            decision_node = ""
        else:
            decision_node = match2.group(1)
        decisions.append((int(match.group(2)), match1.group(1), decision_node))
    formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("{}时间点后的策略有{}".format(formatted_time, decisions))
    return decisions


def vm_stree(node, streeNum):
    logger.info("给当前虚机占用内存(加压)")
    node.run({'command': [f'stress-ng --vm 1 --vm-bytes {streeNum} --vm-keep &'], 'waitstr': '#'})


def check_vm_stress(node):
    logger.info("检查当前虚机是否有加压进程")
    ret = node.run({'command': ["ps -ef|grep stress|grep -v grep"]})
    logger.info(f"查看加压进程的回显是{ret.get('stdout')}")
    return ret.get('stdout')


def quit_vm(node):
    node.run({'command': ['^]'], 'waitstr': '#'})


def kill_stress(node):
    ret = node.run(
        {'command': ["ps -ef|grep stress |grep -v grep|awk '{print $2}'|xargs -I {} -n 1 kill -9 {}"], "timeout": 30,
         'waitstr': '[>#]'})


def enter_vm(node, vm_name, auth=True, first_enter=True):
    logger.info("进入虚机")
    if first_enter:
        res = node.run({'command': [f'virsh console {vm_name}'], "timeout": 60,
                        'waitstr': 'Escape character', 'returnCode': False})
        res = node.run({'command': ['\r'], "timeout": 3600,
                        'waitstr': 'press Control-D to continue|login', 'returnCode': False})
    else:
        res = node.run({'command': [f'virsh console {vm_name}'], "timeout": 60,
                        'waitstr': 'Escape character', 'returnCode': False})
        return res
    times = 0
    login_flag = False
    while times < 60:
        if res['stdout']:
            if 'login' in res['stdout'] or "root@vm0" in res['stdout'] or "root@#" in res['stdout']:
                login_flag = True
                break
            else:
                res = node.run({'command': ['openEuler12#$'], "timeout": 120,
                                'waitstr': 'press Control-D to continue|login'})
        elif res['stderr']:
            if 'login' in res['stderr'] or "root@vm0" in res['stderr']:
                login_flag = True
                break
            else:
                res = node.run({'command': ['openEuler12#$'], "timeout": 120,
                                'waitstr': 'press Control-D to continue|login'})
        else:
            res = node.run({'command': ['openEuler12#$'], "timeout": 120,
                            'waitstr': 'press Control-D to continue|login'})
        times = times + 1
    if not login_flag:
        raise RuntimeError("Login vm error")
    if res['stdout'] is not None:
        if 'login' in res['stdout']:
            res = node.run({'command': ['root'], "timeout": 180,
                            'waitstr': 'Password',
                            'input': ['openEuler12#$', '[>#]'] if auth else ['\r', '[>#]'],
                            'shnormal': True})
    return res


def get_memory(node):
    # 规避 free -m 回显错位导致的失败
    node.run({'command': [''], "timeout": 15, 'waitstr': '#'})

    res = node.run({'command': ['free -m'], 'waitstr': '#'}).get('stdout')
    lines = res.split('\n')
    curLine = lines[1].split()
    return {"total": curLine[1], "used": curLine[2], "free": curLine[3]}


def get_numaInfo(node):
    logger.info(f"执行命令查看numa信息")
    res = node.run({'command': ['numastat -vmc']}).get('stdout')
    if not res:
        time.sleep(5)
        return get_numaInfo(node)
    lines = res.rstrip('root@#>').split('\n')
    start_flag = False
    pattern = r'Node \d+'
    numa_nodes = []
    match_attribute = ['MemFree', 'HugePages_Total', 'HugePages_Free', 'MemTotal']
    for line in lines:
        if "Node 0" in line:
            start_flag = True
            matches = re.findall(pattern, line)
            numa_nodes = [{"name": node_name} for node_name in matches]
            numa_nodes.append({"name": "Total"})
            continue

        if not start_flag:
            continue

        for attribute in match_attribute:
            if attribute in line:
                values = line.split()
                for index in range(1, len(values)):
                    numa_node = numa_nodes[index - 1]
                    numa_node[attribute] = values[index]
    return numa_nodes


def get_borrow_lend_account(node, nodeId):
    '''
        目标：获得当前节点的借入借出账本中的信息
        result = {'borrowedItem':[
                        {
                            'nodeId' : 'Node1',
                            'numaId' : 0,
                            'memory' : '2.0GB'
                        }
                     ],
                 'lentItem':[]
                }
        注：无借出借入时，'borrowedtem' 、'lentItem' 全为空
    '''
    logger.info(f"调用接口查看节点Node{nodeId}上借出借入账本")
    command = [f"curl -X GET http://{node.localIP}:9898/rest/rackmaster/v1/memory-info?nodeId=Node{nodeId}"]
    res = node.run({'command': command}).get('stdout').rstrip('root@#>')
    data = json.loads(res)
    borrow_lend_infos = data['borrowedAndLentInfo']
    return borrow_lend_infos


# 返回特定词后的值
def find_value(text, tar):
    arr = text.split(' ')
    try:
        idx = arr.index(tar)
        if tar == 'percent':
            next_word = arr[idx + 2].rstrip(',')
        else:
            next_word = arr[idx + 1].lstrip(':') if idx + 1 < len(arr) else None
        return next_word
    except ValueError:
        return None


def get_percentInfo(node):
    '''
    功能：从日志中获取内存占用率（水线）信息
    参数：
        node: 环境主节点
    返回值：result = {'Node0': [10,20,30,40], 'Node1': [11,21,31,41]]}
    表示，Node0的numa0的内存占用率是10%，numa1是20%，numa2是30%，numa3是40%
        Node1的numa0的内存占用率是11%，numa1是21%，numa2是31%，numa3是41%
    '''
    logger.info(f"执行命令查看日志中内存占用率（水线）")
    result = {}
    for nodeid in [0, 1]:
        node_info = []
        node_name = 'Node' + str(nodeid)
        for numaid in [0, 1, 2, 3]:
            log_info = node.run({'command': [
                'zgrep -a -A 1 "Node id is {}, numa id is {}"  {}/rackmem_manager.log |tail -n 2'.format(node_name,
                                                                                                         numaid,
                                                                                                         log_path)],
                'waitstr': '#'}).get(
                'stdout')
            percent = re.search(r'The percent is (\d+)', log_info)
            if percent:
                logger.info("{} numa{} memory-used percent is {}%".format(node_name, numaid, percent.group(1)))
                node_info.append(int(percent.group(1)))
            else:
                logger.info("{} numa{} memory-used percent is not found".format(node_name, numaid))
                node_info.append(0)
        result[node_name] = node_info
    return result


def get_percentInfo_for_ms(node, node_name):
    '''
    功能：从日志中获取内存占用率（水线）信息
    参数：
        node: 环境主节点
    返回值：result = {'Node0': [10,20,30,40], 'Node1': [11,21,31,41]]}
    表示，Node0的numa0的内存占用率是10%，numa1是20%，numa2是30%，numa3是40%
        Node1的numa0的内存占用率是11%，numa1是21%，numa2是31%，numa3是41%
    '''
    logger.info(f"执行命令查看日志中内存占用率（水线）")
    result = {}
    node_info = []
    for numaid, sockedid in zip([0, 1, 2, 3], [0, 0, 1, 1]):
        log_info = node.run({'command': [
            '''zgrep -a -A 1 "socketId: {}, numaId: {}" {}/ubs-scheduler-agent.log |tail -n 2'''.format(
                sockedid, numaid, ms_log_path)], 'waitstr': '#'}).get('stdout')
        percent = re.search(r'The percent of memory used is (\d+)', log_info)
        if percent:
            logger.info("{} numa{} memory-used percent is {}%".format(node_name, numaid, percent.group(1)))
            node_info.append(int(percent.group(1)))
        else:
            logger.info("{} numa{} memory-used percent is not found".format(node_name, numaid))
            node_info.append(0)
    result[node_name] = node_info
    return result


def get_assign_log(node, log_path, assign_time, assign_key=None):
    '''
    功能：从日志文件中获取指定时间戳后的指定字段的日志
    参数：
        node: 日志所在节点，示例：self.master
        log_path：日志路径，示例：'/var/log/scbus/rackmem_agent.log'
        assign_time: 指定时间戳，示例：1733895703
        assign_key: 过滤关键词，示例：'percent'
    返回值：字符串，'[2024-12-10 18:36:03.377 +0800][DEBUG][409312][281472277388960][rack_mem_helper.cpp:RackLogFunc:31] [rack_mem_meta_data.h:348][UpdateAndCheckNotify] The percent is 7, high waterMark is 85, low waterMark is 80\r\n'
    '''
    assign_time = datetime.fromtimestamp(assign_time)
    assign_time = assign_time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"从日志文件中获取指定时间戳后的指定字段的日志")
    # 获取日志文件的时间戳格式
    log_info = node.run({'command': ['tail -n 5 {}'.format(log_path)]}).get('stdout')
    pattern_list = [r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} [+-]\d{4}\]']
    pattern_cur = ''
    for pattern in pattern_list:
        percent = re.search(pattern, log_info)
        if percent:
            pattern_cur = percent.re.pattern
            break
    # 规避日志中非日期开头的格式
    pattern_cur = pattern_list[0]
    if pattern_cur == '':
        return ""
    assign_time_format_list = ['[%Y-%m-%d %H:%M:%S']
    assign_time_c = datetime.strptime(assign_time, '%Y-%m-%d %H:%M:%S')
    pattern_time_str = assign_time_c.strftime(assign_time_format_list[pattern_list.index(pattern_cur)])
    str11 = "cat  {}".format(log_path) + " |awk '{if ($0 >= " + '"{}"'.format(pattern_time_str) + ") print $0}'"
    if assign_key:
        str11 = str11 + "|grep '{}'".format(assign_key)
    res = node.run({'command': [str11]}).get('stdout')
    if res:
        log_info = res.rstrip('root@#>')
    else:
        log_info = ''
    return log_info


def set_conf_file(node, file, key, value, sections='DEFAULT'):
    """
    功能：修改ini或conf格式的配置文件
    参数：
        node: 日志所在节点，示例：self.master
        file：配置文件路径，示例：'/etc/nova/nova.conf'
        key: 配置项名称，示例：'ram_allocation_ratio'
        value: 配置项值，示例：'1.175'
        sections：配置节名称
    返回值：True/False
    使用示例：
        client.set_conf_file(self.master, '/home/nova.conf','ram_allocation_ratio', '1.175')
    """
    file_exist_info = node.run({'command': [f'ls {file}']})
    if file_exist_info['rc'] != 0:
        return False
    key_exist_info = node.run({'command': [f'cat {file}|grep ^{key}'], 'timeout': 3})
    if key_exist_info['rc'] != 0:
        logger.info(f"{key} not exist ,now add it")
        res = node.run({'command': [f'sed -i "/\[{sections}\]/a\{key}={value}" {file}'], 'timeout': 3})
    else:
        logger.info(f"{key} exist ,now modify it")
        res = node.run({'command': [f'sed -i "s/^{key}.*/{key}={value}/" {file}'], 'timeout': 3})
    setresult = node.run({'command': [f'cat {file}|grep ^{key}'], 'timeout': 3})
    logger.info(setresult.get('stdout'))
    return setresult['rc'] == 0


def get_ms_controller_log(node, current_time, key_word):
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}.*)'
    res = node.run({'command': [f'grep -a "{key_word}" /var/log/ubs_scheduler/ubs-scheduler-controller.log | tail -n 20'], 'waitstr': '#'})
    if res['stdout'] is None:
        return None
    server = res.get("stdout").replace("root@#>", "")
    lines = server.split('\n')
    decisions = []
    for index in range(0, len(lines) - 1, 1):
        line = lines[index]
        match = re.search(pattern, line)
        if not match:
            continue

        log_time = match.group(1)
        timestamp = datetime.strptime(log_time[:23], "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if timestamp <= current_time or (index + 1) >= len(lines):
            continue

        decision_res = match.group(1)
        decisions.append(decision_res)
    formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("{}时间点后的策略有 {}".format(formatted_time, decisions))
    return decisions


def get_assign_log_zgrep(node, zgrep_log_path, assign_time, assign_key):
    '''
    功能：从日志文件中获取指定时间戳后的指定字段的日志
    参数：
        node: 日志所在节点，示例：self.master
        zgrep_log_path：日志路径，示例：'/var/log/scbus/rackmem_agent.log'
        assign_time: 指定时间戳，示例：1733895703
        assign_key: 过滤关键词，示例：'percent'
    返回值：字符串，'[2024-12-10 18:36:03.377 +0800][DEBUG][409312][281472277388960][rack_mem_helper.cpp:RackLogFunc:31] [rack_mem_meta_data.h:348][UpdateAndCheckNotify] The percent is 7, high waterMark is 85, low waterMark is 80\r\n'
    '''
    dt = datetime.fromtimestamp(assign_time, tz=timezone(timedelta(hours=8)))
    formatted = dt.strftime("%Y-%m-%d %H:%M:%S") + f".{int(dt.microsecond / 1000):03d} {dt.strftime('%z')}"
    str11 = "zgrep -a -h '{}'".format(assign_key) + " {}".format(
        zgrep_log_path) + " |awk '{if ($0 >= " + '"[{}"'.format(formatted) + ") print $0}'"
    res = node.run({'command': [str11]}).get('stdout')
    if res:
        log_info = res.rstrip('root@#>')
    else:
        log_info = ''
    return log_info


def get_ms_log_info(node, start_time, key, file_path, line):
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}'
    command = "tail -n " + line + " " + file_path + " | grep '" + key + "'"
    res = node.run({'command': [f'{command}'], 'waitstr': '#'})
    if res['stdout'] is None:
        return None
    server = res.get("stdout").replace("root@#>", "")
    lines = server.split('\n')
    log_info = ""

    for index in range(0, len(lines) - 1, 1):
        line = lines[index]
        match = re.search(pattern, line)
        if not match:
            continue

        log_time = match.group()
        timestamp = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if timestamp <= start_time or (index + 1) >= len(lines):
            continue

        log_info = lines[index]
        break
    return log_info


def get_migrate_actionType(node, current_time):
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}'
    command = "grep -a \"migrate strategy is\" /var/log/nova/nova-compute.log"
    res = node.run({'command': [f'{command}'], 'waitstr': '#'})
    if res['stdout'] is None:
        return None
    server = res.get("stdout").replace("root@#>", "")
    lines = server.split('\n')
    decisions = []

    for index in range(0, len(lines) - 1, 1):
        line = lines[index]
        match = re.search(pattern, line)
        if not match:
            continue

        log_time = match.group()
        timestamp = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if timestamp <= current_time or (index + 1) >= len(lines):
            continue

        last_line = lines[index]
        match = re.search(r'migrate strategy is (\d+)', last_line)
        decisions.append(match.group(1))
    formatted_time = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("{}时间点后的策略有{}".format(formatted_time, decisions))
    if not decisions:
        return None
    else:
        return decisions[0]


def check_volume_status(node, volume, volume_satus, reserved_time, interval_time):
    flag = False
    wait_time = interval_time
    while wait_time < reserved_time:
        detail = show_volume(node, volume)
        if detail['status'] == volume_satus:
            flag = True
            break
        wait_time = wait_time + interval_time
        time.sleep(interval_time)
    return flag


def get_assign_libvirt_log(node, log_file_path, assign_time, assign_key=None):
    """
    功能：从日志文件中获取指定时间戳后的指定字段的日志
    参数：
        node: 日志所在节点，示例：self.master
        log_path：日志路径，示例：'/var/log/libvirt/libvirtd.log'
        assign_time: 指定时间戳，示例：1733895703
        assign_key: 过滤关键词，示例：'running job remoteDispatchDomainMigratePerform3Params'
    返回值：字符串，'/var/log/libvirt/libvirtd.log:2025-06-10 02:34:37.433+0000: 3653540: debug : virThreadJobSet:93 : Thread 3653540 (rpc-libvirtd) is now running job remoteDispatchDomainMigratePerform3Params'
    """

    dt = 0
    assign_time = datetime.fromtimestamp(assign_time)
    assign_time = assign_time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"从日志文件中获取指定时间戳后的指定字段的日志")
    # 获取日志文件的时间戳格式
    log_info = node.run({'command': ['tail -n 5 {}'.format(log_file_path)]}).get('stdout')
    pattern_list = [r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} [+-]\d{4}\]']
    pattern_cur = ''
    for pattern in pattern_list:
        percent = re.search(pattern, log_info)
        if percent:
            pattern_cur = percent.re.pattern
            break
    # 规避日志中非日期开头的格式
    pattern_cur = pattern_list[0]
    if pattern_cur == '':
        raise RuntimeError("no matching log")
    assign_time_format_list = ['%Y-%m-%d %H:%M:%S']
    assign_time_c = datetime.strptime(assign_time, '%Y-%m-%d %H:%M:%S')
    pattern_time_str = assign_time_c.strftime(assign_time_format_list[pattern_list.index(pattern_cur)])
    str11 = "cat  {}".format(log_file_path) + " |awk '{if ($0 >= " + '"{}"'.format(pattern_time_str) + ") print $0}'"
    if assign_key:
        str11 = str11 + "|grep '{}'".format(assign_key)
    res = node.run({'command': [str11]}).get('stdout')
    if res:
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{3}')
        log_info = res.rstrip('root@#>')
        match = pattern.match(log_info)
        if match:
            match_res = match.group()
            dt = datetime.fromisoformat(match_res).timestamp()
        else:
            raise RuntimeError("no matching log")
    else:
        log_info = ''
    return log_info, dt


def get_assign_vm_plugin_log_date(assign_key=None):
    """
    功能：从vm_plugin日志文件中指定字段获取日志时间戳信息
    参数：
        assign_key: 过滤的关键日志信息
        示例：'[2025-08-11 19:29:39.656 +0800][INFO][4234][281467393400832]
        [ham_migrate.cpp:HamMigrateNorth:206] HamMigrate response'
    返回值：日志对应的时间戳信息，忽略时区，结果为毫秒级别
    """
    # 正则匹配时间部分（精确到毫秒）
    time_pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})'
    match = re.search(time_pattern, assign_key)
    if not match:
        raise ValueError("未找到vm_plugin日志的有效时间信息")

    # 提取基础时间部分（不含时区）
    base_time = match.group(1)
    # 解析为本地时间（假设日志时间为服务器本地时区）
    dt = datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S.%f")
    # 转换为毫秒级时间戳（基于本地时间）
    dt = int(dt.timestamp() * 1000)

    return dt


def get_assign_libvirt_log_date(assign_key=None):
    """
    功能：从libvirt日志文件中指定字段的日志获取时间戳信息
    参数：
        assign_key: 过滤的关键日志信息
        示例：2025-08-11 02:22:16.861+0000: 3448:info : remoteDomainMigratePrepare3Params:6396
        : remote DomainMigratePrepare3Params begin"
    返回值：日志对应的时间戳信息，为UTC时区，比其他日志慢8h，结果为毫秒级别
    """
    # 正则匹配时间部分（精确到毫秒），带时区
    time_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\+\d{4})'
    match = re.match(time_pattern, assign_key)
    if not match:
        raise ValueError("未找到libvirt日志的有效时间信息")

    time_str = match.group(1)
    # 解析带时区的时间（需移除毫秒后的+号冲突问题）
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f%z")
    # 转换为毫秒级时间戳（基于UTC时间）
    dt = int(dt.timestamp() * 1000)

    return dt


def get_ham_migrate_rate_value(log_content):
    """
    功能：从qemu目录下的instance日志中的ham热迁移速率信息中获得速率值
    参数：
        log_content: 虚拟机日志目录中过滤出的日志信息
    返回值：非停机阶段的migrate_pages速率，停机后的migrate_pages速率
    """
    log_lines = log_content.splitlines()
    pattern = re.compile(r'HAM:It takes (\d+)\s*us to migrate (\d+)\s*MB')
    results = []
    for line in log_lines:
        match = pattern.search(line)
        if match:
            time_us = int(match.group(1))
            memory_mb = int(match.group(2))
            results.append((time_us, memory_mb))

    # 如果没有找到任何匹配行，则报中断失败
    if len(results) <= 0:
        raise ValueError("解析获取虚拟机instance日志中确定性热迁移HAM热数据搬移速率信息失败")

    downing_mig_times, downing_mig_mem = results[0]
    down_mig_times, down_mig_mem = results[1]
    downing_vm_ham_hotdata_mig_speed = (downing_mig_mem / 1024) / (downing_mig_times / 1000000)
    down_vm_ham_hotdata_mig_speed = (down_mig_mem / 1024) / (down_mig_times / 1000000)

    return downing_vm_ham_hotdata_mig_speed, down_vm_ham_hotdata_mig_speed


def vm_stressapptester(node, stressNum):
    """
    功能：给虚机加压，用的是stressapptest加压工具
    参数：
        node 对应节点执行
        stressNum 加压值
    """
    logger.info("给当前虚机占用内存(加压)")
    node.run({'command': [f'/root/stressapptest -s 1000000 -M {stressNum} -m 1 -W -v > memtest.log 2>&1 &'], 'waitstr': '#'})


def get_service_status(host, service_name):
    status = None
    cmd = f"systemctl status {service_name} --no-pager"
    response = host.run({"command": [cmd]})
    if response.get("stdout") and re.search(r'running', response["stdout"]):
        status = "running"
    return status


def oom_service_status_change(node, status):
    """
    功能：设置oom相关服务sysSentry和xalarmd的状态，前提是环境上已安装
    参数：
        node 对应节点执行
        status 目标状态(start\stop)
    """
    logger.info("检查sysSentry服务状态")
    sysSentry_status = get_service_status(node, "sysSentry")
    xalarmd_status = get_service_status(node, "xalarmd")
    if status == "start":
        if sysSentry_status != "running" or xalarmd_status != "running":
            node.run({'command': ['modprobe sentry_reporter reboot_timeout_ms=300000']})
            node.run({'command': ['modprobe sentry_remote_reporter']})
            node.run({'command': [
                'sentryctl set sentry_remote_reporter --panic_timeout_ms=300000 --kernel_reboot_timeout_ms=300000']})
            node.run({'command': ['systemctl restart xalarmd']})
            node.run({'command': ['systemctl restart sysSentry']})
            node.run({'command': ['sentryctl set sentry_reporter --oom=on']})
    elif status == "stop":
        node.run({'command': ['sentryctl set sentry_reporter --oom=off']})
        node.run({'command': ['systemctl stop sysSentry']})
        node.run({'command': ['systemctl stop xalarmd']})
    time.sleep(30)
    sysSentry_status = get_service_status(node, "sysSentry")
    xalarmd_status = get_service_status(node, "xalarmd")
    return sysSentry_status, xalarmd_status