#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025
import operator
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import List, Optional


class UbsMemInstance(Enum):
    DISTANCE_DIRECT_NODE = 0
    DISTANCE_HOP_NODE = 1


class UbsMemPerfTp(Enum):
    TP_UBSM_MALLOC = 0
    TP_UBSM_SHM_CREATE = 1


UBSM_SHMEM_OK = 0
UBSM_SHMEM_ERR_PARAM_INVALID = 6010
UBSM_SHMEM_ERR_NOPERM = 6011
UBSM_SHMEM_ERR_MEMORY = 6012
UBSM_SHMEM_ERR_UNIMPL = 6013
UBSM_CHECK_RESOURCE_ERROR = 6014
UBSM_ERR_MEMLIB = 6015
UBSM_ERR_NO_NEEDED = 6016
UBSM_SHMEM_ERR_NOT_FOUND = 6020
UBSM_SHMEM_ERR_ALREADY_EXIST = 6021
UBSM_ERR_MALLOC_FAIL = 6022
UBSM_ERR_RECORD = 6023
UBSM_ERR_IN_USING = 6024
UBSM_ERR_NET = 6040
UBSM_ERR_UBSE = 6050
UBSM_ERR_OBMM = 6051
UBSM_ERR_LOCK_NOT_SUPPORTED = 6060
UBSM_ERR_LOCK_ALREADY_LOCKED = 6061
UBSM_ERR_DLOCK = 6062
UBSM_ERR_BUFF = 6099

UBSM_FLAG_CACHE = 0
UBSM_FLAG_WITH_LOCK = 1
UBSM_FLAG_NONCACHE = 2
UBSM_FLAG_WR_DELAY_COMP = 4
UBSM_FLAG_ONLY_IMPORT_NONCACHE = 8
UBSM_FLAG_MEME_ANONYMOUS = 16
UBSM_FLAG_MMAP_HUGETLB_PMD = 32
UBSM_FLAG_MALLOC_WITH_NUMA = 64

PROT_NONE = 0
PROT_READ = 1
PROT_WRITE = 2
PROT_EXEC = 4

MAP_SHARED = 0x01
MAP_FIXED = 0x10
MAP_ANONYMOUS = 0x20
MAP_FIXED_NOREPLACE = 0x100000

URGENT_MALLOC_TIME = 10
NORMAL_MALLOC_TIME = 3000

MAX_INT32 = 2**31 - 1
MAX_UINT32 = 2**32 - 1

@dataclass
class AddrDesc:
    rc: int
    addr: str


@dataclass
class UbsmemRegionNodeDesc:
    host_name: str = ""
    affinity: bool = False


@dataclass
class UbsmemRegionAttributes:
    host_num: int = 0
    hosts: List[UbsmemRegionNodeDesc] = field(default_factory=list)

    def to_json(self) -> dict:
        data = asdict(self)
        data["hosts"] = [asdict(h) for h in self.hosts]
        return data


@dataclass
class UbsmemRegionDesc:
    region_name: str = ""
    size: int = 0
    host_num: int = 0
    hosts: List[UbsmemRegionNodeDesc] = field(default_factory=list)


@dataclass
class UBSMemLocation:
    slot_id: int = 0
    socket_id: int = 0
    numa_id: int = 0
    port_id: int = 0

    def to_json(self) -> dict:
        return asdict(self)

@dataclass
class UBSMemProvider:
    host_name: str = ""
    socket_id: int = 0
    numa_id: int = 0
    port_id: int = 0

@dataclass
class UBSMemShmInfo:
    """共享内存信息"""
    name: str = ""
    size: int = 0
    mem_num: int = 0
    mem_unit_size: int = 0


@dataclass
class MemLeaseInfo:
    __slots__ = ("name", "pid", "uid", "gid", "size", "numa_id", "mem_list")
    name: str
    pid: int
    uid: int
    gid: int
    size: int
    numa_id: int
    mem_list: List[int]

    def __eq__(self, other):
        if not isinstance(other, MemLeaseInfo):
            return False
        get_attrs = operator.attrgetter(*MemLeaseInfo.__slots__)
        return get_attrs(self) == get_attrs(other)


@dataclass
class ShmAccount:
    name: str
    borrow_node: int
    provider: int
    size: int
    lend_numa: int
    lend_socket: int
    shm_status: str


@dataclass
class BorrowAccount:
    size: int
    borrow_node: int
    lend_node: int
    lend_numa: int
    lend_socket: int


@dataclass
class NodeDesc:
    node_id: Optional[int] = None


@dataclass
class ShmAccessDelay:
    copy_size: int
    min: int
    max: int
    average: int
    percent_95: int
    percent_99: int


@dataclass
class ClusterStatistic:
    slot_id: int
    socket: int
    numa: int
    mem_total: int
    mem_free: int
    mem_borrow: int
    mem_lend: int


@dataclass
class ShmemInfo:
    name: str
    size: int
    mem_num: int
    mem_unit_size: int
    mem_id_list: list


@dataclass
class ShmemBaseInfo:
    name: str
    size: int


@dataclass
class Region:
    region: int
    hostnames: List[str]


@dataclass
class PerfLatency:
    total: float
    avg: float
    max: float


@dataclass
class NodeCluster:
    node_id: int
    role: str


@dataclass
class CpuTopo:
    host_name: str
    slot_id: int
    socket: int
    port_id: int
    interface_name: str
    peer_host: str
    peer_slot: int
    peer_socket: int
    peer_port_id: int
    peer_interface_name: str