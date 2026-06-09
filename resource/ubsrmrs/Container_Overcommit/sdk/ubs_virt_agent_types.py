#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
# virtagent is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
import ctypes

# ========== 常量 ==========
SDK_NO_16 = 16
SDK_NO_64 = 64
SDK_NO_128 = 128
SDK_NO_2048 = 2048


# ========== 基础结构体 ==========
# src_location_t
class SrcLocationT(ctypes.Structure):
    _fields_ = [
        ("socketId", ctypes.c_int),
        ("numaId", ctypes.c_int),
    ]


# borrow_param_t
class BorrowParamT(ctypes.Structure):
    _fields_ = [
        ("srcNid", ctypes.c_char * SDK_NO_16),
        ("srcLocations", SrcLocationT * SDK_NO_16),
        ("srcLocationsSize", ctypes.c_size_t),
    ]


# watermark_t
class WatermarkT(ctypes.Structure):
    _fields_ = [
        ("highWaterMark", ctypes.c_uint16),
        ("lowWaterMark", ctypes.c_uint16),
    ]


# pid_param
class PidParam(ctypes.Structure):
    _fields_ = [
        ("srcNid", ctypes.c_char * SDK_NO_16),
        ("pids", ctypes.c_int * SDK_NO_2048),  # pid_t → int (Linux 默认是 int)
        ("pids_size", ctypes.c_size_t),
    ]


# pid_mem_info
class PidMemInfo(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),  # pid_t
        ("localUsedMem", ctypes.c_uint64),
        ("localNumaIds", ctypes.c_uint16 * SDK_NO_64),
        ("localNumaCount", ctypes.c_size_t),
        ("remoteUsedMem", ctypes.c_uint64),
    ]


# container_id_list
class ContainerIdList(ctypes.Structure):
    _fields_ = [
        ("containerId", (ctypes.c_char * SDK_NO_128) * SDK_NO_128),
        ("containerIdSize", ctypes.c_size_t),
    ]


# container_pid_info
class ContainerPidInfo(ctypes.Structure):
    _fields_ = [
        ("pids", ctypes.c_int * SDK_NO_2048),  # pid_t
        ("pidsCount", ctypes.c_size_t),
        ("containerId", ctypes.c_char_p),  # char*
    ]


# ========== mem migrate ==========
# container_param_t
class ContainerParamT(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("ratio", ctypes.c_int),
    ]


# mem_migrate_request_t
class MemMigrateRequestT(ctypes.Structure):
    _fields_ = [
        ("borrowParam", BorrowParamT),
        ("borrowIds", (ctypes.c_char * SDK_NO_128) * SDK_NO_64),
        ("borrowIdsSize", ctypes.c_size_t),
        ("containerParam", ContainerParamT * SDK_NO_64),
        ("containerParamSize", ctypes.c_size_t),
    ]


# ========== mem return ==========
class ReturnRequestT(ctypes.Structure):
    _fields_ = [
        ("borrowParam", BorrowParamT),
        ("borrowIds", (ctypes.c_char * SDK_NO_128) * SDK_NO_64),
        ("borrowIdsSize", ctypes.c_size_t),
        ("pids", ctypes.c_int * SDK_NO_64),
        ("pidsSize", ctypes.c_size_t),
    ]


# mem_borrow_request_t
class MemBorrowRequestT(ctypes.Structure):
    _fields_ = [
        ("borrowParam", BorrowParamT),
        ("borrowSizes", ctypes.c_uint64 * SDK_NO_64),
        ("borrowSizesSize", ctypes.c_size_t),
        ("waterMark", WatermarkT),
    ]
