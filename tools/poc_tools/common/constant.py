# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from enum import StrEnum, IntEnum


class VmStatusEnum(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"


class MemConvertEnum(IntEnum):
    HUGE_PAGE_TO_MB = 2
    HUGE_PAGE_TO_KB = 2048
    MB_TO_KB = 1024
    GB_TO_MB = 1024
    GB_TO_KB = 1024 * 1024
    TB_TO_MB = 1024 * 1024 * 1024


class MemBorrowLimitParam(IntEnum):
    MAX_BORROW_NUMA_NUM = 8
    MAX_BORROW_MEM_PER_SOCKET = 512
    MEM_BORROW_UNIT_MB = 128
    MEM_BORROW_UNIT_GB = 1024


class CollectHugePageType(IntEnum):
    COLLECT_HUGE_PAGE_GB = 1024
    COLLECT_HUGE_PAGE_MB = 2


class AsyncTaskStatus(IntEnum):
    NOT_EXIST = 0  # Invalid task ID / not stored in database
    RUNNING = 1  # Task is running
    SUCCESS = 2  # Task executed successfully
    FAILED = 3  # Task execution failed
