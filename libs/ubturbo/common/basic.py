#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import time
from typing import Callable

from libs.utils.logger_compat import Log
from libs.ubturbo.common import env, string_utils

logger = Log.getLogger("common_logger")


class Result:
    """
    封装返回结果
    1. stdout、stderr去除终端提示符
    2. stdout、stderr为空时返回空字符串
    3. 新增output，通过output拼接所有返回内容，而不需要额外判断返回值
    """

    def __init__(self, info, user_name):
        """
        :param info: HostBase.run返回的结果字典
        :param user_name: 用户名，用于去除末尾终端提示符
        """
        self.stdout = ''  # 标准输出流
        self.stderr = ''  # 标准错误流
        self.rc = 0  # 返回值
        # 将字典转换为对象变量 如: res['stdout'] -> res.stdout
        self.__dict__.update(info)
        # 标准流为None时转换为空字符串，等价且方便判断
        self.stdout = self.stdout or ''
        self.stderr = self.stderr or ''
        # 去除标准流终端提示符
        self.stdout = string_utils.strip_wait_string(self.stdout, user_name)
        self.stderr = string_utils.strip_wait_string(self.stderr, user_name)
        # 替换错误的回车符
        self.stdout = self.stdout.replace('\r\n', string_utils.STR_ENTER)
        self.stderr = self.stderr.replace('\r\n', string_utils.STR_ENTER)

        self.output = self.stdout + self.stderr

    def __repr__(self):
        return (
            f'stdout:\n{self.stdout}\n'
            f'stderr:\n{self.stderr}\n'
            f'rc:{self.rc}\n'
        )


def run(
        node,
        cmd: str,
        waitstr: str = None,
        timeout: int = None,
        returnCode: bool = True,
        outside_kwargs: dict = None,
        **kwargs
) -> Result:
    """
    封装UniAutos框架Linux.run函数，降低耦合，增加代码可读性
    示例：
        result = run(node, 'ls /')  # 查看根目录文件
        stdout = result.stdout  # 获取标准输出内容
        stderr = result.stderr  # 获取标准错误内容
        return_code = result.rc  # 获取返回值

    :param node: 节点对象
    :param cmd: bash命令
    :param waitstr: 匹配返回字符串 标准流中出现该字符串时，结束当前命令等待 默认为 'root@#>'
                    技巧：
                        1. 可以通过|符号分隔多个待匹配字符串
                        2. 可以使用正则表达式
    :param timeout: 命令超时时间
    :param returnCode: 是否获取返回值（是否在命令后执行echo $?）
    :param outside_kwargs: 传入node.run函数内的具名参数字典
    :param kwargs: UniAutos run函数其他具名参数，如input (示例: run(node, 'touch a.txt; rm a.txt', input=['y']))
    :return: 返回结果
    """
    waitstr = waitstr or f'{node.username}{string_utils.DEFAULT_WAIT_STRING}'
    outside_kwargs = outside_kwargs or {}
    timeout = timeout or {
        env.UB_simulation: 1200,  # UB仿真默认超时为25分钟
    }.get(env.get_env_type(node), 30)  # 默认为30秒

    res_dict = node.run(
        {
            'command': [cmd],
            'waitstr': waitstr,
            'timeout': timeout,
            'returnCode': False,
            **kwargs,
        },
        **outside_kwargs
    )

    if returnCode:
        # 运行echo $? 获取返回值
        res = node.run(
            {
                'command': ['echo $?'],
                'waitstr': waitstr,
                'timeout': 60,
                'returnCode': False,
            }
        )
        res = Result(res, node.username)
        return_code_stdout = res.stdout.strip()

        if return_code_stdout.isdigit():  # 正常获取返回值
            return_code = int(return_code_stdout)
        else:  # 非数字返回值
            return_code = 127
        # 存入结果中
        res_dict['rc'] = return_code

    return Result(res_dict, node.username)


def wait_until(condition_func: Callable, check_sep=5, timeout=60, expect_times=1, msg: str = '',
               timeout_callback: Callable = None) -> int:
    """
    循环等待并检测，直到函数返回值累计达到要求
    示例：
        cmd = 'sleep 20'
        basic.run(self.node, f'{cmd} &')  # 后台执行

        def condition():
            res = system.find_process(self.node, cmd)  # 判断是否存在该进程
            print(res)
            return not res

        # 等待后台命令sleep 20执行完毕
        basic.wait_until(
            condition,  # 也可以使用lambda表达式
        )

    :param condition_func: 条件计算函数，无参数，返回值必须为布尔值或整数
                            True: 次数加1
                            False: 加0
                            整数：次数加上整数
    :param check_sep: 检查间隔 单位：秒
    :param timeout: 超时时间 单位：秒
    :param expect_times: 预计符合次数
    :param msg: 检测对象说明
    :param timeout_callback: 超时未达到预期的回调函数，无参数，无返回值，如: lambda: (_ for _ in ()).throw(Exception("异常信息"))
    :return: 条件累计出现次数
    """
    correspond_times = 0
    start_time = time.time()
    time_waited = 0

    correspond_times += condition_func()  # 调用后随即执行一次
    while (
            correspond_times < expect_times and  # 出现次数未达到预期
            time_waited < timeout  # 未超时
    ):
        time.sleep(check_sep)
        correspond_times += condition_func()
        time_waited = int(time.time() - start_time)
        logger.info(
            f'检测{msg}中，实际出现{correspond_times}次，预期{expect_times}次，'
            f'已等待{time_waited // 60:02}:{time_waited % 60:02}/{timeout // 60:02}:{timeout % 60:02} '
            f'等待间隔{check_sep} s'
        )
    logger.info(f'检测{msg}结束，实际出现{correspond_times}次，预期{expect_times}次')
    if time_waited >= timeout:
        logger.info(f'超时{timeout}秒后退出')
        if timeout_callback is not None:
            timeout_callback()
    return correspond_times

