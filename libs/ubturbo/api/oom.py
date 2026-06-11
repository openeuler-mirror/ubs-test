#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

from libs.ubturbo.common import basic
import libs.ubturbo.api.system as system

OOM_MESSAGE = 'got lowmem message'
OOM_MESSAGE_HUGE = r'got lowmem message.*?sync=1 reason=2'


def get_timestamp(node):
    """
    获取系统启动至今的时间戳
    cat /proc/uptime
    :param node:
    :return: 获取到的时间戳
    """
    res = basic.run(node, f'cat /proc/uptime')
    timestamp = res.stdout.split()[0]
    return timestamp


def filter_dmesg(node, timestamp, word='got lowmem message'):
    """
    解析从某段时间起的dmesg中是否包含指定字符串
    dmesg | awk -v start="timestamp" '{timestamp = gensub(/.*\[([ 0-9.]+)\].*/, "\\1", 1);
    if (timestamp + 0 >= start) {print $0;}}' | grep 'word'
    :param node:
    :param timestamp: 起始时间戳
    :param word: 匹配关键字
    :return:
    """
    res = basic.run(
        node,
        f"dmesg | awk -v start=\"{timestamp}\" '{{timestamp = gensub(/.*\\[([ 0-9.]+)\\].*/, \"\\\\1\", 1); "
        f"if (timestamp + 0 >= start) {{print $0;}}}}' | grep '{word}'"
    )
    return res.stdout


def filter_dmesg_oom(node, timestamp):
    """
    sh filter_dmesg.sh
    :param node:
    :param timestamp:
    :return:
    """
    return filter_dmesg(node, timestamp, word='oomtest')


def check_obmm_memory_borrowing(at_basecase, tmp_timestamp, vm_count):
    """
    检查特定时间点后的 dmesg 日志，判断 obmm 是否成功发出内存借用消息。
    :param node:
    :param tmp_timestamp: 检查日志的起始时间戳
    :param vm_count: 虚拟机的个数，根据虚拟机个数 * 2 作为验证标准
    """
    # 获取特定时间点后的日志
    log_output = filter_dmesg(at_basecase.node, tmp_timestamp) or ''

    # 统计日志中 "got oom_message" 出现的次数
    oom_count = log_output.count("got lowmem message")

    # 计算期望的消息次数，虚拟机个数 * 1
    expected_count = vm_count * 1

    basic.logger.info(f'oom_count: {oom_count}, expected_count: {expected_count}')
    # 判断是否成功发出内存借用消息
    at_basecase.assertEqual(oom_count, expected_count, f"OBMM 发出内存借用消息失败！OBMM 未成功发出足够的内存借用消息，仅出现 {oom_count} 次 'got lowmem message'，期望出现 {expected_count} 次")


# 未产生dmesg
def check_obmm_memory_unborrowing(at_basecase, tmp_timestamp):
    """
    检查特定时间点后的 dmesg 日志，判断 obmm 是否成功发出内存借用消息。
    :param node:
    :param tmp_timestamp: 检查日志的起始时间戳
    :param vm_count: 虚拟机的个数，根据虚拟机个数 * 2 作为验证标准
    """
    # 获取特定时间点后的日志
    log_output = filter_dmesg(at_basecase.node, tmp_timestamp)
    basic.logger.info("==========================================")
    basic.logger.info(log_output)

    times = 0
    if log_output:
        for _ in log_output.split('\n')[:-1]:
            times += 1

    basic.logger.info(f'共出现 {times} 次 got lowmem message')

    # 判断是否成功发出内存借用消息
    at_basecase.assertTrue(
        times == 0,
        f'OBMM 成功发出内存借用消息，共出现 {times} 次 got lowmem message，不符合预期的 0 次'
    )


def check_oom_OS(node, tmp_timestamp):
    # 获取特定时间点后的日志
    log_output = filter_dmesg_oom(node, tmp_timestamp)
    basic.logger.info(f'log_output:{log_output}')
    if 'oomtest normor ret 0' in log_output:
        if 'oomtest repeat ret 0' in log_output:
            basic.logger.info("重复注册钩子成功")
            return 0
        elif 'oomtest repeat ret' in log_output:
            basic.logger.info("重复注册钩子失败")
            return 0
        if 'oomtest exit uninit ret 0' in log_output:
            basic.logger.info("重复注销钩子成功")
            exit(1)
        elif 'oomtest exit uninit ret' in log_output:
            basic.logger.info("重复注册钩子失败")
            return 0
        if 'oomtest exit normal ret 0' in log_output:
            basic.logger.info("调用register_reclaim_notifier注册钩子，调用unregister_reclaim_notifier去注销钩子")
            return 0
    elif 'oomtest null ret 0' in log_output:
        basic.logger.info("注册空钩子成功")
        return 0

