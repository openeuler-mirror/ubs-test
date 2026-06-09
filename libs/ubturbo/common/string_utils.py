#! /bin/python3
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2025

import re
from typing import List, Optional
import random
import string


STR_ENTER = '\n'  # 返回内容的换行符
DEFAULT_WAIT_STRING = '@#>'  # 终端指示符


def get_table_content(string_: str, rows: Optional[slice] = None, cols: Optional[slice] = None) -> List[List[str]]:
    """
    解析文本形式的表格，分隔符为若干空格
    示例：
        解析ls结果
        stdout = run(node, 'ls').stdout
        content = get_table_content(stdout)  # [['file1', 'file2']]
    :param string_: 字符串
    :param rows: 行切片
    :param cols: 列切片
    :return: 二维列表
    """
    rows = rows or slice(None)
    cols = cols or slice(None)
    tb = string_.split(STR_ENTER)
    tb = tb[rows]
    tb = [[j for j in i.split(' ') if j][cols] for i in tb]
    return tb


def strip_wait_string(string_, user_name, wait_string=DEFAULT_WAIT_STRING) -> str:
    """去除末尾的终端指示符"""
    terminal_hint = f'{user_name}{wait_string}'
    if string_.endswith(terminal_hint):
        string_ = string_[:-len(terminal_hint)]
    return string_


def generate_random_string(length: int, source=None) -> str:
    source = source or string.ascii_letters
    return ''.join(random.choice(source) for _ in range(length))


def into_template_name(fn: str) -> str:
    """
    文件名更改，用于生成临时文件名
    示例：
        test1.txt -> test1_%s.txt
    :param fn: 原始文件名
    :return: 增加_%s后文件名
    """
    sps = fn.split('.')
    sp2 = ['.'.join(sps[:-1]), sps[-1]]
    return f'{sp2[0]}_%s.{sp2[1]}'


def get_digit_of_str(line):
    """
    获取字符串中的所有数字，并以int数组形式返回
    :param line:获取数字的字符串
    """
    results = []
    for i in line.split():
        numbers = re.findall(r'\d+\.?\d*', i)
        if len(numbers) >= 1 and '.' in numbers[0]:
            results.append(int(float(numbers[0])))
        elif len(numbers) >= 1 and numbers[0].isdigit():
            results.append(int(numbers[0]))

    return results
