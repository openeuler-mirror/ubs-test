#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import time
from typing import Tuple, Dict, Callable
from libs.ubturbo.common import basic, env, string_utils
from libs.ubturbo.api import numa


def numastat_vm(node) -> Dict[str, Dict[str, float]]:
    """
    解析numastat -vm输出
    输出示例：
    单位: MB
    {'MemTotal': {'Node 0': 128761.28, 'Node 1': 128531.83}, ...}
    """
    res = basic.run(node, 'numastat -vm')
    table = {}
    if res.stdout:
        lines = iter(res.stdout.split(string_utils.STR_ENTER))
        table_string = ''
        # 解析表头所在列（多表头）
        for index, line in enumerate(lines):
            if 'Node' in line:
                table_string += line + string_utils.STR_ENTER
                break
        for line in lines:
            if line:
                table_string += line + string_utils.STR_ENTER
        tmp_table = string_utils.get_table_content(table_string)
        heads = []
        for row in tmp_table:
            if any(['Node' in i for i in row]):  # 查找表头
                heads = []
                ns = iter(row)
                for i in ns:
                    if 'Node' in i:
                        heads.append(f'{i} {next(ns)}')  # Node n
                    else:
                        heads.append(i)
            elif len(row) == len(heads) + 1:  # 正常数据
                table[row[0]] = table.get(row[0], {})
                for index, value in enumerate(row[1:]):
                    table[row[0]][heads[index]] = float(value)
    return table


def numastat_p(node, pid) -> Dict[str, Dict[str, float]]:
    """
    解析 numastat -cp <pid> 的输出，返回每个字段在每个 NUMA 节点上的值（单位：MB）

    示例返回结构：
    {
        'Heap': {'Node 0': 0.0, 'Node 1': 1.0, ...},
        'Private': {'Node 0': 8.0, ...},
        ...
    }
    """
    res = basic.run(node, f'numastat -cp {pid}')
    table = {}
    if not res.stdout:
        return table

    lines = res.stdout.strip().splitlines()
    node_names = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('Per-node'):
            continue

        # 找表头：以 Node 开头
        if line.startswith("Node"):
            items = line.split()
            node_names = [f"{items[i]} {items[i + 1]}" for i in range(0, len(items) - 1, 2)]
            continue

        # 跳过下划线行等
        if set(line.strip()) <= set("- "):
            continue

        # 正常数据行（Huge/Heap/...）
        parts = line.split()
        if len(parts) < len(node_names) + 2:
            continue

        field = parts[0]
        values = parts[1:-1]  # 去掉最后的 Total 值

        table[field] = {}
        for i, v in enumerate(values):
            table[field][node_names[i]] = float(v)

    return table


def set_huge_pages(node, number, numa_index=0, exclude_obmm=False) -> int:
    """
    配置大页总数,UB代际可选择是否排除OBMM预占用的大页内存
    :param node:
    :param number: 大页数
    :param numa_index: numa节点
    :param exclude_obmm: 是否需要排除OBMM预占用的内存
    :return:
    """
    env_type = env.get_env_type(node)
    if (env_type == env.UB_simulation or env_type == env.UB_hardware) and exclude_obmm:
        used_pages, total_pages = get_huge_pages(node, True, numa_index)
        number += used_pages  # 适配UB代际OBMM会预占一定大页内存的情况，保证分配大页后空闲大页数=预期大页数

    res = basic.run(
        node,
        f'timeout 60s echo {int(number)} > /sys/devices/system/node/node{numa_index}/hugepages/hugepages-2048kB/nr_hugepages',
        timeout=65,
    )
    get_huge_pages(node)  # 检测是否修改成功
    return res.rc


def get_huge_pages(node, return_used=False, numa_index: int = None) -> Tuple[int, int]:
    """
    返回当前大页数
    :param node:
    :param return_used: 是否返回已使用大页数
    :param numa_index: 获取指定numa节点大页数
    :return: (剩余/已使用大页数, 大页总数)
    """
    cmd = 'cat /proc/meminfo'
    if numa_index is not None:
        cmd = f'cat /sys/devices/system/node/node{numa_index}/meminfo'

    res = basic.run(node, cmd)
    meminfo = string_utils.get_table_content(res.stdout, rows=slice(0, -1))
    page_info = [None, None]
    for idx, name in enumerate(['HugePages_Free:', 'HugePages_Total:']):
        for row in meminfo:
            if name in row:
                page_info[idx] = int(row[-1])

    free_pages, total_pages = page_info
    if return_used:
        used_pages = total_pages - free_pages
        return used_pages, total_pages
    else:
        return free_pages, total_pages


def wait_until_mem_stable(
        node,
        target_used_huge_page: int,
        max_sep_huge_pages: int = 200,
        check_sep=10,
        timeout=120,
        used_abs_sep: bool = False,
        func_get_cur_mem: Callable = None,
) -> bool:
    """
    等待大页变化到指定值附近并稳定
    :param node:
    :param target_used_huge_page: 内存大页数接近/小于该值且稳定时，函数退出
    :param max_sep_huge_pages: 与init_used_huge_page相差小于该值的视为接近
    :param check_sep: 检测间隔
    :param timeout: 超时时间
    :param used_abs_sep: 检测时使用
    :param func_get_cur_mem: 获取当前内存量的函数
    :return: 内存是否在timeout时限内降低且稳定
    """
    start_time = time.time()
    last_used_pages = -1000

    def get_cur_mem():
        """默认函数：通过大页获取当前内存量"""
        return get_huge_pages(node, return_used=True)[0]

    func_get_cur_mem = func_get_cur_mem or get_cur_mem

    def check_stable():
        nonlocal last_used_pages
        cur_used_pages = func_get_cur_mem()  # 获取当前内存量
        basic.logger.info(f'预期大页数:{target_used_huge_page} 当前大页数:{cur_used_pages}')

        if used_abs_sep:  # 判断绝对值是否接近
            is_close = abs(cur_used_pages - target_used_huge_page) < max_sep_huge_pages
        else:  # 判断当前大页内存数是否接近或者小于目标值
            is_close = cur_used_pages - target_used_huge_page < max_sep_huge_pages

        if (
                is_close and  # 和未加压时大页数接近
                (abs(cur_used_pages - last_used_pages) < 5)  # 稳定
        ):
            basic.logger.info(f'等待{int(time.time() - start_time)} s后稳定')
            return True
        last_used_pages = cur_used_pages
        return False

    return basic.wait_until(check_stable, timeout=timeout, check_sep=check_sep, msg='内存是否稳定') > 0


def wait_until_huge_stable(
        node,
        numaid_list,
        attribute: str,
        target_used_huge_page: int,
        max_sep_huge_pages: int = 1,
        check_sep=10,
        timeout=600,
        used_abs_sep: bool = True
) -> bool:
    """
    等待{node}节点的{numaid_list}列表上字段{attribute}值的累计值变化到指定值附近并稳定
    :param node:
    :param numaid_list:numaid列表
    :param attribute:可查字段有'MemFree', 'HugePages_Total', 'HugePages_Free', 'MemTotal'
    :param numa_index: 获取指定numa节点大页数
    :param target_used_huge_page: 内存大页数接近/小于该值且稳定时，函数退出
    :param max_sep_huge_pages: 与init_used_huge_page相差小于该值的视为接近
    :param check_sep: 检测间隔
    :param timeout: 超时时间
    :param used_abs_sep: 检测时使用
    :return: 内存是否在timeout时限内降低且稳定
    """
    def func_get_cur_mem():
        sum_of_huge_pages = 0
        for numaid in numaid_list:
            cur_huge_pages = numa.parse_node_numa_attribute(node, numaid, attribute)
            basic.logger.info(f'numa{numaid}的属性{attribute}的当前值:{cur_huge_pages}M')
            sum_of_huge_pages += cur_huge_pages
        basic.logger.info(f'numaid列表为{numaid_list},属性{attribute}的预期值累计：{target_used_huge_page}M,当前累计值{sum_of_huge_pages}M')
        return sum_of_huge_pages

    return wait_until_mem_stable(
        node,
        target_used_huge_page=target_used_huge_page,
        max_sep_huge_pages=max_sep_huge_pages,
        check_sep=check_sep,
        timeout=timeout,
        used_abs_sep=used_abs_sep,
        func_get_cur_mem=func_get_cur_mem,
    )
