import dataclasses
import random
import string
import time
from datetime import datetime, timedelta
from functools import wraps


def generate_random_key(key_len: int) -> str:
    characters = string.ascii_letters + string.digits
    random_str = ''.join(random.choice(characters) for _ in range(key_len))
    return random_str


def calculate_address(start_addr: str, offset: int) -> str:
    """
    进行地址偏移转换
    :param start_addr: 16进制起始地址
    :param offset: 偏移量
    :return: 16进制计算结果
    """
    start = int(start_addr, 16)
    return hex(start + offset)


def round_down_to_align(size: int, alignment: int) -> int:
    """
    向下以指定单位对齐
    :param size: 原始大小
    :param alignment: 对齐单位
    :return:
    """
    return int((size // alignment) * alignment)


def stringify_members(cls):
    @wraps(cls)
    def __str__(self):
        def serialize(value):
            if isinstance(value, list):
                return " ".join(serialize(item) for item in value)
            elif isinstance(value, bool):
                return str(int(value))
            else:
                return str(value)

        return " ".join(serialize(getattr(self, attr.name)) for attr in dataclasses.fields(self))

    cls.__str__ = __str__
    return cls


def get_now_time_str() -> str:
    utc_timestamp = time.time()
    beijing_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
    return beijing_time.strftime("%Y-%m-%d_%H:%M:%S.%f")[:-3]


def pop_random_element(lst):
    """随机选择一个元素并从列表中移除"""
    if not lst:
        return None
    element = random.choice(lst)
    lst.remove(element)
    return element


def get_random_char() -> str:
    """
    随机获取0-9、a-z、A-Z中的一个字符
    """
    chars = string.digits + string.ascii_lowercase + string.ascii_uppercase
    return random.choice(chars)