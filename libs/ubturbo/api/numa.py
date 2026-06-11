#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025
import re
from libs.ubturbo.common import basic
from libs.ubturbo.common.string_utils import STR_ENTER, get_digit_of_str


def get_oom_water_mark(node, numa_id):
    """
    获取指定NUMA NODE的内存水线信息
    :param node:
    :param numa_id: NUMA NODE ID
    :return: water_mark dictionary,其成员分别为min,low,high水线,float类型,单位为MB
    """
    pattern = f"'Node {numa_id}, zone.* Normal'"
    cmd = f"cat /proc/zoneinfo | grep -E {pattern} -A 75 | grep 'min' -A 2 | awk '{{print $2}}'"
    res = basic.run(node, cmd)
    if res.rc != 0:
        basic.logger.error(f"NUMA {numa_id}获取水线数据失败")
        raise Exception(f"NUMA {numa_id}获取水线数据失败")
    water_mark_str = res.stdout.split()

    # 将水线单位由pages转为MB
    water_mark = {}
    water_mark['min'] = float(water_mark_str[0]) * 4 / 1024
    water_mark['low'] = float(water_mark_str[1]) * 4 / 1024
    water_mark['high'] = float(water_mark_str[2]) * 4 / 1024
    return water_mark


def get_numa_count(node):
    res = basic.run(node, "numastat -m | grep -o Node", timeout=100)
    return res.stdout.count('Node')


def get_numa_count_with_cpu(node):
    res = basic.run(node, "lscpu | grep \"NUMA node[0-9]\" | grep -v \"CPU(s):\\s*$\" | wc -l", timeout=3*60)
    numa_counts = int(res.stdout.strip())
    basic.logger.info(f"=====本地numa数量为: {numa_counts}=====")
    if numa_counts % 2 != 0:
        basic.logger.warn(f"查询到numa数量为奇数--{numa_counts}")
    return numa_counts


def get_numa_mem(node, numa_id):
    """
    获取指定NUMA NODE的内存信息
    :param node:
    :param numa_id: NUMA NODE ID
    :return: meminfo dictionary，其成员分别为total、free、used，float类型，单位MB
    """
    numa_count = get_numa_count(node)
    if numa_id >= numa_count:
        basic.logger.error(f"numa id参数不合法,numa id = {numa_id}, numa count = {numa_count}")
        raise Exception(f"numa id参数不合法,numa id = {numa_id}, numa count = {numa_count}")

    res = basic.run(node, "numastat -m | grep Mem | awk '{{print ${}}}'".format(numa_id + 2))
    mems = res.stdout.split()
    mem_info = {}
    mem_info['total'] = float(mems[0])
    mem_info['free'] = float(mems[1])
    mem_info['used'] = float(mems[2])
    return mem_info


def get_numa_huge_mem(node, numa_id):
    """
    获取指定NUMA NODE的大页内存信息
    :param node:
    :param numa_id: NUMA NODE ID
    :return: meminfo dictionary，其成员分别为total、free、used，float类型，单位MB
    """
    res = basic.run(node, "numastat -m | grep HugePages_ | awk '{{print ${}}}'".format(numa_id + 2))
    mems = res.stdout.split()
    mem_info = {}
    mem_info['total'] = int(float(mems[0]))
    mem_info['free'] = int(float(mems[1]))
    mem_info['used'] = int(float(mems[2]))
    return mem_info


def get_numa_cpuset(node, numa_id):
    """
    获取指定NUMA NODE对应的CPU核心，例：get_numa_cpuset(node, 3)，返回"7-8"
    :param node:
    :param numa_id: NUMA NODE ID
    :return: 字符串，cpuset，例："7-8"
    """
    numa_count = get_numa_count(node)
    if numa_id >= numa_count:
        basic.logger.error(f"numa id参数不合法,numa id = {numa_id}, numa count = {numa_count}")
        raise Exception(f"numa id参数不合法,numa id = {numa_id}, numa count = {numa_count}")
    cmd = f"lscpu | grep 'NUMA node{numa_id} CPU(s)' | awk -F: '{{print $2}}' | tr -d ' ' | tr ',' '-'"
    res = basic.run(node, cmd)
    return res.stdout.strip(STR_ENTER)


def apply_pre_online_memory(node, address, size, numa_id):
    """
    执行内存预上线，例：apply_pre_online_memory(node, '0x10000000', '0x100000', 5)
    :param node:
    :param address: 预上线的内存首地址
    :param size: 预上线内存段大小，16进制
    :param numa_id: 该段内存预上线的NUMA ID
    """
    basic.run(node, "cd /sys/kernel/debug/numa_remote")
    basic.run(node, f"echo {address} > addr")
    basic.run(node, f"echo {size} > size")
    basic.run(node, f"echo {numa_id} > node")
    basic.run(node, f"echo 1 > pre-online", timeout=100)


def apply_offline_memory(node, address, size, numa_id):
    """
    下线已上线的内存，例：apply_offline_memory(node, '0x10000000', '0x100000', 5)
    :param node:
    :param address: 已上线的内存首地址
    :param size: 已上线内存段大小，16进制
    :param numa_id: 该段内存对应的NUMA ID
    """
    basic.run(node, "cd /sys/kernel/debug/numa_remote")
    basic.run(node, f"echo {address} > addr")
    basic.run(node, f"echo {size} > size")
    basic.run(node, f"echo {numa_id} > node")
    basic.run(node, f"echo 1 > offline", timeout=100)


def get_obmm_mempool_total_ub(node):
    """
    获取obmm为ub场景设置的预留借用内存总大小，非ub场景返回0
    :param node:
    :return: 总预留内存大小，单位GB
    """
    size = 0
    ret = basic.run(node, "cat /sys/module/obmm/parameters/mempool_size").stdout.strip(STR_ENTER)
    number = re.findall(r'\d+', ret)
    if number:
        size = int(number[0])
        basic.logger.info(f"当前ub环境蓄水池预留内存大小为{size}GB")
    return size


def get_obmm_mempool_preNuma_ub(master):
    """
    获取obmm为ub场景设置的预留借用内存,在每个本地numa上的大小，非ub场景返回0，执行时需保证无远端Numa
    :param master: 主节点node
    :return: 每个numa预留内存大小，单位MB
    """
    # 获取UB环境下obmm预留内存池大小,当前默认单位为G
    ub_reserve_mem_size = 0
    numa_count = get_numa_count(master)
    ret = basic.run(master, "cat /sys/module/obmm/parameters/mempool_size").stdout.strip(STR_ENTER)
    number = re.findall(r'\d+', ret)
    if number:
        ub_reserve_mem_size = int(number[0]) * 1024 // numa_count
        basic.logger.info(f"当前ub环境蓄水池预留内存大小为{number[0]}GB, 每个numa上各有{ub_reserve_mem_size}MB")
    return ub_reserve_mem_size


def get_numaInfos(node, delete_numa_which_memtotal_is_0=True):
    """
    :param delete_numa_which_memtotal_is_0:当设置为True时，会从节点numa信息中删除memTotal=0的numa
    """
    # 获取节点numa信息
    res = basic.run(node, 'numastat -vmc').stdout
    pattern = r'Node \d+'
    match_attribute = ['MemFree', 'HugePages_Total', 'HugePages_Free', 'MemTotal']
    numa_nodes_line = basic.run(node, 'numastat -cvm | grep Node').stdout
    numa_nodes_matches = re.findall(pattern, numa_nodes_line)
    numa_nodes = [{"name": node_name} for node_name in numa_nodes_matches]
    basic.logger.info(numa_nodes)
    for attribute in match_attribute:
        attribute_line = basic.run(node, f'numastat -cvm | grep {attribute}').stdout
        values = attribute_line.split()
        for index in range(1, len(values) - 1):
            numa_node = numa_nodes[index - 1]
            numa_node[attribute] = int(values[index])
    if delete_numa_which_memtotal_is_0:
        for numa_node in numa_nodes:
            if numa_node['MemTotal'] == 0:
                numa_nodes.remove(numa_node)
    basic.logger.info(numa_nodes)
    return numa_nodes


def parse_node_numa_attribute(node, numaid, attribute):
    """
    解析{node}节点的numa信息
    :param node
    :param numaid：numa的id，例如0,1,2,3
    :param attribute:可以查询的属性有'MemFree', 'HugePages_Total', 'HugePages_Free', 'MemTotal'
    :return:返回{node}节点的numa{numaId}的属性{attribute}的值
    """
    numas_info = get_numaInfos(node)
    numa_info = [d for d in numas_info if int(''.join(filter(str.isdigit, d.get("name")))) == int(numaid)][0]
    attribute_value = numa_info[attribute]
    return attribute_value


def get_num_of_local_numa(node):
    """
    获取{node}节点的本地numa数量
    :return num:返回本地numa数量
    """
    res = basic.run(node, 'lscpu | grep "NUMA node(s)"').stdout
    num = res.strip().split()[-1]
    return int(num)


def get_cpu_num(node):
    cpu_nums = int(basic.run(node, 'nproc').stdout.strip())
    basic.logger.info(f"=====cpu数量为: {cpu_nums}=====")
    return cpu_nums


def get_huge_of_specific_numa_on_vm(node, pid, numa_id):
    """
    获取虚机上特定numa的huge，并以不小于0的int型数据返回，如0，2048,如果输入的numa_id不存在则返回-1
    :param node:创建虚机的节点
    :param pid:虚机id
    :param numa_id:特定numa的numa_id,例如：0、1、2、3、4、5、6、7、8
    """
    ret = basic.run(node, "numastat -p " + str(pid), timeout=300)
    if ret.rc != 0:
        raise Exception("numastat -p命令failed!")
    lines = ret.stdout.split(STR_ENTER)
    # 初始化结果字典
    result = {}
    # 遍历每一行，寻找包含 "Huge" 的行
    key_word = []
    values = []
    for line in lines:
        if 'Node' in line:
            # 分割行中的数值
            key_word.extend(get_digit_of_str(line))
        if 'Huge' in line:
            values.extend(get_digit_of_str(line))
    len_key_word = len(key_word)
    for i in range(len_key_word):
        result[key_word[i]] = values[i]
    basic.logger.info(f'解析虚机{pid}的numa信息：{result}')

    if numa_id not in key_word:
        return -1

    return result.get(numa_id, 'Not exist')


def get_socket_ids(node):
    """获取当前节点所有socket_id，当前都是2socket系统"""
    cpus = get_cpu_num(node)
    socket_ids = []
    socket0_id = int(basic.run(node, 'cat /sys/devices/system/cpu/'
                                     'cpu0/topology/physical_package_id').stdout.strip())
    socket1_id = int(basic.run(node, f'cat /sys/devices/system/cpu/'
                                     f'cpu{cpus // 2}/topology/physical_package_id').stdout.strip())
    socket_ids.append(socket0_id)
    socket_ids.append(socket1_id)
    basic.logger.info(f"=====socket_ids为: {socket_ids}=====")
    return socket_ids


def match_socket_numa(node):
    """按照numa数量平分给每个socket的原则，建立socket <--> numa双向映射。
    例如：
    2socket4numa，返回
    sokcet2numa = {socket_id0: [0, 1], socket_id1: [2, 3]}
    numa2socket = {0: socket_id0, 1: socket_id0, 2: socket_id1, 3: socket_id2}
    """
    socket2numa = {}
    numa2socket = {}

    socket_ids = get_socket_ids(node)  # e.g. [0, 1]
    local_numa_counts = get_numa_count_with_cpu(node)  # e.g. 4
    numa_per_socket = local_numa_counts // len(socket_ids)

    numa_id = 0
    for socket_id in socket_ids:
        # 给当前 socket 分配 numa
        numa_list = list(range(numa_id, numa_id + numa_per_socket))
        if local_numa_counts == 2:  # 2numa填充为[0, 0] [1, 1]减少代码适配量
            numa_list = [numa_id, numa_id]
        socket2numa[socket_id] = numa_list

        # 同时建立 numa->socket 的反向映射
        for nid in numa_list:
            numa2socket[nid] = socket_id

        numa_id += numa_per_socket

    basic.logger.info(f"=====socket2numa: {socket2numa}=====")
    basic.logger.info(f"=====numa2socket: {numa2socket}=====")
    return socket2numa, numa2socket


def get_cluster_cna2socket(node_list):
    socket_ids = get_socket_ids(node_list[0])
    cna2socket = {}
    for node in node_list:
        cna0 = basic.run(node, 'cat /sys/devices/ub_bus_controller0/00001/primary_cna').stdout.strip()
        cna1 = basic.run(node, 'cat /sys/devices/ub_bus_controller1/00002/primary_cna').stdout.strip()
        cna2socket[int(cna0, 0)] = socket_ids[0]
        cna2socket[int(cna1, 0)] = socket_ids[1]
    basic.logger.info(f"=====cna2socket: {cna2socket}=====")
    return cna2socket
