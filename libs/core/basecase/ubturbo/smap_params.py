import dataclasses
from dataclasses import dataclass
from typing import List
from functools import wraps


def stringify_members(cls):
    # 定义__str__方法，负责将成员转化为字符串并拼接
    @wraps(cls)
    def __str__(self):
        # 获取对象的成员，递归地处理
        def serialize(value):
            if isinstance(value, list):
                # 如果成员是列表，则递归序列化每个元素
                return " ".join(serialize(item) for item in value)
            else:
                # 如果是基本类型，直接转为字符串
                return str(value)

        # 获取所有成员并进行序列化
        return " ".join(serialize(getattr(self, attr.name)) for attr in dataclasses.fields(self))

    # 动态添加__str__方法到类
    cls.__str__ = __str__
    return cls


@dataclass
class SmapTrackInfo(object):
    hpa: int
    freq: int


@dataclass
@stringify_members
class EnableNodeMsg:
    enable: int
    nid: int


@dataclass
@stringify_members
class MigrateOutPayload:
    dest_nid: int
    pid: int
    ratio: int


@dataclass
@stringify_members
class MigrateOutMsg:
    payload: List[MigrateOutPayload]


@dataclass
@stringify_members
class MigrateOutSizePayload:
    dest_nid: int
    pid: int
    ratio: int
    mem_size: int
    migrate_mode: int


@dataclass
@stringify_members
class MigrateOutSizeMsg:
    payload: List[MigrateOutSizePayload]


@dataclass
@stringify_members
class MigrateBackPayload:
    src_nid: int
    dest_nid: int
    pa_start: int
    pa_end: int


@dataclass
@stringify_members
class MigrateBackMsg:
    payload: List[MigrateBackPayload]


@dataclass
@stringify_members
class RemovePayload:
    pid: int


@dataclass
@stringify_members
class RemoveMsg:
    payload: List[RemovePayload]


@dataclass
@stringify_members
class QueryPayload:
    ratio: float
    pid: int


@dataclass
@stringify_members
class QueryMsg:
    ret: int
    payload: List[QueryPayload]


@dataclass
class SmapAddr:
    pa_start: int
    pa_end: int

    def __eq__(self, other):
        if not isinstance(other, SmapAddr):
            return NotImplemented
        return (self.pa_start, self.pa_end) == (other.pa_start, other.pa_end)

    def __hash__(self):
        return hash((self.pa_start, self.pa_end))


@dataclass
class ObmmDeviceInfo:
    mem_id: int
    numa_id: int
    pa: int
    size: int


@dataclass
class RedisRes:
    set: int
    get: int


@dataclass
@stringify_members
class MigrateNumaPayload:
    pa_start: int
    pa_end: int


@dataclass
@stringify_members
class MigrateNumaMsg:
    src_nid: int
    dest_nid: int
    count: int
    payload: List[MigrateNumaPayload]


@dataclass
@stringify_members
class MigratePidNumaPayload:
    pid: int
    srcNid: int
    destNid: int
    ratio: int
    memSize: int


@dataclass
@stringify_members
class MigratePidNumaMsg:
    count: int
    payload: List[MigratePidNumaPayload]


@dataclass
@stringify_members
class ProcessConfigPayload:
    pid: int
    type: int
    ratio: int
    l1_node: int
    l2_node: int
    scan_type: int
    scan_time: int


@dataclass
@stringify_members
class ProcessConfig:
    ret: int
    outLen: int
    payload: List[ProcessConfigPayload]